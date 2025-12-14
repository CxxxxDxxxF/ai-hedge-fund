# Deterministic Backtest Runner

## Overview

The deterministic backtest runner executes the 5-core-agent system in rule-based mode (no LLMs) to simulate trading decisions over a historical period.

## Features

- **Deterministic**: Uses only rule-based logic (`HEDGEFUND_NO_LLM=1`)
- **Daily Simulation**: Runs trading decisions for each business day
- **Performance Metrics**: Tracks cumulative PnL, max drawdown, Sharpe ratio, win rate
- **Agent Contributions**: Shows PnL and trade count by agent (Value, Growth, Valuation, Momentum, Mean Reversion)

## Usage

### Basic Command

```bash
python src/backtesting/deterministic_backtest.py \
  --tickers AAPL,MSFT,GOOGL \
  --start-date 2024-01-01 \
  --end-date 2024-12-31 \
  --initial-capital 100000
```

### Full Options

```bash
python src/backtesting/deterministic_backtest.py \
  --tickers AAPL,MSFT,GOOGL \
  --start-date 2024-01-01 \
  --end-date 2024-12-31 \
  --initial-capital 100000 \
  --margin-requirement 0.5
```

### Arguments

- `--tickers`: Comma-separated list of tickers (required)
- `--start-date`: Start date in YYYY-MM-DD format (required)
- `--end-date`: End date in YYYY-MM-DD format (required)
- `--initial-capital`: Starting capital in USD (default: 100000)
- `--margin-requirement`: Margin requirement for shorting, 0.0-1.0 (default: 0.0)

## Output

The backtest outputs a summary table with:

### Performance Metrics
- Final Portfolio Value
- Cumulative PnL
- Total Return (%)
- Max Drawdown (%)
- Max Drawdown Date
- Sharpe Ratio
- Win Rate (%)
- Total Trades

### Agent Contributions
- PnL by agent (Value, Growth, Valuation, Momentum, Mean Reversion)
- PnL percentage contribution
- Trade count per agent

## Example Output

```
================================================================================
DETERMINISTIC BACKTEST SUMMARY
================================================================================

Period: 2024-01-01 to 2024-12-31
Tickers: AAPL, MSFT, GOOGL
Initial Capital: $100,000.00

--------------------------------------------------------------------------------
PERFORMANCE METRICS
--------------------------------------------------------------------------------
Final Portfolio Value: $115,234.56
Cumulative PnL: $15,234.56
Total Return: 15.23%
Max Drawdown: -8.45%
Max Drawdown Date: 2024-03-15
Sharpe Ratio: 1.23
Win Rate: 58.5%
Total Trades: 127

--------------------------------------------------------------------------------
AGENT CONTRIBUTIONS
--------------------------------------------------------------------------------
Agent                PnL            PnL %      Trades    
--------------------------------------------------------------------------------
Value                $5,234.56     34.4%      42        
Growth               $4,123.45     27.1%      38        
Valuation            $3,456.78     22.7%      25        
Momentum             $1,890.12     12.4%      15        
Mean Reversion       $529.65       3.5%       7        
================================================================================
```

## Notes

- The backtest uses a 30-day lookback window for agent analysis
- Prices are fetched from the Financial Datasets API (cached)
- All trading decisions are deterministic (no LLM calls)
- Portfolio state is maintained between days
- Trades are executed at closing prices for each day

## Requirements

- `HEDGEFUND_NO_LLM=1` is automatically set
- Requires `FINANCIAL_DATASETS_API_KEY` environment variable
- All 5 core agents must be available (warren_buffett, peter_lynch, aswath_damodaran, momentum, mean_reversion)
