"""
Capital Preservation / Drawdown Minimization Agent

Focuses on protecting capital and minimizing drawdowns.
- Reduces position sizes when drawdowns occur
- Exits positions when drawdown exceeds threshold
- Prefers defensive positions during high volatility
- Only trades when risk/reward is favorable
"""

from src.graph.state import AgentState, show_agent_reasoning
from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field
import json
from typing_extensions import Literal
from src.tools.api import get_prices, prices_to_df
from src.utils.progress import progress
from src.utils.api_key import get_api_key_from_state
import pandas as pd
import numpy as np


class CapitalPreservationSignal(BaseModel):
    signal: Literal["bullish", "bearish", "neutral"]
    confidence: int = Field(description="Confidence 0-100")
    reasoning: str = Field(description="Reasoning for the decision")
    drawdown_risk: str = Field(description="Drawdown risk level: low/medium/high")
    position_size_multiplier: float = Field(description="Position size multiplier (0.0-1.0) based on drawdown risk")


def calculate_portfolio_drawdown(portfolio_value_history: list[float]) -> float:
    """Calculate current drawdown from peak."""
    if not portfolio_value_history or len(portfolio_value_history) < 2:
        return 0.0
    
    current_value = portfolio_value_history[-1]
    peak_value = max(portfolio_value_history)
    
    if peak_value <= 0:
        return 0.0
    
    drawdown = (current_value - peak_value) / peak_value
    return float(drawdown)


def calculate_capital_preservation_signal_rule_based(
    ticker: str,
    prices_df: pd.DataFrame,
    portfolio_drawdown: float,
    portfolio_value: float | None = None,
    initial_capital: float | None = None,
) -> CapitalPreservationSignal:
    """
    Generate capital preservation signal based on drawdown risk.
    Reduces position sizes or exits when drawdown is high.
    """
    if prices_df.empty or len(prices_df) < 20:
        return CapitalPreservationSignal(
            signal="neutral",
            confidence=50,
            reasoning="Insufficient price data for capital preservation analysis",
            drawdown_risk="medium",
            position_size_multiplier=0.5,
        )
    
    # Calculate volatility (risk measure)
    returns = prices_df["close"].pct_change().dropna()
    if len(returns) >= 20:
        volatility = returns.iloc[-20:].std() * np.sqrt(252)  # Annualized
    else:
        volatility = 0.30  # Default
    
    # Drawdown thresholds
    DRAWDOWN_SEVERE = -0.15  # -15% drawdown
    DRAWDOWN_MODERATE = -0.08  # -8% drawdown
    DRAWDOWN_MILD = -0.03  # -3% drawdown
    
    # Determine drawdown risk level
    if portfolio_drawdown <= DRAWDOWN_SEVERE:
        drawdown_risk = "high"
        position_size_multiplier = 0.0  # Exit all positions
        signal = "neutral"
        confidence = 50
        reasoning = f"SEVERE drawdown ({portfolio_drawdown:.1%}) - capital preservation: EXIT all positions"
    
    elif portfolio_drawdown <= DRAWDOWN_MODERATE:
        drawdown_risk = "high"
        position_size_multiplier = 0.25  # Reduce to 25% of normal
        signal = "neutral"
        confidence = 50
        reasoning = f"MODERATE drawdown ({portfolio_drawdown:.1%}) - capital preservation: REDUCE positions to 25%"
    
    elif portfolio_drawdown <= DRAWDOWN_MILD:
        drawdown_risk = "medium"
        position_size_multiplier = 0.50  # Reduce to 50% of normal
        signal = "neutral"
        confidence = 50
        reasoning = f"MILD drawdown ({portfolio_drawdown:.1%}) - capital preservation: REDUCE positions to 50%"
    
    else:
        # No significant drawdown - can trade normally, but still consider volatility
        drawdown_risk = "low"
        
        # High volatility = reduce position sizes even without drawdown
        if volatility > 0.40:
            position_size_multiplier = 0.50
            signal = "neutral"
            confidence = 50
            reasoning = f"No drawdown but HIGH volatility ({volatility:.1%}) - capital preservation: REDUCE positions to 50%"
        elif volatility > 0.30:
            position_size_multiplier = 0.75
            signal = "neutral"
            confidence = 50
            reasoning = f"No drawdown but MODERATE volatility ({volatility:.1%}) - capital preservation: REDUCE positions to 75%"
        else:
            # Low volatility, no drawdown - can trade normally
            position_size_multiplier = 1.0
            
            # Still generate signals, but with capital preservation focus
            current_price = float(prices_df["close"].iloc[-1])
            price_20_days_ago = float(prices_df["close"].iloc[-20])
            momentum = (current_price - price_20_days_ago) / price_20_days_ago if price_20_days_ago > 0 else 0.0
            
            # Only trade strong, low-risk opportunities
            if momentum > 0.10 and volatility < 0.25:
                signal = "bullish"
                confidence = 65  # Moderate confidence (capital preservation focus)
                reasoning = f"Capital preservation: Strong bullish ({momentum:.1%}) with LOW volatility ({volatility:.1%})"
            elif momentum < -0.10 and volatility < 0.25:
                signal = "bearish"
                confidence = 65
                reasoning = f"Capital preservation: Strong bearish ({momentum:.1%}) with LOW volatility ({volatility:.1%})"
            else:
                signal = "neutral"
                confidence = 50
                reasoning = f"Capital preservation: No strong low-risk opportunity (momentum: {momentum:.1%}, vol: {volatility:.1%})"
    
    return CapitalPreservationSignal(
        signal=signal,
        confidence=confidence,
        reasoning=reasoning,
        drawdown_risk=drawdown_risk,
        position_size_multiplier=position_size_multiplier,
    )


def capital_preservation_agent(state: AgentState, agent_id: str = "capital_preservation_agent"):
    """
    Analyzes stocks with focus on capital preservation and drawdown minimization.
    Reduces position sizes or exits when drawdowns occur.
    """
    data = state["data"]
    start_date = data["start_date"]
    end_date = data["end_date"]
    tickers = data["tickers"]
    api_key = get_api_key_from_state(state, "FINANCIAL_DATASETS_API_KEY")
    
    # Get portfolio information
    portfolio = data.get("portfolio", {})
    portfolio_value = portfolio.get("cash", 0.0)
    
    # Calculate portfolio value (cash + positions)
    # This is a simplified calculation - in practice, would use actual position values
    # For now, use cash as proxy
    initial_capital = portfolio.get("initial_capital", 100000.0)
    
    # Calculate drawdown (simplified - would need historical portfolio values)
    # For now, use a placeholder
    portfolio_drawdown = 0.0  # Would calculate from portfolio history
    
    capital_preservation_analysis = {}
    
    for ticker in tickers:
        progress.update_status(agent_id, ticker, "Analyzing capital preservation risk")
        
        prices = get_prices(
            ticker=ticker,
            start_date=start_date,
            end_date=end_date,
            api_key=api_key,
        )
        
        if not prices:
            capital_preservation_analysis[ticker] = {
                "signal": "neutral",
                "confidence": 50,
                "reasoning": "No price data available",
                "drawdown_risk": "medium",
                "position_size_multiplier": 0.5,
            }
            continue
        
        prices_df = prices_to_df(prices)
        
        if prices_df.empty or len(prices_df) < 20:
            capital_preservation_analysis[ticker] = {
                "signal": "neutral",
                "confidence": 50,
                "reasoning": "Insufficient price data for capital preservation analysis",
                "drawdown_risk": "medium",
                "position_size_multiplier": 0.5,
            }
            continue
        
        signal_output = calculate_capital_preservation_signal_rule_based(
            ticker, prices_df, portfolio_drawdown, portfolio_value, initial_capital
        )
        
        capital_preservation_analysis[ticker] = {
            "signal": signal_output.signal,
            "confidence": signal_output.confidence,
            "reasoning": signal_output.reasoning,
            "drawdown_risk": signal_output.drawdown_risk,
            "position_size_multiplier": signal_output.position_size_multiplier,
        }
        
        progress.update_status(agent_id, ticker, f"Drawdown risk: {signal_output.drawdown_risk}, size multiplier: {signal_output.position_size_multiplier:.0%}")
    
    message = HumanMessage(content=json.dumps(capital_preservation_analysis), name=agent_id)
    
    if state["metadata"]["show_reasoning"]:
        show_agent_reasoning(capital_preservation_analysis, agent_id)
    
    state["data"]["analyst_signals"][agent_id] = capital_preservation_analysis
    
    progress.update_status(agent_id, None, "Done")
    
    return {"messages": [message], "data": state["data"]}
