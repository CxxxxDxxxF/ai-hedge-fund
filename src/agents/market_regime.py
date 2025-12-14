"""
Market Regime Analyst Agent (Advisory Only)

A deterministic agent that classifies market conditions (trending, mean-reverting, volatile, calm)
and publishes recommended strategy weights for Momentum and Mean Reversion agents.

This agent is advisory only - it does NOT emit trade signals or combine analyst outputs.
It provides context (regime classification) and recommendations (weights) that Portfolio Manager
uses when aggregating signals.

In trending markets: Recommends higher Momentum weight, lower Mean Reversion weight
In mean-reverting markets: Recommends higher Mean Reversion weight, lower Momentum weight
In volatile markets: Recommends dampened weights for both
In calm markets: Recommends normal weights for both
"""

from src.graph.state import AgentState, show_agent_reasoning
from langchain_core.messages import HumanMessage
from src.tools.api import get_prices, prices_to_df
from src.utils.progress import progress
from src.utils.api_key import get_api_key_from_state
import pandas as pd
import numpy as np
import json


# Regime classification thresholds
TRENDING_THRESHOLD = 0.6  # ADX > 25 and strong directional movement
MEAN_REVERTING_THRESHOLD = 0.4  # Low ADX, high RSI oscillation
VOLATILE_THRESHOLD = 0.15  # High volatility (std dev > 15% of price)
CALM_THRESHOLD = 0.05  # Low volatility (std dev < 5% of price)

# Regime-based recommended weight adjustments (advisory)
REGIME_WEIGHTS = {
    "trending": {"momentum": 1.5, "mean_reversion": 0.5},  # Boost momentum, reduce mean reversion
    "mean_reverting": {"momentum": 0.5, "mean_reversion": 1.5},  # Boost mean reversion, reduce momentum
    "volatile": {"momentum": 0.7, "mean_reversion": 0.7},  # Dampen both
    "calm": {"momentum": 1.0, "mean_reversion": 1.0},  # Normal weights
}

# Risk multipliers by regime (for position sizing adjustments)
REGIME_RISK_MULTIPLIERS = {
    "trending": 1.0,  # Normal risk
    "mean_reverting": 0.9,  # Slightly reduced risk
    "volatile": 0.8,  # Reduced risk in volatile markets
    "calm": 1.0,  # Normal risk
}


def calculate_adx(prices_df: pd.DataFrame, period: int = 14) -> float | None:
    """
    Calculate Average Directional Index (ADX) - measures trend strength.
    ADX > 25 indicates strong trend, ADX < 20 indicates weak/no trend.
    """
    if len(prices_df) < period + 1:
        return None
    
    high = prices_df["high"].values
    low = prices_df["low"].values
    close = prices_df["close"].values
    
    # Calculate True Range (TR)
    tr_list = []
    for i in range(1, len(prices_df)):
        tr = max(
            high[i] - low[i],
            abs(high[i] - close[i-1]),
            abs(low[i] - close[i-1])
        )
        tr_list.append(tr)
    
    # Calculate +DM and -DM
    plus_dm = []
    minus_dm = []
    for i in range(1, len(prices_df)):
        up_move = high[i] - high[i-1]
        down_move = low[i-1] - low[i]
        
        if up_move > down_move and up_move > 0:
            plus_dm.append(up_move)
        else:
            plus_dm.append(0)
        
        if down_move > up_move and down_move > 0:
            minus_dm.append(down_move)
        else:
            minus_dm.append(0)
    
    # Smooth TR, +DM, -DM
    atr = np.mean(tr_list[-period:])
    plus_di = np.mean(plus_dm[-period:]) / atr * 100 if atr > 0 else 0
    minus_di = np.mean(minus_dm[-period:]) / atr * 100 if atr > 0 else 0
    
    # Calculate DX and ADX
    dx = abs(plus_di - minus_di) / (plus_di + minus_di) * 100 if (plus_di + minus_di) > 0 else 0
    adx = dx  # Simplified: use current DX as ADX proxy
    
    return float(adx)


def classify_market_regime(
    ticker: str,
    prices_df: pd.DataFrame,
) -> tuple[str, dict]:
    """
    Classify market regime based on:
    1. ADX (trend strength)
    2. Volatility (price standard deviation)
    3. RSI oscillation (mean reversion tendency)
    
    Returns: (regime_name, regime_metrics)
    """
    if prices_df.empty or len(prices_df) < 50:
        return "calm", {"reason": "Insufficient data"}
    
    # Calculate ADX (trend strength)
    adx = calculate_adx(prices_df, period=14)
    
    # Calculate volatility (20-day rolling std dev as % of price)
    returns = prices_df["close"].pct_change()
    volatility = returns.rolling(window=20).std().iloc[-1] * np.sqrt(252)  # Annualized
    price_level = prices_df["close"].iloc[-1]
    volatility_pct = volatility / price_level if price_level > 0 else 0
    
    # Calculate RSI oscillation (how much RSI swings)
    def calc_rsi(df: pd.DataFrame, period: int = 14) -> float | None:
        """Calculate RSI for regime analysis."""
        if len(df) < period + 1:
            return None
        closes = df["close"].values
        deltas = np.diff(closes)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        avg_gain = np.mean(gains[-period:])
        avg_loss = np.mean(losses[-period:])
        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return float(100 - (100 / (1 + rs)))
    
    rsi_values = []
    for i in range(len(prices_df) - 14, len(prices_df)):
        rsi = calc_rsi(prices_df.iloc[:i+1], period=14)
        if rsi is not None:
            rsi_values.append(rsi)
    
    rsi_oscillation = np.std(rsi_values) if len(rsi_values) > 5 else 0
    
    # Calculate price trend consistency (how consistently price moves in one direction)
    price_changes = prices_df["close"].pct_change().dropna()
    positive_days = sum(1 for x in price_changes[-20:] if x > 0)
    negative_days = sum(1 for x in price_changes[-20:] if x < 0)
    trend_consistency = max(positive_days, negative_days) / 20.0 if len(price_changes) >= 20 else 0.5
    
    regime_metrics = {
        "adx": adx if adx else 0,
        "volatility_pct": volatility_pct,
        "rsi_oscillation": rsi_oscillation,
        "trend_consistency": trend_consistency,
    }
    
    # Classification logic
    if adx and adx > 25 and trend_consistency > 0.6:
        regime = "trending"
        reason = f"Strong trend (ADX={adx:.1f}, consistency={trend_consistency:.1%})"
    elif volatility_pct > VOLATILE_THRESHOLD:
        regime = "volatile"
        reason = f"High volatility ({volatility_pct:.1%})"
    elif adx and adx < 20 and rsi_oscillation > 10:
        regime = "mean_reverting"
        reason = f"Weak trend, high RSI oscillation (ADX={adx:.1f}, RSI_std={rsi_oscillation:.1f})"
    elif volatility_pct < CALM_THRESHOLD:
        regime = "calm"
        reason = f"Low volatility ({volatility_pct:.1%})"
    else:
        # Default: calm
        regime = "calm"
        reason = f"Moderate conditions (ADX={adx:.1f if adx else 0:.1f}, vol={volatility_pct:.1%})"
    
    regime_metrics["reason"] = reason
    return regime, regime_metrics




def market_regime_agent(state: AgentState, agent_id: str = "market_regime_agent"):
    """
    Advisory-only agent that classifies market regime and publishes recommended strategy weights.
    
    Does NOT emit trade signals or combine analyst outputs.
    Stores regime classification and recommended weights in state["data"]["market_regime"].
    Portfolio Manager reads these weights and applies them when aggregating signals.
    """
    data = state["data"]
    start_date = data["start_date"]
    end_date = data["end_date"]
    tickers = data["tickers"]
    api_key = get_api_key_from_state(state, "FINANCIAL_DATASETS_API_KEY")
    
    market_regimes = {}  # Store regime classifications and weights per ticker
    
    for ticker in tickers:
        progress.update_status(agent_id, ticker, "Fetching price data")
        
        # Get price data
        prices = get_prices(
            ticker=ticker,
            start_date=start_date,
            end_date=end_date,
            api_key=api_key,
        )
        
        if not prices:
            progress.update_status(agent_id, ticker, "Failed: No price data found")
            # Default regime when no data
            market_regimes[ticker] = {
                "regime": "calm",
                "weights": REGIME_WEIGHTS["calm"],
                "risk_multiplier": REGIME_RISK_MULTIPLIERS["calm"],
                "reasoning": "No price data available"
            }
            continue
        
        prices_df = prices_to_df(prices)
        
        if prices_df.empty or len(prices_df) < 50:
            progress.update_status(agent_id, ticker, "Warning: Insufficient data")
            # Default regime when insufficient data
            market_regimes[ticker] = {
                "regime": "calm",
                "weights": REGIME_WEIGHTS["calm"],
                "risk_multiplier": REGIME_RISK_MULTIPLIERS["calm"],
                "reasoning": "Insufficient price data for regime analysis"
            }
            continue
        
        progress.update_status(agent_id, ticker, "Classifying market regime")
        
        # Classify regime
        regime, regime_metrics = classify_market_regime(ticker, prices_df)
        
        # Get recommended weights for this regime
        weights = REGIME_WEIGHTS.get(regime, REGIME_WEIGHTS["calm"])
        risk_multiplier = REGIME_RISK_MULTIPLIERS.get(regime, REGIME_RISK_MULTIPLIERS["calm"])
        
        # Store regime classification and recommended weights
        market_regimes[ticker] = {
            "regime": regime,
            "weights": weights,
            "risk_multiplier": risk_multiplier,
            "reasoning": regime_metrics.get("reason", f"Regime: {regime}")
        }
        
        progress.update_status(agent_id, ticker, f"Regime: {regime}, weights: Momentum×{weights['momentum']:.1f}, MR×{weights['mean_reversion']:.1f}")
    
    # Store regime classifications and weights in state (for use by Portfolio Manager)
    if "market_regime" not in data:
        data["market_regime"] = {}
    data["market_regime"].update(market_regimes)
    
    # Create advisory message (for logging/debugging, not for trading decisions)
    message_content = json.dumps({
        "advisory": "Market regime classification and recommended weights",
        "regimes": market_regimes
    })
    message = HumanMessage(content=message_content, name=agent_id)
    
    # Show reasoning if requested
    if state["metadata"]["show_reasoning"]:
        show_agent_reasoning(market_regimes, agent_id)
    
    # Do NOT add to analyst_signals - this is advisory only
    # Portfolio Manager reads from state["data"]["market_regime"] directly
    
    progress.update_status(agent_id, None, "Done")
    
    return {"messages": [message], "data": state["data"]}
