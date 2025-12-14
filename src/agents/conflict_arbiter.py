from src.graph.state import AgentState, show_agent_reasoning
from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field
import json
from typing_extensions import Literal
from src.utils.progress import progress


class ConflictArbiterSignal(BaseModel):
    signal: Literal["bullish", "bearish", "neutral"]
    confidence: int = Field(description="Confidence 0-100")
    reasoning: str = Field(description="Reasoning for the decision")


# Conflict detection thresholds (explicitly documented)
HIGH_CONFIDENCE_THRESHOLD = 70  # Confidence >= 70% is considered "high confidence"
STRONG_DISAGREEMENT_THRESHOLD = 50  # Confidence difference >= 50% indicates strong disagreement
CONFIDENCE_DIFFERENCE_THRESHOLD = 30  # If one agent has >= 30% more confidence, defer to it

# Credibility weighting parameters (Part B)
CREDIBILITY_FLOOR = 0.2  # Minimum credibility multiplier (prevents zeroing out agents)


def signal_to_numeric(signal: str) -> float:
    """Convert signal to numeric for conflict analysis."""
    if signal == "bullish":
        return 1.0
    elif signal == "bearish":
        return -1.0
    else:  # neutral
        return 0.0


def detect_conflicts(
    signals: dict[str, dict]
) -> dict:
    """Detect conflicts and analyze signal distribution."""
    if not signals:
        return {
            "has_conflict": False,
            "bullish_count": 0,
            "bearish_count": 0,
            "neutral_count": 0,
            "max_confidence": 0,
            "min_confidence": 100,
            "avg_confidence": 0,
            "conflicting_pairs": [],
        }
    
    bullish_count = 0
    bearish_count = 0
    neutral_count = 0
    confidences = []
    signal_values = []
    
    for agent_name, signal_data in signals.items():
        sig = signal_data.get("signal")
        conf = signal_data.get("confidence", 50)
        
        if sig == "bullish":
            bullish_count += 1
            signal_values.append((1.0, conf, agent_name))
        elif sig == "bearish":
            bearish_count += 1
            signal_values.append((-1.0, conf, agent_name))
        else:  # neutral
            neutral_count += 1
            signal_values.append((0.0, conf, agent_name))
        
        confidences.append(conf)
    
    # Find conflicting pairs (high confidence, opposite signals)
    conflicting_pairs = []
    signal_list = list(signals.items())
    for i, (agent1, data1) in enumerate(signal_list):
        sig1 = data1.get("signal")
        conf1 = data1.get("confidence", 50)
        if conf1 < HIGH_CONFIDENCE_THRESHOLD:
            continue
        
        for j, (agent2, data2) in enumerate(signal_list[i+1:], start=i+1):
            sig2 = data2.get("signal")
            conf2 = data2.get("confidence", 50)
            if conf2 < HIGH_CONFIDENCE_THRESHOLD:
                continue
            
            # Check for strong disagreement
            if (sig1 == "bullish" and sig2 == "bearish") or (sig1 == "bearish" and sig2 == "bullish"):
                conflicting_pairs.append({
                    "agent1": agent1,
                    "signal1": sig1,
                    "confidence1": conf1,
                    "agent2": agent2,
                    "signal2": sig2,
                    "confidence2": conf2,
                })
    
    has_conflict = len(conflicting_pairs) > 0
    
    return {
        "has_conflict": has_conflict,
        "bullish_count": bullish_count,
        "bearish_count": bearish_count,
        "neutral_count": neutral_count,
        "max_confidence": max(confidences) if confidences else 0,
        "min_confidence": min(confidences) if confidences else 100,
        "avg_confidence": sum(confidences) / len(confidences) if confidences else 0,
        "conflicting_pairs": conflicting_pairs,
        "signal_values": signal_values,
    }


def adjust_signal_for_conflict(
    ticker: str,
    signals: dict[str, dict],
    conflict_analysis: dict,
    agent_credibility: dict[str, float] | None = None,
) -> ConflictArbiterSignal:
    """
    Apply deterministic conflict adjustment rules.
    Part B: Now weights signals by credibility scores if available.
    
    Credibility weighting formula:
    - Each signal's confidence is multiplied by its credibility (with floor at CREDIBILITY_FLOOR)
    - If credibility missing, default to 1.0
    - Weighted averages use credibility-adjusted confidences
    """
    
    if not signals:
        return ConflictArbiterSignal(
            signal="neutral",
            confidence=50,
            reasoning="No analyst signals available"
        )
    
    has_conflict = conflict_analysis["has_conflict"]
    bullish_count = conflict_analysis["bullish_count"]
    bearish_count = conflict_analysis["bearish_count"]
    neutral_count = conflict_analysis["neutral_count"]
    max_conf = conflict_analysis["max_confidence"]
    avg_conf = conflict_analysis["avg_confidence"]
    conflicting_pairs = conflict_analysis["conflicting_pairs"]
    signal_values = conflict_analysis["signal_values"]
    
    # Rule 1: If signals align (all same direction) → pass through with average confidence
    if bullish_count > 0 and bearish_count == 0:
        # All bullish or neutral
        avg_confidence = int(avg_conf)
        return ConflictArbiterSignal(
            signal="bullish",
            confidence=avg_confidence,
            reasoning=f"Consensus bullish ({bullish_count} bullish, {neutral_count} neutral), avg confidence {avg_confidence}%"
        )
    
    if bearish_count > 0 and bullish_count == 0:
        # All bearish or neutral
        avg_confidence = int(avg_conf)
        return ConflictArbiterSignal(
            signal="bearish",
            confidence=avg_confidence,
            reasoning=f"Consensus bearish ({bearish_count} bearish, {neutral_count} neutral), avg confidence {avg_confidence}%"
        )
    
    if bullish_count == 0 and bearish_count == 0:
        # All neutral
        return ConflictArbiterSignal(
            signal="neutral",
            confidence=int(avg_conf),
            reasoning=f"All neutral signals, avg confidence {avg_conf:.0f}%"
        )
    
    # Rule 2: If one agent has significantly higher confidence (>= 30% difference) → defer to stronger agent
    # Part B: Apply credibility weighting to confidences before comparison
    if len(signal_values) >= 2:
        # Apply credibility to confidences
        cred_adjusted_values = []
        for sig_val, conf, agent_name in signal_values:
            cred = 1.0
            if agent_credibility:
                cred = max(CREDIBILITY_FLOOR, agent_credibility.get(agent_name, 1.0))
            adjusted_conf = conf * cred
            cred_adjusted_values.append((sig_val, adjusted_conf, agent_name, conf, cred))
        
        # Find the agent with highest credibility-adjusted confidence
        max_agent = max(cred_adjusted_values, key=lambda x: x[1])
        second_max_agent = max([s for s in cred_adjusted_values if s != max_agent], key=lambda x: x[1], default=None)
        
        if second_max_agent and (max_agent[1] - second_max_agent[1]) >= CONFIDENCE_DIFFERENCE_THRESHOLD:
            # Defer to highest credibility-adjusted confidence agent
            signal_numeric, adj_conf, agent_name, orig_conf, cred = max_agent
            signal_str = "bullish" if signal_numeric > 0 else "bearish" if signal_numeric < 0 else "neutral"
            cred_info = f" (cred={cred:.2f})" if agent_credibility else ""
            return ConflictArbiterSignal(
                signal=signal_str,
                confidence=int(orig_conf * 0.9),  # Use original confidence with slight reduction
                reasoning=f"Deferring to {agent_name} (adj conf {adj_conf:.0f}%{cred_info} vs {second_max_agent[1]:.0f}%, {adj_conf - second_max_agent[1]:.0f}% difference)"
            )
    
    # Rule 3: If strong disagreement (high confidence, opposite signals) → reduce conviction, move toward neutral
    # Part B: Apply credibility weighting to weights
    if has_conflict and conflicting_pairs:
        # Calculate credibility-weighted average signal
        total_weight = 0
        weighted_sum = 0.0
        for sig_val, conf, agent_name in signal_values:
            cred = 1.0
            if agent_credibility:
                cred = max(CREDIBILITY_FLOOR, agent_credibility.get(agent_name, 1.0))
            # Weight = confidence * credibility
            weight = (conf / 100.0) * cred
            weighted_sum += sig_val * weight
            total_weight += weight
        
        if total_weight > 0:
            weighted_signal = weighted_sum / total_weight
        else:
            weighted_signal = 0.0
        
        # Convert to signal
        if weighted_signal > 0.2:
            final_signal = "bullish"
        elif weighted_signal < -0.2:
            final_signal = "bearish"
        else:
            final_signal = "neutral"
        
        # Reduce confidence based on conflict severity
        conflict_severity = len(conflicting_pairs)
        confidence_reduction = min(30, conflict_severity * 10)  # Up to 30% reduction
        adjusted_confidence = max(30, int(avg_conf - confidence_reduction))
        
        return ConflictArbiterSignal(
            signal=final_signal,
            confidence=adjusted_confidence,
            reasoning=f"Conflict detected ({len(conflicting_pairs)} high-confidence disagreements). Weighted signal: {final_signal}, confidence reduced by {confidence_reduction}% to {adjusted_confidence}%"
        )
    
    # Rule 4: Mixed signals without strong conflict → weighted average with moderate confidence
    # Part B: Apply credibility weighting to weights
    if len(signal_values) > 0:
        total_weight = 0
        weighted_sum = 0.0
        for sig_val, conf, agent_name in signal_values:
            cred = 1.0
            if agent_credibility:
                cred = max(CREDIBILITY_FLOOR, agent_credibility.get(agent_name, 1.0))
            # Weight = confidence * credibility
            weight = (conf / 100.0) * cred
            weighted_sum += sig_val * weight
            total_weight += weight
        
        if total_weight > 0:
            weighted_signal = weighted_sum / total_weight
        else:
            weighted_signal = 0.0
        
        if weighted_signal > 0.2:
            final_signal = "bullish"
        elif weighted_signal < -0.2:
            final_signal = "bearish"
        else:
            final_signal = "neutral"
        
        # Moderate confidence for mixed signals
        adjusted_confidence = max(40, int(avg_conf * 0.8))
        
        return ConflictArbiterSignal(
            signal=final_signal,
            confidence=adjusted_confidence,
            reasoning=f"Mixed signals ({bullish_count} bullish, {bearish_count} bearish, {neutral_count} neutral). Weighted average: {final_signal}, confidence {adjusted_confidence}%"
        )
    
    # Fallback
    return ConflictArbiterSignal(
        signal="neutral",
        confidence=50,
        reasoning="Unable to determine conflict-adjusted signal"
    )


def conflict_arbiter_agent(state: AgentState, agent_id: str = "conflict_arbiter_agent"):
    """Detects conflicts between analyst signals and adjusts confidence deterministically."""
    data = state["data"]
    tickers = data["tickers"]
    analyst_signals = data.get("analyst_signals", {})
    
    # Filter out risk_manager and portfolio_manager signals (only analyze analyst signals)
    analyst_only_signals = {
        k: v for k, v in analyst_signals.items()
        if not k.startswith("risk_management_agent") and not k.startswith("portfolio_manager")
    }
    
    conflict_analysis = {}
    
    for ticker in tickers:
        progress.update_status(agent_id, ticker, "Reading analyst signals")
        
        # Collect all analyst signals for this ticker
        ticker_signals = {}
        for agent_name, agent_data in analyst_only_signals.items():
            if isinstance(agent_data, dict) and ticker in agent_data:
                ticker_signals[agent_name] = agent_data[ticker]
        
        if not ticker_signals:
            progress.update_status(agent_id, ticker, "No analyst signals found")
            conflict_analysis[ticker] = {
                "signal": "neutral",
                "confidence": 50,
                "reasoning": "No analyst signals available for conflict analysis"
            }
            continue
        
        progress.update_status(agent_id, ticker, "Detecting conflicts")
        
        # Detect conflicts
        conflict_info = detect_conflicts(ticker_signals)
        
        progress.update_status(agent_id, ticker, "Adjusting signal for conflicts with credibility weighting")
        
        # Get credibility scores from state (Part B: credibility weighting)
        agent_credibility = data.get("agent_credibility", None)
        
        # Apply conflict adjustment rules with credibility weighting
        arbiter_output = adjust_signal_for_conflict(
            ticker=ticker,
            signals=ticker_signals,
            conflict_analysis=conflict_info,
            agent_credibility=agent_credibility,
        )
        
        conflict_analysis[ticker] = {
            "signal": arbiter_output.signal,
            "confidence": arbiter_output.confidence,
            "reasoning": arbiter_output.reasoning,
        }
        
        progress.update_status(agent_id, ticker, "Done", analysis=arbiter_output.reasoning)
    
    # Create the message
    message = HumanMessage(content=json.dumps(conflict_analysis), name=agent_id)
    
    # Show reasoning if requested
    if state["metadata"]["show_reasoning"]:
        show_agent_reasoning(conflict_analysis, agent_id)
    
    # Add the signal to the analyst_signals list
    state["data"]["analyst_signals"][agent_id] = conflict_analysis
    
    progress.update_status(agent_id, None, "Done")
    
    return {"messages": [message], "data": state["data"]}

