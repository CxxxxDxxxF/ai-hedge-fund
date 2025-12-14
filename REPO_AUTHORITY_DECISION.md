# Repository Authority Decision

## Decision: This Repo is AUTHORITATIVE

**For deterministic backtesting, this repository is the source of truth.**

## Rationale

1. **Complete Implementation**: We have a fully hardened, proven deterministic backtest
2. **Contracts Defined**: Clear contracts and invariants
3. **Reference Implementation**: Minimal reference loop exists
4. **Proven Correctness**: Resilience tests verify behavior

## Implications

### If Engine Repo and This Repo Disagree

**This repo is right.**

The deterministic backtest in this repo:
- Has invariant logging
- Has duplicate date guards
- Has determinism enforcement
- Has engine/strategy separation
- Has guaranteed summary printing

If another implementation lacks these, it is incomplete.

### Enforcement Hooks

**Tests are Reusable**:
- `test_backtest_resilience.py` can be run against any backtest implementation
- If another implementation fails these tests, it's not equivalent

**Contracts are Documented**:
- `DETERMINISTIC_BACKTEST_CONTRACT.md` defines what must be true
- Any implementation claiming to be "deterministic backtest" must satisfy these contracts

**Reference Implementation**:
- `reference_loop.py` shows the minimal pattern
- Deviations from this pattern are bugs

### What This Means

1. **New Backtest Implementations**:
   - Must satisfy contracts in `DETERMINISTIC_BACKTEST_CONTRACT.md`
   - Must pass tests in `test_backtest_resilience.py`
   - Must follow pattern in `reference_loop.py`

2. **Changes to This Repo**:
   - Must not violate existing contracts
   - Must pass all resilience tests
   - Must maintain determinism

3. **Integration with Other Systems**:
   - Other systems should use `DeterministicBacktest` from this repo
   - Or implement equivalent that satisfies contracts

## Alternative Implementations

If another repo has a backtest implementation:

**It must**:
- Satisfy all contracts
- Pass all resilience tests
- Produce identical output hashes for identical inputs

**If it doesn't**, it's not a valid deterministic backtest.

## Freeze Status

**This implementation is frozen at `backtest-hardened-v1`**.

Future changes:
- Must not break contracts
- Must pass all tests
- Must maintain determinism
- Must preserve all hardening features

## Reference Documents

- `DETERMINISTIC_BACKTEST_CONTRACT.md` - Contracts that must be satisfied
- `reference_loop.py` - Minimal reference implementation
- `test_backtest_resilience.py` - Tests that must pass
- `POSTMORTEM_BACKTEST_HANG.md` - What we learned

Any implementation claiming to be "deterministic backtest" must satisfy these.
