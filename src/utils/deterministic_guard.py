"""
Deterministic Mode Guard: Prevents external I/O during backtests.

When HEDGEFUND_NO_LLM=1, agents must NOT make:
- External network calls
- API requests
- File downloads
- Scraping

This guard provides a reusable pattern for all agents.
"""

import os
from typing import Optional, Callable, Any


# Global flag to track if we've logged the warning (once per run)
_DETERMINISTIC_MODE_LOGGED = set()

# Global flag to track if RNG has been seeded
_RNG_SEEDED = False


def is_deterministic_mode() -> bool:
    """
    Check if system is in deterministic mode (no external I/O allowed).
    
    Returns:
        True if HEDGEFUND_NO_LLM=1, False otherwise
    """
    return os.getenv("HEDGEFUND_NO_LLM") == "1"


def require_deterministic_data(
    agent_id: str,
    data_name: str,
    fallback_value: Any = None,
) -> tuple[bool, Any]:
    """
    Check if external data fetching is allowed.
    
    In deterministic mode, returns False with fallback value.
    Otherwise, returns True indicating data fetch is allowed.
    
    Args:
        agent_id: Agent identifier (e.g., "peter_lynch_agent")
        data_name: Name of data being fetched (e.g., "insider_trades")
        fallback_value: Value to return if deterministic mode (default: None)
    
    Returns:
        Tuple of (is_allowed, fallback_value)
        - is_allowed: True if external fetch allowed, False if deterministic mode
        - fallback_value: Value to use if not allowed
    
    Example:
        allowed, fallback = require_deterministic_data("peter_lynch_agent", "insider_trades", [])
        if not allowed:
            insider_trades = fallback
            # Skip external fetch
        else:
            insider_trades = get_insider_trades(...)
    """
    if is_deterministic_mode():
        # Log once per agent+data combination
        log_key = f"{agent_id}:{data_name}"
        if log_key not in _DETERMINISTIC_MODE_LOGGED:
            print(f"⚠️  {agent_id}: External data '{data_name}' disabled for deterministic backtest")
            _DETERMINISTIC_MODE_LOGGED.add(log_key)
        return False, fallback_value
    return True, fallback_value


def skip_if_deterministic(
    agent_id: str,
    operation_name: str,
    default_return: Any = None,
) -> Optional[Any]:
    """
    Skip an operation if in deterministic mode.
    
    Convenience function that checks deterministic mode and returns default
    if external operations should be skipped.
    
    Args:
        agent_id: Agent identifier
        operation_name: Name of operation being skipped
        default_return: Value to return if skipping
    
    Returns:
        default_return if deterministic mode, None otherwise (continue operation)
    
    Example:
        result = skip_if_deterministic("peter_lynch_agent", "insider_trades", [])
        if result is not None:
            return result  # Skipped, use default
        # Continue with external fetch
    """
    if is_deterministic_mode():
        log_key = f"{agent_id}:{operation_name}"
        if log_key not in _DETERMINISTIC_MODE_LOGGED:
            print(f"⚠️  {agent_id}: Operation '{operation_name}' skipped for deterministic backtest")
            _DETERMINISTIC_MODE_LOGGED.add(log_key)
        return default_return
    return None


def initialize_determinism(seed: int = 42) -> None:
    """
    Centralized determinism initializer.
    
    Seeds all RNGs exactly once in deterministic mode.
    Must be called before any random operations.
    
    Args:
        seed: Random seed (default: 42)
    
    Raises:
        RuntimeError: If called when not in deterministic mode
    """
    global _RNG_SEEDED
    
    if not is_deterministic_mode():
        raise RuntimeError(
            "initialize_determinism() called but HEDGEFUND_NO_LLM != '1'. "
            "This function should only be called in deterministic mode."
        )
    
    if _RNG_SEEDED:
        return  # Already seeded
    
    import random
    try:
        import numpy as np
        np.random.seed(seed)
    except ImportError:
        pass  # numpy not installed, skip
    
    random.seed(seed)
    _RNG_SEEDED = True


def guard_external_io(
    agent_id: str,
    operation_name: str,
    fallback_fn: Optional[Callable[[], Any]] = None,
) -> Callable:
    """
    Decorator to guard external I/O operations.
    
    In deterministic mode, calls fallback_fn instead of the decorated function.
    
    Args:
        agent_id: Agent identifier
        operation_name: Name of operation
        fallback_fn: Function to call in deterministic mode (returns fallback value)
    
    Example:
        @guard_external_io("peter_lynch_agent", "get_insider_trades", lambda: [])
        def fetch_insider_trades(...):
            return get_insider_trades(...)
    """
    def decorator(func: Callable) -> Callable:
        def wrapper(*args, **kwargs):
            if is_deterministic_mode():
                log_key = f"{agent_id}:{operation_name}"
                if log_key not in _DETERMINISTIC_MODE_LOGGED:
                    print(f"⚠️  {agent_id}: External I/O '{operation_name}' blocked for deterministic backtest")
                    _DETERMINISTIC_MODE_LOGGED.add(log_key)
                if fallback_fn:
                    return fallback_fn()
                return None
            return func(*args, **kwargs)
        return wrapper
    return decorator
