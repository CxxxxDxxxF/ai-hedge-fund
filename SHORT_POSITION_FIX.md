# Short Position Accounting Fix

## Problem

Portfolio values were going negative in backtests, which should be impossible with capital constraints. The root cause was incorrect accounting for short positions.

## Root Cause

When shorting a stock, the code was:
1. ❌ Only decreasing cash by (margin + costs)
2. ❌ Missing the proceeds from selling the shorted shares

**Correct accounting for shorting:**
1. ✅ Receive proceeds from sale (cash increases)
2. ✅ Put up margin as collateral (cash decreases)
3. ✅ Pay transaction costs (cash decreases)
4. ✅ Net: cash increases by (proceeds - margin - costs)

## Fix Applied

### Files Modified
- `src/backtesting/isolated_agent_backtest.py`
- `src/backtesting/deterministic_backtest.py`

### Changes

**Before (incorrect):**
```python
elif action == "short":
    margin_needed = trade_value * self.margin_requirement
    total_needed = margin_needed + total_cost
    self.portfolio["cash"] -= total_needed  # ❌ Only decreases cash
```

**After (correct):**
```python
elif action == "short":
    margin_needed = trade_value * self.margin_requirement
    total_needed = margin_needed + total_cost
    self.portfolio["cash"] += trade_value  # ✅ Receive proceeds
    self.portfolio["cash"] -= total_needed  # ✅ Pay margin + costs
    # Net: cash increases by (trade_value - margin_needed - total_cost)
```

### NAV Calculation

The NAV calculation for short positions was also clarified:

```python
# Short positions
# When you short, you sold at short_cost_basis and owe shares at current price
# P&L = (sale_price - current_price) * quantity
if pos["short"] > 0:
    short_pnl = (pos["short_cost_basis"] - price) * pos["short"]
    total_value += short_pnl
```

This is correct because:
- You sold at `short_cost_basis` (proceeds already in cash)
- You owe shares worth `current_price * quantity`
- P&L = `(short_cost_basis - current_price) * quantity`
- If price goes up, P&L is negative (loss)
- If price goes down, P&L is positive (gain)

## Impact

This fix ensures:
1. ✅ Cash correctly reflects short sale proceeds
2. ✅ NAV calculation is accurate
3. ✅ Portfolio values should never go negative (unless constraints are violated)
4. ✅ Short positions are properly accounted for

## Testing

Re-run the momentum isolated test:

```bash
./test_momentum_isolated.sh
```

Expected improvements:
- Portfolio values should remain positive (or at least not go deeply negative)
- NAV calculations should be accurate
- Short positions should be properly accounted for

## Notes

- This is a **realism fix**, not a strategy change
- Short accounting now matches real-world mechanics
- Capital constraints should now work correctly with short positions
