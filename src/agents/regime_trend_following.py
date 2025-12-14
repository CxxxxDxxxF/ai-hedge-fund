"""
Regime-Conditional Trend Following Agent

Only trades trends when market regime is favorable.
- Trending regime: Strong trend following signals
- Mean-reverting regime: Weak/no trend signals
- Volatile regime: Reduced position sizes
- Calm regime: Normal trend following
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


class RegimeTrendFollowingSignal(BaseModel):
    signal: Literal["bullish", "bearish", "neutral"]
    confidence: int = Field(description="Confidence 0-100")
    reasoning: str = Field(description="Reasoning for the decision")
    regime: str = Field(description="Current market regime")
    regime_adjusted: bool = Field(description="Whether signal was adjusted by regime")


def calculate_trend_strength(prices_df: pd.DataFrame) -> tuple[float, str]:
    """
    Calculate trend strength and direction.
    Returns: (strength_score, direction) where strength_score is -1 to +1
    """
    if len(prices_df) < 50:
        return 0.0, "neutral"
    
    current_price = float(prices_df["close"].iloc[-1])
    
    # Multiple moving averages for trend confirmation
    ma10 = float(prices_df["close"].rolling(window=10).mean().iloc[-1])
    ma20 = float(prices_df["close"].rolling(window=20).mean().iloc[-1])
    ma50 = float(prices_df["close"].rolling(window=50).mean().iloc[-1])
    
    # Trend alignment score
    alignment_score = 0.0
    if current_price > ma10 > ma20 > ma50:
        alignment_score = 1.0  # Strong uptrend
        direction = "bullish"
    elif current_price > ma20 > ma50:
        alignment_score = 0.6  # Moderate uptrend
        direction = "bullish"
    elif current_price > ma50:
        alignment_score = 0.3  # Weak uptrend
        direction = "bullish"
    elif current_price < ma10 < ma20 < ma50:
        alignment_score = -1.0  # Strong downtrend
        direction = "bearish"
    elif current_price < ma20 < ma50:
        alignment_score = -0.6  # Moderate downtrend
        direction = "bearish"
    elif current_price < ma50:
        alignment_score = -0.3  # Weak downtrend
        direction = "bearish"
    else:
        direction = "neutral"
    
    # Momentum component
    price_20_days_ago = float(prices_df["close"].iloc[-20])
    momentum = (current_price - price_20_days_ago) / price_20_days_ago if price_20_days_ago > 0 else 0.0
    
    # Combine alignment and momentum
    strength_score = (alignment_score * 0.7) + (np.clip(momentum * 5, -1, 1) * 0.3)
    
    return float(strength_score), direction


def calculate_regime_trend_following_signal_rule_based(
    ticker: str,
    prices_df: pd.DataFrame,
    market_regime: dict | None,
) -> RegimeTrendFollowingSignal:
    """
    Generate trend following signal adjusted by market regime.
    """
    if prices_df.empty or len(prices_df) < 50:
        return RegimeTrendFollowingSignal(
            signal="neutral",
            confidence=50,
            reasoning="Insufficient price data for trend following (need 50+ days)",
            regime="unknown",
            regime_adjusted=False,
        )
    
    # Get market regime
    regime_name = "calm"  # Default
    regime_data = market_regime or {}
    if isinstance(regime_data, dict):
        regime_name = regime_data.get("regime", "calm")
    
    # Calculate trend strength
    trend_strength, trend_direction = calculate_trend_strength(prices_df)
    
    # Regime-based adjustments
    regime_adjusted = True
    base_confidence = 50
    
    if regime_name == "trending":
        # Trending regime: Strong trend following signals
        if trend_strength > 0.3:
            signal = "bullish"
            base_confidence = 70 + int(trend_strength * 15)  # 70-85
            reasoning = f"Strong trend following in TRENDING regime: {trend_direction} trend (strength: {trend_strength:.2f})"
        elif trend_strength < -0.3:
            signal = "bearish"
            base_confidence = 70 + int(abs(trend_strength) * 15)  # 70-85
            reasoning = f"Strong trend following in TRENDING regime: {trend_direction} trend (strength: {trend_strength:.2f})"
        else:
            signal = "neutral"
            base_confidence = 50
            reasoning = f"Weak trend in TRENDING regime: {trend_direction} (strength: {trend_strength:.2f})"
    
    elif regime_name == "mean_reverting":
        # Mean-reverting regime: Weak/no trend signals
        signal = "neutral"
        base_confidence = 50
        reasoning = f"Trend following suppressed in MEAN-REVERTING regime: {trend_direction} trend (strength: {trend_strength:.2f})"
    
    elif regime_name == "volatile":
        # Volatile regime: Reduced confidence
        if trend_strength > 0.4:
            signal = "bullish"
            base_confidence = 55 + int(trend_strength * 10)  # 55-65 (reduced)
            reasoning = f"Reduced trend following in VOLATILE regime: {trend_direction} trend (strength: {trend_strength:.2f})"
        elif trend_strength < -0.4:
            signal = "bearish"
            base_confidence = 55 + int(abs(trend_strength) * 10)  # 55-65 (reduced)
            reasoning = f"Reduced trend following in VOLATILE regime: {trend_direction} trend (strength: {trend_strength:.2f})"
        else:
            signal = "neutral"
            base_confidence = 50
            reasoning = f"Weak trend in VOLATILE regime: {trend_direction} (strength: {trend_strength:.2f})"
    
    else:  # calm or unknown
        # Calm regime: Normal trend following
        if trend_strength > 0.2:
            signal = "bullish"
            base_confidence = 60 + int(trend_strength * 20)  # 60-80
            reasoning = f"Trend following in CALM regime: {trend_direction} trend (strength: {trend_strength:.2f})"
        elif trend_strength < -0.2:
            signal = "bearish"
            base_confidence = 60 + int(abs(trend_strength) * 20)  # 60-80
            reasoning = f"Trend following in CALM regime: {trend_direction} trend (strength: {trend_strength:.2f})"
        else:
            signal = "neutral"
            base_confidence = 50
            reasoning = f"No clear trend in CALM regime: {trend_direction} (strength: {trend_strength:.2f})"
    
    confidence = min(85, max(50, base_confidence))
    
    return RegimeTrendFollowingSignal(
        signal=signal,
        confidence=confidence,
        reasoning=reasoning,
        regime=regime_name,
        regime_adjusted=regime_adjusted,
    )


def regime_trend_following_agent(state: AgentState, agent_id: str = "regime_trend_following_agent"):
    """
    Analyzes stocks using trend following, adjusted by market regime.
    Only trades trends when regime is favorable.
    """
    data = state["data"]
    start_date = data["start_date"]
    end_date = data["end_date"]
    tickers = data["tickers"]
    api_key = get_api_key_from_state(state, "FINANCIAL_DATASETS_API_KEY")
    
    # Get market regime data (from Market Regime Analyst)
    market_regime_data = data.get("market_regime", {})
    
    trend_analysis = {}
    
    for ticker in tickers:
        progress.update_status(agent_id, ticker, "Fetching price data")
        
        prices = get_prices(
            ticker=ticker,
            start_date=start_date,
            end_date=end_date,
            api_key=api_key,
        )
        
        if not prices:
            trend_analysis[ticker] = {
                "signal": "neutral",
                "confidence": 50,
                "reasoning": "No price data available",
                "regime": "unknown",
                "regime_adjusted": False,
            }
            continue
        
        prices_df = prices_to_df(prices)
        
        if prices_df.empty or len(prices_df) < 50:
            trend_analysis[ticker] = {
                "signal": "neutral",
                "confidence": 50,
                "reasoning": "Insufficient price data for trend following (need 50+ days)",
                "regime": "unknown",
                "regime_adjusted": False,
            }
            continue
        
        # Get regime for this ticker
        ticker_regime = market_regime_data.get(ticker, {})
        
        progress.update_status(agent_id, ticker, "Calculating trend strength and regime adjustment")
        
        signal_output = calculate_regime_trend_following_signal_rule_based(
            ticker, prices_df, ticker_regime
        )
        
        trend_analysis[ticker] = {
            "signal": signal_output.signal,
            "confidence": signal_output.confidence,
            "reasoning": signal_output.reasoning,
            "regime": signal_output.regime,
            "regime_adjusted": signal_output.regime_adjusted,
        }
        
        progress.update_status(agent_id, ticker, f"Done ({signal_output.regime} regime)", analysis=signal_output.reasoning)
    
    message = HumanMessage(content=json.dumps(trend_analysis), name=agent_id)
    
    if state["metadata"]["show_reasoning"]:
        show_agent_reasoning(trend_analysis, agent_id)
    
    state["data"]["analyst_signals"][agent_id] = trend_analysis
    
    progress.update_status(agent_id, None, "Done")
    
    return {"messages": [message], "data": state["data"]}
