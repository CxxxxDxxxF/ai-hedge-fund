# Deterministic Backtest Fix: Eliminating External I/O

## Problem

The deterministic backtest was hanging on day 1 at:
```
"Peter Lynch [TICKER] Fetching insider trades"
```

This was caused by synchronous external API calls inside the daily backtest loop, which is invalid for large-scale historical simulation.

## Solution

Implemented a **system-wide guard** that prevents all external I/O when `HEDGEFUND_NO_LLM=1`.

### 1. Deterministic Guard Utility (`src/utils/deterministic_guard.py`)

Created a reusable guard utility with:
- `is_deterministic_mode()`: Check if system is in deterministic mode
- `require_deterministic_data()`: Check if external data fetching is allowed
- `skip_if_deterministic()`: Skip operations in deterministic mode
- `guard_external_io()`: Decorator to guard external I/O

### 2. API-Level Guard (`src/tools/api.py`)

Added guard in `_make_api_request()` to block **all HTTP requests** in deterministic mode:
- Returns mock empty response immediately
- Prevents any agent from making external calls
- System-wide protection

### 3. Agent-Level Guard (`src/agents/peter_lynch.py`)

Updated Peter Lynch agent to:
- Check deterministic mode **before** any external calls
- Return neutral signal immediately: `signal="neutral"`, `confidence=0.0`
- Clear reasoning: "Disabled external data in deterministic backtest"
- Skip all external data fetching (insider trades, company news, financial data)

## Behavior in Deterministic Mode

When `HEDGEFUND_NO_LLM=1`:

1. **Peter Lynch Agent**:
   - Returns immediately with neutral signal
   - No external API calls
   - No blocking I/O

2. **All API Functions**:
   - `get_insider_trades()` → Returns empty list
   - `get_company_news()` → Returns empty list
   - `get_financial_metrics()` → Returns empty list
   - `search_line_items()` → Returns empty list
   - `get_market_cap()` → Returns None

3. **System Health**:
   - No network calls
   - No blocking operations
   - Fast, deterministic execution

## Logging

The guard logs once per agent+operation combination:
```
⚠️  peter_lynch_agent: External data 'insider_trades' disabled for deterministic backtest
```

## Performance Guarantees

- ✅ Backtest advances past day 1 immediately
- ✅ Long runs (500+ days, multiple tickers) complete without blocking
- ✅ No agent may block the main loop
- ✅ All external I/O is prevented at API level

## Testing

Run the backtest to verify it completes without hanging:

```bash
HEDGEFUND_NO_LLM=1 python src/backtesting/deterministic_backtest.py \
  --tickers AAPL,MSFT,GOOGL \
  --start-date 2022-01-03 \
  --end-date 2023-12-29 \
  --initial-capital 100000
```

**Expected behavior**:
- No hanging on day 1
- Fast execution (no external API calls)
- Agents return neutral signals when external data is required
- Backtest completes successfully

## Files Modified

1. `src/utils/deterministic_guard.py` (NEW)
   - System-wide guard utility

2. `src/tools/api.py`
   - Added guard in `_make_api_request()` to block all HTTP requests

3. `src/agents/peter_lynch.py`
   - Early return in deterministic mode
   - Skip all external data fetching

## Future Agents

Any new agent that needs external data should:
1. Check `is_deterministic_mode()` before external calls
2. Return appropriate fallback values
3. Use `require_deterministic_data()` helper if needed

The API-level guard provides **defense in depth** - even if an agent forgets to check, external calls are blocked.
