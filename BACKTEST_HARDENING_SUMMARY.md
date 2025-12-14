# Backtest Hardening: Turning Silent Failure into Impossible Failure

## Overview

Comprehensive hardening of the deterministic backtest to eliminate silent failures, enforce determinism, and provide complete observability.

## 1. Proving the Fix

Created `src/backtesting/test_backtest_resilience.py` to intentionally break the system and verify:

✅ **Exception Handling**: Loop advances past exceptions
✅ **Duplicate Date Guard**: RuntimeError fires on duplicate dates  
✅ **Malformed Data**: Engine failures detected and abort
✅ **Progress Rendering**: Disabled by default, non-blocking
✅ **Determinism**: Identical runs produce identical outputs
✅ **Partial Results**: Preserved on failure
✅ **Snapshots**: Last known good state saved

Run tests:
```bash
python src/backtesting/test_backtest_resilience.py
```

## 2. Invariant Logging (One Line Per Iteration)

**Added**: `_log_invariant()` method that logs exactly one line per iteration to stderr:

```
[index] date | PV=$value | Agents=count | Δt=seconds
```

**Example output**:
```
[   0] 2024-01-02 | PV=$100,000 | Agents=5 | Δt=2.34s
[   1] 2024-01-03 | PV=$100,123 | Agents=5 | Δt=2.12s
[   2] 2024-01-04 | PV=$99,987 | Agents=5 | Δt=2.45s
```

**Benefits**:
- Turns "it hung" into "it stopped at index 143 on date 2024-06-15"
- Lightweight (one line per day)
- Goes to stderr (doesn't interfere with summary)
- Always flushes (no buffering)

## 3. Engine vs Strategy Failure Separation

**Engine Failures** (abort immediately):
- Duplicate date processing
- Malformed data from `run_hedge_fund`
- Unexpected exceptions in loop
- Determinism violations

**Strategy Failures** (log, skip, continue):
- Agent exceptions
- Invalid decision formats
- Missing data
- Strategy logic errors

**Implementation**:
- `_run_daily_decision()` returns `(is_engine_failure, agent_count)`
- Engine failures raise `RuntimeError("ENGINE FAILURE: ...")`
- Strategy failures log to stderr and continue
- Loop aborts on engine failures, continues on strategy failures

## 4. Progress Rendering Non-Blocking

**Changes**:
- `progress.start()` checks `HEDGEFUND_NO_LLM=1` and skips starting
- `progress._refresh_display()` only refreshes if started
- `main.py` only starts progress if not in deterministic mode
- All progress operations wrapped in try/except

**Result**: Progress rendering never blocks the simulation loop.

## 5. Determinism Enforcement

**Seeding**:
```python
DETERMINISTIC_SEED = 42
random.seed(DETERMINISTIC_SEED)
np.random.seed(DETERMINISTIC_SEED)
```

**Output Hashing**:
- Each day's output is hashed: `hashlib.md5(f"{date}:{portfolio_value}:{trades}")`
- Final hash is MD5 of all daily hashes
- Stored in metrics for verification

**Verification Function**:
```python
verify_determinism(run1_output_hash, run2_output_hash)
# Raises RuntimeError if hashes differ
```

**Assertion**: Two identical runs must produce identical output hashes.

## 6. Last Known Good State Snapshot

**Implementation**:
- `_save_snapshot()` called after each day
- Saves to `snapshot_dir` if provided
- Contains: date, index, portfolio state, counts

**Usage**:
```bash
--snapshot-dir ./snapshots
```

**Recovery**: If run crashes, inspect last snapshot to see where it stopped.

## 7. Postmortem Document

Created `POSTMORTEM_BACKTEST_HANG.md` answering:
- What failed
- Why it was silent
- What guard would have caught it
- What signal to never ignore again

## Key Changes Summary

### `src/backtesting/deterministic_backtest.py`

1. **Invariant Logging**: One line per iteration to stderr
2. **Duplicate Date Guard**: RuntimeError if same date processed twice
3. **Explicit Loop Index**: `for i in range(total_days)` ensures advancement
4. **Engine vs Strategy Separation**: Different handling for different failure types
5. **Determinism**: RNG seeding + output hashing
6. **Snapshots**: Last known good state saved
7. **Full Tracebacks**: All exceptions logged to stderr with stack traces
8. **Guaranteed Summary**: Always prints, even on failure

### `src/utils/progress.py`

1. **Non-Blocking**: Checks `HEDGEFUND_NO_LLM=1` before starting
2. **Graceful Degradation**: Continues without display if TTY unavailable
3. **Error Handling**: All operations wrapped in try/except

### `src/main.py`

1. **Conditional Progress**: Only starts if not in deterministic mode
2. **Safe Stop**: Checks if started before stopping

## Testing

Run resilience tests:
```bash
python src/backtesting/test_backtest_resilience.py
```

Run actual backtest:
```bash
HEDGEFUND_NO_LLM=1 python src/backtesting/deterministic_backtest.py \
  --tickers AAPL,MSFT,GOOGL \
  --start-date 2022-01-03 \
  --end-date 2023-12-29 \
  --initial-capital 100000 \
  --snapshot-dir ./snapshots
```

**Expected behavior**:
- Invariant logs appear on stderr (one per day)
- No hanging
- Summary always prints
- Determinism hash in output
- Snapshots created (if dir provided)

## Verification Checklist

- [x] Loop advances even on exceptions
- [x] Duplicate date guard fires
- [x] Full tracebacks appear
- [x] Summary still prints on failure
- [x] Partial results preserved
- [x] Invariant logging (one line per iteration)
- [x] Engine vs strategy failure separation
- [x] Progress rendering non-blocking
- [x] Determinism enforced (seeding + hashing)
- [x] Snapshots saved
- [x] Postmortem written

## Result

**Silent failure is now impossible failure.**

Every failure mode is:
- Detected (guards)
- Logged (invariants + tracebacks)
- Recoverable (snapshots)
- Verifiable (determinism)

The backtest can no longer hang silently.
