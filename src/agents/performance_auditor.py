"""
Performance Auditor Agent

A deterministic agent that tracks analyst performance metrics and produces
credibility scores based on:
- Signal correctness (signal direction vs actual price movement)
- PnL contribution (whether signals led to profitable trades)
- Drawdown contribution (whether signals coincided with portfolio drawdowns)

This agent runs BEFORE Conflict Arbiter to provide credibility signals that
can inform conflict resolution.
"""

from src.graph.state import AgentState, show_agent_reasoning
from langchain_core.messages import HumanMessage
from src.utils.progress import progress
from src.tools.api import get_prices, prices_to_df
from src.utils.api_key import get_api_key_from_state
import json
from typing import Dict, Any
import pandas as pd
from datetime import datetime, timedelta


# Deterministic credibility update parameters
INITIAL_CREDIBILITY = 0.5  # Start with neutral credibility (0.0-1.0)
CREDIBILITY_UPDATE_RATE = 0.1  # How fast credibility changes (0.0-1.0, lower = slower)
CORRECT_SIGNAL_BOOST = 0.05  # Increase credibility for correct signal
INCORRECT_SIGNAL_PENALTY = -0.05  # Decrease credibility for incorrect signal
PROFITABLE_SIGNAL_BOOST = 0.10  # Additional boost for profitable signals
DRAWDOWN_SIGNAL_PENALTY = -0.10  # Additional penalty for drawdown-causing signals
MIN_CREDIBILITY = 0.0  # Minimum credibility score
MAX_CREDIBILITY = 1.0  # Maximum credibility score
SIGNAL_LOOKBACK_DAYS = 5  # Days to look back for evaluating signal correctness


def evaluate_signal_correctness(
    signal: str,
    price_change_pct: float,
    signal_threshold: float = 2.0
) -> bool | None:
    """
    Evaluate if a signal was correct based on actual price movement.
    
    Args:
        signal: "bullish", "bearish", or "neutral"
        price_change_pct: Actual price change percentage
        signal_threshold: Minimum price change to consider signal meaningful (default 2%)
    
    Returns:
        True if correct, False if incorrect, None if neutral or inconclusive
    """
    if signal == "neutral":
        return None  # Neutral signals don't count as correct/incorrect
    
    # Signal is correct if direction matches outcome
    if signal == "bullish":
        return price_change_pct >= signal_threshold
    elif signal == "bearish":
        return price_change_pct <= -signal_threshold
    
    return None


def calculate_price_change(
    ticker: str,
    current_date: str,
    lookback_days: int,
    api_key: str | None
) -> float | None:
    """
    Calculate price change over the lookback period.
    
    Args:
        ticker: Stock ticker symbol
        current_date: Current date (YYYY-MM-DD)
        lookback_days: Number of days to look back
        api_key: API key for data access
    
    Returns:
        Price change percentage, or None if unable to calculate
    """
    try:
        # Calculate start date for lookback
        current_dt = datetime.strptime(current_date, "%Y-%m-%d")
        start_dt = current_dt - timedelta(days=lookback_days + 10)  # Extra buffer for weekends
        start_date = start_dt.strftime("%Y-%m-%d")
        
        prices = get_prices(ticker, start_date, current_date, api_key=api_key)
        if not prices:
            return None
        
        prices_df = prices_to_df(prices)
        if prices_df.empty or len(prices_df) < 2:
            return None
        
        # Get price at start and end of lookback period
        # Use last available price as current
        current_price = prices_df["close"].iloc[-1]
        
        # Find price lookback_days ago (or closest available)
        if len(prices_df) > lookback_days:
            lookback_price = prices_df["close"].iloc[-lookback_days-1]
        else:
            lookback_price = prices_df["close"].iloc[0]
        
        if lookback_price == 0:
            return None
        
        price_change_pct = ((current_price - lookback_price) / lookback_price) * 100
        return price_change_pct
    
    except Exception:
        return None


def update_credibility_score(
    current_credibility: float,
    is_correct: bool | None,
    is_profitable: bool = False,
    caused_drawdown: bool = False
) -> float:
    """
    Update credibility score deterministically based on performance.
    
    Args:
        current_credibility: Current credibility score (0.0-1.0)
        is_correct: Whether signal was correct (True/False/None)
        is_profitable: Whether signal led to profitable trade
        caused_drawdown: Whether signal coincided with drawdown
    
    Returns:
        Updated credibility score (clamped to [MIN_CREDIBILITY, MAX_CREDIBILITY])
    """
    adjustment = 0.0
    
    # Base adjustment for signal correctness
    if is_correct is True:
        adjustment += CORRECT_SIGNAL_BOOST
    elif is_correct is False:
        adjustment += INCORRECT_SIGNAL_PENALTY
    
    # Additional adjustments for profitability/drawdowns
    if is_profitable:
        adjustment += PROFITABLE_SIGNAL_BOOST
    if caused_drawdown:
        adjustment += DRAWDOWN_SIGNAL_PENALTY
    
    # Apply gradual update (weighted average)
    new_credibility = current_credibility + (adjustment * CREDIBILITY_UPDATE_RATE)
    
    # Clamp to valid range
    new_credibility = max(MIN_CREDIBILITY, min(MAX_CREDIBILITY, new_credibility))
    
    return new_credibility


def performance_auditor_agent(state: AgentState, agent_id: str = "performance_auditor_agent"):
    """
    Performance Auditor Agent - tracks analyst performance and produces credibility scores.
    
    This agent:
    - Reads analyst signals from state
    - Evaluates signal correctness against actual price movements
    - Calculates credibility scores per analyst
    - Stores credibility scores in analyst_signals for use by other agents
    """
    data = state["data"]
    tickers = data["tickers"]
    end_date = data.get("end_date")
    analyst_signals = data.get("analyst_signals", {})
    api_key = get_api_key_from_state(state, "FINANCIAL_DATASETS_API_KEY")
    
    # Filter to only analyst agents (exclude system agents)
    analyst_only_signals = {
        k: v for k, v in analyst_signals.items()
        if not k.startswith("risk_management_agent") 
        and not k.startswith("portfolio_manager")
        and not k.startswith("performance_auditor_agent")
        and not k.startswith("conflict_arbiter_agent")
    }
    
    # Initialize or load existing credibility scores
    performance_data = data.get("performance_tracking", {})
    credibility_scores = performance_data.get("credibility_scores", {})
    
    # Initialize credibility for analysts that don't have scores yet
    for agent_name in analyst_only_signals.keys():
        if agent_name not in credibility_scores:
            credibility_scores[agent_name] = {
                "credibility": INITIAL_CREDIBILITY,
                "correct_signals": 0,
                "incorrect_signals": 0,
                "neutral_signals": 0,
                "total_evaluated": 0,
                "last_updated": end_date
            }
    
    # Evaluate signals for each analyst and ticker
    # Note: In backtesting context, this evaluates against actual price outcomes
    # In real-time, this maintains existing credibility scores
    if end_date:
        for agent_name, agent_data in analyst_only_signals.items():
            if not isinstance(agent_data, dict):
                continue
            
            for ticker in tickers:
                if ticker not in agent_data:
                    continue
                
                progress.update_status(agent_id, ticker, f"Evaluating {agent_name}")
                
                signal_data = agent_data[ticker]
                signal = signal_data.get("signal", "neutral")
                
                # Calculate price change to evaluate signal correctness
                # This works in backtesting where we have historical data
                price_change = calculate_price_change(
                    ticker=ticker,
                    current_date=end_date,
                    lookback_days=SIGNAL_LOOKBACK_DAYS,
                    api_key=api_key
                )
                
                if price_change is not None:
                    # Evaluate signal correctness
                    is_correct = evaluate_signal_correctness(signal, price_change)
                    
                    # Update credibility score
                    current_cred = credibility_scores[agent_name]["credibility"]
                    
                    # For simplicity, we don't track profitability/drawdowns in this version
                    # as it would require portfolio state tracking across backtest runs
                    # This can be extended later by accessing portfolio outcomes from state
                    new_cred = update_credibility_score(
                        current_credibility=current_cred,
                        is_correct=is_correct,
                        is_profitable=False,  # TODO: Track from portfolio outcomes in state
                        caused_drawdown=False  # TODO: Track from portfolio drawdowns in state
                    )
                    
                    # Update tracking stats
                    if is_correct is True:
                        credibility_scores[agent_name]["correct_signals"] += 1
                        credibility_scores[agent_name]["total_evaluated"] += 1
                    elif is_correct is False:
                        credibility_scores[agent_name]["incorrect_signals"] += 1
                        credibility_scores[agent_name]["total_evaluated"] += 1
                    else:
                        credibility_scores[agent_name]["neutral_signals"] += 1
                    
                    credibility_scores[agent_name]["credibility"] = new_cred
                    credibility_scores[agent_name]["last_updated"] = end_date
    
    # Build output: credibility scores for each analyst
    auditor_output = {}
    explanations = {}
    
    for agent_name in analyst_only_signals.keys():
        if agent_name in credibility_scores:
            cred_data = credibility_scores[agent_name]
            cred_score = cred_data["credibility"]
            
            # Format credibility score (0.0-1.0, stored as percentage 0-100 for consistency)
            cred_percentage = int(cred_score * 100)
            
            # Build explanation
            correct = cred_data.get("correct_signals", 0)
            incorrect = cred_data.get("incorrect_signals", 0)
            total = cred_data.get("total_evaluated", 0)
            
            if total > 0:
                accuracy_pct = (correct / total * 100) if total > 0 else 0
                explanation = (
                    f"Credibility: {cred_percentage}% (Accuracy: {correct}/{total} = {accuracy_pct:.1f}%). "
                    f"Updated gradually based on signal correctness."
                )
            else:
                explanation = (
                    f"Credibility: {cred_percentage}% (initial/default score). "
                    f"No signals evaluated yet."
                )
            
            # Store in format compatible with analyst_signals
            auditor_output[agent_name] = {
                "credibility": cred_percentage,
                "explanation": explanation,
                "correct_signals": correct,
                "incorrect_signals": incorrect,
                "total_evaluated": total
            }
            
            explanations[agent_name] = explanation
    
    # Update state with performance tracking data
    if "performance_tracking" not in data:
        data["performance_tracking"] = {}
    data["performance_tracking"]["credibility_scores"] = credibility_scores
    
    # Store credibility map for use by other agents (Part B: credibility weighting)
    # Format: {agent_name: credibility_score (0.0-1.0)}
    agent_credibility = {}
    for agent_name, cred_data in credibility_scores.items():
        agent_credibility[agent_name] = cred_data["credibility"]  # Already 0.0-1.0
    
    data["agent_credibility"] = agent_credibility
    
    # Add credibility scores to analyst_signals for access by other agents
    # Store under performance_auditor_agent key
    message_content = json.dumps({
        "credibility_scores": auditor_output,
        "summary": explanations
    })
    
    message = HumanMessage(content=message_content, name=agent_id)
    
    # Show reasoning if requested
    if state["metadata"].get("show_reasoning", False):
        show_agent_reasoning({
            "credibility_scores": auditor_output,
            "explanations": explanations
        }, agent_id)
    
    # Do NOT store in analyst_signals - this is advisory only
    # Store credibility map for use by other agents (Part B: credibility weighting)
    agent_credibility = {}
    for agent_name, cred_data in credibility_scores.items():
        agent_credibility[agent_name] = cred_data["credibility"]
    data["agent_credibility"] = agent_credibility
    
    # Also attach credibility metadata to each analyst's signal data for easy access (read-only metadata)
    for agent_name, cred_data in auditor_output.items():
        if agent_name in state["data"]["analyst_signals"]:
            agent_signal_data = state["data"]["analyst_signals"][agent_name]
            if isinstance(agent_signal_data, dict):
                # Add credibility metadata to each ticker's signal (metadata only, not a signal)
                for ticker in tickers:
                    if ticker in agent_signal_data:
                        if not isinstance(agent_signal_data[ticker], dict):
                            continue
                        agent_signal_data[ticker]["credibility"] = cred_data["credibility"]
                        agent_signal_data[ticker]["credibility_explanation"] = cred_data["explanation"]
    
    progress.update_status(agent_id, None, "Done")
    
    return {"messages": [message], "data": state["data"]}
