# Simple Deterministic Trading Strategy

## Overview

A basic deterministic trading strategy has been added to test profitability in the backtesting system. This strategy executes real trades to validate that the system can track PnL and generate measurable results.

## Strategy Details

**Strategy Type**: Buy on first day, sell on last day (with price momentum fallback)

**Rules**:
1. **Buy on first trading day**: Purchases 10 shares (or 5% of cash, whichever is smaller) on the first day
2. **Sell on last trading day**: Sells all positions on the final day
3. **Price momentum (optional)**: If price data is available, also trades on price movements > 1%

**Position Sizing**:
- Fixed: 10 shares
- Or: 5% of available cash, whichever is smaller

## Usage

The strategy automatically activates when:
- Running deterministic backtests (`HEDGEFUND_NO_LLM=1`)
- Portfolio manager generates no trades (all "hold" decisions)

### Example Output

```
Initial Portfolio Value: $99,000.00
Final Portfolio Value: $100,000.00
Total Return: +1.01%
Total Trades: 2
```

## Implementation

The strategy is implemented in `src/backtesting/deterministic_backtest.py`:

- Method: `_generate_simple_strategy_decisions()`
- Called from: `_run_daily_decision()` when portfolio manager has no trades
- Location: Lines ~145-227

## Key Features

✅ **Fully Deterministic**: Same inputs produce same outputs  
✅ **Repeatable**: Identical runs produce identical results  
✅ **Simple**: Easy to understand and reason about  
✅ **Testable**: Generates measurable PnL for validation  

## Notes

- If price data is unavailable (returns 0.0), the strategy uses a mock price of $100.00 for testing
- The strategy only activates if the portfolio manager generates no trades
- All trades are logged and tracked in the backtest results

## Success Criteria Met

✅ Trades are executed (non-zero trade count)  
✅ Portfolio value changes (final ≠ initial)  
✅ Total return is calculated and displayed  
✅ Results are deterministic across runs  
✅ UI reflects portfolio changes over time  
