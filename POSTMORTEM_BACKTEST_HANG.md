# Postmortem: Deterministic Backtest Hang

## What Failed

The deterministic backtest hung after processing all agents for a trading day. Symptoms:
- All agents printed "Done"
- Terminal re-rendered the same day
- No exception shown
- Backtest never exited or printed summary

## Why It Was Silent

1. **Swallowed Exceptions**: The try/except block in `_run_daily_decision` caught all exceptions but only printed a warning. If an exception occurred that prevented the method from completing, the loop would appear to hang.

2. **No Loop Advancement Guarantee**: Using `enumerate(dates)` without explicit index tracking meant if there was any issue with iteration, the loop could theoretically get stuck.

3. **No Duplicate Detection**: If the same date was somehow processed twice (e.g., due to a bug in date generation or iteration), there was no guard to detect it.

4. **No Invariant Logging**: Without per-iteration logging, it was impossible to tell where the loop stopped advancing. "It hung" became "it stopped at some unknown point."

5. **Progress Rendering**: The Rich Live display could potentially cause re-rendering issues, making it look like the same day was being processed repeatedly.

6. **No Guaranteed Summary**: If `run()` raised an exception, the summary never printed, leaving no indication of what happened.

## What Guard Would Have Caught It Earlier

1. **Invariant Logging**: One line per iteration showing:
   - Day index
   - Date
   - Portfolio value
   - Agent count processed
   - Wall-clock delta
   
   This would have immediately shown: "Stopped at index 143 on date X"

2. **Duplicate Date Guard**: Tracking processed dates and raising RuntimeError if same date processed twice would catch loop bugs immediately.

3. **Explicit Loop Index**: Using `for i in range(total_days)` instead of `enumerate()` ensures loop always advances exactly once per iteration.

4. **Engine vs Strategy Failure Separation**: Distinguishing engine failures (abort) from strategy failures (continue) would prevent silent hangs from engine issues.

5. **Determinism Verification**: Hashing daily outputs and comparing across runs would catch non-deterministic behavior that could cause hangs.

## What Signal I Will Never Ignore Again

1. **"All agents Done but no advancement"**: This is a red flag that the loop is stuck, not that agents are slow.

2. **"Terminal re-renders same day"**: This indicates the loop is not advancing, not that progress is updating.

3. **"No summary printed"**: This means `run()` never completed or raised an exception that was swallowed.

4. **"Exception caught but loop continues"**: If exceptions are being caught, they must be logged with full tracebacks to stderr, not just warnings.

5. **"No per-iteration logging"**: Without invariant logging, hangs are impossible to diagnose. One line per iteration is non-negotiable.

## Root Cause Analysis

The most likely root cause was:
- An exception in `run_hedge_fund` or subsequent processing that was caught
- The exception prevented `_run_daily_decision` from completing fully
- The loop continued but appeared to hang because no progress was visible
- Without invariant logging, there was no way to see the loop was actually stuck

## Prevention Measures Implemented

1. ✅ **Invariant Logging**: One line per iteration to stderr
2. ✅ **Duplicate Date Guard**: RuntimeError if same date processed twice
3. ✅ **Explicit Loop Index**: `range(total_days)` ensures advancement
4. ✅ **Full Tracebacks**: All exceptions logged to stderr with full stack traces
5. ✅ **Engine vs Strategy Separation**: Engine failures abort, strategy failures continue
6. ✅ **Guaranteed Summary**: Summary always prints, even on failure
7. ✅ **Progress Rendering Disabled**: Non-blocking by default in deterministic mode
8. ✅ **Determinism Verification**: Output hashing to catch non-deterministic behavior
9. ✅ **Snapshot Support**: Last known good state saved for recovery

## Lesson Learned

**Silent failure is impossible failure.** 

If a system can fail silently, it will. The fix is not to prevent failures, but to make them impossible to ignore:
- Log invariants at every iteration
- Separate engine failures from strategy failures
- Always print summaries, even on failure
- Disable blocking operations in deterministic mode
- Verify determinism explicitly

The goal is not zero failures, but zero silent failures.
