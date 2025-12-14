"""
Unified data pipeline orchestrator with monitoring and validation.

Provides a centralized interface for data fetching, validation, and monitoring.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
import pandas as pd

from src.data.cache import get_cache
from src.data.validation import (
    validate_price_data,
    validate_price_range,
    validate_data_freshness,
    validate_financial_metrics,
    log_validation_results,
    DataValidationError,
)
from src.tools.api import (
    get_prices,
    get_financial_metrics,
    get_company_news,
    get_insider_trades,
    search_line_items,
)
from src.data.price_cache import get_price_cache

logger = logging.getLogger(__name__)


class DataPipeline:
    """
    Unified data pipeline orchestrator.
    
    Features:
    - Centralized data fetching
    - Automatic validation
    - Cache management
    - Performance monitoring
    - Error handling and recovery
    """
    
    def __init__(
        self,
        enable_validation: bool = True,
        enable_monitoring: bool = True,
        cache_max_age_hours: int = 24,
    ):
        """
        Initialize data pipeline.
        
        Args:
            enable_validation: Enable data validation (default: True)
            enable_monitoring: Enable performance monitoring (default: True)
            cache_max_age_hours: Maximum cache age in hours (default: 24)
        """
        self.enable_validation = enable_validation
        self.enable_monitoring = enable_monitoring
        self.cache_max_age_hours = cache_max_age_hours
        self.cache = get_cache()
        self.price_cache = get_price_cache()
        
        # Monitoring metrics
        self.metrics = {
            "requests": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "validation_passes": 0,
            "validation_failures": 0,
            "errors": 0,
            "start_time": datetime.now(),
        }
    
    def get_price_data(
        self,
        ticker: str,
        start_date: str,
        end_date: str,
        validate: Optional[bool] = None,
        use_local_cache: bool = True,
    ) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """
        Get price data with validation and monitoring.
        
        Args:
            ticker: Ticker symbol
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            validate: Override pipeline validation setting
            use_local_cache: Use local CSV cache if available (default: True)
        
        Returns:
            Tuple of (DataFrame with price data, metadata dict)
        """
        metadata = {
            "ticker": ticker,
            "start_date": start_date,
            "end_date": end_date,
            "source": None,
            "cached": False,
            "validated": False,
            "validation_errors": [],
        }
        
        self.metrics["requests"] += 1
        start_time = datetime.now()
        
        try:
            # Try local cache first if enabled
            if use_local_cache:
                try:
                    df = self.price_cache.get_prices_for_range(ticker, start_date, end_date)
                    metadata["source"] = "local_cache"
                    metadata["cached"] = True
                    self.metrics["cache_hits"] += 1
                    logger.info(f"Loaded price data from local cache: {ticker}")
                except (FileNotFoundError, ValueError) as e:
                    logger.debug(f"Local cache miss for {ticker}: {e}")
                    self.metrics["cache_misses"] += 1
                    # Fall through to API fetch
                    df = None
            else:
                df = None
            
            # Fetch from API if not in local cache
            if df is None or df.empty:
                prices = get_prices(ticker, start_date, end_date)
                if not prices:
                    raise DataValidationError(f"No price data available for {ticker}")
                
                # Convert to DataFrame
                df = pd.DataFrame([p.model_dump() for p in prices])
                df["Date"] = pd.to_datetime(df["time"])
                df.set_index("Date", inplace=True)
                df = df[["open", "high", "low", "close", "volume"]]
                df.sort_index(inplace=True)
                
                metadata["source"] = "api"
                self.metrics["cache_misses"] += 1
                logger.info(f"Fetched price data from API: {ticker}")
            
            # Validate data
            should_validate = validate if validate is not None else self.enable_validation
            if should_validate:
                is_valid, errors = validate_price_data(df, ticker)
                metadata["validated"] = True
                metadata["validation_errors"] = errors
                
                if is_valid:
                    self.metrics["validation_passes"] += 1
                    logger.debug(f"Price data validation passed: {ticker}")
                else:
                    self.metrics["validation_failures"] += 1
                    log_validation_results(is_valid, errors, "price_data", ticker)
                    # Continue with warnings, but log issues
                
                # Validate date range coverage
                range_valid, range_errors = validate_price_range(df, start_date, end_date, ticker)
                if not range_valid:
                    metadata["validation_errors"].extend(range_errors)
                    log_validation_results(range_valid, range_errors, "price_range", ticker)
            
            # Add performance metrics
            elapsed = (datetime.now() - start_time).total_seconds()
            metadata["fetch_time_seconds"] = elapsed
            metadata["row_count"] = len(df)
            
            if self.enable_monitoring:
                logger.debug(
                    f"Price data fetch completed: {ticker} "
                    f"({len(df)} rows, {elapsed:.2f}s)"
                )
            
            return df, metadata
            
        except Exception as e:
            self.metrics["errors"] += 1
            logger.error(f"Error fetching price data for {ticker}: {e}", exc_info=True)
            raise
    
    def get_financial_data(
        self,
        ticker: str,
        end_date: str,
        period: str = "ttm",
        limit: int = 10,
        validate: Optional[bool] = None,
    ) -> Tuple[List[Dict], Dict[str, Any]]:
        """
        Get financial metrics with validation and monitoring.
        
        Args:
            ticker: Ticker symbol
            end_date: End date (YYYY-MM-DD)
            period: Period type (default: "ttm")
            limit: Maximum number of records (default: 10)
            validate: Override pipeline validation setting
        
        Returns:
            Tuple of (list of financial metrics, metadata dict)
        """
        metadata = {
            "ticker": ticker,
            "end_date": end_date,
            "period": period,
            "source": "api",
            "cached": False,
            "validated": False,
            "validation_errors": [],
        }
        
        self.metrics["requests"] += 1
        start_time = datetime.now()
        
        try:
            # Check cache first
            cache_key = f"{ticker}_{period}_{end_date}_{limit}"
            cached_data = self.cache.get_financial_metrics(cache_key)
            
            if cached_data:
                metrics = [dict(m) for m in cached_data]
                metadata["cached"] = True
                self.metrics["cache_hits"] += 1
                logger.debug(f"Loaded financial metrics from cache: {ticker}")
            else:
                # Fetch from API
                financial_metrics = get_financial_metrics(ticker, end_date, period, limit)
                metrics = [m.model_dump() for m in financial_metrics]
                self.metrics["cache_misses"] += 1
                logger.debug(f"Fetched financial metrics from API: {ticker}")
            
            # Validate data
            should_validate = validate if validate is not None else self.enable_validation
            if should_validate:
                is_valid, errors = validate_financial_metrics(metrics, ticker)
                metadata["validated"] = True
                metadata["validation_errors"] = errors
                
                if is_valid:
                    self.metrics["validation_passes"] += 1
                else:
                    self.metrics["validation_failures"] += 1
                    log_validation_results(is_valid, errors, "financial_metrics", ticker)
            
            # Add performance metrics
            elapsed = (datetime.now() - start_time).total_seconds()
            metadata["fetch_time_seconds"] = elapsed
            metadata["record_count"] = len(metrics)
            
            return metrics, metadata
            
        except Exception as e:
            self.metrics["errors"] += 1
            logger.error(f"Error fetching financial data for {ticker}: {e}", exc_info=True)
            raise
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """
        Get pipeline performance metrics summary.
        
        Returns:
            Dictionary with metrics
        """
        elapsed = (datetime.now() - self.metrics["start_time"]).total_seconds()
        total_requests = self.metrics["requests"]
        
        cache_hit_rate = (
            (self.metrics["cache_hits"] / total_requests * 100)
            if total_requests > 0
            else 0.0
        )
        
        validation_pass_rate = (
            (self.metrics["validation_passes"] / (self.metrics["validation_passes"] + self.metrics["validation_failures"]) * 100)
            if (self.metrics["validation_passes"] + self.metrics["validation_failures"]) > 0
            else 0.0
        )
        
        error_rate = (
            (self.metrics["errors"] / total_requests * 100)
            if total_requests > 0
            else 0.0
        )
        
        # Get cache stats
        cache_stats = self.cache.get_cache_stats()
        
        return {
            "pipeline_metrics": {
                "total_requests": total_requests,
                "cache_hits": self.metrics["cache_hits"],
                "cache_misses": self.metrics["cache_misses"],
                "cache_hit_rate_percent": round(cache_hit_rate, 2),
                "validation_passes": self.metrics["validation_passes"],
                "validation_failures": self.metrics["validation_failures"],
                "validation_pass_rate_percent": round(validation_pass_rate, 2),
                "errors": self.metrics["errors"],
                "error_rate_percent": round(error_rate, 2),
                "uptime_seconds": round(elapsed, 2),
            },
            "cache_stats": cache_stats,
        }
    
    def reset_metrics(self):
        """Reset pipeline metrics."""
        self.metrics = {
            "requests": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "validation_passes": 0,
            "validation_failures": 0,
            "errors": 0,
            "start_time": datetime.now(),
        }
        logger.info("Pipeline metrics reset")


# Global pipeline instance
_pipeline: Optional[DataPipeline] = None


def get_data_pipeline(
    enable_validation: bool = True,
    enable_monitoring: bool = True,
) -> DataPipeline:
    """
    Get or create global data pipeline instance.
    
    Args:
        enable_validation: Enable data validation
        enable_monitoring: Enable performance monitoring
    
    Returns:
        DataPipeline instance
    """
    global _pipeline
    if _pipeline is None:
        _pipeline = DataPipeline(
            enable_validation=enable_validation,
            enable_monitoring=enable_monitoring,
        )
    return _pipeline
