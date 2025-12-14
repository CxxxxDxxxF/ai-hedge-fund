# Enforcement Hooks: Making Hardening Mandatory

## Problem

Hardening is only effective if it's **used**. If someone can bypass it, it's optional instead of enforced.

## Solution: Single Entry Point + Contracts

### 1. Single Entry Point Enforcement

**ONLY ONE WAY** to run deterministic backtest:

```python
# ✅ CORRECT
from src.backtesting.deterministic_backtest import DeterministicBacktest
backtest = DeterministicBacktest(...)
metrics = backtest.run()

# ❌ FORBIDDEN - Bypasses hardening
from src.backtesting.engine import BacktestEngine
engine = BacktestEngine(...)
engine.run_backtest()  # No invariant logging, no duplicate guard, etc.
```

**Enforcement**: Document in `DETERMINISTIC_BACKTEST_CONTRACT.md` that `DeterministicBacktest` is the only valid entry point.

### 2. Contract Assertions

**Turn runtime behavior into fail-fast assertions**:

```python
# Contract: Loop index must match processed count
assert i == len(self.processed_dates), "CONTRACT VIOLATION: Loop broken"

# Contract: Every iteration must log
assert len(self.iteration_log) == len(self.processed_dates), "CONTRACT VIOLATION: Missing logs"

# Contract: Determinism must be verifiable
assert final_hash is not None, "CONTRACT VIOLATION: No determinism hash"
```

**Enforcement**: These assertions fail fast if contracts are violated.

### 3. Determinism Verification

**Make non-determinism impossible to ignore**:

```python
def verify_determinism(run1_hash: str, run2_hash: str) -> bool:
    if run1_hash != run2_hash:
        raise RuntimeError(
            f"DETERMINISM VIOLATION: Output hashes differ\n"
            f"  Run 1: {run1_hash}\n"
            f"  Run 2: {run2_hash}\n"
            f"This indicates non-deterministic behavior - BUG, not feature."
        )
    return True
```

**Enforcement**: CI/CD can run two identical backtests and verify hashes match.

### 4. Reference Implementation

**Minimal canary**: `reference_loop.py` shows the pattern.

**Enforcement**: If `DeterministicBacktest` diverges from `reference_loop.py` pattern, it's a bug.

### 5. Test Suite

**Resilience tests** prove the hardening works.

**Enforcement**: All tests must pass. If they don't, hardening is broken.

## What Cannot Be Bypassed

### Invariant Logging

**Cannot bypass**: `_log_invariant()` is called in `_run_daily_decision()`, which is the only way to process a day.

**If someone**:
- Calls `run_hedge_fund()` directly in a loop → No invariant logging → Not deterministic backtest
- Uses `BacktestEngine` → No invariant logging → Not deterministic backtest

**Enforcement**: Only `DeterministicBacktest.run()` has invariant logging.

### Duplicate Date Guard

**Cannot bypass**: Guard is in `_run_daily_decision()`, which is the only way to process a day.

**Enforcement**: No way to process a date without going through the guard.

### Determinism

**Cannot bypass**: Seeding happens at module import, hashing happens in `_run_daily_decision()`.

**Enforcement**: If someone bypasses `DeterministicBacktest`, they don't get determinism.

### Summary Printing

**Cannot bypass**: `main()` has try/except that always calls `print_summary()`.

**Enforcement**: Even on failure, summary prints.

## Future Code Review Checklist

Before accepting any backtest-related code:

- [ ] Does it use `DeterministicBacktest`? (If no, reject)
- [ ] Does it preserve invariant logging? (If no, reject)
- [ ] Does it preserve duplicate date guard? (If no, reject)
- [ ] Does it preserve determinism? (If no, reject)
- [ ] Does it preserve engine/strategy separation? (If no, reject)
- [ ] Does it pass resilience tests? (If no, reject)

## Making It Impossible to Misuse

**Current State**: Hardening exists but could be bypassed.

**Target State**: Hardening is the only way.

**How**:
1. Document single entry point
2. Add contract assertions (fail-fast)
3. Make alternative paths clearly "not deterministic backtest"
4. Require tests to pass
5. Use reference implementation as canary

## Result

**Hardening is no longer optional - it's mandatory.**

Anyone trying to run a "deterministic backtest" must use `DeterministicBacktest`, which enforces all contracts.
