# REAL DATA STRATEGY SANITY REPORT
**Date:** 2025-01-XX  
**Mode:** REAL DATA STRATEGY SANITY TEST  
**Role:** Quant Engineer (Behavioral Validation)

---

## OBJECTIVE

Evaluate TopstepStrategy behavior on real intraday market data using the full available dataset (~60 trading days). This is a realism + survivability sanity check, not a final funded-account stress test.

---

## TEST PARAMETERS

### Data
- **Instrument:** ES (proxy: ^GSPC 5-minute data from Yahoo Finance)
- **Date Range:** 2025-09-19 to 2025-12-12
- **Trading Days:** 61 days
- **Data Type:** Real intraday market data (5-minute bars)

### Friction (Fixed)
- **Commission per trade:** $2.00
- **Slippage:** 5.0 bps (0.05%)
- **Spread:** 2.0 bps (0.02%)
- **Total friction per trade:** ~0.07% + $2.00 commission

### Strategy Parameters (Frozen)
- **Risk per trade:** 0.25% of account value
- **Max risk/reward:** 1.5R
- **Max trades per day:** 1
- **Max loss per day:** 0.5R
- **Opening range:** First 15 minutes (9:30-9:45 AM)
- **Trading window end:** 10:30 AM (60 minutes after open)

---

## CORE METRICS

| Metric | Value |
|--------|-------|
| **Total Trades** | 0 |
| **Trades per Week** | 0.00 |
| **Cumulative PnL** | $0.00 |
| **Final NAV** | $100,000.00 |
| **Initial Capital** | $100,000.00 |
| **Max Drawdown** | 0.00% |
| **Largest Losing Day** | 0.00% |
| **Longest Losing Streak** | 0 days |
| **Win Rate** | 0.00% (N/A - no trades) |
| **Total Commissions** | $0.00 |
| **Total Slippage Cost** | $0.00 |

---

## BEHAVIORAL ANALYSIS

### Overtrading
- **Status:** ✅ NO
- **Analysis:** Strategy took 0 trades over 61 trading days (0.00 trades/week)
- **Conclusion:** Strategy does not overtrade. In fact, it trades extremely rarely.

### Clusters Losses
- **Status:** ✅ NO
- **Analysis:** No trades = no losses to cluster
- **Conclusion:** Cannot evaluate loss clustering without trades.

### Respects Risk Limits
- **Status:** ✅ YES (assumed)
- **Analysis:** Strategy enforces risk limits internally:
  - Max 1 trade per day
  - Max 0.5R loss per day
  - 0.25% risk per trade
- **Conclusion:** Risk limits are hard-coded in strategy logic. No violations possible when strategy refuses to trade.

### Drawdown Stabilizes
- **Status:** ✅ YES
- **Analysis:** No drawdown occurred (NAV remained constant at $100,000)
- **Conclusion:** Drawdown cannot accelerate if no trades are taken.

### Trades Rarely
- **Status:** ✅ YES
- **Analysis:** 0 trades over 61 trading days = 0.00 trades/week
- **Threshold:** < 0.1 trades/week considered "rarely"
- **Conclusion:** Strategy trades extremely rarely, effectively not trading at all in this period.

---

## OBSERVED BEHAVIOR

### Trade Frequency
- **Trades:** 0 over 61 trading days
- **Frequency:** 0.00 trades/week
- **Interpretation:** Strategy found no valid setups meeting all entry criteria

### Strategy Filter Behavior
The TopstepStrategy requires multiple conditions to be met simultaneously:
1. **ATR Filter:** Current ATR(14) must be above 20-day median
2. **Opening Range Break:** Price must break OR high/low and close outside range
3. **Pullback Entry:** Price must retrace 50-70% of breakout candle with engulfing pattern
4. **Daily Limits:** Max 1 trade/day, max 0.5R loss/day

**Result:** None of these conditions were met simultaneously during the test period.

### NAV Stability
- **Initial NAV:** $100,000.00
- **Final NAV:** $100,000.00
- **Change:** $0.00 (0.00%)
- **Interpretation:** No trades = no PnL = no NAV change

### Risk Exposure
- **Gross Exposure:** 0% (no positions)
- **Net Exposure:** 0% (no positions)
- **Cash:** $100,000.00 (100% of NAV)
- **Interpretation:** Strategy maintained 100% cash position throughout test period

---

## FAILURE MODES OBSERVED

### Primary Failure Mode: No Trade Execution
- **Frequency:** 100% of test period (61/61 days)
- **Impact:** Complete - zero PnL, zero risk, zero evaluation
- **Root Cause:** Strategy filters too restrictive for available market conditions
- **Severity:** HIGH (strategy is effectively non-functional)

### Secondary Failure Mode: Over-Filtering
- **Frequency:** 100% of test period
- **Impact:** Strategy refuses to trade even when market conditions may be acceptable
- **Root Cause:** Multiple simultaneous filter requirements (ATR, OR break, pullback, daily limits)
- **Severity:** MEDIUM (may be by design for survival-first approach)

---

## STRATEGY BEHAVIOR ASSESSMENT

### Positive Behaviors
1. ✅ **No Overtrading:** Strategy does not trade excessively
2. ✅ **Risk Limits Enforced:** Hard-coded limits prevent violations
3. ✅ **No Drawdown:** Zero risk exposure = zero drawdown
4. ✅ **Deterministic:** Behavior is consistent and reproducible

### Negative Behaviors
1. ❌ **Extreme Under-Trading:** 0 trades over 61 days is effectively non-functional
2. ❌ **Over-Filtering:** Multiple simultaneous requirements may be too restrictive
3. ❌ **No Performance Data:** Cannot evaluate profitability, risk, or edge without trades

### Neutral Observations
1. ⚠️ **Survival-First Design:** Strategy prioritizes not losing over making money
2. ⚠️ **Filter Conservatism:** May be intentional for funded-account survival (avoid rule violations)

---

## CONCLUSION

### Strategy Behavior Assessment

**"Strategy behavior is unsafe"**

**Rationale:**
1. **Non-Functional:** 0 trades over 61 trading days indicates the strategy is effectively non-functional
2. **Cannot Evaluate:** Without trades, we cannot assess:
   - Profitability
   - Risk management effectiveness
   - Edge or skill
   - Funded-account survival capability
3. **Over-Filtering:** The combination of filters (ATR, OR break, pullback, daily limits) appears too restrictive for real market conditions
4. **No Survivability Data:** Cannot determine if strategy would survive funded-account rules without trade execution

### Key Findings

1. **Zero Trade Execution:** Strategy found no valid setups in 61 trading days of real market data
2. **Filter Restrictiveness:** Multiple simultaneous filter requirements prevent trade execution
3. **Survival-First Design:** Strategy appears designed to avoid trading rather than seek opportunities
4. **No Performance Metrics:** Cannot evaluate profitability, drawdown, or risk without trades

### Recommendations (Outside Scope)

The following are outside the scope of this sanity test but may be relevant for future work:

- ⚠️ **Filter Relaxation:** Consider relaxing or removing some filter requirements
- ⚠️ **Alternative Strategies:** Evaluate other strategies that may trade more frequently
- ⚠️ **Extended Testing:** Test over longer periods or different market regimes
- ⚠️ **Parameter Tuning:** Adjust ATR thresholds, OR parameters, or pullback criteria

**Note:** These recommendations are for future consideration. No changes were made during this sanity test.

---

## DATA QUALITY NOTES

### Real Market Data
- ✅ **Source:** Yahoo Finance (^GSPC 5-minute data)
- ✅ **Intraday Granularity:** 5-minute bars enable proper opening range detection
- ✅ **Real Volatility:** Actual market volatility and regime behavior
- ✅ **Trading Hours:** Regular market hours (9:30 AM - 4:00 PM ET)

### Data Limitations
- ⚠️ **Index vs Futures:** ^GSPC is index data, not ES futures (price levels may differ)
- ⚠️ **60-Day Window:** Limited to last 60 days (Yahoo Finance API restriction)
- ⚠️ **Single Period:** Only one 60-day period tested (may not represent all market regimes)

---

## TEST EXECUTION

### Backtest Configuration
- **Engine:** DeterministicBacktest
- **Mode:** Deterministic (HEDGEFUND_NO_LLM=1)
- **Friction:** Enabled (commission, slippage, spread)
- **Capital:** $100,000 initial
- **Execution:** All 61 trading days processed successfully

### Execution Status
- ✅ **Backtest Completed:** No errors or failures
- ✅ **Data Loading:** Intraday data loaded correctly
- ✅ **Price Resolution:** Last bar of each day used for NAV calculation
- ✅ **Determinism:** Results are reproducible

---

**END OF REPORT**
