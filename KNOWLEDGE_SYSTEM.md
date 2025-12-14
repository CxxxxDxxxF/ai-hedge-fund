# Knowledge Management System - How Your Hedge Fund Gets Smarter

## Overview

Your hedge fund now has a **Knowledge Management System** that learns from every backtest and shares insights across all agents. This ensures your fund gets smarter over time and all agents work together effectively.

## How It Works

### 1. **Learning from Backtests**

After each backtest completes, the system automatically:

- **Extracts insights** from performance metrics, regime analysis, and agent contributions
- **Identifies patterns** that show consistent edge (agent combinations, signal patterns, market regimes)
- **Stores learnings** in a persistent knowledge base (JSON files in `src/knowledge/data/`)

### 2. **Knowledge Storage**

The knowledge base stores:

- **Trading Patterns**: Agent combinations and signal patterns that work
- **Market Regime Knowledge**: How the system performs in different market conditions
- **Agent Performance History**: Historical credibility scores, best/worst conditions
- **Signal Pattern Knowledge**: Which patterns predict success
- **Successful Techniques**: Techniques that have shown edge

### 3. **Knowledge Sharing**

Agents can access the knowledge base to:

- See their historical performance
- Learn which techniques work in current market conditions
- Get warnings about what to avoid
- Access relevant trading patterns

## Where Knowledge is Stored

All knowledge is stored in `src/knowledge/data/`:

```
src/knowledge/data/
├── trading_patterns.json      # Learned trading patterns
├── market_regimes.json        # Market regime knowledge
├── agent_performance.json     # Agent performance history
├── signal_patterns.json      # Signal pattern knowledge
└── techniques.json           # Successful techniques
```

These files are JSON, so you can inspect them directly to see what the system has learned.

## How Agents Work Together

### 1. **Shared Performance Data**

All agents can see each other's historical performance through the knowledge base:

```python
from src.knowledge.agent_knowledge import get_agent_credibility_from_knowledge_base

# Get agent's learned credibility
credibility = get_agent_credibility_from_knowledge_base("warren_buffett_agent")
```

### 2. **Pattern Recognition**

The system learns which agent combinations work:

- "Warren Buffett + Momentum" works well in bull markets
- "High confidence bullish consensus" predicts success
- Certain signal patterns show consistent edge

### 3. **Regime Awareness**

Agents know which strategies work in different market conditions:

- Bull market: Growth agents perform better
- Bear market: Value agents perform better
- Volatile market: Momentum agents perform better

### 4. **Credibility Weighting**

The Ensemble agent and Conflict Arbiter use knowledge base credibility scores to weight signals, ensuring better-performing agents have more influence.

## Example: How an Agent Uses Knowledge

```python
from src.knowledge.agent_knowledge import (
    get_knowledge_for_agent,
    format_knowledge_for_agent_reasoning,
)

def my_agent(state: AgentState, agent_id: str = "my_agent"):
    # Get learned knowledge for current conditions
    knowledge = get_knowledge_for_agent(
        agent_name=agent_id,
        state=state,
        regime=state["data"].get("market_regime", {}).get("regime"),
    )
    
    # Format knowledge for reasoning
    knowledge_context = format_knowledge_for_agent_reasoning(knowledge)
    
    # Use knowledge in decision-making
    # Knowledge includes:
    # - Historical performance
    # - Best techniques for current conditions
    # - Warnings about what to avoid
    # - Relevant trading patterns
```

## Integration with Backtesting

The learning engine is **automatically integrated** into `deterministic_backtest.py`. After each backtest:

1. ✅ Regime analysis runs
2. ✅ Learning engine extracts insights
3. ✅ Knowledge base is updated
4. ✅ Agents can use this knowledge in future runs

You'll see this message after each backtest:

```
================================================================================
KNOWLEDGE BASE UPDATED
================================================================================
Insights from this backtest have been stored in the knowledge base.
Agents will use this knowledge in future runs.
```

## Ensuring All Agents Work Together

The knowledge base enables collaboration through:

1. **Shared State**: All agents read from the same knowledge base
2. **Performance Tracking**: Agents see each other's track records
3. **Pattern Sharing**: Successful patterns are available to all agents
4. **Regime Coordination**: Agents know which strategies work in current conditions

## Manual Knowledge Inspection

You can inspect what the system has learned:

```python
from src.knowledge.knowledge_base import get_knowledge_base

kb = get_knowledge_base()

# Get all learned patterns
patterns = kb.get_patterns(min_sharpe=1.0)
for pattern in patterns:
    print(f"{pattern.description}: Sharpe {pattern.sharpe_ratio:.2f}")

# Get regime knowledge
regime = kb.get_regime("bull")
print(f"Bull market: Sharpe {regime.sharpe_ratio:.2f}, Win Rate {regime.win_rate:.1f}%")

# Get agent performance
agent = kb.get_agent_performance("warren_buffett_agent")
print(f"Warren Buffett: Credibility {agent.overall_credibility:.1%}")
```

## Future Enhancements

The system can be extended to:

- Real-time learning from live trading
- Cross-agent technique sharing
- Pattern matching for similar market conditions
- Automated strategy refinement based on learnings
- Agent-to-agent knowledge sharing (agents teaching each other)

## Summary

Your hedge fund now:

1. ✅ **Learns from every backtest** - Extracts insights automatically
2. ✅ **Stores knowledge persistently** - JSON files in `src/knowledge/data/`
3. ✅ **Shares knowledge with agents** - All agents can access learned patterns
4. ✅ **Gets smarter over time** - Each backtest improves future decisions
5. ✅ **Ensures collaboration** - Agents work together using shared knowledge

The system is fully integrated and will start learning from your next backtest!
