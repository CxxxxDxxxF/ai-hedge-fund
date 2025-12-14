# Capital and Leverage Constraints

## Implementation

Strict capital and leverage constraints have been added to the deterministic backtesting execution layer.

### Constraints Enforced

1. **Portfolio value must never go below zero**
   - Pre-trade validation
   - Post-trade validation
   - Raises RuntimeError if violated

2. **Max gross exposure ≤ 100% of NAV**
   - Gross exposure = sum of long positions + short positions (notional)
   - Checked before trade execution
   - Trade rejected if would exceed 100%

3. **Max position size per ticker ≤ 20% of NAV**
   - Applies to both long and short positions
   - Checked before trade execution
   - Trade rejected if would exceed 20%

4. **No new positions if NAV ≤ 50% of initial capital**
   - Prevents new entries when portfolio is severely underwater
   - Only blocks NEW positions (existing positions can be managed)
   - Trade rejected if NAV ≤ 50% and position is new

### Implementation Details

**Files Modified**:
- `src/backtesting/isolated_agent_backtest.py`
- `src/backtesting/deterministic_backtest.py`

**New Methods**:
- `_calculate_gross_exposure()` - Calculates total gross exposure
- `_check_capital_constraints()` - Validates all constraints before trade

**Modified Methods**:
- `_execute_trade()` - Now checks constraints before executing
- `_execute_agent_signal()` - Position sizing respects 20% max per ticker

### Constraint Logic

```python
def _check_capital_constraints(ticker, action, quantity, price, prices):
    # 1. NAV must be > 0
    if current_nav <= 0:
        return (False, "NAV is zero or negative")
    
    # 4. No new positions if NAV ≤ 50%
    if nav_pct <= 0.5 and is_new_position:
        return (False, "NAV ≤ 50% - no new positions")
    
    # 1. Post-trade NAV must be > 0
    if post_trade_nav <= 0:
        return (False, "Trade would make NAV negative")
    
    # 2. Gross exposure ≤ 100% of NAV
    if gross_exposure_pct > 1.0:
        return (False, "Gross exposure would exceed 100%")
    
    # 3. Position size ≤ 20% of NAV
    if position_pct > 0.20:
        return (False, "Position size would exceed 20%")
    
    return (True, "OK")
```

### Position Sizing

In isolated agent backtest, position sizing now respects constraints:
- Max position value = 20% of NAV
- Confidence scales within this limit
- Example: 80% confidence → 16% of NAV (80% of 20% max)

### Behavior

- **Constraint violations**: Trade is rejected (returns False)
- **No strategy changes**: Agent signals unchanged
- **Deterministic**: Same constraints, same results
- **Realistic**: Enforces real-world risk limits

### Testing

After implementation, re-run momentum isolated test:

```bash
./test_momentum_isolated.sh
```

Expected behavior:
- Trades that would violate constraints are rejected
- NAV never goes negative
- Gross exposure never exceeds 100%
- Position sizes never exceed 20% per ticker
- No new positions when NAV ≤ 50%

### Notes

- Constraints are enforced at execution layer, not signal generation
- Agent signals are unchanged
- This is a realism fix, not a strategy change
- Determinism preserved (same constraints, same results)
