# Agent Classification - Deterministic Mode

## Classification Results

### ❌ INVALID - Warren Buffett (Value Agent)

**Status**: FALSIFIED
**Reason**: Failed 5-year deterministic backtest with real historical prices
**Evidence**: Does not beat buy-and-hold after costs with lower drawdown
**Action**: Marked as invalid for direct trade execution

**Signal Generation**:
- Requires financial data (balance sheet, income statement, etc.)
- Has rule-based fallback but insufficient edge
- Cannot operate on price data alone

---

### ✅ CANDIDATE - Momentum Agent

**Status**: READY FOR ISOLATED TEST
**Signal Generation**: Pure price-based
- Uses 20-day price momentum
- No external data required
- Always deterministic (rule-based)
- Generates: bullish/bearish/neutral signals with confidence

**Implementation**: `src/agents/momentum.py`
- `calculate_momentum_signal_rule_based()` - pure price calculation
- Thresholds: >5% strong, >2% moderate, <-5% strong bearish, <-2% moderate bearish

---

### ✅ CANDIDATE - Mean Reversion Agent

**Status**: READY FOR ISOLATED TEST (after momentum)
**Signal Generation**: Pure price-based
- Uses RSI, moving averages (20-day, 50-day)
- No external data required
- Always deterministic (rule-based)
- Generates: bullish/bearish/neutral signals with confidence

**Implementation**: `src/agents/mean_reversion.py`
- `calculate_mean_reversion_signal_rule_based()` - pure price calculation
- Requires 50+ days of price data

---

### ⚠️ PARTIAL - Peter Lynch (Growth Agent)

**Status**: HAS PRICE-BASED FALLBACK
**Signal Generation**: Price-based fallback in deterministic mode
- Uses 60-day price momentum as growth proxy
- Falls back when external data unavailable
- Not pure price-based (prefers financial data)

**Note**: Can be tested after momentum/mean reversion if needed

---

### ❌ REQUIRES EXTERNAL DATA - Other Agents

**Agents requiring financial data** (not testable in pure price mode):
- Aswath Damodaran (Valuation) - requires financial statements
- Other value agents - require fundamental data

---

## Testing Priority

1. **Momentum Agent** - Next isolated test (pure price-based)
2. **Mean Reversion Agent** - After momentum (pure price-based)
3. **Peter Lynch** - If needed (has price fallback)

## Notes

- Only agents that generate signals from price data alone can be tested in isolation
- Agents requiring external data cannot be properly tested without that data
- Warren Buffett agent is marked invalid and should not be tuned or repaired
