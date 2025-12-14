"""
Mean Reversion Agent

A deterministic agent that identifies oversold (bullish) and overbought (bearish) conditions
based on statistical price extremes. This provides contrarian signals that complement
momentum and trend-following agents.
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


class MeanReversionSignal(BaseModel):
    signal: Literal["bullish", "bearish", "neutral"]
    confidence: int = Field(description="Confidence 0-100")
    reasoning: str = Field(description="Reasoning for the decision")


def calculate_rsi(prices_df: pd.DataFrame, period: int = 14) -> float | None:
    """Calculate Relative Strength Index (RSI) - standard mean reversion indicator."""
    if len(prices_df) < period + 1:
        return None
    
    closes = prices_df["close"].values
    deltas = np.diff(closes)
    
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)
    
    # Calculate average gain and loss over period
    avg_gain = np.mean(gains[-period:])
    avg_loss = np.mean(losses[-period:])
    
    if avg_loss == 0:
        return 100.0  # All gains, no losses
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    
    return float(rsi)


def calculate_mean_reversion_signal_rule_based(
    ticker: str,
    prices_df: pd.DataFrame,
) -> MeanReversionSignal:
    """
    Generate deterministic mean reversion signal based on:
    1. RSI (Relative Strength Index) - oversold < 30, overbought > 70
    2. Price vs 20-day moving average - deviation from mean
    3. Price vs 50-day moving average - longer-term mean reversion
    """
    if prices_df.empty or len(prices_df) < 50:
        return MeanReversionSignal(
            signal="neutral",
            confidence=50,
            reasoning="Insufficient price data for mean reversion analysis (need 50+ days)"
        )
    
    current_price = float(prices_df["close"].iloc[-1])
    
    # Calculate RSI
    rsi = calculate_rsi(prices_df, period=14)
    
    # Calculate moving averages
    ma20 = float(prices_df["close"].rolling(window=20).mean().iloc[-1])
    ma50 = float(prices_df["close"].rolling(window=50).mean().iloc[-1])
    
    # Calculate deviations from moving averages
    deviation_20 = (current_price - ma20) / ma20 if ma20 > 0 else 0.0
    deviation_50 = (current_price - ma50) / ma50 if ma50 > 0 else 0.0
    
    # Score components (each contributes to mean reversion signal)
    score = 0
    reasons = []
    
    # RSI-based signals (strongest indicator)
    if rsi is not None:
        if rsi < 30:  # Oversold - bullish mean reversion opportunity
            score += 3
            reasons.append(f"RSI {rsi:.1f} (oversold)")
        elif rsi < 40:
            score += 1
            reasons.append(f"RSI {rsi:.1f} (moderately oversold)")
        elif rsi > 70:  # Overbought - bearish mean reversion opportunity
            score -= 3
            reasons.append(f"RSI {rsi:.1f} (overbought)")
        elif rsi > 60:
            score -= 1
            reasons.append(f"RSI {rsi:.1f} (moderately overbought)")
        else:
            reasons.append(f"RSI {rsi:.1f} (neutral)")
    
    # Price deviation from 20-day MA
    if deviation_20 < -0.05:  # 5% below MA20 - oversold
        score += 2
        reasons.append(f"Price {deviation_20:.1%} below MA20")
    elif deviation_20 < -0.02:  # 2% below MA20
        score += 1
        reasons.append(f"Price {deviation_20:.1%} below MA20")
    elif deviation_20 > 0.05:  # 5% above MA20 - overbought
        score -= 2
        reasons.append(f"Price {deviation_20:.1%} above MA20")
    elif deviation_20 > 0.02:  # 2% above MA20
        score -= 1
        reasons.append(f"Price {deviation_20:.1%} above MA20")
    
    # Price deviation from 50-day MA (longer-term mean reversion)
    if deviation_50 < -0.08:  # 8% below MA50 - strongly oversold
        score += 2
        reasons.append(f"Price {deviation_50:.1%} below MA50")
    elif deviation_50 < -0.03:  # 3% below MA50
        score += 1
        reasons.append(f"Price {deviation_50:.1%} below MA50")
    elif deviation_50 > 0.08:  # 8% above MA50 - strongly overbought
        score -= 2
        reasons.append(f"Price {deviation_50:.1%} above MA50")
    elif deviation_50 > 0.03:  # 3% above MA50
        score -= 1
        reasons.append(f"Price {deviation_50:.1%} above MA50")
    
    # Determine signal from composite score
    # Score range: -7 (strong bearish) to +7 (strong bullish)
    if score >= 4:
        signal = "bullish"
        confidence = min(85, 50 + score * 8)  # Scale: 50-85
        reasoning = f"Mean reversion bullish: {', '.join(reasons)}"
    elif score <= -4:
        signal = "bearish"
        confidence = min(85, 50 + abs(score) * 8)  # Scale: 50-85
        reasoning = f"Mean reversion bearish: {', '.join(reasons)}"
    else:
        signal = "neutral"
        confidence = 50
        reasoning = f"Mean reversion neutral: {', '.join(reasons)}"
    
    return MeanReversionSignal(
        signal=signal,
        confidence=confidence,
        reasoning=reasoning
    )


def mean_reversion_agent(state: AgentState, agent_id: str = "mean_reversion_agent"):
    """
    Analyzes stocks using mean reversion principles.
    Identifies oversold (bullish) and overbought (bearish) conditions.
    """
    data = state["data"]
    start_date = data["start_date"]
    end_date = data["end_date"]
    tickers = data["tickers"]
    api_key = get_api_key_from_state(state, "FINANCIAL_DATASETS_API_KEY")
    
    mean_reversion_analysis = {}
    
    for ticker in tickers:
        progress.update_status(agent_id, ticker, "Fetching price data")
        
        # Get price data (need at least 50 days for reliable mean reversion)
        prices = get_prices(
            ticker=ticker,
            start_date=start_date,
            end_date=end_date,
            api_key=api_key,
        )
        
        if not prices:
            progress.update_status(agent_id, ticker, "Failed: No price data found")
            mean_reversion_analysis[ticker] = {
                "signal": "neutral",
                "confidence": 50,
                "reasoning": "No price data available"
            }
            continue
        
        prices_df = prices_to_df(prices)
        
        if prices_df.empty or len(prices_df) < 50:
            progress.update_status(agent_id, ticker, "Warning: Insufficient data for mean reversion")
            mean_reversion_analysis[ticker] = {
                "signal": "neutral",
                "confidence": 50,
                "reasoning": "Insufficient price data for mean reversion analysis (need 50+ days)"
            }
            continue
        
        progress.update_status(agent_id, ticker, "Calculating RSI and moving averages")
        progress.update_status(agent_id, ticker, "Generating mean reversion signal")
        
        # Mean reversion agent is always deterministic (rule-based)
        mean_reversion_output = calculate_mean_reversion_signal_rule_based(ticker, prices_df)
        
        mean_reversion_analysis[ticker] = {
            "signal": mean_reversion_output.signal,
            "confidence": mean_reversion_output.confidence,
            "reasoning": mean_reversion_output.reasoning,
        }
        
        progress.update_status(agent_id, ticker, "Done", analysis=mean_reversion_output.reasoning)
    
    # Create the message
    message = HumanMessage(content=json.dumps(mean_reversion_analysis), name=agent_id)
    
    # Show reasoning if requested
    if state["metadata"]["show_reasoning"]:
        show_agent_reasoning(mean_reversion_analysis, agent_id)
    
    # Add the signal to the analyst_signals list
    state["data"]["analyst_signals"][agent_id] = mean_reversion_analysis
    
    progress.update_status(agent_id, None, "Done")
    
    return {"messages": [message], "data": state["data"]}
