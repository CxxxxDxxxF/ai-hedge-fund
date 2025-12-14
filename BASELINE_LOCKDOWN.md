# Baseline Lockdown: backtest-hardened-v1

## Tagged State

**Tag**: `backtest-hardened-v1`

**Commit**: Current HEAD

**Status**: FROZEN - Reference Implementation

## What This Tag Represents

This is the **golden state** for deterministic backtesting. It includes:

- ✅ Invariant logging (one line per iteration)
- ✅ Duplicate date guard (RuntimeError on duplicate)
- ✅ Engine vs strategy failure separation
- ✅ Determinism enforcement (seeding + output hashing)
- ✅ Last known good state snapshots
- ✅ Progress rendering non-blocking
- ✅ Guaranteed summary printing
- ✅ Full tracebacks on all errors

## Rules for This Tag

1. **Do NOT add features on top of this branch**
2. **Treat as reference implementation**
3. **If you need changes, create a new branch/tag**
4. **This is the "known good" state**

## Why This Matters

Without freezing, you blur "known good" with "experimental" and lose the value of everything that was proved.

This tag is the baseline against which all future changes are measured.
