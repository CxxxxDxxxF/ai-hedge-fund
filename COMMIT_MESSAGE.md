# Commit Message

```
fix: Resolve IndentationError and agent attribution issues in backtest

## Issues Fixed

1. **Peter Lynch IndentationError**
   - Verified all functions have executable code (not just docstrings)
   - Added regression test to prevent docstring-only functions

2. **Deterministic Backtest Agent Attribution**
   - Fixed CORE_AGENTS to use canonical registry keys (warren_buffett, not warren_buffett_agent)
   - Added AGENT_NODE_NAMES mapping for signal lookup
   - Added defensive guards to prevent KeyError when agents are missing
   - Initialize agent_contributions with all 5 canonical agent names

3. **Damodaran NoneType Formatting Crash**
   - Added guards for None values in score and max_score
   - Returns neutral signal when financial data is missing
   - Safe defaults for all formatting variables

## Files Changed

- src/agents/peter_lynch.py: Enhanced to Growth Composite (449 lines changed)
- src/agents/aswath_damodaran.py: Added None guards (54 lines added)
- src/backtesting/deterministic_backtest.py: Fixed agent keys, added defensive guards (new, 511 lines)
- src/backtesting/deterministic_backtest_cli.py: CLI entry point (new)
- tests/test_peter_lynch_functions.py: Regression test (new, 55 lines)
- tests/test_deterministic_backtest_agent_keys.py: Regression test (new, 83 lines)

## Verification

- ✓ python -m compileall src: Zero errors
- ✓ Regression tests pass
- ✓ All functions have executable code
- ✓ CORE_AGENTS uses canonical registry keys only

## Testing

Run in poetry environment:
```bash
HEDGEFUND_NO_LLM=1 poetry run python -m compileall src
HEDGEFUND_NO_LLM=1 poetry run python src/main.py --ticker AAPL --analysts warren_buffett,peter_lynch,aswath_damodaran,momentum,mean_reversion,market_regime
HEDGEFUND_NO_LLM=1 poetry run python src/backtesting/deterministic_backtest.py --tickers AAPL,MSFT --start-date 2024-01-02 --end-date 2024-02-29 --initial-capital 100000
```

Expected results:
- compileall: Zero errors
- main.py: Completes without IndentationError
- backtest: Zero warnings about 'warren_buffett_agent', prints agent attribution for all 5 agents
```
