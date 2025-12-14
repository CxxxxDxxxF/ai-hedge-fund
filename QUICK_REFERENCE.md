# AI Hedge Fund - Quick Reference

## What This Project Does

An AI-powered hedge fund simulation system that:
- Uses 18 different AI agents (each representing a famous investor's philosophy) to analyze stocks
- Aggregates their signals through a risk manager and portfolio manager
- Makes trading decisions (buy/sell/short/cover/hold) for multiple tickers
- Supports backtesting historical performance
- Provides both CLI and web interfaces

**Note**: Does NOT execute real trades - educational/research only.

## Entry Points

| Entry Point | File | Purpose |
|------------|------|---------|
| CLI Hedge Fund | `src/main.py` | Run trading decisions interactively |
| CLI Backtester | `src/backtester.py` | Run historical backtests |
| Web Backend | `app/backend/main.py` | FastAPI REST API |
| Web Frontend | `app/frontend/src/main.tsx` | React web interface |

## Data Flow

```
Tickers + Dates
    ↓
[Analyst Agents] → Fetch data → Analyze → LLM → Signal
    ↓
[Risk Manager] → Volatility + Correlation → Position Limits
    ↓
[Portfolio Manager] → Aggregate Signals → LLM → Trading Decisions
    ↓
Output / Execution
```

## Key Files

| File | Purpose |
|------|---------|
| `src/main.py` | CLI entry, workflow construction |
| `src/backtester.py` | Backtest entry point |
| `src/graph/state.py` | AgentState definition (shared state) |
| `src/utils/analysts.py` | Agent registry (ANALYST_CONFIG) |
| `src/agents/portfolio_manager.py` | Final decision maker |
| `src/agents/risk_manager.py` | Position sizing & risk limits |
| `src/tools/api.py` | Financial data fetching |
| `src/backtesting/engine.py` | Backtest orchestrator |
| `app/backend/services/graph.py` | Web app graph construction |

## Agent Types

**Analyst Agents** (18 total):
- Value: Warren Buffett, Ben Graham, Charlie Munger, Michael Burry, Mohnish Pabrai
- Growth: Cathie Wood, Peter Lynch, Phil Fisher
- Macro: Stanley Druckenmiller, Rakesh Jhunjhunwala
- Technical: Technical Analyst, Fundamentals Analyst, Growth Analyst
- Sentiment: News Sentiment, Sentiment Analyst
- Valuation: Aswath Damodaran, Valuation Analyst

**System Agents** (always present):
- Risk Manager: Sets position limits
- Portfolio Manager: Makes final decisions

## Extension Points

### 1. Add Custom Strategy
```python
# 1. Create src/agents/my_strategy.py
def my_strategy_agent(state: AgentState, agent_id: str = "my_strategy_agent"):
    # Your logic here
    return {"messages": [...], "data": state["data"]}

# 2. Register in src/utils/analysts.py
ANALYST_CONFIG["my_strategy"] = {
    "display_name": "My Strategy",
    "agent_func": my_strategy_agent,
    # ...
}
```

### 2. Add Data Source
```python
# In src/tools/api.py
def get_my_data(ticker: str, start_date: str, end_date: str):
    # Fetch and return data
    pass
```

### 3. Add Backtest Hook
```python
# Create src/backtesting/hooks.py
class MyHook:
    def on_day_end(self, date, portfolio_value):
        # Your logic
        pass

# In BacktestEngine.__init__
self._hooks = [MyHook()]
```

## Execution Commands

```bash
# CLI Hedge Fund
poetry run python src/main.py --ticker AAPL,MSFT,NVDA

# CLI Backtest
poetry run python src/backtester.py --ticker AAPL,MSFT,NVDA

# Web App (from app/ directory)
./run.sh
```

## Dependencies

- Python 3.11+
- Poetry
- Node.js & npm (for web app)
- At least one LLM API key (OpenAI, Anthropic, Groq, etc.)

## Configuration

- `.env` file in root directory
- Required: At least one LLM API key
- Optional: `FINANCIAL_DATASETS_API_KEY` (needed for tickers beyond AAPL, GOOGL, MSFT, NVDA, TSLA)

## Architecture Pattern

- **Agent Pattern**: Each agent is a function that takes `AgentState` and returns updated state
- **Workflow Pattern**: LangGraph StateGraph orchestrates execution
- **Data Flow**: Immutable state updates via merge functions
- **Separation**: Agents are independent, communicate via shared state

## State Structure

```python
AgentState = {
    "messages": [BaseMessage, ...],  # LangChain message history
    "data": {
        "tickers": ["AAPL", ...],
        "portfolio": {...},
        "start_date": "2024-01-01",
        "end_date": "2024-03-01",
        "analyst_signals": {
            "warren_buffett_agent": {
                "AAPL": {"signal": "bullish", "confidence": 85, ...}
            }
        }
    },
    "metadata": {
        "model_name": "gpt-4o",
        "model_provider": "OpenAI",
        "show_reasoning": False
    }
}
```

