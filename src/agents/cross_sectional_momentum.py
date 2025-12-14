"""
Cross-Sectional Momentum Agent

Ranks stocks relative to each other based on recent performance.
Longs top performers, shorts bottom performers.
This is different from time-series momentum (which looks at a single stock's trend).
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


class CrossSectionalMomentumSignal(BaseModel):
    signal: Literal["bullish", "bearish", "neutral"]
    confidence: int = Field(description="Confidence 0-100")
    reasoning: str = Field(description="Reasoning for the decision")
    rank: int = Field(description="Rank among all tickers (1 = best, N = worst)")
    percentile: float = Field(description="Percentile rank (0-100, higher = better performance)")


def calculate_cross_sectional_momentum_signal_rule_based(
    ticker: str,
    prices_df: pd.DataFrame,
    all_ticker_returns: dict[str, float],
) -> CrossSectionalMomentumSignal:
    """
    Generate cross-sectional momentum signal by ranking ticker's return vs all tickers.
    
    Args:
        ticker: Current ticker
        prices_df: Price data for this ticker
        all_ticker_returns: Dict of {ticker: return} for all tickers in universe
    """
    if prices_df.empty or len(prices_df) < 20:
        return CrossSectionalMomentumSignal(
            signal="neutral",
            confidence=50,
            reasoning="Insufficient price data for cross-sectional momentum (need 20+ days)",
            rank=len(all_ticker_returns) // 2,
            percentile=50.0,
        )
    
    # Get this ticker's return
    current_price = float(prices_df["close"].iloc[-1])
    price_20_days_ago = float(prices_df["close"].iloc[-20])
    ticker_return = (current_price - price_20_days_ago) / price_20_days_ago if price_20_days_ago > 0 else 0.0
    
    if not all_ticker_returns or len(all_ticker_returns) < 2:
        return CrossSectionalMomentumSignal(
            signal="neutral",
            confidence=50,
            reasoning="Insufficient tickers for cross-sectional ranking (need 2+)",
            rank=1,
            percentile=50.0,
        )
    
    # Rank this ticker among all tickers
    sorted_returns = sorted(all_ticker_returns.items(), key=lambda x: x[1], reverse=True)
    rank = 1
    for other_ticker, other_return in sorted_returns:
        if other_ticker == ticker:
            break
        rank += 1
    
    total_tickers = len(all_ticker_returns)
    percentile = ((total_tickers - rank) / (total_tickers - 1)) * 100 if total_tickers > 1 else 50.0
    
    # Generate signal based on percentile rank
    # Top 20%: Strong bullish (long)
    # Bottom 20%: Strong bearish (short)
    # Middle 60%: Neutral
    
    if percentile >= 80:
        signal = "bullish"
        confidence = min(85, 50 + int((percentile - 80) * 1.75))  # 50-85 for 80-100 percentile
        reasoning = f"Top {100-percentile:.0f}% performer: {ticker_return:.1%} return (rank {rank}/{total_tickers})"
    elif percentile >= 60:
        signal = "bullish"
        confidence = min(70, 50 + int((percentile - 60) * 1.0))  # 50-70 for 60-80 percentile
        reasoning = f"Above-average performer: {ticker_return:.1%} return (rank {rank}/{total_tickers}, {percentile:.0f}th percentile)"
    elif percentile <= 20:
        signal = "bearish"
        confidence = min(85, 50 + int((20 - percentile) * 1.75))  # 50-85 for 0-20 percentile
        reasoning = f"Bottom {percentile:.0f}% performer: {ticker_return:.1%} return (rank {rank}/{total_tickers})"
    elif percentile <= 40:
        signal = "bearish"
        confidence = min(70, 50 + int((40 - percentile) * 1.0))  # 50-70 for 20-40 percentile
        reasoning = f"Below-average performer: {ticker_return:.1%} return (rank {rank}/{total_tickers}, {percentile:.0f}th percentile)"
    else:
        signal = "neutral"
        confidence = 50
        reasoning = f"Middle performer: {ticker_return:.1%} return (rank {rank}/{total_tickers}, {percentile:.0f}th percentile)"
    
    return CrossSectionalMomentumSignal(
        signal=signal,
        confidence=confidence,
        reasoning=reasoning,
        rank=rank,
        percentile=percentile,
    )


def cross_sectional_momentum_agent(state: AgentState, agent_id: str = "cross_sectional_momentum_agent"):
    """
    Analyzes stocks using cross-sectional momentum.
    Ranks all tickers by 20-day return and generates signals based on relative performance.
    """
    data = state["data"]
    start_date = data["start_date"]
    end_date = data["end_date"]
    tickers = data["tickers"]
    api_key = get_api_key_from_state(state, "FINANCIAL_DATASETS_API_KEY")
    
    # Step 1: Calculate returns for all tickers
    all_ticker_returns = {}
    ticker_prices = {}
    
    for ticker in tickers:
        progress.update_status(agent_id, ticker, "Fetching price data for ranking")
        
        prices = get_prices(
            ticker=ticker,
            start_date=start_date,
            end_date=end_date,
            api_key=api_key,
        )
        
        if prices:
            prices_df = prices_to_df(prices)
            if len(prices_df) >= 20:
                current_price = float(prices_df["close"].iloc[-1])
                price_20_days_ago = float(prices_df["close"].iloc[-20])
                ticker_return = (current_price - price_20_days_ago) / price_20_days_ago if price_20_days_ago > 0 else 0.0
                all_ticker_returns[ticker] = ticker_return
                ticker_prices[ticker] = prices_df
    
    if not all_ticker_returns:
        # Fallback: return neutral for all
        cross_sectional_analysis = {
            ticker: {
                "signal": "neutral",
                "confidence": 50,
                "reasoning": "Insufficient price data for cross-sectional ranking",
                "rank": len(tickers) // 2,
                "percentile": 50.0,
            }
            for ticker in tickers
        }
    else:
        # Step 2: Generate signals based on rankings
        cross_sectional_analysis = {}
        
        for ticker in tickers:
            progress.update_status(agent_id, ticker, "Calculating cross-sectional rank")
            
            prices_df = ticker_prices.get(ticker)
            if prices_df is None or prices_df.empty:
                cross_sectional_analysis[ticker] = {
                    "signal": "neutral",
                    "confidence": 50,
                    "reasoning": "No price data available",
                    "rank": len(all_ticker_returns) // 2,
                    "percentile": 50.0,
                }
                continue
            
            # Generate signal based on ranking
            signal_output = calculate_cross_sectional_momentum_signal_rule_based(
                ticker, prices_df, all_ticker_returns
            )
            
            cross_sectional_analysis[ticker] = {
                "signal": signal_output.signal,
                "confidence": signal_output.confidence,
                "reasoning": signal_output.reasoning,
                "rank": signal_output.rank,
                "percentile": signal_output.percentile,
            }
            
            progress.update_status(agent_id, ticker, f"Rank {signal_output.rank}/{len(all_ticker_returns)} ({signal_output.percentile:.0f}th percentile)")
    
    # Create the message
    message = HumanMessage(content=json.dumps(cross_sectional_analysis), name=agent_id)
    
    # Show reasoning if requested
    if state["metadata"]["show_reasoning"]:
        show_agent_reasoning(cross_sectional_analysis, agent_id)
    
    # Add the signal to the analyst_signals list
    state["data"]["analyst_signals"][agent_id] = cross_sectional_analysis
    
    progress.update_status(agent_id, None, "Done")
    
    return {"messages": [message], "data": state["data"]}
