"""
Intelligence Agent: Provides market intelligence and strategic insights.

This agent analyzes market data to provide:
- Pattern detection (breakouts, reversals, momentum shifts)
- Anomaly detection (price spikes, volume surges)
- Market structure analysis (support/resistance levels)
- Strategic insights and recommendations
"""

import sys
from src.graph.state import AgentState, show_agent_reasoning
from langchain_core.messages import HumanMessage
from src.utils.progress import progress
from src.utils.api_key import get_api_key_from_state
from src.tools.api import get_prices, prices_to_df
from src.intelligence.intelligence_engine import get_intelligence_engine
import pandas as pd
import json
from typing import Dict, Any


def intelligence_agent(state: AgentState, agent_id: str = "intelligence_agent"):
    """
    Intelligence Agent - provides market intelligence and strategic insights.
    
    This agent:
    - Analyzes price data for patterns and anomalies
    - Detects market structure (support/resistance)
    - Generates strategic insights
    - Provides actionable recommendations
    """
    data = state["data"]
    tickers = data["tickers"]
    start_date = data.get("start_date")
    end_date = data.get("end_date")
    api_key = get_api_key_from_state(state, "FINANCIAL_DATASETS_API_KEY")
    
    intelligence_engine = get_intelligence_engine()
    intelligence_data = {}
    
    # Get benchmark prices for comparison (SPY as proxy for market)
    benchmark_prices = None
    try:
        spy_prices = get_prices("SPY", start_date, end_date, api_key=api_key)
        if spy_prices:
            benchmark_prices = prices_to_df(spy_prices)
    except Exception:
        pass  # Benchmark optional
    
    for ticker in tickers:
        progress.update_status(agent_id, ticker, "Gathering market intelligence")
        
        try:
            # Get price data
            prices = get_prices(ticker, start_date, end_date, api_key=api_key)
            if not prices:
                continue
            
            prices_df = prices_to_df(prices)
            if prices_df.empty or len(prices_df) < 20:
                continue
            
            # Generate intelligence
            market_intelligence = intelligence_engine.analyze_ticker(
                ticker=ticker,
                prices_df=prices_df,
                date=end_date,
                benchmark_prices=benchmark_prices,
            )
            
            # Format intelligence for storage
            intelligence_data[ticker] = {
                "volatility_regime": market_intelligence.volatility_regime,
                "trend_strength": market_intelligence.trend_strength,
                "trend_direction": market_intelligence.trend_direction,
                "momentum_score": market_intelligence.momentum_score,
                "risk_score": market_intelligence.risk_score,
                "risk_factors": market_intelligence.risk_factors,
                "patterns": [
                    {
                        "type": p.pattern_type.value,
                        "description": p.description,
                        "confidence": p.confidence,
                        "strength": p.strength,
                        "implications": p.implications,
                    }
                    for p in market_intelligence.patterns
                ],
                "anomalies": [
                    {
                        "type": a.anomaly_type,
                        "severity": a.severity.value,
                        "description": a.description,
                        "deviation_pct": a.deviation_pct,
                        "recommended_action": a.recommended_action,
                    }
                    for a in market_intelligence.anomalies
                ],
                "support_levels": market_intelligence.support_levels,
                "resistance_levels": market_intelligence.resistance_levels,
                "key_levels": market_intelligence.key_levels,
                "relative_strength": market_intelligence.relative_strength,
                "market_correlation": market_intelligence.market_correlation,
                "volume_anomaly": market_intelligence.volume_anomaly,
            }
            
            progress.update_status(
                agent_id,
                ticker,
                f"Intelligence: {market_intelligence.trend_direction} trend, "
                f"risk {market_intelligence.risk_score:.2f}, "
                f"{len(market_intelligence.patterns)} patterns, "
                f"{len(market_intelligence.anomalies)} anomalies"
            )
            
        except Exception as e:
            print(f"STRATEGY FAILURE: Intelligence analysis failed for {ticker}: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc(file=sys.stderr)
            continue
    
    # Generate strategic insights if we have intelligence data
    strategic_insights = []
    if intelligence_data:
        # Convert to MarketIntelligence objects for insight generation
        ticker_intelligence = {}
        for ticker, intel_dict in intelligence_data.items():
            # Create simplified MarketIntelligence for insight generation
            from src.intelligence.intelligence_types import MarketIntelligence, AnomalyAlert, PatternDetection, IntelligenceLevel, PatternType
            
            anomalies = [
                AnomalyAlert(
                    alert_id=f"{ticker}_anomaly_{i}",
                    ticker=ticker,
                    anomaly_type=a["type"],
                    severity=IntelligenceLevel(a["severity"]),
                    description=a["description"],
                    detected_at=end_date,
                    current_value=0.0,
                    expected_value=0.0,
                    deviation_pct=a["deviation_pct"],
                    potential_causes=[],
                    recommended_action=a.get("recommended_action"),
                )
                for i, a in enumerate(intel_dict["anomalies"])
            ]
            
            patterns = [
                PatternDetection(
                    pattern_id=f"{ticker}_pattern_{i}",
                    pattern_type=PatternType(p["type"]),
                    ticker=ticker,
                    description=p["description"],
                    confidence=p["confidence"],
                    detected_at=end_date,
                    strength=p["strength"],
                    implications=p["implications"],
                )
                for i, p in enumerate(intel_dict["patterns"])
            ]
            
            ticker_intelligence[ticker] = MarketIntelligence(
                ticker=ticker,
                date=end_date,
                volatility_regime=intel_dict["volatility_regime"],
                trend_strength=intel_dict["trend_strength"],
                trend_direction=intel_dict["trend_direction"],
                momentum_score=intel_dict["momentum_score"],
                anomalies=anomalies,
                patterns=patterns,
                support_levels=intel_dict["support_levels"],
                resistance_levels=intel_dict["resistance_levels"],
                key_levels=intel_dict["key_levels"],
                relative_strength=intel_dict["relative_strength"],
                sector_correlation=0.0,
                market_correlation=intel_dict["market_correlation"],
                volume_profile={},
                volume_anomaly=intel_dict["volume_anomaly"],
                risk_score=intel_dict["risk_score"],
                risk_factors=intel_dict["risk_factors"],
            )
        
        # Generate insights
        strategic_insights = intelligence_engine.generate_strategic_insights(ticker_intelligence)
    
    # Build output message
    output = {
        "intelligence": intelligence_data,
        "strategic_insights": [
            {
                "category": insight.category,
                "title": insight.title,
                "description": insight.description,
                "confidence": insight.confidence,
                "priority": insight.priority.value,
                "recommended_actions": insight.recommended_actions,
            }
            for insight in strategic_insights
        ],
    }
    
    message = HumanMessage(content=json.dumps(output), name=agent_id)
    
    # Show reasoning if requested
    if state["metadata"].get("show_reasoning", False):
        show_agent_reasoning(output, agent_id)
    
    # Store intelligence in state for other agents to use
    state["data"]["market_intelligence"] = intelligence_data
    state["data"]["strategic_insights"] = [
        {
            "category": insight.category,
            "title": insight.title,
            "description": insight.description,
            "confidence": insight.confidence,
            "priority": insight.priority.value,
            "recommended_actions": insight.recommended_actions,
        }
        for insight in strategic_insights
    ]
    
    progress.update_status(agent_id, None, "Done")
    
    return {"messages": state["messages"] + [message], "data": state["data"]}

