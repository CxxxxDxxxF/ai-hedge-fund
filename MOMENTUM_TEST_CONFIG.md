# Momentum Agent - Isolated Test Configuration

## Agent Status

**Momentum Agent**: ✅ CANDIDATE FOR ISOLATED TEST

**Signal Generation**:
- Pure price-based (20-day momentum)
- No external data required
- Always deterministic (rule-based)
- Generates meaningful signals: bullish/bearish/neutral

## Test Configuration

### Command

```bash
./test_momentum_isolated.sh
```

Or manually:

```bash
HEDGEFUND_NO_LLM=1 poetry run python src/backtesting/isolated_agent_backtest.py \
    --agent momentum \
    --tickers AAPL,MSFT \
    --start-date 2020-01-02 \
    --end-date 2024-12-30 \
    --initial-capital 100000
```

### Parameters

- **Agent**: `momentum` (ONLY - no other agents)
- **Tickers**: `AAPL,MSFT` (tickers with CSV price data)
- **Start Date**: `2020-01-02` (matches CSV data availability)
- **End Date**: `2024-12-30` (matches CSV data availability)
- **Initial Capital**: `$100,000`
- **Seed**: `42` (deterministic)

### Rules

✅ Momentum agent ONLY
✅ No aggregation
✅ No portfolio manager
✅ Direct signal execution
✅ No parameter tuning
✅ Same rules throughout
✅ Real historical prices from PriceCache

### Expected Output

```
================================================================================
ISOLATED AGENT BACKTEST - MOMENTUM
================================================================================
Agent: momentum (ONLY - no aggregation, no other agents)
Period: 2020-01-02 to 2024-12-30
Tickers: AAPL, MSFT
Initial Capital: $100,000.00
Deterministic Seed: 42
================================================================================

Total trading days: 1257

Processing 2020-01-02 (1/1257)...
  Got prices for 2/2 tickers
  Getting agent signal...
  Signal executed
  Day 1 complete. Portfolio value: $100,000.00
...
```

### Acceptance Criteria

**PASS** if:
- Excess return > 0% (beats buy-and-hold)
- Max drawdown < buy-and-hold drawdown
- After transaction costs

**FAIL** if:
- Excess return ≤ 0%
- Max drawdown ≥ buy-and-hold drawdown
- Or any other failure condition

### Next Steps

**If PASSES**:
- Document results
- Proceed to Mean Reversion isolated test
- Do NOT add agents or tune parameters

**If FAILS**:
- Document results
- STOP
- Do NOT tune parameters
- Do NOT add agents
- Accept the result

## Notes

- Momentum agent uses 20-day price momentum
- Signals: >5% strong bullish, >2% moderate bullish, <-5% strong bearish, <-2% moderate bearish
- Requires 20+ days of price data
- Pure price-based - no external data needed
