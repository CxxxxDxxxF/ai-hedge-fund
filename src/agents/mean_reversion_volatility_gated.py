"""
Mean Reversion with Volatility Gating Agent

Enhanced mean reversion that only trades when volatility is low.
High volatility = stay neutral (mean reversion less reliable).
Low volatility = trade mean reversion signals (more reliable).
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


class MeanReversionVolatilityGatedSignal(BaseModel):
    signal: Literal["bullish", "bearish", "neutral"]
    confidence: int = Field(description="Confidence 0-100")
    reasoning: str = Field(description="Reasoning for the decision")
    volatility_gated: bool = Field(description="Whether signal was gated by volatility")


def calculate_volatility(prices_df: pd.DataFrame, period: int = 20) -> float:
    """Calculate annualized volatility."""
    if len(prices_df) < period + 1:
        return 0.0
    
    returns = prices_df["close"].pct_change().dropna()
    if len(returns) < period:
        return 0.0
    
    recent_returns = returns.iloc[-period:]
    volatility = recent_returns.std() * np.sqrt(252)  # Annualized
    return float(volatility)


def calculate_rsi(prices_df: pd.DataFrame, period: int = 14) -> float | None:
    """Calculate Relative Strength Index (RSI)."""
    if len(prices_df) < period + 1:
        return None
    
    closes = prices_df["close"].values
    deltas = np.diff(closes)
    
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)
    
    avg_gain = np.mean(gains[-period:])
    avg_loss = np.mean(losses[-period:])
    
    if avg_loss == 0:
        return 100.0
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    
    return float(rsi)


def calculate_mean_reversion_volatility_gated_signal_rule_based(
    ticker: str,
    prices_df: pd.DataFrame,
) -> MeanReversionVolatilityGatedSignal:
    """
    Generate mean reversion signal with volatility gating.
    Only trades when volatility is below threshold (mean reversion more reliable).
    """
    if prices_df.empty or len(prices_df) < 50:
        return MeanReversionVolatilityGatedSignal(
            signal="neutral",
            confidence=50,
            reasoning="Insufficient price data for mean reversion analysis (need 50+ days)",
            volatility_gated=False,
        )
    
    # Calculate volatility (20-day annualized)
    volatility = calculate_volatility(prices_df, period=20)
    
    # Volatility threshold: 30% annualized
    # Above 30% = high volatility, mean reversion less reliable
    # Below 30% = low volatility, mean reversion more reliable
    VOLATILITY_THRESHOLD = 0.30
    
    if volatility > VOLATILITY_THRESHOLD:
        return MeanReversionVolatilityGatedSignal(
            signal="neutral",
            confidence=50,
            reasoning=f"High volatility ({volatility:.1%}) - mean reversion gated (threshold: {VOLATILITY_THRESHOLD:.0%})",
            volatility_gated=True,
        )
    
    # Low volatility - proceed with mean reversion analysis
    current_price = float(prices_df["close"].iloc[-1])
    
    # Calculate RSI
    rsi = calculate_rsi(prices_df, period=14)
    
    # Calculate moving averages
    ma20 = float(prices_df["close"].rolling(window=20).mean().iloc[-1])
    ma50 = float(prices_df["close"].rolling(window=50).mean().iloc[-1])
    
    # Calculate deviations
    deviation_20 = (current_price - ma20) / ma20 if ma20 > 0 else 0.0
    deviation_50 = (current_price - ma50) / ma50 if ma50 > 0 else 0.0
    
    # Score components
    score = 0
    reasons = []
    
    # RSI-based signals
    if rsi is not None:
        if rsi < 30:
            score += 3
            reasons.append(f"RSI {rsi:.1f} (oversold)")
        elif rsi < 40:
            score += 1
            reasons.append(f"RSI {rsi:.1f} (moderately oversold)")
        elif rsi > 70:
            score -= 3
            reasons.append(f"RSI {rsi:.1f} (overbought)")
        elif rsi > 60:
            score -= 1
            reasons.append(f"RSI {rsi:.1f} (moderately overbought)")
    
    # Price deviation signals
    if deviation_20 < -0.05:
        score += 2
        reasons.append(f"Price {deviation_20:.1%} below MA20")
    elif deviation_20 < -0.02:
        score += 1
        reasons.append(f"Price {deviation_20:.1%} below MA20")
    elif deviation_20 > 0.05:
        score -= 2
        reasons.append(f"Price {deviation_20:.1%} above MA20")
    elif deviation_20 > 0.02:
        score -= 1
        reasons.append(f"Price {deviation_20:.1%} above MA20")
    
    if deviation_50 < -0.08:
        score += 2
        reasons.append(f"Price {deviation_50:.1%} below MA50")
    elif deviation_50 < -0.03:
        score += 1
        reasons.append(f"Price {deviation_50:.1%} below MA50")
    elif deviation_50 > 0.08:
        score -= 2
        reasons.append(f"Price {deviation_50:.1%} above MA50")
    elif deviation_50 > 0.03:
        score -= 1
        reasons.append(f"Price {deviation_50:.1%} above MA50")
    
    # Determine signal
    if score >= 4:
        signal = "bullish"
        confidence = min(85, 50 + score * 8)
        reasoning = f"Mean reversion bullish (vol {volatility:.1%}): {', '.join(reasons)}"
    elif score <= -4:
        signal = "bearish"
        confidence = min(85, 50 + abs(score) * 8)
        reasoning = f"Mean reversion bearish (vol {volatility:.1%}): {', '.join(reasons)}"
    else:
        signal = "neutral"
        confidence = 50
        reasoning = f"Mean reversion neutral (vol {volatility:.1%}): {', '.join(reasons)}"
    
    return MeanReversionVolatilityGatedSignal(
        signal=signal,
        confidence=confidence,
        reasoning=reasoning,
        volatility_gated=False,
    )


def mean_reversion_volatility_gated_agent(state: AgentState, agent_id: str = "mean_reversion_volatility_gated_agent"):
    """
    Analyzes stocks using mean reversion with volatility gating.
    Only trades when volatility is low (mean reversion more reliable).
    """
    data = state["data"]
    start_date = data["start_date"]
    end_date = data["end_date"]
    tickers = data["tickers"]
    api_key = get_api_key_from_state(state, "FINANCIAL_DATASETS_API_KEY")
    
    mean_reversion_analysis = {}
    
    for ticker in tickers:
        progress.update_status(agent_id, ticker, "Fetching price data")
        
        prices = get_prices(
            ticker=ticker,
            start_date=start_date,
            end_date=end_date,
            api_key=api_key,
        )
        
        if not prices:
            mean_reversion_analysis[ticker] = {
                "signal": "neutral",
                "confidence": 50,
                "reasoning": "No price data available",
                "volatility_gated": False,
            }
            continue
        
        prices_df = prices_to_df(prices)
        
        if prices_df.empty or len(prices_df) < 50:
            mean_reversion_analysis[ticker] = {
                "signal": "neutral",
                "confidence": 50,
                "reasoning": "Insufficient price data for mean reversion analysis (need 50+ days)",
                "volatility_gated": False,
            }
            continue
        
        progress.update_status(agent_id, ticker, "Calculating volatility and mean reversion")
        
        signal_output = calculate_mean_reversion_volatility_gated_signal_rule_based(ticker, prices_df)
        
        mean_reversion_analysis[ticker] = {
            "signal": signal_output.signal,
            "confidence": signal_output.confidence,
            "reasoning": signal_output.reasoning,
            "volatility_gated": signal_output.volatility_gated,
        }
        
        progress.update_status(agent_id, ticker, "Done", analysis=signal_output.reasoning)
    
    message = HumanMessage(content=json.dumps(mean_reversion_analysis), name=agent_id)
    
    if state["metadata"]["show_reasoning"]:
        show_agent_reasoning(mean_reversion_analysis, agent_id)
    
    state["data"]["analyst_signals"][agent_id] = mean_reversion_analysis
    
    progress.update_status(agent_id, None, "Done")
    
    return {"messages": [message], "data": state["data"]}
