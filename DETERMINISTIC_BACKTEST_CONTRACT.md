# Deterministic Backtest Contract

## Single Entry Point

**ONLY ONE WAY TO RUN DETERMINISTIC BACKTEST:**

```python
from src.backtesting.deterministic_backtest import DeterministicBacktest

backtest = DeterministicBacktest(...)
metrics = backtest.run()
backtest.print_summary(metrics)
```

**OR via CLI:**

```bash
python src/backtesting/deterministic_backtest.py --tickers AAPL --start-date ... --end-date ...
```

## Forbidden Alternatives

The following are **NOT** deterministic backtest entry points:

- ❌ `BacktestEngine` (in `src/backtesting/engine.py`) - Different implementation
- ❌ `TradeTrackingBacktestEngine` (in `src/compare_backtests.py`) - Different implementation
- ❌ `run_backtest()` (in `src/backtester.py`) - Different implementation
- ❌ Any direct calls to `run_hedge_fund()` in a loop - Bypasses hardening

## Contracts (What Must Never Be True)

### 1. Duplicate Date Processing

**Contract**: The same date must never be processed twice.

**Enforcement**: 
```python
if date in self.processed_dates:
    raise RuntimeError(f"ENGINE FAILURE: Date {date} already processed")
```

**Violation**: This is a bug, not a recoverable event.

### 2. Loop Advancement

**Contract**: Loop index must advance exactly once per iteration.

**Enforcement**:
```python
for i in range(total_days):  # Explicit index, cannot skip or repeat
    date = dates[i]
    # Process date
```

**Violation**: If index doesn't advance, this is a bug.

### 3. Determinism

**Contract**: Identical inputs must produce identical output hashes.

**Enforcement**:
```python
# Seed RNGs
random.seed(DETERMINISTIC_SEED)
np.random.seed(DETERMINISTIC_SEED)

# Hash outputs
daily_hash = hashlib.md5(f"{date}:{portfolio_value}:{trades}").hexdigest()
final_hash = hashlib.md5("".join(daily_hashes)).hexdigest()

# Verify
verify_determinism(run1_hash, run2_hash)  # Raises RuntimeError if different
```

**Violation**: If two identical runs produce different hashes, this is a bug.

### 4. Invariant Logging

**Contract**: Every iteration must log exactly one line to stderr.

**Enforcement**:
```python
self._log_invariant(index, date, portfolio_value, agent_count, wall_clock_delta)
# Always called, always flushes
```

**Violation**: If an iteration completes without logging, this is a bug.

### 5. Summary Printing

**Contract**: Summary must always print, even on failure.

**Enforcement**:
```python
try:
    metrics = backtest.run()
except Exception:
    # Still print partial results
    partial_metrics = backtest._calculate_metrics()
    backtest.print_summary(partial_metrics)
```

**Violation**: If backtest completes but summary doesn't print, this is a bug.

### 6. Engine vs Strategy Separation

**Contract**: Engine failures must abort, strategy failures must continue.

**Enforcement**:
```python
# Engine failures
if date in self.processed_dates:
    raise RuntimeError("ENGINE FAILURE: ...")  # Abort

# Strategy failures
except Exception as e:
    print(f"STRATEGY FAILURE: {e}", file=sys.stderr)  # Continue
```

**Violation**: If engine failures continue or strategy failures abort incorrectly, this is a bug.

### 7. External I/O Blocking

**Contract**: No external I/O in deterministic mode.

**Enforcement**:
```python
# API level
if is_deterministic_mode():
    return MockResponse()  # Block all HTTP

# Agent level
if is_deterministic_mode():
    return neutral_signal  # Skip external calls
```

**Violation**: If external I/O occurs in deterministic mode, this is a bug.

## Fail-Fast Assertions

These conditions are checked and raise `RuntimeError` immediately:

1. **Duplicate date**: `RuntimeError("ENGINE FAILURE: Date already processed")`
2. **Malformed data**: `RuntimeError("ENGINE FAILURE: run_hedge_fund returned non-dict")`
3. **Determinism violation**: `RuntimeError("DETERMINISM VIOLATION: Output hashes differ")`

## What Happens on Violation

**Engine Failures** (contract violations):
- Raise `RuntimeError("ENGINE FAILURE: ...")`
- Abort backtest immediately
- Print last known good state
- Print partial results
- Exit with code 1

**Strategy Failures** (recoverable):
- Log to stderr with full traceback
- Continue to next day
- Record partial daily value
- Complete backtest

## Testing Contracts

Run resilience tests to verify contracts:

```bash
python src/backtesting/test_backtest_resilience.py
```

These tests intentionally violate contracts to verify they're enforced.

## Future Code

Any code that:
- Bypasses `DeterministicBacktest`
- Skips invariant logging
- Disables determinism silently
- Processes dates without tracking

**Is a bug and must be rejected.**
