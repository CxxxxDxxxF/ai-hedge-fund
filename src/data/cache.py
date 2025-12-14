import logging
from datetime import datetime
from typing import Optional, Dict, List, Any

logger = logging.getLogger(__name__)


class Cache:
    """
    Enhanced in-memory cache for API responses with metadata tracking.
    
    Features:
    - Tracks cache hit/miss statistics
    - Records last update timestamps
    - Supports cache size limits
    - Provides cache health metrics
    """

    def __init__(self, max_size: Optional[int] = None):
        """
        Initialize cache.
        
        Args:
            max_size: Maximum number of entries per cache type (None = unlimited)
        """
        self._prices_cache: Dict[str, List[Dict[str, Any]]] = {}
        self._financial_metrics_cache: Dict[str, List[Dict[str, Any]]] = {}
        self._line_items_cache: Dict[str, List[Dict[str, Any]]] = {}
        self._insider_trades_cache: Dict[str, List[Dict[str, Any]]] = {}
        self._company_news_cache: Dict[str, List[Dict[str, Any]]] = {}
        
        # Metadata tracking
        self._last_update: Dict[str, datetime] = {}
        self._hit_count: Dict[str, int] = {}
        self._miss_count: Dict[str, int] = {}
        self.max_size = max_size

    def _merge_data(self, existing: Optional[List[Dict[str, Any]]], new_data: List[Dict[str, Any]], key_field: str) -> List[Dict[str, Any]]:
        """Merge existing and new data, avoiding duplicates based on a key field."""
        if not existing:
            return new_data

        # Create a set of existing keys for O(1) lookup
        existing_keys = {item[key_field] for item in existing}

        # Only add items that don't exist yet
        merged = existing.copy()
        merged.extend([item for item in new_data if item[key_field] not in existing_keys])
        return merged

    def get_prices(self, ticker: str) -> Optional[List[Dict[str, Any]]]:
        """Get cached price data if available."""
        cache_key = f"prices_{ticker}"
        if ticker in self._prices_cache:
            self._hit_count[cache_key] = self._hit_count.get(cache_key, 0) + 1
            logger.debug(f"Cache hit for prices: {ticker}")
            return self._prices_cache.get(ticker)
        else:
            self._miss_count[cache_key] = self._miss_count.get(cache_key, 0) + 1
            logger.debug(f"Cache miss for prices: {ticker}")
            return None

    def set_prices(self, ticker: str, data: List[Dict[str, Any]]):
        """Append new price data to cache."""
        cache_key = f"prices_{ticker}"
        
        # Check size limit
        if self.max_size and len(self._prices_cache) >= self.max_size and ticker not in self._prices_cache:
            # Remove oldest entry (simple FIFO)
            oldest_key = next(iter(self._prices_cache))
            del self._prices_cache[oldest_key]
            logger.debug(f"Cache size limit reached, evicted: {oldest_key}")
        
        self._prices_cache[ticker] = self._merge_data(self._prices_cache.get(ticker), data, key_field="time")
        self._last_update[cache_key] = datetime.now()
        logger.debug(f"Cached prices for {ticker}: {len(data)} records")

    def get_financial_metrics(self, ticker: str) -> Optional[List[Dict[str, Any]]]:
        """Get cached financial metrics if available."""
        return self._financial_metrics_cache.get(ticker)

    def set_financial_metrics(self, ticker: str, data: List[Dict[str, Any]]):
        """Append new financial metrics to cache."""
        self._financial_metrics_cache[ticker] = self._merge_data(self._financial_metrics_cache.get(ticker), data, key_field="report_period")

    def get_line_items(self, ticker: str) -> Optional[List[Dict[str, Any]]]:
        """Get cached line items if available."""
        return self._line_items_cache.get(ticker)

    def set_line_items(self, ticker: str, data: List[Dict[str, Any]]):
        """Append new line items to cache."""
        self._line_items_cache[ticker] = self._merge_data(self._line_items_cache.get(ticker), data, key_field="report_period")

    def get_insider_trades(self, ticker: str) -> Optional[List[Dict[str, Any]]]:
        """Get cached insider trades if available."""
        return self._insider_trades_cache.get(ticker)

    def set_insider_trades(self, ticker: str, data: List[Dict[str, Any]]):
        """Append new insider trades to cache."""
        self._insider_trades_cache[ticker] = self._merge_data(self._insider_trades_cache.get(ticker), data, key_field="filing_date")  # Could also use transaction_date if preferred

    def get_company_news(self, ticker: str) -> Optional[List[Dict[str, Any]]]:
        """Get cached company news if available."""
        return self._company_news_cache.get(ticker)

    def set_company_news(self, ticker: str, data: List[Dict[str, Any]]):
        """Append new company news to cache."""
        cache_key = f"news_{ticker}"
        
        # Check size limit
        if self.max_size and len(self._company_news_cache) >= self.max_size and ticker not in self._company_news_cache:
            oldest_key = next(iter(self._company_news_cache))
            del self._company_news_cache[oldest_key]
            logger.debug(f"Cache size limit reached, evicted: {oldest_key}")
        
        self._company_news_cache[ticker] = self._merge_data(self._company_news_cache.get(ticker), data, key_field="date")
        self._last_update[cache_key] = datetime.now()
        logger.debug(f"Cached company news for {ticker}: {len(data)} records")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total_hits = sum(self._hit_count.values())
        total_misses = sum(self._miss_count.values())
        total_requests = total_hits + total_misses
        hit_rate = (total_hits / total_requests * 100) if total_requests > 0 else 0.0
        
        return {
            "prices_entries": len(self._prices_cache),
            "financial_metrics_entries": len(self._financial_metrics_cache),
            "line_items_entries": len(self._line_items_cache),
            "insider_trades_entries": len(self._insider_trades_cache),
            "company_news_entries": len(self._company_news_cache),
            "total_hits": total_hits,
            "total_misses": total_misses,
            "hit_rate_percent": round(hit_rate, 2),
            "max_size": self.max_size,
        }
    
    def clear_cache(self, cache_type: Optional[str] = None):
        """
        Clear cache entries.
        
        Args:
            cache_type: Type of cache to clear ('prices', 'financial_metrics', etc.)
                       If None, clears all caches
        """
        if cache_type == "prices":
            self._prices_cache.clear()
        elif cache_type == "financial_metrics":
            self._financial_metrics_cache.clear()
        elif cache_type == "line_items":
            self._line_items_cache.clear()
        elif cache_type == "insider_trades":
            self._insider_trades_cache.clear()
        elif cache_type == "company_news":
            self._company_news_cache.clear()
        else:
            # Clear all
            self._prices_cache.clear()
            self._financial_metrics_cache.clear()
            self._line_items_cache.clear()
            self._insider_trades_cache.clear()
            self._company_news_cache.clear()
            self._last_update.clear()
            self._hit_count.clear()
            self._miss_count.clear()
        
        logger.info(f"Cleared cache: {cache_type or 'all'}")


# Global cache instance
_cache = Cache()


def get_cache() -> Cache:
    """Get the global cache instance."""
    return _cache
