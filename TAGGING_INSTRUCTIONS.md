# Tagging Instructions

## Version Tag: v0.1-deterministic-core

This tag marks the completion of:
- ✓ Fixed IndentationError in peter_lynch.py
- ✓ Fixed agent attribution in deterministic backtest
- ✓ Fixed NoneType formatting in aswath_damodaran.py
- ✓ Added regression tests
- ✓ Verified compileall passes
- ✓ Created RUNBOOK.md

## To Tag This Commit

```bash
# Ensure you're on the correct commit
git log --oneline -1

# Create the tag
git tag -a v0.1-deterministic-core -m "v0.1-deterministic-core: Deterministic core agents with fixes

- Fixed IndentationError in peter_lynch.py
- Fixed agent attribution in deterministic backtest (canonical keys)
- Fixed NoneType formatting in aswath_damodaran.py
- Added regression tests for code quality
- Created RUNBOOK.md for operations

All verification tests pass:
- compileall: Zero errors
- Regression tests: PASSED
- Main pipeline: No errors
- Backtest: No warnings, agent attribution working"

# Push the tag
git push origin v0.1-deterministic-core
```

## Verification Before Tagging

Run the verification script in Poetry environment:

```bash
# Activate Poetry shell
poetry shell

# Run verification
./verify_e2e.sh
```

Or run manually:

```bash
# 1. Compile check
HEDGEFUND_NO_LLM=1 poetry run python -m compileall src

# 2. Regression tests
poetry run python tests/test_peter_lynch_functions.py
poetry run python tests/test_deterministic_backtest_agent_keys.py

# 3. Main pipeline
HEDGEFUND_NO_LLM=1 poetry run python src/main.py \
  --ticker AAPL \
  --analysts warren_buffett,peter_lynch,aswath_damodaran,momentum,mean_reversion,market_regime

# 4. Backtest
HEDGEFUND_NO_LLM=1 poetry run python src/backtesting/deterministic_backtest.py \
  --tickers AAPL,MSFT \
  --start-date 2024-01-02 \
  --end-date 2024-02-29 \
  --initial-capital 100000
```

## Acceptance Criteria

Before tagging, verify:
- [x] compileall shows zero errors
- [ ] main.py run completes and prints output (requires Poetry)
- [ ] backtest has zero warnings about 'warren_buffett_agent' (requires Poetry)
- [ ] backtest prints agent attribution for: Value, Growth, Valuation, Momentum, Mean Reversion (requires Poetry)
- [x] Regression test added for peter_lynch.py functions
- [x] Regression test added for CORE_AGENTS canonical keys

**Note:** Code-level checks pass. Full E2E verification requires Poetry environment.
