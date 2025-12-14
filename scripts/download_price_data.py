#!/usr/bin/env python3
"""
Helper script to download historical price data and save as CSV.

Usage:
    poetry run python scripts/download_price_data.py AAPL MSFT GOOGL --start-date 2020-01-01 --end-date 2024-12-31

Requires: yfinance library
    poetry add yfinance
"""

import sys
import argparse
from pathlib import Path
import pandas as pd

try:
    import yfinance as yf
except ImportError:
    print("Error: yfinance not installed. Run: poetry add yfinance")
    sys.exit(1)


def download_and_save(ticker: str, start_date: str, end_date: str, output_dir: Path):
    """Download historical data and save as CSV."""
    print(f"Downloading {ticker} from {start_date} to {end_date}...")
    
    try:
        # Download data
        data = yf.download(ticker, start=start_date, end=end_date, progress=False)
        
        if data.empty:
            print(f"  ⚠️  Warning: No data returned for {ticker}")
            return False
        
        # Rename columns to lowercase
        if isinstance(data.columns, pd.MultiIndex):
            # Handle MultiIndex columns (Open, High, Low, Close, Volume, Adj Close)
            data.columns = [col[0].lower() if col[0] else col[1].lower() for col in data.columns]
        else:
            data.columns = [col.lower() for col in data.columns]
        
        # Reset index to get date as column
        data.reset_index(inplace=True)
        if "Date" in data.columns:
            data.rename(columns={"Date": "date"}, inplace=True)
        elif data.index.name == "Date":
            data.reset_index(inplace=True)
            data.rename(columns={data.columns[0]: "date"}, inplace=True)
        
        # Select required columns (drop adj close if present)
        required_cols = ["date", "open", "high", "low", "close", "volume"]
        available_cols = [col for col in required_cols if col in data.columns]
        
        if len(available_cols) < len(required_cols):
            missing = set(required_cols) - set(available_cols)
            print(f"  ⚠️  Warning: Missing columns for {ticker}: {missing}")
            print(f"  Available columns: {list(data.columns)}")
            return False
        
        data = data[required_cols]
        
        # Ensure date is datetime
        data["date"] = pd.to_datetime(data["date"])
        data["date"] = data["date"].dt.strftime("%Y-%m-%d")
        
        # Save to CSV
        output_path = output_dir / f"{ticker.upper()}.csv"
        data.to_csv(output_path, index=False)
        
        print(f"  ✅ Saved {len(data)} rows to {output_path}")
        print(f"     Date range: {data['date'].iloc[0]} to {data['date'].iloc[-1]}")
        return True
        
    except Exception as e:
        print(f"  ❌ Error downloading {ticker}: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Download historical price data and save as CSV"
    )
    parser.add_argument(
        "tickers",
        nargs="+",
        help="Ticker symbols (e.g., AAPL MSFT GOOGL)",
    )
    parser.add_argument(
        "--start-date",
        default="2020-01-01",
        help="Start date (YYYY-MM-DD, default: 2020-01-01)",
    )
    parser.add_argument(
        "--end-date",
        default="2024-12-31",
        help="End date (YYYY-MM-DD, default: 2024-12-31)",
    )
    parser.add_argument(
        "--output-dir",
        default="src/data/prices",
        help="Output directory (default: src/data/prices)",
    )
    
    args = parser.parse_args()
    
    # Create output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"Downloading price data to {output_dir}")
    print("=" * 80)
    
    success_count = 0
    for ticker in args.tickers:
        if download_and_save(ticker, args.start_date, args.end_date, output_dir):
            success_count += 1
    
    print("=" * 80)
    print(f"Completed: {success_count}/{len(args.tickers)} tickers downloaded")
    
    if success_count < len(args.tickers):
        sys.exit(1)


if __name__ == "__main__":
    main()
