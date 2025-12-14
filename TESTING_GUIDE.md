# Testing Guide for AI Hedge Fund

This guide covers all the ways to test your hedge fund system, from quick smoke tests to comprehensive backtests.

## Table of Contents
1. [Quick Tests](#quick-tests)
2. [Deterministic Backtests](#deterministic-backtests)
3. [Unit & Integration Tests](#unit--integration-tests)
4. [Full Backtest Suite](#full-backtest-suite)
5. [Web UI Testing](#web-ui-testing)
6. [Validation & Verification](#validation--verification)

---

## Quick Tests

### 1. Compile Check
Verify all Python files compile without errors:

```bash
cd /Users/cristianruizjr/moneymaker/ai-hedge-fund
HEDGEFUND_NO_LLM=1 poetry run python -m compileall src
```

**Expected:** No errors

### 2. Single Ticker Test
Test the main pipeline with a single ticker:

```bash
HEDGEFUND_NO_LLM=1 poetry run python src/main.py \
  --ticker AAPL \
  --analysts warren_buffett,peter_lynch,aswath_damodaran,momentum,mean_reversion,market_regime
```

**Expected:** Trading decisions output without errors

### 3. Quick Backtest (2 months)
Run a short backtest to verify everything works:

```bash
HEDGEFUND_NO_LLM=1 poetry run python src/backtesting/deterministic_backtest.py \
  --tickers AAPL,MSFT \
  --start-date 2024-01-02 \
  --end-date 2024-02-29 \
  --initial-capital 100000
```

**Expected:** Performance metrics and agent attribution output

---

## Deterministic Backtests

### Basic Usage

Run a backtest over any date range:

```bash
HEDGEFUND_NO_LLM=1 poetry run python src/backtesting/deterministic_backtest.py \
  --tickers AAPL,MSFT,GOOGL \
  --start-date 2024-01-01 \
  --end-date 2024-12-31 \
  --initial-capital 100000
```

### Command Line Arguments

- `--tickers TICKER1,TICKER2,...`: Comma-separated list of tickers (required)
- `--start-date YYYY-MM-DD`: Backtest start date (required)
- `--end-date YYYY-MM-DD`: Backtest end date (required)
- `--initial-capital AMOUNT`: Starting capital in USD (default: 100000)
- `--margin-requirement FLOAT`: Margin requirement for shorting, 0.0-1.0 (default: 0.0)

### Example Backtest Scenarios

#### Short-term test (2 months)
```bash
HEDGEFUND_NO_LLM=1 poetry run python src/backtesting/deterministic_backtest.py \
  --tickers AAPL,MSFT \
  --start-date 2024-01-02 \
  --end-date 2024-02-29 \
  --initial-capital 100000
```

#### Medium-term test (6 months)
```bash
HEDGEFUND_NO_LLM=1 poetry run python src/backtesting/deterministic_backtest.py \
  --tickers AAPL,MSFT,GOOGL,TSLA \
  --start-date 2024-01-01 \
  --end-date 2024-06-30 \
  --initial-capital 500000
```

#### Long-term test (1 year)
```bash
HEDGEFUND_NO_LLM=1 poetry run python src/backtesting/deterministic_backtest.py \
  --tickers AAPL,MSFT,GOOGL,TSLA,NVDA \
  --start-date 2023-01-01 \
  --end-date 2023-12-31 \
  --initial-capital 1000000
```

#### Single ticker deep dive
```bash
HEDGEFUND_NO_LLM=1 poetry run python src/backtesting/deterministic_backtest.py \
  --tickers AAPL \
  --start-date 2024-01-02 \
  --end-date 2024-12-31 \
  --initial-capital 50000
```

### Backtest Output

The backtest provides:

1. **Performance Metrics**:
   - Final Portfolio Value
   - Cumulative PnL
   - Total Return (%)
   - Max Drawdown (%)
   - Max Drawdown Date
   - Sharpe Ratio
   - Win Rate (%)
   - Total Trades

2. **Agent Contributions**:
   - PnL by agent (Value, Growth, Valuation, Momentum, Mean Reversion)
   - PnL percentage contribution
   - Trade count per agent

3. **Trade Log**:
   - Daily trading decisions
   - Position changes
   - PnL per trade

---

## Unit & Integration Tests

### Run All Tests

```bash
cd /Users/cristianruizjr/moneymaker/ai-hedge-fund
poetry run pytest tests/ -v
```

### Run Specific Test Suites

#### Backtesting Tests
```bash
poetry run pytest tests/backtesting/ -v
```

#### Integration Tests
```bash
poetry run pytest tests/backtesting/integration/ -v
```

#### Individual Test Files
```bash
# Peter Lynch functions test
poetry run pytest tests/test_peter_lynch_functions.py -v

# Deterministic backtest agent keys test
poetry run pytest tests/test_deterministic_backtest_agent_keys.py -v

# API rate limiting test
poetry run pytest tests/test_api_rate_limiting.py -v
```

### Run Tests Directly (without pytest)

```bash
poetry run python tests/test_peter_lynch_functions.py
poetry run python tests/test_deterministic_backtest_agent_keys.py
```

---

## Full Backtest Suite

### Using the Backtester Script

The main backtester script provides more options:

```bash
poetry run python src/backtester.py --ticker AAPL,MSFT,NVDA
```

With date range:
```bash
poetry run python src/backtester.py \
  --ticker AAPL,MSFT,NVDA \
  --start-date 2024-01-01 \
  --end-date 2024-03-01
```

With Ollama (local LLMs):
```bash
poetry run python src/backtester.py \
  --ticker AAPL,MSFT,NVDA \
  --ollama
```

### Compare Different Strategies

Compare your hedge fund against baseline strategies:

```bash
HEDGEFUND_NO_LLM=1 poetry run python src/compare_backtests.py \
  --tickers AAPL,MSFT \
  --start-date 2024-01-01 \
  --end-date 2024-06-30 \
  --initial-capital 100000
```

---

## Web UI Testing

### Start the Web Application

1. **Start Backend**:
```bash
cd /Users/cristianruizjr/moneymaker/ai-hedge-fund/app/backend
poetry run uvicorn main:app --reload
```

2. **Start Frontend** (in another terminal):
```bash
cd /Users/cristianruizjr/moneymaker/ai-hedge-fund/app/frontend
npm run dev
```

3. **Access the UI**: Open `http://localhost:5173` in your browser

### Run Backtests via Web UI

1. Create a new flow in the left sidebar
2. Add nodes: Portfolio Input → Analyst Agents → Portfolio Manager
3. Configure tickers and date range
4. Click "Run" to execute
5. View results in the bottom panel

---

## Validation & Verification

### Full Verification Suite

Run the complete verification suite:

```bash
cd /Users/cristianruizjr/moneymaker/ai-hedge-fund

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

# 4. Unit tests
poetry run pytest tests/ -v
```

### Validation Suite

Run the validation suite for comprehensive testing:

```bash
HEDGEFUND_NO_LLM=1 poetry run python src/backtesting/validation_suite.py
```

---

## Testing Best Practices

### 1. Start Small
- Begin with single ticker tests
- Use short date ranges (1-2 months)
- Verify results before scaling up

### 2. Use Deterministic Mode
- Always use `HEDGEFUND_NO_LLM=1` for consistent results
- Ensures reproducibility across runs

### 3. Test Different Market Conditions
- Bull markets (2020-2021)
- Bear markets (2022)
- Volatile periods (2020 Q1)
- Calm periods (2017)

### 4. Monitor Key Metrics
- Total Return
- Sharpe Ratio
- Max Drawdown
- Win Rate
- Agent Contributions

### 5. Compare Against Baselines
- Buy & Hold
- Equal Weight
- Market Cap Weighted
- Your hedge fund strategy

---

## Troubleshooting

### Common Issues

1. **Import Errors**
   ```bash
   poetry install  # Reinstall dependencies
   ```

2. **API Rate Limiting**
   - Use `HEDGEFUND_NO_LLM=1` for deterministic mode
   - Check `.env` file for API keys

3. **Date Range Issues**
   - Ensure dates are valid business days
   - Check that data exists for the date range

4. **Memory Issues**
   - Reduce number of tickers
   - Use shorter date ranges
   - Process in batches

---

## Quick Reference

### Most Common Test Commands

```bash
# Quick compile check
HEDGEFUND_NO_LLM=1 poetry run python -m compileall src

# Quick single ticker test
HEDGEFUND_NO_LLM=1 poetry run python src/main.py --ticker AAPL

# Quick backtest
HEDGEFUND_NO_LLM=1 poetry run python src/backtesting/deterministic_backtest.py \
  --tickers AAPL,MSFT \
  --start-date 2024-01-02 \
  --end-date 2024-02-29 \
  --initial-capital 100000

# Run all tests
poetry run pytest tests/ -v
```

---

## Next Steps

After running tests:

1. **Analyze Results**: Review performance metrics and agent contributions
2. **Compare Strategies**: Use `compare_backtests.py` to benchmark
3. **Optimize**: Adjust agent weights, risk parameters, or strategies
4. **Document**: Record findings and insights
5. **Iterate**: Run more tests with different configurations

For more details, see:
- `RUNBOOK.md` - Detailed operational guide
- `DETERMINISTIC_BACKTEST_USAGE.md` - Backtest documentation
- `README.md` - General project information
