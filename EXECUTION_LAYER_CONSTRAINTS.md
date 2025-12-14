# Execution-Layer Risk Constraints

## Overview

Strict execution-layer risk constraints have been implemented in the isolated agent backtesting engine. These constraints are enforced at the trade execution level, **not** at the signal generation level, ensuring realistic risk management without modifying agent logic.

## Constraints Implemented

### 1. Portfolio NAV Must Never Go Below Zero

**Enforcement:**
- Pre-trade check: `_check_capital_constraints()` validates NAV > 0 before any trade
- Post-trade check: `_execute_trade()` validates NAV after execution
- Daily check: `run()` validates NAV at end of each day
- **If NAV ≤ 0**: Forces liquidation and stops backtest

**Implementation:**
```python
if portfolio_value <= 0:
    self._force_liquidation(date_str, prices)
    break  # Stop backtest
```

### 2. Max Gross Exposure ≤ 100% of NAV

**Definition:**
- Gross exposure = sum of long positions + short positions (notional value)

**Enforcement:**
- Checked in `_check_capital_constraints()` before trade execution
- Trade rejected if would exceed 100% of NAV

**Calculation:**
```python
gross_exposure = sum(long_positions) + sum(short_positions)
if gross_exposure / NAV > 1.0:
    reject_trade()
```

### 3. Max Position Size ≤ 20% of NAV Per Ticker

**Enforcement:**
- Checked in `_check_capital_constraints()` before trade execution
- Applied to both long and short positions
- Position sizing in `_execute_agent_signal()` respects this limit

**Implementation:**
```python
max_position_value = current_nav * 0.20
target_position_value = (confidence / 100.0) * max_position_value
quantity = int(target_position_value / price)
```

### 4. No New Positions If NAV ≤ 50% of Initial Capital

**Enforcement:**
- Checked in `_check_capital_constraints()` before trade execution
- Only blocks **new** positions (existing positions can be managed)
- Allows position management even when underwater

**Logic:**
```python
if nav_pct <= 0.5:
    is_new_position = (action == "buy" and pos["long"] == 0) or \
                      (action == "short" and pos["short"] == 0)
    if is_new_position:
        reject_trade()
```

### 5. Forced Liquidation If NAV ≤ 0

**Enforcement:**
- Triggered in `run()` when daily NAV check detects NAV ≤ 0
- `_force_liquidation()` closes all positions immediately
- Bypasses constraint checks to ensure positions are closed
- Backtest stops after liquidation

**Process:**
1. Detect NAV ≤ 0
2. Call `_force_liquidation(date, prices)`
3. Close all long positions (sell)
4. Close all short positions (cover)
5. Record final NAV
6. Stop backtest (break from loop)

## Implementation Details

### Files Modified
- `src/backtesting/isolated_agent_backtest.py`

### Key Methods

**`_check_capital_constraints()`**
- Validates all constraints before trade execution
- Returns `(allowed, reason)` tuple
- Called by `_execute_trade()` before any trade

**`_execute_trade()`**
- Checks constraints before executing
- Validates NAV after execution
- Raises RuntimeError if NAV goes negative

**`_force_liquidation()`**
- Closes all positions when NAV ≤ 0
- Bypasses constraint checks (emergency liquidation)
- Records liquidation event in daily_values

**`run()`**
- Daily NAV validation
- Triggers liquidation if NAV ≤ 0
- Stops backtest after liquidation

**`_execute_agent_signal()`**
- Pre-checks NAV before processing signals
- Position sizing respects 20% max per ticker
- Blocks all trades if NAV ≤ 0

## Constraint Flow

```
Trade Request
    ↓
_check_capital_constraints():
    1. NAV > 0?
    2. NAV ≤ 50% and new position? → Reject
    3. Post-trade NAV > 0?
    4. Gross exposure ≤ 100%?
    5. Position size ≤ 20%?
    ↓
If all pass → _execute_trade()
If any fail → Reject trade (return False)
    ↓
Post-trade validation:
    NAV > 0? → Continue
    NAV ≤ 0? → Raise RuntimeError
    ↓
Daily NAV check:
    NAV > 0? → Continue
    NAV ≤ 0? → Force liquidation → Stop backtest
```

## Behavior

### Normal Operation
- Trades that violate constraints are rejected (no error, just rejected)
- NAV stays positive
- Position sizes respect limits
- Gross exposure respects limit

### Constraint Violation
- Trade rejected with reason logged
- Backtest continues
- Agent signals unchanged

### Critical Violation (NAV ≤ 0)
- Forced liquidation triggered
- All positions closed
- Backtest stopped
- Final NAV recorded

## Testing

Re-run the momentum isolated test:

```bash
./test_momentum_isolated.sh
```

### Expected Behavior

**If constraints work correctly:**
- NAV should never go negative (or should trigger liquidation immediately)
- Position sizes should respect 20% limit
- Gross exposure should respect 100% limit
- No new positions when NAV ≤ 50%

**If NAV goes negative:**
- Liquidation should trigger immediately
- Backtest should stop
- Final NAV should be recorded

## Notes

- **No strategy changes**: Agent signals unchanged
- **No parameter tuning**: Constraints are fixed rules
- **Deterministic**: Same constraints, same results
- **Realistic**: Enforces real-world risk limits
- **Execution layer only**: Constraints at trade execution, not signal generation

## Constraint Summary

| Constraint | Check Location | Action on Violation |
|------------|---------------|-------------------|
| NAV > 0 | Pre-trade, post-trade, daily | Reject trade / Force liquidation |
| Gross exposure ≤ 100% | Pre-trade | Reject trade |
| Position size ≤ 20% | Pre-trade | Reject trade |
| No new positions if NAV ≤ 50% | Pre-trade | Reject trade |
| NAV ≤ 0 | Daily check | Force liquidation, stop backtest |
