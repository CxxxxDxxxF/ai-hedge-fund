"""
Local Historical Price Data Cache

Provides deterministic, file-based price data for backtesting.
No external API calls. Fails loudly if data is missing.
"""

from __future__ import annotations

import logging
import os
import pandas as pd
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class PriceCache:
    """
    In-memory cache for historical price data loaded from CSV files.
    
    CSV Format (src/data/prices/{TICKER}.csv):
        date,open,high,low,close,volume
        2024-01-02,185.50,186.20,184.80,185.14,50000000
        2024-01-03,185.20,186.00,184.90,185.59,48000000
        ...
    """
    
    def __init__(self, data_dir: Optional[str] = None):
        """
        Initialize price cache.
        
        Args:
            data_dir: Directory containing price CSV files (default: src/data/prices/)
        """
        if data_dir is None:
            # Default to src/data/prices/ relative to this file
            base_dir = Path(__file__).parent.parent.parent
            self.data_dir = base_dir / "src" / "data" / "prices"
        else:
            self.data_dir = Path(data_dir)
        
        # In-memory cache: {ticker: DataFrame}
        self._cache: Dict[str, pd.DataFrame] = {}
        self._loaded_tickers: set = set()
    
    def _load_ticker_csv(self, ticker: str) -> pd.DataFrame:
        """
        Load price data from CSV file for a ticker.
        
        Raises FileNotFoundError if CSV doesn't exist.
        Raises ValueError if CSV is malformed.
        """
        csv_path = self.data_dir / f"{ticker.upper()}.csv"
        
        if not csv_path.exists():
            raise FileNotFoundError(
                f"Price data file not found: {csv_path}\n"
                f"Expected CSV format: date,open,high,low,close,volume\n"
                f"To generate: Download historical data and save as {csv_path}"
            )
        
        try:
            # Parse dates flexibly - handle both date-only (YYYY-MM-DD) and datetime (YYYY-MM-DD HH:MM:SS)
            df = pd.read_csv(
                csv_path,
                parse_dates=["date"],
            )
            
            # Validate required columns
            required_cols = ["date", "open", "high", "low", "close", "volume"]
            missing_cols = [col for col in required_cols if col not in df.columns]
            if missing_cols:
                raise ValueError(
                    f"CSV file {csv_path} missing required columns: {missing_cols}\n"
                    f"Expected columns: {required_cols}"
                )
            
            # Set date as index
            df.set_index("date", inplace=True)
            df.sort_index(inplace=True)
            
            # Ensure numeric columns
            for col in ["open", "high", "low", "close", "volume"]:
                df[col] = pd.to_numeric(df[col], errors="coerce")
            
            # Optional: Validate data on load
            try:
                from src.data.validation import validate_price_data
                is_valid, errors = validate_price_data(df, ticker)
                if not is_valid:
                    logger.warning(
                        f"Price data validation issues for {ticker} in {csv_path}: {errors}"
                    )
                    # Continue loading even with validation issues (fail loudly on critical errors)
            except ImportError:
                # Validation module not available, skip
                pass
            except Exception as e:
                logger.debug(f"Validation check skipped for {ticker}: {e}")
            
            logger.debug(f"Loaded {len(df)} price records for {ticker} from {csv_path}")
            return df
            
        except pd.errors.EmptyDataError:
            raise ValueError(f"CSV file {csv_path} is empty")
        except Exception as e:
            raise ValueError(f"Failed to parse CSV file {csv_path}: {e}")
    
    def get(self, ticker: str, date: str) -> Optional[Dict]:
        """
        Get price data for a ticker on a specific date.
        Returns dict with price fields or None if missing.
        
        This method provides a dict interface compatible with the isolated backtest.
        
        Args:
            ticker: Stock ticker symbol (e.g., "AAPL")
            date: Date string in YYYY-MM-DD format
        
        Returns:
            Dict with "close", "open", "high", "low", "volume" keys, or None if not found
        """
        try:
            ticker_upper = ticker.upper()
            
            # Load ticker data if not cached
            if ticker_upper not in self._cache:
                self._cache[ticker_upper] = self._load_ticker_csv(ticker_upper)
                self._loaded_tickers.add(ticker_upper)
            
            df = self._cache[ticker_upper]
            
            # Convert date string to datetime
            try:
                target_date = pd.Timestamp(date)
            except Exception:
                return None
            
            # Find exact date or nearest previous date
            if target_date in df.index:
                row = df.loc[target_date]
            else:
                previous_dates = df.index[df.index <= target_date]
                if len(previous_dates) == 0:
                    return None
                nearest_date = previous_dates[-1]
                row = df.loc[nearest_date]
            
            # Return dict with all price fields
            return {
                "close": float(row["close"]),
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "volume": float(row["volume"]),
            }
        except (FileNotFoundError, ValueError, KeyError):
            return None
    
    def get_price(self, ticker: str, date: str) -> float:
        """
        Get closing price for a ticker on a specific date.
        
        Args:
            ticker: Stock ticker symbol (e.g., "AAPL")
            date: Date string in YYYY-MM-DD format
        
        Returns:
            Closing price as float
        
        Raises:
            FileNotFoundError: If price CSV file doesn't exist
            ValueError: If date not found in data
            KeyError: If ticker data not loaded
        """
        ticker_upper = ticker.upper()
        
        # Load ticker data if not cached
        if ticker_upper not in self._cache:
            self._cache[ticker_upper] = self._load_ticker_csv(ticker_upper)
            self._loaded_tickers.add(ticker_upper)
        
        df = self._cache[ticker_upper]
        
        # Convert date string to datetime
        try:
            target_date = pd.Timestamp(date)
        except Exception as e:
            raise ValueError(f"Invalid date format '{date}': {e}")
        
        # Find exact date or nearest previous date (for non-trading days)
        if target_date in df.index:
            return float(df.loc[target_date, "close"])
        
        # Try to find nearest previous trading day
        previous_dates = df.index[df.index <= target_date]
        if len(previous_dates) > 0:
            nearest_date = previous_dates[-1]
            return float(df.loc[nearest_date, "close"])
        
        # No data available for this date or earlier
        available_dates = df.index.strftime("%Y-%m-%d").tolist()
        raise ValueError(
            f"No price data available for {ticker} on {date} (or earlier)\n"
            f"Available date range: {available_dates[0] if available_dates else 'N/A'} to {available_dates[-1] if available_dates else 'N/A'}\n"
            f"Requested date: {date}"
        )
    
    def get_prices_for_range(self, ticker: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        Get price DataFrame for a date range.
        
        Args:
            ticker: Stock ticker symbol
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
        
        Returns:
            DataFrame with date index and columns: open, high, low, close, volume
        
        Raises:
            FileNotFoundError: If price CSV file doesn't exist
            ValueError: If date range not available
        """
        ticker_upper = ticker.upper()
        
        # Load ticker data if not cached
        if ticker_upper not in self._cache:
            self._cache[ticker_upper] = self._load_ticker_csv(ticker_upper)
            self._loaded_tickers.add(ticker_upper)
        
        df = self._cache[ticker_upper]
        
        # Filter by date range
        # Handle both date strings (YYYY-MM-DD) and datetime strings (YYYY-MM-DD HH:MM:SS)
        try:
            start_ts = pd.Timestamp(start_date)
            end_ts = pd.Timestamp(end_date)
        except Exception as e:
            raise ValueError(f"Invalid date format: {e}")
        
        # For intraday data: if start_ts is date-only (00:00:00), include all bars on that date
        # For daily data: exact match
        if len(df) > 0:
            # Check if we have intraday data
            sample_ts = df.index[0]
            has_intraday = hasattr(sample_ts, 'hour') and (sample_ts.hour > 0 or sample_ts.minute > 0)
            
            if has_intraday:
                # For intraday: if start_ts is at midnight, include all bars on that date
                if start_ts.hour == 0 and start_ts.minute == 0:
                    start_date_only = start_ts.date()
                    filtered = df[df.index.date >= start_date_only]
                else:
                    filtered = df[df.index >= start_ts]
                
                # For end_ts: if at midnight, include all bars on that date
                if end_ts.hour == 0 and end_ts.minute == 0:
                    end_date_only = end_ts.date()
                    filtered = filtered[filtered.index.date <= end_date_only]
                else:
                    filtered = filtered[filtered.index <= end_ts]
            else:
                # Daily data: exact timestamp match
                filtered = df[(df.index >= start_ts) & (df.index <= end_ts)]
        else:
            filtered = df
        
        if filtered.empty:
            available_range = f"{df.index.min()} to {df.index.max()}" if not df.empty else "N/A"
            raise ValueError(
                f"No price data available for {ticker} in range {start_date} to {end_date}\n"
                f"Available date range: {available_range}"
            )
        
        return filtered.copy()
    
    def clear_cache(self):
        """Clear in-memory cache (useful for testing)."""
        self._cache.clear()
        self._loaded_tickers.clear()


# Global cache instance
_price_cache: Optional[PriceCache] = None


def get_price_cache(data_dir: Optional[str] = None) -> PriceCache:
    """Get or create global price cache instance."""
    global _price_cache
    if _price_cache is None:
        _price_cache = PriceCache(data_dir)
    return _price_cache


def reset_price_cache():
    """Reset global cache (useful for testing)."""
    global _price_cache
    _price_cache = None
