# AI Hedge Fund - Architecture Analysis & Extension Plan

## A. Architecture Overview

### Project Structure

```
ai-hedge-fund/
├── src/                          # Core trading system (CLI-based)
│   ├── main.py                   # Entry point for CLI hedge fund execution
│   ├── backtester.py             # Entry point for backtesting
│   ├── agents/                   # Trading agent implementations (18 agents)
│   │   ├── portfolio_manager.py  # Final decision maker
│   │   ├── risk_manager.py       # Position sizing & risk limits
│   │   ├── warren_buffett.py     # Value investing agent
│   │   ├── [15 other analyst agents]
│   ├── backtesting/              # Backtesting engine
│   │   ├── engine.py             # Main backtest orchestrator
│   │   ├── controller.py          # Agent invocation wrapper
│   │   ├── portfolio.py          # Portfolio state management
│   │   ├── trader.py              # Trade execution
│   │   ├── metrics.py             # Performance calculations
│   │   └── valuation.py          # Portfolio valuation
│   ├── graph/                    # LangGraph workflow state
│   │   └── state.py               # AgentState definition
│   ├── tools/                    # Data fetching utilities
│   │   └── api.py                 # Financial data API client
│   ├── data/                     # Data models & caching
│   │   ├── models.py              # Pydantic data models
│   │   └── cache.py               # In-memory API cache
│   ├── llm/                      # LLM provider configuration
│   │   ├── models.py              # Model registry & factory
│   │   ├── api_models.json        # Cloud LLM configs
│   │   └── ollama_models.json      # Local LLM configs
│   └── utils/                     # Helper utilities
│       ├── analysts.py            # Agent configuration registry
│       ├── llm.py                 # LLM invocation wrapper
│       └── display.py              # Output formatting
│
├── app/                          # Web application (full-stack)
│   ├── backend/                  # FastAPI backend
│   │   ├── main.py                # FastAPI app entry point
│   │   ├── routes/                # API endpoints
│   │   │   ├── hedge_fund.py      # Trading execution endpoint
│   │   │   ├── flows.py            # Flow management
│   │   │   └── [other routes]
│   │   ├── services/              # Business logic
│   │   │   ├── graph.py            # Graph construction from UI
│   │   │   ├── agent_service.py    # Agent wrapper for web
│   │   │   └── backtest_service.py # Backtest orchestration
│   │   ├── database/              # SQLAlchemy models
│   │   │   ├── models.py           # Database schema
│   │   │   └── connection.py       # DB connection
│   │   └── repositories/           # Data access layer
│   └── frontend/                 # React/Vite frontend
│       └── src/
│           ├── components/         # React components
│           ├── nodes/              # Flow node definitions
│           ├── contexts/           # React contexts
│           └── services/           # API client services
│
├── tests/                        # Test suite
│   └── backtesting/              # Backtest integration tests
│
└── pyproject.toml               # Poetry dependencies
```

### Core Responsibilities

#### 1. **Trading Agents** (`src/agents/`)
- **18 Analyst Agents**: Each implements a specific investment philosophy
  - Value investors: Warren Buffett, Ben Graham, Charlie Munger, etc.
  - Growth investors: Cathie Wood, Peter Lynch, Phil Fisher
  - Contrarian: Michael Burry
  - Technical/Fundamental: Technical Analyst, Fundamentals Analyst
  - Sentiment: News Sentiment, Sentiment Analyst
- **Risk Manager** (`risk_manager.py`): 
  - Calculates volatility-adjusted position limits
  - Performs correlation analysis across positions
  - Sets maximum position sizes per ticker
- **Portfolio Manager** (`portfolio_manager.py`):
  - Aggregates analyst signals
  - Makes final trading decisions (buy/sell/short/cover/hold)
  - Respects risk limits and portfolio constraints

#### 2. **Workflow Engine** (`src/graph/`, `src/main.py`)
- Uses **LangGraph** to orchestrate agent execution
- **AgentState**: TypedDict containing:
  - `messages`: LangChain message history
  - `data`: Tickers, portfolio, dates, analyst signals
  - `metadata`: Model config, reasoning flags
- **Execution Flow**:
  1. Start node → Analyst agents (parallel)
  2. Analyst agents → Risk Manager
  3. Risk Manager → Portfolio Manager
  4. Portfolio Manager → END

#### 3. **Data Layer** (`src/tools/api.py`, `src/data/`)
- **API Client**: Fetches from `api.financialdatasets.ai`
  - Price data (OHLCV)
  - Financial metrics (ROE, margins, ratios)
  - Line items (revenue, expenses, cash flow)
  - Insider trades
  - Company news
- **Caching**: In-memory cache to avoid redundant API calls
- **Models**: Pydantic models for type safety

#### 4. **Backtesting Engine** (`src/backtesting/`)
- **BacktestEngine**: Orchestrates time-series simulation
- **Portfolio**: Tracks cash, positions, cost basis, realized gains
- **TradeExecutor**: Executes trades with margin support
- **PerformanceMetricsCalculator**: Computes Sharpe, Sortino, drawdown
- **BenchmarkCalculator**: Compares against SPY

#### 5. **Web Application** (`app/`)
- **Backend**: FastAPI REST API
  - Endpoints for running hedge fund, backtesting, flow management
  - SQLite database for persisting flows/runs
  - Graph construction from React Flow UI
- **Frontend**: React + TypeScript
  - Visual flow builder (drag-and-drop agents)
  - Real-time execution monitoring
  - Results visualization

---

## B. Execution Instructions

### Prerequisites
- Python 3.11+ (project requires `^3.11`)
- Poetry (dependency manager)
- Node.js & npm (for web app)
- API keys (at least one LLM provider)

### Installation

```bash
# 1. Clone repository
git clone https://github.com/virattt/ai-hedge-fund.git
cd ai-hedge-fund

# 2. Install Poetry (if not installed)
curl -sSL https://install.python-poetry.org | python3 -

# 3. Install Python dependencies
poetry install

# 4. Create .env file
cp .env.example .env
# Edit .env and add at least one LLM API key:
# OPENAI_API_KEY=your-key-here
# FINANCIAL_DATASETS_API_KEY=your-key-here  # Optional for AAPL, GOOGL, MSFT, NVDA, TSLA
```

### Running CLI Version

```bash
# Run hedge fund (interactive analyst selection)
poetry run python src/main.py --ticker AAPL,MSFT,NVDA

# Run with specific analysts
poetry run python src/main.py --ticker AAPL,MSFT,NVDA --analysts warren_buffett,michael_burry

# Run with date range
poetry run python src/main.py --ticker AAPL,MSFT,NVDA --start-date 2024-01-01 --end-date 2024-03-01

# Run with Ollama (local LLMs)
poetry run python src/main.py --ticker AAPL,MSFT,NVDA --ollama

# Run backtester
poetry run python src/backtester.py --ticker AAPL,MSFT,NVDA
```

### Running Web Application

```bash
# Option 1: Use convenience script (from app/ directory)
cd app
./run.sh  # Mac/Linux
# or
run.bat   # Windows

# Option 2: Manual setup
# Terminal 1: Backend
cd app/backend
poetry run uvicorn main:app --reload

# Terminal 2: Frontend
cd app/frontend
npm install
npm run dev

# Access:
# - Frontend: http://localhost:5173
# - Backend API: http://localhost:8000
# - API Docs: http://localhost:8000/docs
```

---

## C. Verified Runtime Behavior

### CLI Execution Flow

1. **Input Parsing** (`src/cli/input.py`):
   - Parses tickers, dates, analyst selection
   - Interactive prompts for model/analyst selection
   - Validates date formats

2. **Workflow Construction** (`src/main.py::create_workflow`):
   - Builds LangGraph StateGraph
   - Adds selected analyst nodes
   - Always adds Risk Manager and Portfolio Manager
   - Connects: Start → Analysts → Risk → Portfolio → END

3. **Agent Execution**:
   - Each analyst agent:
     - Fetches relevant data (prices, metrics, news, etc.)
     - Performs analysis (fundamental, technical, sentiment)
     - Calls LLM with structured prompt
     - Returns signal: `{signal: "bullish"|"bearish"|"neutral", confidence: 0-100, reasoning: str}`
   - Risk Manager:
     - Calculates volatility for each ticker
     - Computes correlation matrix
     - Sets position limits (volatility + correlation adjusted)
   - Portfolio Manager:
     - Aggregates all analyst signals
     - Computes allowed actions (buy/sell/short/cover/hold) with max quantities
     - Calls LLM to make final decisions
     - Returns trading decisions per ticker

4. **Output** (`src/utils/display.py`):
   - Prints formatted trading decisions
   - Shows analyst signals summary
   - Optionally shows reasoning from each agent

### Backtesting Execution Flow

1. **Initialization** (`src/backtesting/engine.py`):
   - Creates Portfolio with initial cash
   - Prefetches data for all tickers (1 year lookback)

2. **Daily Loop** (for each business day):
   - Fetches current prices
   - Invokes hedge fund agent (same as CLI)
   - Executes trades via `TradeExecutor`
   - Updates portfolio (cash, positions, cost basis)
   - Calculates portfolio value
   - Computes exposures (long/short/gross/net)
   - Updates performance metrics (Sharpe, Sortino, drawdown)
   - Prints daily summary table

3. **Final Output**:
   - Performance metrics summary
   - Portfolio value over time
   - Benchmark comparison (SPY)

### Data Flow

```
User Input (tickers, dates)
    ↓
CLI Parser → Portfolio Initialization
    ↓
LangGraph Workflow
    ↓
┌─────────────────────────────────────┐
│ Analyst Agents (parallel)           │
│  ├─ Fetch data (api.py)            │
│  ├─ Analyze fundamentals/tech      │
│  ├─ Call LLM (llm.py)              │
│  └─ Return signal                   │
└─────────────────────────────────────┘
    ↓
Risk Manager
    ├─ Fetch prices
    ├─ Calculate volatility
    ├─ Compute correlations
    └─ Set position limits
    ↓
Portfolio Manager
    ├─ Aggregate signals
    ├─ Compute allowed actions
    ├─ Call LLM for decisions
    └─ Return trading decisions
    ↓
Output/Execution
```

---

## D. Identified Extension Points

### 1. **Custom Trading Strategies**

**Location**: `src/agents/`

**How to Add**:
- Create new agent file: `src/agents/my_strategy.py`
- Implement agent function:
  ```python
  def my_strategy_agent(state: AgentState, agent_id: str = "my_strategy_agent"):
      # Fetch data
      # Perform analysis
      # Call LLM
      # Return signal
      return {"messages": [...], "data": state["data"]}
  ```
- Register in `src/utils/analysts.py::ANALYST_CONFIG`:
  ```python
  "my_strategy": {
      "display_name": "My Strategy",
      "description": "...",
      "investing_style": "...",
      "agent_func": my_strategy_agent,
      "type": "analyst",
      "order": 17,
  }
  ```

**Files to Modify**:
- `src/agents/my_strategy.py` (new file)
- `src/utils/analysts.py` (add to ANALYST_CONFIG)
- `src/agents/__init__.py` (import new agent)

**What NOT to Touch**:
- `src/graph/state.py` (AgentState definition)
- `src/main.py::create_workflow` (workflow logic - unless adding new node types)
- `src/agents/portfolio_manager.py` (final decision logic)

---

### 2. **Alternative Data Sources**

**Location**: `src/tools/api.py`

**How to Add**:
- Add new fetch function:
  ```python
  def get_alternative_data(ticker: str, start_date: str, end_date: str, api_key: str = None):
      # Fetch from new data source
      # Parse response
      # Cache if needed
      return data
  ```
- Add to cache in `src/data/cache.py` if needed
- Use in agent:
  ```python
  from src.tools.api import get_alternative_data
  data = get_alternative_data(ticker, start_date, end_date, api_key)
  ```

**Files to Modify**:
- `src/tools/api.py` (add fetch function)
- `src/data/cache.py` (add cache methods if needed)
- `src/data/models.py` (add Pydantic models if needed)
- Agent files (use new data source)

**What NOT to Touch**:
- `src/data/models.py` (existing models - add new ones)
- `src/tools/api.py` (existing functions - add new ones)

---

### 3. **Modular Backtesting Hooks**

**Location**: `src/backtesting/`

**How to Add**:
- Create hook interface in `src/backtesting/hooks.py`:
  ```python
  class BacktestHook:
      def on_day_start(self, date: str, portfolio: Portfolio): pass
      def on_trade_executed(self, ticker: str, action: str, qty: int, price: float): pass
      def on_day_end(self, date: str, portfolio_value: float): pass
  ```
- Modify `BacktestEngine` to accept hooks:
  ```python
  def __init__(self, ..., hooks: list[BacktestHook] = None):
      self._hooks = hooks or []
  ```
- Call hooks at appropriate points in `run_backtest()`

**Files to Modify**:
- `src/backtesting/hooks.py` (new file - hook interface)
- `src/backtesting/engine.py` (add hook calls)
- Create hook implementations as needed

**What NOT to Touch**:
- `src/backtesting/portfolio.py` (portfolio state management)
- `src/backtesting/trader.py` (trade execution logic - unless adding new order types)
- `src/backtesting/metrics.py` (performance calculations)

---

### 4. **Custom Risk Models**

**Location**: `src/agents/risk_manager.py`

**How to Extend**:
- Add new risk calculation function:
  ```python
  def calculate_custom_risk_metric(prices_df: pd.DataFrame) -> float:
      # Custom risk calculation
      return risk_value
  ```
- Integrate into `risk_management_agent`:
  ```python
  custom_risk = calculate_custom_risk_metric(prices_df)
  # Use in position limit calculation
  ```

**Files to Modify**:
- `src/agents/risk_manager.py` (add functions, modify agent)

**What NOT to Touch**:
- `src/agents/portfolio_manager.py` (expects risk manager output format)
- `src/graph/state.py` (state structure)

---

### 5. **Custom Portfolio Constraints**

**Location**: `src/agents/portfolio_manager.py`

**How to Extend**:
- Modify `compute_allowed_actions()` to add constraints:
  ```python
  # Add sector limits, concentration limits, etc.
  if violates_constraint(ticker, action, qty):
      actions[action] = 0  # Disallow
  ```

**Files to Modify**:
- `src/agents/portfolio_manager.py` (add constraint logic)

**What NOT to Touch**:
- `src/backtesting/portfolio.py` (portfolio state - unless adding new fields)
- `src/backtesting/trader.py` (execution logic)

---

## E. Safe Extension Plan

### ✅ Safe to Modify

1. **Agent Implementations** (`src/agents/*.py`):
   - Add new agents
   - Modify agent logic (as long as signature matches)
   - Change prompts/analysis logic

2. **Data Fetching** (`src/tools/api.py`):
   - Add new data sources
   - Modify caching behavior
   - Add new API endpoints

3. **Backtesting Hooks** (`src/backtesting/`):
   - Add hook system (new file)
   - Extend metrics calculations
   - Add new output formats

4. **Configuration** (`src/utils/analysts.py`):
   - Add new agents to ANALYST_CONFIG
   - Modify agent metadata

5. **Web UI** (`app/frontend/`):
   - Add new UI components
   - Modify flow builder
   - Add new visualizations

### ⚠️ Modify with Caution

1. **AgentState** (`src/graph/state.py`):
   - Only add new fields if necessary
   - Maintain backward compatibility
   - All agents expect specific state structure

2. **Workflow Graph** (`src/main.py::create_workflow`):
   - Can add new node types
   - Must maintain: Start → Analysts → Risk → Portfolio → END flow
   - Web app (`app/backend/services/graph.py`) also constructs graphs

3. **Portfolio Manager** (`src/agents/portfolio_manager.py`):
   - Core decision logic
   - Output format must match expectations
   - Used by both CLI and backtester

4. **Portfolio State** (`src/backtesting/portfolio.py`):
   - Core state management
   - Trade execution depends on this
   - Only extend if adding new position types

### ❌ Do NOT Modify

1. **AgentState Structure** (`src/graph/state.py`):
   - Breaking changes will break all agents
   - If needed, use versioning or migration

2. **Core Workflow Logic** (`src/main.py::create_workflow`):
   - Risk Manager and Portfolio Manager must always be present
   - Execution order is critical

3. **Trade Execution** (`src/backtesting/trader.py`):
   - Core execution logic
   - Margin calculations are complex
   - Only modify if adding new order types

4. **Data Models** (`src/data/models.py`):
   - Pydantic models used throughout
   - Breaking changes affect API parsing
   - Add new models, don't modify existing ones

5. **Backend Database Schema** (`app/backend/database/models.py`):
   - Requires Alembic migrations
   - Breaking changes affect stored data

---

## Extension Implementation Checklist

### For Custom Strategies:
- [ ] Create agent file in `src/agents/`
- [ ] Implement agent function with correct signature
- [ ] Register in `ANALYST_CONFIG`
- [ ] Import in `src/agents/__init__.py`
- [ ] Test with CLI: `poetry run python src/main.py --ticker AAPL --analysts my_strategy`
- [ ] Verify signal format matches expectations

### For Alternative Data:
- [ ] Add fetch function to `src/tools/api.py`
- [ ] Add Pydantic models to `src/data/models.py` if needed
- [ ] Add cache methods to `src/data/cache.py` if needed
- [ ] Use in agent implementation
- [ ] Test data fetching and caching

### For Backtesting Hooks:
- [ ] Create `src/backtesting/hooks.py` with interface
- [ ] Modify `BacktestEngine.__init__` to accept hooks
- [ ] Add hook calls in `run_backtest()`
- [ ] Create example hook implementation
- [ ] Test with backtester

---

## Known Limitations & Runtime Considerations

1. **Python Version**: Requires Python 3.11+ (current system has 3.9.6)
   - Solution: Use pyenv or conda to install Python 3.11

2. **API Rate Limiting**: Financial Datasets API has rate limits
   - Solution: Caching is implemented, but may need to add delays

3. **LLM Costs**: Each agent makes LLM calls
   - Solution: Use local Ollama models for development

4. **Data Availability**: Free tier only supports AAPL, GOOGL, MSFT, NVDA, TSLA
   - Solution: Get API key for other tickers

5. **Backtesting Performance**: Daily loop can be slow for long periods
   - Solution: Consider parallelization or optimization

---

## Summary

This is a **well-architected multi-agent trading system** using:
- **LangGraph** for agent orchestration
- **LangChain** for LLM integration
- **Pydantic** for data validation
- **FastAPI** for web backend
- **React** for web frontend

**Key Strengths**:
- Modular agent design
- Clear separation of concerns
- Extensible architecture
- Both CLI and web interfaces

**Extension Readiness**:
- ✅ Easy to add new agents
- ✅ Easy to add new data sources
- ✅ Moderate effort to add backtesting hooks
- ⚠️ Requires care when modifying core workflow

The codebase is **production-ready for extension** with clear extension points and minimal coupling between components.

