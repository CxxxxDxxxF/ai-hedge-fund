# Quantitative Research Status

## Agent Classification

### ❌ INVALID - Warren Buffett (Value Agent)

**Status**: FALSIFIED
**Evidence**: Failed 5-year deterministic backtest (2020-01-02 to 2024-12-30)
- Does not beat buy-and-hold after costs
- Higher drawdown than buy-and-hold
- No standalone edge detected

**Action Taken**: 
- Marked as invalid for direct trade execution
- Added status note in agent docstring
- **DO NOT TUNE OR REPAIR** - agent has no edge

**Signal Requirements**: External financial data (balance sheet, income statement, etc.)

---

### ✅ CANDIDATE - Momentum Agent

**Status**: READY FOR ISOLATED TEST
**Signal Generation**: Pure price-based (20-day momentum)
- No external data required
- Always deterministic (rule-based)
- Uses `calculate_momentum_signal_rule_based()`

**Signal Logic**:
- Strong bullish: momentum > 5%
- Moderate bullish: momentum > 2%
- Strong bearish: momentum < -5%
- Moderate bearish: momentum < -2%
- Neutral: momentum between -2% and 2%

**Test Configuration**: Ready (see below)

---

### ✅ CANDIDATE - Mean Reversion Agent

**Status**: READY FOR ISOLATED TEST (after momentum)
**Signal Generation**: Pure price-based (RSI + moving averages)
- No external data required
- Always deterministic (rule-based)
- Uses `calculate_mean_reversion_signal_rule_based()`
- Requires 50+ days of price data

---

### ⚠️ PARTIAL - Peter Lynch (Growth Agent)

**Status**: HAS PRICE-BASED FALLBACK
**Signal Generation**: Price-based fallback in deterministic mode
- Uses 60-day price momentum as growth proxy
- Not pure price-based (prefers financial data)
- Can be tested if needed after momentum/mean reversion

---

## Momentum Agent - Isolated Test

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

### Test Parameters

- **Agent**: `momentum` (ONLY)
- **Tickers**: `AAPL,MSFT` (tickers with CSV price data)
- **Period**: `2020-01-02` to `2024-12-30` (1,257 trading days)
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

### Acceptance Criteria

**PASS** if:
- Excess return > 0% (beats buy-and-hold)
- Max drawdown < buy-and-hold drawdown
- After transaction costs

**FAIL** if:
- Excess return ≤ 0%
- Max drawdown ≥ buy-and-hold drawdown

### Expected Behavior

- Uses real historical prices from CSV files
- Logs: "Got prices for 2/2 tickers"
- Generates momentum signals based on 20-day price changes
- Executes trades directly (no aggregation)
- Compares against equal-weighted buy-and-hold

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

---

## Technical Details

### Price Data

- **Source**: CSV files in `src/data/prices/`
- **Available**: `AAPL.csv`, `MSFT.csv`
- **Date Range**: 2020-01-02 to 2024-12-30
- **Format**: `date,open,high,low,close,volume`

### PriceCache Integration

- `PriceCache.get()` - Returns dict with price fields or None
- `get_prices()` - Uses PriceCache in deterministic mode
- Both backtests use PriceCache directly

### Determinism

- Seed: 42 (fixed)
- No external API calls
- No randomness
- Reproducible results

---

## Research Protocol

1. **Test one agent at a time** in complete isolation
2. **Use real historical prices** from PriceCache
3. **No parameter tuning** - same rules throughout
4. **Compare against buy-and-hold** - honest benchmark
5. **Accept results** - do not tune until green
6. **Document findings** - pass or fail, no speculation

---

## Current Status

- ✅ Warren Buffett: FALSIFIED (marked invalid)
- ⏳ Momentum: Ready for test
- ⏳ Mean Reversion: Waiting (after momentum)
- ⏳ Peter Lynch: Optional (has price fallback)
