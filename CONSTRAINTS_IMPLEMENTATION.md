# Capital and Leverage Constraints - Implementation Summary

## Constraints Added

### 1. Portfolio Value Must Never Go Below Zero
- **Pre-trade check**: Validates current NAV > 0
- **Post-trade check**: Validates NAV after trade > 0
- **Daily check**: Validates NAV at end of each day
- **Failure**: Raises RuntimeError (ENGINE FAILURE)

### 2. Max Gross Exposure ≤ 100% of NAV
- **Definition**: Gross exposure = sum of long positions + short positions (notional)
- **Check**: Before trade execution
- **Failure**: Trade rejected (returns False)

### 3. Max Position Size Per Ticker ≤ 20% of NAV
- **Applies to**: Both long and short positions
- **Check**: Before trade execution
- **Calculation**: `position_value / NAV ≤ 0.20`
- **Failure**: Trade rejected (returns False)

### 4. No New Positions If NAV ≤ 50% of Initial Capital
- **Applies to**: New positions only (existing positions can be managed)
- **Check**: Before trade execution
- **Calculation**: `NAV / initial_capital ≤ 0.50` blocks new entries
- **Failure**: Trade rejected (returns False)

## Implementation Details

### Files Modified

1. **`src/backtesting/isolated_agent_backtest.py`**
   - Added `_calculate_gross_exposure()`
   - Added `_check_capital_constraints()`
   - Modified `_execute_trade()` to check constraints
   - Modified `_execute_agent_signal()` to respect 20% max position size
   - Added post-trade NAV validation

2. **`src/backtesting/deterministic_backtest.py`**
   - Added `_calculate_gross_exposure()`
   - Added `_check_capital_constraints()`
   - Modified `_execute_trade()` to check constraints
   - Added pre-trade NAV validation
   - Added post-trade NAV validation

### Constraint Checking Flow

```
Trade Request
    ↓
Check Constraints:
    1. Current NAV > 0?
    2. NAV ≤ 50% and new position? → Reject
    3. Post-trade NAV > 0?
    4. Gross exposure ≤ 100%?
    5. Position size ≤ 20%?
    ↓
If all pass → Execute trade
If any fail → Reject trade (return False)
    ↓
Post-trade validation:
    NAV > 0? → Continue
    NAV ≤ 0? → Raise RuntimeError
```

### Position Sizing (Isolated Agent Backtest)

Position sizing now respects 20% max per ticker:
```python
max_position_value = current_nav * 0.20
target_position_value = (confidence / 100.0) * max_position_value
quantity = int(target_position_value / price)
```

Example:
- NAV = $100,000
- Max position = $20,000 (20%)
- Confidence = 80%
- Target position = $16,000 (80% of max)
- Quantity = $16,000 / price

## Testing

### Re-run Momentum Isolated Test

```bash
./test_momentum_isolated.sh
```

### Expected Behavior

1. **Trades rejected due to constraints**:
   - Logged as rejected (no error)
   - Backtest continues
   - NAV remains valid

2. **NAV validation**:
   - NAV never goes negative
   - Pre-trade checks prevent violations
   - Post-trade checks catch any edge cases

3. **Position sizes**:
   - No position exceeds 20% of NAV
   - Position sizing respects limit

4. **Gross exposure**:
   - Never exceeds 100% of NAV
   - Long + short positions capped

5. **New positions blocked**:
   - When NAV ≤ 50% of initial capital
   - Existing positions can still be managed

## Verification

After running the test, verify:
- No "ENGINE FAILURE: Portfolio value went negative" errors
- Trades may be rejected (expected if constraints violated)
- NAV stays positive throughout
- Position sizes respect 20% limit
- Gross exposure respects 100% limit

## Notes

- **No strategy changes**: Agent signals unchanged
- **Deterministic**: Same constraints, same results
- **Realistic**: Enforces real-world risk limits
- **Execution layer only**: Constraints at trade execution, not signal generation
