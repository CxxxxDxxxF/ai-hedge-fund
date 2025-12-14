from src.graph.state import AgentState, show_agent_reasoning
from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field
import json
from typing_extensions import Literal
from src.tools.api import get_prices, prices_to_df
from src.utils.progress import progress
from src.utils.api_key import get_api_key_from_state
import pandas as pd


class MomentumSignal(BaseModel):
    signal: Literal["bullish", "bearish", "neutral"]
    confidence: int = Field(description="Confidence 0-100")
    reasoning: str = Field(description="Reasoning for the decision")


def calculate_momentum_signal_rule_based(
        ticker: str,
        prices_df: pd.DataFrame,
) -> MomentumSignal:
    """Generate deterministic momentum signal based on 20-day price momentum."""
    if prices_df.empty or len(prices_df) < 20:
        return MomentumSignal(
            signal="neutral",
            confidence=50,
            reasoning="Insufficient price data for 20-day momentum"
        )
    
    # Calculate 20-day momentum: (current_price - price_20_days_ago) / price_20_days_ago
    current_price = float(prices_df["close"].iloc[-1])
    price_20_days_ago = float(prices_df["close"].iloc[-20])
    momentum = (current_price - price_20_days_ago) / price_20_days_ago if price_20_days_ago > 0 else 0.0
    
    # Rule-based decision logic
    # Strong bullish: momentum > 5%
    if momentum > 0.05:
        confidence = min(85, 50 + int(momentum * 500))  # Scale confidence with momentum strength
        return MomentumSignal(
            signal="bullish",
            confidence=confidence,
            reasoning=f"Strong positive momentum: {momentum:.1%} over 20 days"
        )
    # Moderate bullish: momentum > 2%
    elif momentum > 0.02:
        confidence = min(70, 50 + int(momentum * 400))
        return MomentumSignal(
            signal="bullish",
            confidence=confidence,
            reasoning=f"Positive momentum: {momentum:.1%} over 20 days"
        )
    # Strong bearish: momentum < -5%
    elif momentum < -0.05:
        confidence = min(85, 50 + int(abs(momentum) * 500))
        return MomentumSignal(
            signal="bearish",
            confidence=confidence,
            reasoning=f"Strong negative momentum: {momentum:.1%} over 20 days"
        )
    # Moderate bearish: momentum < -2%
    elif momentum < -0.02:
        confidence = min(70, 50 + int(abs(momentum) * 400))
        return MomentumSignal(
            signal="bearish",
            confidence=confidence,
            reasoning=f"Negative momentum: {momentum:.1%} over 20 days"
        )
    # Neutral: momentum between -2% and 2%
    else:
        return MomentumSignal(
            signal="neutral",
            confidence=50,
            reasoning=f"Neutral momentum: {momentum:.1%} over 20 days"
        )


def momentum_agent(state: AgentState, agent_id: str = "momentum_agent"):
    """Analyzes stocks using 20-day price momentum."""
    data = state["data"]
    start_date = data["start_date"]
    end_date = data["end_date"]
    tickers = data["tickers"]
    api_key = get_api_key_from_state(state, "FINANCIAL_DATASETS_API_KEY")
    
    momentum_analysis = {}
    
    for ticker in tickers:
        progress.update_status(agent_id, ticker, "Fetching price data")
        
        # Get price data (need at least 20 days)
        prices = get_prices(
            ticker=ticker,
            start_date=start_date,
            end_date=end_date,
            api_key=api_key,
        )
        
        if not prices:
            progress.update_status(agent_id, ticker, "Failed: No price data found")
            momentum_analysis[ticker] = {
                "signal": "neutral",
                "confidence": 50,
                "reasoning": "No price data available"
            }
            continue
        
        prices_df = prices_to_df(prices)
        
        if prices_df.empty or len(prices_df) < 20:
            progress.update_status(agent_id, ticker, "Warning: Insufficient data for 20-day momentum")
            momentum_analysis[ticker] = {
                "signal": "neutral",
                "confidence": 50,
                "reasoning": "Insufficient price data for 20-day momentum"
            }
            continue
        
        progress.update_status(agent_id, ticker, "Calculating 20-day momentum")
        progress.update_status(agent_id, ticker, "Generating momentum signal")
        
        # Momentum agent is always deterministic (rule-based)
        momentum_output = calculate_momentum_signal_rule_based(ticker, prices_df)
        
        momentum_analysis[ticker] = {
            "signal": momentum_output.signal,
            "confidence": momentum_output.confidence,
            "reasoning": momentum_output.reasoning,
        }
        
        progress.update_status(agent_id, ticker, "Done", analysis=momentum_output.reasoning)
    
    # Create the message
    message = HumanMessage(content=json.dumps(momentum_analysis), name=agent_id)
    
    # Show reasoning if requested
    if state["metadata"]["show_reasoning"]:
        show_agent_reasoning(momentum_analysis, agent_id)
    
    # Add the signal to the analyst_signals list
    state["data"]["analyst_signals"][agent_id] = momentum_analysis
    
    progress.update_status(agent_id, None, "Done")
    
    return {"messages": [message], "data": state["data"]}

