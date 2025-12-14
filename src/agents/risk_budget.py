"""
Risk Budget & Position Sizing Agent

A deterministic agent that converts Portfolio Manager trading decisions into risk-based
capital allocations. This agent does NOT generate trade direction - it only determines
position size based on:
- Portfolio Manager confidence
- Market Regime risk_multiplier
- Volatility (ATR or rolling std dev)

Execution flow: Portfolio Manager (direction) → Risk Budget (size) → Risk Manager (limits)
"""

from src.graph.state import AgentState, show_agent_reasoning
from langchain_core.messages import HumanMessage
from src.tools.api import get_prices, prices_to_df
from src.utils.progress import progress
from src.utils.api_key import get_api_key_from_state
import pandas as pd
import numpy as np
import json


# Risk budget parameters
BASE_RISK_PCT = 0.02  # Base risk per position: 2% of portfolio
MIN_RISK_PCT = 0.005  # Minimum risk: 0.5%
MAX_RISK_PCT = 0.05  # Maximum risk: 5%
CONFIDENCE_SCALING = 0.01  # Confidence scaling factor (confidence/100 * scaling)


def calculate_atr(prices_df: pd.DataFrame, period: int = 14) -> float | None:
    """
    Calculate Average True Range (ATR) - volatility measure.
    Returns ATR as absolute dollar amount.
    """
    if len(prices_df) < period + 1:
        return None
    
    high = prices_df["high"].values
    low = prices_df["low"].values
    close = prices_df["close"].values
    
    # Calculate True Range
    tr_list = []
    for i in range(1, len(prices_df)):
        tr = max(
            high[i] - low[i],
            abs(high[i] - close[i-1]),
            abs(low[i] - close[i-1])
        )
        tr_list.append(tr)
    
    # ATR is average of True Range over period
    atr = np.mean(tr_list[-period:])
    return float(atr)


def calculate_volatility_adjustment(prices_df: pd.DataFrame) -> float:
    """
    Calculate volatility adjustment factor based on ATR.
    Higher volatility → lower position size (adjustment < 1.0)
    Lower volatility → higher position size (adjustment > 1.0)
    """
    if prices_df.empty or len(prices_df) < 20:
        return 1.0  # Default: no adjustment
    
    current_price = float(prices_df["close"].iloc[-1])
    atr = calculate_atr(prices_df, period=14)
    
    if atr is None or current_price == 0:
        return 1.0
    
    # ATR as percentage of price
    atr_pct = atr / current_price
    
    # Volatility adjustment: inverse relationship
    # High volatility (ATR > 3%) → lower adjustment (0.5-0.75)
    # Low volatility (ATR < 1%) → higher adjustment (1.0-1.25)
    if atr_pct > 0.03:  # High volatility
        adjustment = max(0.5, 1.0 - (atr_pct - 0.03) * 5)
    elif atr_pct < 0.01:  # Low volatility
        adjustment = min(1.25, 1.0 + (0.01 - atr_pct) * 5)
    else:  # Normal volatility
        adjustment = 1.0
    
    return float(adjustment)


def calculate_risk_budget(
    ticker: str,
    pm_decision: dict,
    market_regime: dict | None,
    prices_df: pd.DataFrame,
    portfolio_value: float,
) -> dict:
    """
    Calculate risk budget for a ticker based on:
    - Portfolio Manager confidence
    - Market Regime risk_multiplier
    - Volatility (ATR-based adjustment)
    
    Returns risk budget structure.
    """
    action = pm_decision.get("action", "hold")
    confidence = pm_decision.get("confidence", 50)
    
    # Skip risk budget calculation for hold actions
    if action == "hold":
        return {
            "base_risk_pct": 0.0,
            "volatility_adjustment": 1.0,
            "regime_multiplier": 1.0,
            "final_risk_pct": 0.0,
            "reasoning": "Hold action - no position sizing"
        }
    
    # Base risk percentage scaled by confidence
    # Higher confidence → higher risk allocation (up to BASE_RISK_PCT)
    confidence_factor = confidence / 100.0
    base_risk_pct = BASE_RISK_PCT * confidence_factor
    
    # Volatility adjustment
    volatility_adjustment = calculate_volatility_adjustment(prices_df)
    
    # Regime risk multiplier (from Market Regime Analyst)
    regime_multiplier = 1.0
    if market_regime:
        regime_multiplier = market_regime.get("risk_multiplier", 1.0)
    
    # Calculate final risk percentage
    final_risk_pct = base_risk_pct * volatility_adjustment * regime_multiplier
    
    # Clamp to min/max bounds
    final_risk_pct = max(MIN_RISK_PCT, min(MAX_RISK_PCT, final_risk_pct))
    
    # Build reasoning
    vol_desc = "high" if volatility_adjustment < 0.8 else "low" if volatility_adjustment > 1.1 else "normal"
    regime_name = market_regime.get("regime", "unknown") if market_regime else "unknown"
    
    reasoning = (
        f"Confidence {confidence}% → base {base_risk_pct:.1%}, "
        f"volatility {vol_desc} (adj {volatility_adjustment:.2f}), "
        f"regime {regime_name} (mult {regime_multiplier:.2f}) → "
        f"final risk {final_risk_pct:.1%}"
    )
    
    return {
        "base_risk_pct": float(base_risk_pct),
        "volatility_adjustment": float(volatility_adjustment),
        "regime_multiplier": float(regime_multiplier),
        "final_risk_pct": float(final_risk_pct),
        "reasoning": reasoning
    }


def risk_budget_agent(state: AgentState, agent_id: str = "risk_budget_agent"):
    """
    Converts Portfolio Manager decisions into risk-based capital allocations.
    
    Reads PM decisions from state, calculates risk budgets based on confidence,
    volatility, and market regime, then stores in state["data"]["risk_budget"].
    """
    data = state["data"]
    tickers = data["tickers"]
    portfolio = data["portfolio"]
    start_date = data["start_date"]
    end_date = data["end_date"]
    api_key = get_api_key_from_state(state, "FINANCIAL_DATASETS_API_KEY")
    
    # Get Portfolio Manager decisions from messages
    pm_decisions = {}
    for message in state["messages"]:
        if message.name == "portfolio_manager":
            try:
                decisions_dict = json.loads(message.content)
                pm_decisions = decisions_dict
                break
            except (json.JSONDecodeError, TypeError):
                continue
    
    # If no PM decisions found, check if stored in data
    if not pm_decisions:
        pm_decisions = data.get("portfolio_decisions", {})
    
    # Calculate portfolio value for risk percentage calculations
    current_prices = data.get("current_prices", {})
    portfolio_value = portfolio.get("cash", 0.0)
    for ticker, positions in portfolio.get("positions", {}).items():
        if ticker in current_prices:
            price = current_prices[ticker]
            long_shares = positions.get("long", 0)
            short_shares = positions.get("short", 0)
            portfolio_value += (long_shares - short_shares) * price
    
    # Default portfolio value if calculation fails
    if portfolio_value <= 0:
        portfolio_value = portfolio.get("cash", 100000.0)  # Fallback to cash
    
    # Get market regime data
    market_regime_data = data.get("market_regime", {})
    
    risk_budgets = {}
    
    for ticker in tickers:
        progress.update_status(agent_id, ticker, "Reading Portfolio Manager decision")
        
        # Get PM decision for this ticker
        pm_decision = pm_decisions.get(ticker, {})
        if not pm_decision:
            # No decision available - set zero risk budget
            risk_budgets[ticker] = {
                "base_risk_pct": 0.0,
                "volatility_adjustment": 1.0,
                "regime_multiplier": 1.0,
                "final_risk_pct": 0.0,
                "reasoning": "No Portfolio Manager decision available"
            }
            continue
        
        # Get market regime for this ticker
        ticker_regime = market_regime_data.get(ticker)
        
        # Fetch price data for volatility calculation
        progress.update_status(agent_id, ticker, "Calculating volatility")
        prices = get_prices(
            ticker=ticker,
            start_date=start_date,
            end_date=end_date,
            api_key=api_key,
        )
        
        if not prices:
            progress.update_status(agent_id, ticker, "Warning: No price data, using defaults")
            # Use default risk budget without volatility adjustment
            risk_budgets[ticker] = {
                "base_risk_pct": BASE_RISK_PCT * (pm_decision.get("confidence", 50) / 100.0),
                "volatility_adjustment": 1.0,
                "regime_multiplier": ticker_regime.get("risk_multiplier", 1.0) if ticker_regime else 1.0,
                "final_risk_pct": BASE_RISK_PCT * (pm_decision.get("confidence", 50) / 100.0),
                "reasoning": "No price data - using base risk with regime adjustment"
            }
            continue
        
        prices_df = prices_to_df(prices)
        
        progress.update_status(agent_id, ticker, "Calculating risk budget")
        
        # Calculate risk budget
        risk_budget = calculate_risk_budget(
            ticker=ticker,
            pm_decision=pm_decision,
            market_regime=ticker_regime,
            prices_df=prices_df,
            portfolio_value=portfolio_value,
        )
        
        risk_budgets[ticker] = risk_budget
        
        progress.update_status(agent_id, ticker, f"Risk budget: {risk_budget['final_risk_pct']:.1%}")
    
    # Store risk budgets in state
    if "risk_budget" not in data:
        data["risk_budget"] = {}
    data["risk_budget"].update(risk_budgets)
    
    # Create advisory message (for logging/debugging)
    message_content = json.dumps({
        "advisory": "Risk budget allocations based on PM decisions, volatility, and regime",
        "risk_budgets": risk_budgets
    })
    message = HumanMessage(content=message_content, name=agent_id)
    
    # Show reasoning if requested
    if state["metadata"]["show_reasoning"]:
        show_agent_reasoning(risk_budgets, agent_id)
    
    # Do NOT add to analyst_signals - this is advisory only
    # Risk Manager reads from state["data"]["risk_budget"] directly
    
    progress.update_status(agent_id, None, "Done")
    
    return {"messages": [message], "data": state["data"]}
