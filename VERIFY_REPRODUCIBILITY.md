# Verifying Backtest Comparison Reproducibility

## How Trades Are Counted

The comparison runner uses a **trade log** mechanism:

1. **TradeTrackingBacktestEngine** extends `BacktestEngine` to track all executed trades
2. During backtest execution, every non-zero trade execution is logged:
   - Date
   - Ticker
   - Action (buy/sell/short/cover)
   - Quantity executed
   - Price
3. **Trade count** = `len(trade_log)` - the exact number of executed trades

This is more accurate than estimating from portfolio state because:
- Counts actual trade executions (not just position changes)
- Handles partial fills correctly
- Tracks all trade types (buy, sell, short, cover)

## Verifying Deterministic Reproducibility

### Command to Test

```bash
# Run comparison twice with same parameters
poetry run python src/compare_backtests.py --tickers AAPL --start-date 2024-01-01 --end-date 2024-01-31 --initial-capital 100000 > run1.log 2>&1
poetry run python src/compare_backtests.py --tickers AAPL --start-date 2024-01-01 --end-date 2024-01-31 --initial-capital 100000 > run2.log 2>&1

# Compare CSV files (excluding timestamp from filename)
# Find the CSV files
CSV1=$(ls -t backtest_comparison_*.csv | head -1)
CSV2=$(ls -t backtest_comparison_*.csv | head -2 | tail -1)

# Compare contents (should be identical)
diff "$CSV1" "$CSV2"

# Compare JSON files
JSON1=$(ls -t backtest_comparison_*.json | head -1)
JSON2=$(ls -t backtest_comparison_*.json | head -2 | tail -1)
diff "$JSON1" "$JSON2"
```

### Expected Results

- **CSV files**: Should be identical (except filename timestamp)
- **JSON files**: Should be identical (except filename timestamp)
- **Markdown files**: Should be identical except for "Generated" timestamp line

### Deterministic Guarantees

1. **Ticker ordering**: Tickers are sorted alphabetically (uppercase)
2. **Strategy ordering**: Strategies are sorted alphabetically
3. **Result ordering**: Results are sorted by strategy name in all outputs
4. **Rounding**: All numeric values use consistent rounding (2 decimals for returns/drawdown, 3 for Sharpe)
5. **HEDGEFUND_NO_LLM**: Set at start of `main()`, ensuring deterministic agent behavior
6. **Trade counting**: Uses exact trade log, not estimates

### Sources of Non-Determinism (Eliminated)

- ✅ **Dictionary iteration order**: Results sorted by strategy name
- ✅ **Ticker input order**: Tickers sorted alphabetically
- ✅ **Strategy execution order**: Strategies sorted alphabetically
- ✅ **LLM randomness**: Disabled via HEDGEFUND_NO_LLM=1
- ✅ **Floating point precision**: Consistent rounding applied

### Remaining Non-Determinism (Expected)

- **Filename timestamps**: Files include timestamp in filename (content is identical)
- **Markdown "Generated" timestamp**: One line in markdown shows generation time (doesn't affect metrics)

