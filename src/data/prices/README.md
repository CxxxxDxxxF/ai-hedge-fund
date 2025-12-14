# Historical Price Data

This directory contains CSV files with historical price data for deterministic backtesting.

## File Format

Each ticker has its own CSV file: `{TICKER}.csv`

**Required columns:**
- `date`: Date in YYYY-MM-DD format
- `open`: Opening price
- `high`: High price
- `low`: Low price
- `close`: Closing price (used for backtesting)
- `volume`: Trading volume

**Example (`AAPL.csv`):**
```csv
date,open,high,low,close,volume
2024-01-02,185.50,186.20,184.80,185.14,50000000
2024-01-03,185.20,186.00,184.90,185.59,48000000
2024-01-04,185.80,186.50,185.30,186.19,52000000
```

## Data Sources

You can obtain historical price data from:
- Yahoo Finance (`yfinance` library)
- Alpha Vantage
- Financial Modeling Prep
- Your broker's historical data API

## Generating CSV Files

Example using `yfinance`:

```python
import yfinance as yf
import pandas as pd

ticker = "AAPL"
start_date = "2020-01-01"
end_date = "2024-12-31"

# Download data
data = yf.download(ticker, start=start_date, end=end_date)

# Rename columns to lowercase
data.columns = [col.lower() for col in data.columns]

# Reset index to get date as column
data.reset_index(inplace=True)
data.rename(columns={"Date": "date"}, inplace=True)

# Select required columns
data = data[["date", "open", "high", "low", "close", "volume"]]

# Save to CSV
data.to_csv(f"src/data/prices/{ticker}.csv", index=False)
```

## Requirements

- Files must exist before running deterministic backtests
- Date range must cover all dates in your backtest period
- Missing data will cause backtest to fail loudly (no silent fallbacks)

## Notes

- Data is cached in memory after first load (fast lookups)
- Non-trading days: System uses nearest previous trading day's price
- If date is missing and no earlier date available, backtest fails
