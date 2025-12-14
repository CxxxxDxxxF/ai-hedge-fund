"""
Data validation and quality checks for the data pipeline.

Provides validation functions for:
- Price data (OHLCV)
- Financial metrics
- Data completeness
- Data consistency
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Tuple
import pandas as pd
from datetime import datetime

logger = logging.getLogger(__name__)


class DataValidationError(Exception):
    """Raised when data validation fails."""
    pass


def validate_price_data(df: pd.DataFrame, ticker: str = None) -> Tuple[bool, List[str]]:
    """
    Validate price data DataFrame.
    
    Checks:
    - Required columns present (date, open, high, low, close, volume)
    - OHLC relationships (high >= low, high >= open/close, low <= open/close)
    - No missing values in OHLCV
    - Date index is sorted
    - No duplicate dates
    - Volume is non-negative
    
    Args:
        df: DataFrame with price data
        ticker: Optional ticker symbol for error messages
    
    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    errors = []
    ticker_str = f" for {ticker}" if ticker else ""
    
    # Check required columns
    required_cols = ["open", "high", "low", "close", "volume"]
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        errors.append(f"Missing required columns{ticker_str}: {missing_cols}")
        return False, errors
    
    # Check for missing values
    for col in required_cols:
        if df[col].isna().any():
            na_count = df[col].isna().sum()
            errors.append(f"Missing values in {col}{ticker_str}: {na_count} NaN values")
    
    # Check OHLC relationships
    invalid_high_low = df[df["high"] < df["low"]]
    if len(invalid_high_low) > 0:
        errors.append(
            f"Invalid high/low relationship{ticker_str}: "
            f"{len(invalid_high_low)} rows where high < low"
        )
    
    invalid_high_oc = df[(df["high"] < df["open"]) | (df["high"] < df["close"])]
    if len(invalid_high_oc) > 0:
        errors.append(
            f"Invalid high/open-close relationship{ticker_str}: "
            f"{len(invalid_high_oc)} rows where high < open or high < close"
        )
    
    invalid_low_oc = df[(df["low"] > df["open"]) | (df["low"] > df["close"])]
    if len(invalid_low_oc) > 0:
        errors.append(
            f"Invalid low/open-close relationship{ticker_str}: "
            f"{len(invalid_low_oc)} rows where low > open or low > close"
        )
    
    # Check volume is non-negative
    negative_volume = df[df["volume"] < 0]
    if len(negative_volume) > 0:
        errors.append(
            f"Negative volume{ticker_str}: {len(negative_volume)} rows with negative volume"
        )
    
    # Check date index is sorted
    if not df.index.is_monotonic_increasing:
        errors.append(f"Date index not sorted{ticker_str}")
    
    # Check for duplicate dates
    duplicate_dates = df.index.duplicated()
    if duplicate_dates.any():
        dup_count = duplicate_dates.sum()
        errors.append(f"Duplicate dates{ticker_str}: {dup_count} duplicate dates found")
    
    # Check for zero or negative prices
    zero_prices = df[(df["open"] <= 0) | (df["close"] <= 0) | (df["high"] <= 0) | (df["low"] <= 0)]
    if len(zero_prices) > 0:
        errors.append(
            f"Zero or negative prices{ticker_str}: {len(zero_prices)} rows with invalid prices"
        )
    
    is_valid = len(errors) == 0
    return is_valid, errors


def validate_price_range(
    df: pd.DataFrame, 
    start_date: str, 
    end_date: str,
    ticker: str = None
) -> Tuple[bool, List[str]]:
    """
    Validate that price data covers the requested date range.
    
    Args:
        df: DataFrame with price data
        start_date: Requested start date
        end_date: Requested end date
        ticker: Optional ticker symbol for error messages
    
    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    errors = []
    ticker_str = f" for {ticker}" if ticker else ""
    
    if df.empty:
        errors.append(f"No data available{ticker_str} for range {start_date} to {end_date}")
        return False, errors
    
    start_ts = pd.Timestamp(start_date)
    end_ts = pd.Timestamp(end_date)
    
    # Check start date coverage
    if df.index.min() > start_ts:
        errors.append(
            f"Data starts after requested start date{ticker_str}: "
            f"available from {df.index.min()}, requested from {start_date}"
        )
    
    # Check end date coverage
    if df.index.max() < end_ts:
        errors.append(
            f"Data ends before requested end date{ticker_str}: "
            f"available until {df.index.max()}, requested until {end_date}"
        )
    
    is_valid = len(errors) == 0
    return is_valid, errors


def validate_data_freshness(
    last_update: datetime,
    max_age_hours: int = 24,
    ticker: str = None
) -> Tuple[bool, Optional[str]]:
    """
    Validate that data is fresh enough.
    
    Args:
        last_update: Timestamp of last data update
        max_age_hours: Maximum age in hours (default: 24)
        ticker: Optional ticker symbol for error messages
    
    Returns:
        Tuple of (is_fresh, error_message)
    """
    if last_update is None:
        return False, f"No update timestamp available for {ticker}" if ticker else "No update timestamp available"
    
    age_hours = (datetime.now() - last_update).total_seconds() / 3600
    
    if age_hours > max_age_hours:
        ticker_str = f" for {ticker}" if ticker else ""
        return False, (
            f"Data is stale{ticker_str}: "
            f"last updated {age_hours:.1f} hours ago (max: {max_age_hours} hours)"
        )
    
    return True, None


def validate_financial_metrics(metrics: List[Dict], ticker: str = None) -> Tuple[bool, List[str]]:
    """
    Validate financial metrics data.
    
    Args:
        metrics: List of financial metric dictionaries
        ticker: Optional ticker symbol for error messages
    
    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    errors = []
    ticker_str = f" for {ticker}" if ticker else ""
    
    if not metrics:
        errors.append(f"No financial metrics available{ticker_str}")
        return False, errors
    
    # Check for required fields
    required_fields = ["ticker", "report_period", "period"]
    for i, metric in enumerate(metrics):
        for field in required_fields:
            if field not in metric or metric[field] is None:
                errors.append(
                    f"Missing required field '{field}'{ticker_str} in metric {i}"
                )
    
    # Check for reasonable values (if present)
    for i, metric in enumerate(metrics):
        # Market cap should be positive if present
        if "market_cap" in metric and metric["market_cap"] is not None:
            if metric["market_cap"] < 0:
                errors.append(
                    f"Negative market cap{ticker_str} in metric {i}: {metric['market_cap']}"
                )
        
        # Ratios should be reasonable (not extreme outliers)
        ratio_fields = [
            "price_to_earnings_ratio",
            "price_to_book_ratio",
            "price_to_sales_ratio",
        ]
        for field in ratio_fields:
            if field in metric and metric[field] is not None:
                value = metric[field]
                # Flag extreme outliers (e.g., > 1000 or < -100)
                if value > 1000 or value < -100:
                    errors.append(
                        f"Extreme ratio value{ticker_str} for {field} in metric {i}: {value}"
                    )
    
    is_valid = len(errors) == 0
    return is_valid, errors


def log_validation_results(
    is_valid: bool,
    errors: List[str],
    data_type: str,
    ticker: str = None
) -> None:
    """
    Log validation results.
    
    Args:
        is_valid: Whether validation passed
        errors: List of error messages
        data_type: Type of data validated (e.g., "price_data", "financial_metrics")
        ticker: Optional ticker symbol
    """
    ticker_str = f" for {ticker}" if ticker else ""
    
    if is_valid:
        logger.debug(f"Validation passed for {data_type}{ticker_str}")
    else:
        logger.warning(f"Validation failed for {data_type}{ticker_str}: {len(errors)} errors")
        for error in errors:
            logger.warning(f"  - {error}")
