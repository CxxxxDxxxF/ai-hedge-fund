from src.graph.state import AgentState, show_agent_reasoning
from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field
import json
from typing_extensions import Literal
from src.utils.progress import progress


class EnsembleSignal(BaseModel):
    signal: Literal["bullish", "bearish", "neutral"]
    confidence: int = Field(description="Confidence 0-100")
    reasoning: str = Field(description="Reasoning for the decision")


# Fixed weights for ensemble combination
# These weights are explicitly documented and fixed for deterministic behavior
WARREN_BUFFETT_WEIGHT = 0.6  # 60% weight on Warren Buffett signal
MOMENTUM_WEIGHT = 0.4  # 40% weight on Momentum signal

# Credibility damping parameters
CREDIBILITY_FLOOR = 0.2  # Minimum credibility multiplier (prevents zeroing out agents)


def signal_to_numeric(signal: str) -> float:
    """Convert signal string to numeric value for weighted combination."""
    if signal == "bullish":
        return 1.0
    elif signal == "bearish":
        return -1.0
    else:  # neutral
        return 0.0


def numeric_to_signal(value: float) -> str:
    """Convert weighted numeric value back to signal."""
    if value > 0.3:  # Threshold for bullish
        return "bullish"
    elif value < -0.3:  # Threshold for bearish
        return "bearish"
    else:
        return "neutral"


def calculate_ensemble_signal_rule_based(
        ticker: str,
        buffett_signal: str | None,
        buffett_confidence: int | None,
        momentum_signal: str | None,
        momentum_confidence: int | None,
        agent_credibility: dict[str, float] | None = None,
) -> EnsembleSignal:
    """
    Generate deterministic ensemble signal by combining Warren Buffett and Momentum signals.
    Part B: Now weights signals by credibility scores if available.
    
    Credibility weighting formula:
    - Base weight * credibility (with floor at CREDIBILITY_FLOOR)
    - If credibility missing, default to 1.0
    - Final weights normalized to sum to 1.0
    """
    
    # Handle missing signals
    if buffett_signal is None or buffett_confidence is None:
        if momentum_signal is None or momentum_confidence is None:
            # Both missing - return neutral
            return EnsembleSignal(
                signal="neutral",
                confidence=50,
                reasoning="Both Warren Buffett and Momentum signals unavailable"
            )
        else:
            # Only momentum available - use momentum only
            return EnsembleSignal(
                signal=momentum_signal,
                confidence=momentum_confidence,
                reasoning=f"Ensemble: Using Momentum signal only (Warren Buffett unavailable)"
            )
    
    if momentum_signal is None or momentum_confidence is None:
        # Only Buffett available - use Buffett only
        return EnsembleSignal(
            signal=buffett_signal,
            confidence=buffett_confidence,
            reasoning=f"Ensemble: Using Warren Buffett signal only (Momentum unavailable)"
        )
    
    # Both signals available - combine with credibility-weighted base weights
    buffett_numeric = signal_to_numeric(buffett_signal)
    momentum_numeric = signal_to_numeric(momentum_signal)
    
    # Get credibility scores (default to 1.0 if missing)
    buffett_cred = 1.0
    momentum_cred = 1.0
    if agent_credibility:
        buffett_cred = max(CREDIBILITY_FLOOR, agent_credibility.get("warren_buffett_agent", 1.0))
        momentum_cred = max(CREDIBILITY_FLOOR, agent_credibility.get("momentum_agent", 1.0))
    
    # Apply credibility to base weights
    buffett_weight_cred = WARREN_BUFFETT_WEIGHT * buffett_cred
    momentum_weight_cred = MOMENTUM_WEIGHT * momentum_cred
    
    # Normalize weights to sum to 1.0
    total_weight = buffett_weight_cred + momentum_weight_cred
    if total_weight > 0:
        buffett_weight_normalized = buffett_weight_cred / total_weight
        momentum_weight_normalized = momentum_weight_cred / total_weight
    else:
        # Fallback if both credibilities are zero (shouldn't happen with floor)
        buffett_weight_normalized = WARREN_BUFFETT_WEIGHT
        momentum_weight_normalized = MOMENTUM_WEIGHT
    
    # Weighted combination with credibility-adjusted weights
    weighted_value = (buffett_numeric * buffett_weight_normalized) + (momentum_numeric * momentum_weight_normalized)
    
    # Convert back to signal
    ensemble_signal = numeric_to_signal(weighted_value)
    
    # Weighted confidence with credibility-adjusted weights
    ensemble_confidence = int(
        (buffett_confidence * buffett_weight_normalized) + (momentum_confidence * momentum_weight_normalized)
    )
    ensemble_confidence = max(0, min(100, ensemble_confidence))  # Clamp to 0-100
    
    # Build reasoning with credibility info
    cred_info = ""
    if agent_credibility:
        cred_info = f" (cred: Buffett={buffett_cred:.2f}, Momentum={momentum_cred:.2f})"
    
    reasoning = (
        f"Ensemble: {buffett_weight_normalized:.0%} Buffett ({buffett_signal}, {buffett_confidence}%) + "
        f"{momentum_weight_normalized:.0%} Momentum ({momentum_signal}, {momentum_confidence}%) = "
        f"{ensemble_signal} ({ensemble_confidence}%){cred_info}"
    )
    
    return EnsembleSignal(
        signal=ensemble_signal,
        confidence=ensemble_confidence,
        reasoning=reasoning
    )


def ensemble_agent(state: AgentState, agent_id: str = "ensemble_agent"):
    """Combines Warren Buffett and Momentum agent signals using fixed weights."""
    data = state["data"]
    tickers = data["tickers"]
    analyst_signals = data.get("analyst_signals", {})
    
    # Try to get credibility from knowledge base (learned from past backtests)
    try:
        from src.knowledge.agent_knowledge import get_agent_credibility_from_knowledge_base
        
        # Enhance agent_credibility with knowledge base data
        agent_credibility = data.get("agent_credibility", {})
        kb_credibility = {}
        for agent_name in ["warren_buffett_agent", "momentum_agent"]:
            kb_cred = get_agent_credibility_from_knowledge_base(agent_name)
            # Use knowledge base credibility if available, otherwise use state credibility
            if agent_name not in agent_credibility or agent_credibility[agent_name] == 0.5:
                kb_credibility[agent_name] = kb_cred
            else:
                # Blend: 70% state (current run), 30% knowledge base (historical)
                kb_credibility[agent_name] = (agent_credibility[agent_name] * 0.7) + (kb_cred * 0.3)
        
        # Update agent_credibility with knowledge base insights
        if kb_credibility:
            agent_credibility.update(kb_credibility)
    except Exception:
        # Fallback to state credibility if knowledge base unavailable
        agent_credibility = data.get("agent_credibility", None)
    
    ensemble_analysis = {}
    
    for ticker in tickers:
        progress.update_status(agent_id, ticker, "Reading Warren Buffett and Momentum signals")
        
        # Extract signals from state
        buffett_signals = analyst_signals.get("warren_buffett_agent", {})
        momentum_signals = analyst_signals.get("momentum_agent", {})
        
        buffett_ticker_data = buffett_signals.get(ticker, {})
        momentum_ticker_data = momentum_signals.get(ticker, {})
        
        buffett_signal = buffett_ticker_data.get("signal")
        buffett_confidence = buffett_ticker_data.get("confidence")
        momentum_signal = momentum_ticker_data.get("signal")
        momentum_confidence = momentum_ticker_data.get("confidence")
        
        progress.update_status(agent_id, ticker, "Combining signals with credibility-weighted weights")
        
        # Generate ensemble signal (always deterministic, now with credibility weighting)
        ensemble_output = calculate_ensemble_signal_rule_based(
            ticker=ticker,
            buffett_signal=buffett_signal,
            buffett_confidence=buffett_confidence,
            momentum_signal=momentum_signal,
            momentum_confidence=momentum_confidence,
            agent_credibility=agent_credibility,
        )
        
        ensemble_analysis[ticker] = {
            "signal": ensemble_output.signal,
            "confidence": ensemble_output.confidence,
            "reasoning": ensemble_output.reasoning,
        }
        
        progress.update_status(agent_id, ticker, "Done", analysis=ensemble_output.reasoning)
    
    # Create the message
    message = HumanMessage(content=json.dumps(ensemble_analysis), name=agent_id)
    
    # Show reasoning if requested
    if state["metadata"]["show_reasoning"]:
        show_agent_reasoning(ensemble_analysis, agent_id)
    
    # Add the signal to the analyst_signals list
    state["data"]["analyst_signals"][agent_id] = ensemble_analysis
    
    progress.update_status(agent_id, None, "Done")
    
    return {"messages": [message], "data": state["data"]}

