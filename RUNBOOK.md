# Hedge Fund Runbook

## Prerequisites

This project requires **Poetry** for dependency management. Install Poetry if you haven't already:

```bash
curl -sSL https://install.python-poetry.org | python3 -
```

Then install dependencies:

```bash
cd ai-hedge-fund
poetry install
```

## Environment Setup

Set the deterministic mode environment variable to disable LLM calls:

```bash
export HEDGEFUND_NO_LLM=1
```

Or use it inline with commands:

```bash
HEDGEFUND_NO_LLM=1 poetry run python src/main.py ...
```

## Running the Main Pipeline

### Basic Usage

Run the hedge fund with a single ticker and selected analysts:

```bash
HEDGEFUND_NO_LLM=1 poetry run python src/main.py \
  --ticker AAPL \
  --analysts warren_buffett,peter_lynch,aswath_damodaran,momentum,mean_reversion,market_regime
```

### Command Line Arguments

- `--ticker TICKER`: Single ticker symbol (e.g., `AAPL`, `MSFT`)
- `--tickers TICKER1,TICKER2,...`: Multiple tickers (comma-separated)
- `--analysts ANALYST1,ANALYST2,...`: Comma-separated list of analyst keys
- `--start-date YYYY-MM-DD`: Start date for analysis (optional)
- `--end-date YYYY-MM-DD`: End date for analysis (optional)

### Available Analysts

#### Core Signal Generators (with weights)

1. **warren_buffett** (Weight: 0.30)
   - Value Composite Analyst
   - Combines: Valuation margin of safety, Business quality, Balance sheet strength, Earnings quality, Conservative growth

2. **peter_lynch** (Weight: 0.25)
   - Growth Composite Analyst
   - Combines: Revenue growth, Earnings growth, PEG-style valuation, Business simplicity

3. **aswath_damodaran** (Weight: 0.20)
   - Valuation Analyst
   - Intrinsic value analysis, Growth projections, Margin of safety

4. **momentum** (Weight: 0.15)
   - Momentum Analyst
   - Price momentum, Volume trends, Technical indicators

5. **mean_reversion** (Weight: 0.10)
   - Mean Reversion Analyst
   - Overbought/oversold conditions, Reversion signals

#### Advisory Agents (no trade direction)

6. **market_regime** (Advisory only)
   - Market Regime Classifier
   - Classifies market conditions (trending, mean-reverting, volatile, calm)
   - Provides risk multipliers and strategy weight recommendations

7. **performance_auditor** (Advisory only)
   - Performance Auditor
   - Tracks agent credibility scores
   - Provides historical performance metrics

### Example: Full Pipeline Run

```bash
# Single ticker with all core analysts
HEDGEFUND_NO_LLM=1 poetry run python src/main.py \
  --ticker AAPL \
  --analysts warren_buffett,peter_lynch,aswath_damodaran,momentum,mean_reversion,market_regime

# Multiple tickers
HEDGEFUND_NO_LLM=1 poetry run python src/main.py \
  --tickers AAPL,MSFT,GOOGL \
  --analysts warren_buffett,peter_lynch,aswath_damodaran,momentum,mean_reversion

# With date range
HEDGEFUND_NO_LLM=1 poetry run python src/main.py \
  --ticker AAPL \
  --start-date 2024-01-01 \
  --end-date 2024-12-31 \
  --analysts warren_buffett,peter_lynch,aswath_damodaran,momentum,mean_reversion,market_regime
```

### Output

The main pipeline outputs:
- **Trading Decisions**: Buy/sell/hold recommendations with position sizes
- **Market Regime**: Current market classification and risk multipliers
- **Risk Budget**: Position sizing based on volatility and regime
- **Portfolio Allocation**: Adjusted positions after applying constraints

---

## Running Deterministic Backtests

### Basic Usage

Run a backtest over a date range:

```bash
HEDGEFUND_NO_LLM=1 poetry run python src/backtesting/deterministic_backtest.py \
  --tickers AAPL,MSFT \
  --start-date 2024-01-02 \
  --end-date 2024-02-29 \
  --initial-capital 100000
```

### Command Line Arguments

- `--tickers TICKER1,TICKER2,...`: Comma-separated list of tickers to backtest
- `--start-date YYYY-MM-DD`: Backtest start date (required)
- `--end-date YYYY-MM-DD`: Backtest end date (required)
- `--initial-capital AMOUNT`: Starting capital in USD (default: 100000)

### Example Backtest Runs

```bash
# Short window (2 months)
HEDGEFUND_NO_LLM=1 poetry run python src/backtesting/deterministic_backtest.py \
  --tickers AAPL,MSFT \
  --start-date 2024-01-02 \
  --end-date 2024-02-29 \
  --initial-capital 100000

# Longer window (1 year)
HEDGEFUND_NO_LLM=1 poetry run python src/backtesting/deterministic_backtest.py \
  --tickers AAPL,MSFT,GOOGL,TSLA \
  --start-date 2023-01-01 \
  --end-date 2023-12-31 \
  --initial-capital 1000000

# Single ticker
HEDGEFUND_NO_LLM=1 poetry run python src/backtesting/deterministic_backtest.py \
  --tickers AAPL \
  --start-date 2024-01-02 \
  --end-date 2024-06-30 \
  --initial-capital 50000
```

### Backtest Output

The backtest provides:

1. **Performance Metrics**:
   - Cumulative PnL
   - Total Return %
   - Max Drawdown
   - Sharpe Ratio
   - Win Rate

2. **Agent Attribution**:
   - PnL contribution by agent (Value, Growth, Valuation, Momentum, Mean Reversion)
   - Trade count per agent
   - PnL percentage per agent

3. **Trade Log**:
   - Daily trading decisions
   - Position changes
   - PnL per trade

---

## Verification & Testing

### Compile Check

Verify all Python files compile without errors:

```bash
HEDGEFUND_NO_LLM=1 poetry run python -m compileall src
```

Expected: No errors

### Regression Tests

Run regression tests:

```bash
poetry run pytest tests/test_peter_lynch_functions.py
poetry run pytest tests/test_deterministic_backtest_agent_keys.py
```

Or run directly:

```bash
poetry run python tests/test_peter_lynch_functions.py
poetry run python tests/test_deterministic_backtest_agent_keys.py
```

### Full Verification

Run the complete verification suite:

```bash
# 1. Compile check
HEDGEFUND_NO_LLM=1 poetry run python -m compileall src

# 2. Main pipeline test
HEDGEFUND_NO_LLM=1 poetry run python src/main.py \
  --ticker AAPL \
  --analysts warren_buffett,peter_lynch,aswath_damodaran,momentum,mean_reversion,market_regime

# 3. Backtest test
HEDGEFUND_NO_LLM=1 poetry run python src/backtesting/deterministic_backtest.py \
  --tickers AAPL,MSFT \
  --start-date 2024-01-02 \
  --end-date 2024-02-29 \
  --initial-capital 100000
```

**Acceptance Criteria:**
- ✓ Zero compile errors
- ✓ No IndentationError
- ✓ No NoneType formatting errors
- ✓ No warnings referencing `*_agent` key mismatches
- ✓ Backtest prints agent attribution for: Value, Growth, Valuation, Momentum, Mean Reversion

---

## Architecture

### Agent Execution Flow

```
Core Analysts → Market Regime (optional) → Performance Auditor → 
Portfolio Manager → Risk Budget → Portfolio Allocator → END
```

### Core Analysts (Signal Generators)

1. **warren_buffett_agent**: Value Composite
2. **peter_lynch_agent**: Growth Composite
3. **aswath_damodaran_agent**: Valuation
4. **momentum_agent**: Momentum
5. **mean_reversion_agent**: Mean Reversion

### Meta-Agents

- **market_regime_agent**: Advisory only (no trade direction)
- **performance_auditor_agent**: Advisory only (credibility scores)
- **portfolio_manager_agent**: Aggregates signals, makes trading decisions
- **risk_budget_agent**: Calculates position sizes based on risk
- **portfolio_allocator_agent**: Applies portfolio-level constraints

### State Management

All agents read from and write to `AgentState`:
- `state["data"]["analyst_signals"]`: Signals from core analysts
- `state["data"]["portfolio_decisions"]`: Portfolio Manager decisions
- `state["data"]["risk_budget"]`: Risk Budget allocations
- `state["data"]["portfolio_allocation"]`: Final allocated positions
- `state["data"]["agent_credibility"]`: Performance Auditor scores
- `state["data"]["market_regime"]`: Market Regime classification

---

## Troubleshooting

### ModuleNotFoundError

If you see `ModuleNotFoundError`, ensure dependencies are installed:

```bash
poetry install
```

### IndentationError

If you see `IndentationError`, run the regression test:

```bash
poetry run python tests/test_peter_lynch_functions.py
```

### Agent Key Warnings

If you see warnings about `*_agent` keys, verify canonical keys:

```bash
poetry run python tests/test_deterministic_backtest_agent_keys.py
```

### NoneType Formatting Errors

If you see `TypeError: unsupported format string passed to NoneType.__format__`:
- This should be fixed in `aswath_damodaran.py` with None guards
- Check that the fix is applied: `grep -n "score is None" src/agents/aswath_damodaran.py`

### Missing Price Data

If backtest fails with missing price data:
- Ensure date range is valid (trading days only)
- Check that tickers are valid symbols
- Verify API access for price data

---

## Version

Current version: **v0.1-deterministic-core**

This version includes:
- 5 core deterministic analysts
- Deterministic backtest runner
- Risk budget and portfolio allocation agents
- Regression tests for code quality
