"""
Market-Neutral Long/Short Agent

Generates market-neutral pairs by:
1. Ranking all tickers by momentum/strength
2. Longing top performers
3. Shorting bottom performers
4. Maintaining dollar-neutral exposure (long $ = short $)
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


class MarketNeutralSignal(BaseModel):
    signal: Literal["bullish", "bearish", "neutral"]
    confidence: int = Field(description="Confidence 0-100")
    reasoning: str = Field(description="Reasoning for the decision")
    market_neutral_rank: int = Field(description="Rank for market-neutral pairing (1 = top long, N = bottom short)")


def calculate_market_neutral_signal_rule_based(
    ticker: str,
    prices_df: pd.DataFrame,
    all_ticker_scores: dict[str, float],
) -> MarketNeutralSignal:
    """
    Generate market-neutral signal by ranking ticker vs all tickers.
    Top half: bullish (long)
    Bottom half: bearish (short)
    """
    if prices_df.empty or len(prices_df) < 20:
        return MarketNeutralSignal(
            signal="neutral",
            confidence=50,
            reasoning="Insufficient price data for market-neutral analysis (need 20+ days)",
            market_neutral_rank=len(all_ticker_scores) // 2,
        )
    
    if not all_ticker_scores or len(all_ticker_scores) < 2:
        return MarketNeutralSignal(
            signal="neutral",
            confidence=50,
            reasoning="Insufficient tickers for market-neutral pairing (need 2+)",
            market_neutral_rank=1,
        )
    
    # Rank this ticker
    sorted_scores = sorted(all_ticker_scores.items(), key=lambda x: x[1], reverse=True)
    rank = 1
    for other_ticker, _ in sorted_scores:
        if other_ticker == ticker:
            break
        rank += 1
    
    total_tickers = len(all_ticker_scores)
    median_rank = (total_tickers + 1) // 2
    
    # Top half: bullish (long)
    # Bottom half: bearish (short)
    if rank <= median_rank:
        signal = "bullish"
        # Higher rank (lower number) = stronger bullish
        percentile = ((median_rank - rank + 1) / median_rank) * 100
        confidence = min(85, 50 + int(percentile * 0.35))  # 50-85
        reasoning = f"Market-neutral LONG: Rank {rank}/{total_tickers} (top {percentile:.0f}% of longs)"
    else:
        signal = "bearish"
        # Lower rank (higher number) = stronger bearish
        bottom_half_size = total_tickers - median_rank
        percentile = ((rank - median_rank) / bottom_half_size) * 100 if bottom_half_size > 0 else 0
        confidence = min(85, 50 + int(percentile * 0.35))  # 50-85
        reasoning = f"Market-neutral SHORT: Rank {rank}/{total_tickers} (bottom {percentile:.0f}% of shorts)"
    
    return MarketNeutralSignal(
        signal=signal,
        confidence=confidence,
        reasoning=reasoning,
        market_neutral_rank=rank,
    )


def calculate_strength_score(prices_df: pd.DataFrame) -> float:
    """
    Calculate composite strength score for market-neutral ranking.
    Combines momentum, trend, and volatility.
    """
    if len(prices_df) < 20:
        return 0.0
    
    current_price = float(prices_df["close"].iloc[-1])
    price_20_days_ago = float(prices_df["close"].iloc[-20])
    
    # 20-day momentum (60% weight)
    momentum = (current_price - price_20_days_ago) / price_20_days_ago if price_20_days_ago > 0 else 0.0
    
    # Trend strength: price vs moving averages (30% weight)
    ma10 = float(prices_df["close"].rolling(window=10).mean().iloc[-1])
    ma20 = float(prices_df["close"].rolling(window=20).mean().iloc[-1])
    trend_score = 0.0
    if ma20 > 0:
        if current_price > ma10 > ma20:
            trend_score = 1.0  # Strong uptrend
        elif current_price > ma20:
            trend_score = 0.5  # Moderate uptrend
        elif current_price < ma10 < ma20:
            trend_score = -1.0  # Strong downtrend
        elif current_price < ma20:
            trend_score = -0.5  # Moderate downtrend
    
    # Volatility-adjusted: lower vol = higher score (10% weight)
    returns = prices_df["close"].pct_change().dropna()
    if len(returns) >= 20:
        volatility = returns.iloc[-20:].std() * np.sqrt(252)
        vol_score = max(0, 1.0 - volatility / 0.50)  # Penalize high volatility
    else:
        vol_score = 0.5
    
    # Composite score
    composite_score = (momentum * 0.6) + (trend_score * 0.3) + (vol_score * 0.1)
    
    return float(composite_score)


def market_neutral_ls_agent(state: AgentState, agent_id: str = "market_neutral_ls_agent"):
    """
    Generates market-neutral long/short signals.
    Ranks all tickers and pairs top (long) with bottom (short).
    """
    data = state["data"]
    start_date = data["start_date"]
    end_date = data["end_date"]
    tickers = data["tickers"]
    api_key = get_api_key_from_state(state, "FINANCIAL_DATASETS_API_KEY")
    
    # Step 1: Calculate strength scores for all tickers
    all_ticker_scores = {}
    ticker_prices = {}
    
    for ticker in tickers:
        progress.update_status(agent_id, ticker, "Calculating strength score for market-neutral ranking")
        
        prices = get_prices(
            ticker=ticker,
            start_date=start_date,
            end_date=end_date,
            api_key=api_key,
        )
        
        if prices:
            prices_df = prices_to_df(prices)
            if len(prices_df) >= 20:
                strength_score = calculate_strength_score(prices_df)
                all_ticker_scores[ticker] = strength_score
                ticker_prices[ticker] = prices_df
    
    if not all_ticker_scores:
        # Fallback: return neutral for all
        market_neutral_analysis = {
            ticker: {
                "signal": "neutral",
                "confidence": 50,
                "reasoning": "Insufficient price data for market-neutral ranking",
                "market_neutral_rank": len(tickers) // 2,
            }
            for ticker in tickers
        }
    else:
        # Step 2: Generate market-neutral signals
        market_neutral_analysis = {}
        
        for ticker in tickers:
            progress.update_status(agent_id, ticker, "Generating market-neutral signal")
            
            prices_df = ticker_prices.get(ticker)
            if prices_df is None or prices_df.empty:
                market_neutral_analysis[ticker] = {
                    "signal": "neutral",
                    "confidence": 50,
                    "reasoning": "No price data available",
                    "market_neutral_rank": len(all_ticker_scores) // 2,
                }
                continue
            
            signal_output = calculate_market_neutral_signal_rule_based(
                ticker, prices_df, all_ticker_scores
            )
            
            market_neutral_analysis[ticker] = {
                "signal": signal_output.signal,
                "confidence": signal_output.confidence,
                "reasoning": signal_output.reasoning,
                "market_neutral_rank": signal_output.market_neutral_rank,
            }
            
            progress.update_status(agent_id, ticker, f"Market-neutral rank {signal_output.market_neutral_rank}/{len(all_ticker_scores)}")
    
    message = HumanMessage(content=json.dumps(market_neutral_analysis), name=agent_id)
    
    if state["metadata"]["show_reasoning"]:
        show_agent_reasoning(market_neutral_analysis, agent_id)
    
    state["data"]["analyst_signals"][agent_id] = market_neutral_analysis
    
    progress.update_status(agent_id, None, "Done")
    
    return {"messages": [message], "data": state["data"]}
