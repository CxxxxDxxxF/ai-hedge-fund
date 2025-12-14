# PROFIT STRESS REPORT
**Date:** 2025-01-XX  
**Mode:** PROFIT STRESS TESTING  
**Role:** Quant Engineer (Funded-Account Survival)

---

## EXECUTION PARAMETERS

### Instrument Tested
- **Symbol:** ES (E-mini S&P 500)
- **Data Source:** `src/data/prices/ES.csv`
- **Date Range Available:** 2024-01-02 to 2024-01-31 (22 trading days)

### Friction Parameters (Fixed)
- **Commission per trade:** $2.00
- **Slippage:** 5.0 bps (0.05%)
- **Spread:** 2.0 bps (0.02%)
- **Total friction per trade:** ~0.07% + $2.00 commission

### Strategy Parameters (TopstepStrategy - Frozen)
- **Risk per trade:** 0.25% of account value
- **Max risk/reward:** 1.5R
- **Max trades per day:** 1
- **Max loss per day:** 0.5R
- **Opening range:** First 15 minutes (9:30-9:45)
- **Trading window end:** 10:30 AM (60 minutes after open)

### Strategy Requirements (Constraints)
- **ATR Lookback:** 20 days minimum for market regime filter
- **ATR Filter:** Current ATR(14) must be above 20-day median
- **Opening Range Break:** Price must break OR high/low and close outside range
- **Pullback Entry:** 50-70% retrace of breakout candle with engulfing pattern

---

## STRESS WINDOWS

### Window Selection Methodology

Given limited data (22 trading days), selected 4 non-overlapping windows:

| Window | Name | Start Date | End Date | Days | Rationale |
|--------|------|------------|----------|------|------------|
| A | Baseline (Typical Conditions) | 2024-01-08 | 2024-01-12 | 5 | Middle period, typical market conditions |
| B | High Volatility | 2024-01-02 | 2024-01-05 | 4 | Early period with highest ATR ($30.00) |
| C | Sideways/Chop | 2024-01-15 | 2024-01-19 | 5 | Lower volatility period, potential choppy action |
| D | Strong Trend | 2024-01-22 | 2024-01-31 | 8 | Continuation of uptrend, highest trend strength |

**Note:** All windows are shorter than the 20-day ATR lookback requirement, which prevents the strategy from trading.

---

## TEST RESULTS

### Funded Account Thresholds

| Threshold | Limit | Description |
|-----------|-------|-------------|
| Max Drawdown | 5.0% | Maximum portfolio drawdown |
| Largest Losing Day | 1.0% | Maximum single-day loss |
| Max Losing Streak | 3 days | Maximum consecutive losing days |
| Min Profit Factor | 1.0 | Gross profit / gross loss |
| Max Time to Recovery | 30 days | Days from drawdown trough to prior peak |

---

### Results Table

| Window | Period | Final NAV | Cumulative PnL | Max DD % | Total Trades | Win Rate % | Result | Failures |
|--------|--------|-----------|-----------------|----------|-------------|------------|--------|----------|
| A_BASELINE | 2024-01-08 to 2024-01-12 | $100,000.00 | $0.00 | 0.00% | 0 | 0.0% | **FAIL** | Profit factor 0.00 below limit 1.0 |
| B_HIGH_VOL | 2024-01-02 to 2024-01-05 | $100,000.00 | $0.00 | 0.00% | 0 | 0.0% | **FAIL** | Profit factor 0.00 below limit 1.0 |
| C_SIDEWAYS | 2024-01-15 to 2024-01-19 | $100,000.00 | $0.00 | 0.00% | 0 | 0.0% | **FAIL** | Profit factor 0.00 below limit 1.0 |
| D_STRONG_TREND | 2024-01-22 to 2024-01-31 | $100,000.00 | $0.00 | 0.00% | 0 | 0.0% | **FAIL** | Profit factor 0.00 below limit 1.0 |

### Detailed Metrics Per Window

#### Window A: Baseline (Typical Conditions)
- **Period:** 2024-01-08 to 2024-01-12 (5 days)
- **Final NAV:** $100,000.00
- **Cumulative PnL:** $0.00
- **Max Drawdown:** 0.00%
- **Total Trades:** 0
- **Win Rate:** 0.0%
- **Total Commissions:** $0.00
- **Total Slippage Cost:** $0.00
- **% Profitable Days:** 0.0%
- **Largest Losing Day:** 0.00%
- **Max Losing Streak:** 0 days
- **Time to Recovery:** 0 days
- **Profit Factor:** 0.00
- **Result:** **FAIL** (Profit factor below limit)

#### Window B: High Volatility
- **Period:** 2024-01-02 to 2024-01-05 (4 days)
- **Final NAV:** $100,000.00
- **Cumulative PnL:** $0.00
- **Max Drawdown:** 0.00%
- **Total Trades:** 0
- **Win Rate:** 0.0%
- **Total Commissions:** $0.00
- **Total Slippage Cost:** $0.00
- **% Profitable Days:** 0.0%
- **Largest Losing Day:** 0.00%
- **Max Losing Streak:** 0 days
- **Time to Recovery:** 0 days
- **Profit Factor:** 0.00
- **Result:** **FAIL** (Profit factor below limit)

#### Window C: Sideways/Chop
- **Period:** 2024-01-15 to 2024-01-19 (5 days)
- **Final NAV:** $100,000.00
- **Cumulative PnL:** $0.00
- **Max Drawdown:** 0.00%
- **Total Trades:** 0
- **Win Rate:** 0.0%
- **Total Commissions:** $0.00
- **Total Slippage Cost:** $0.00
- **% Profitable Days:** 0.0%
- **Largest Losing Day:** 0.00%
- **Max Losing Streak:** 0 days
- **Time to Recovery:** 0 days
- **Profit Factor:** 0.00
- **Result:** **FAIL** (Profit factor below limit)

#### Window D: Strong Trend
- **Period:** 2024-01-22 to 2024-01-31 (8 days)
- **Final NAV:** $100,000.00
- **Cumulative PnL:** $0.00
- **Max Drawdown:** 0.00%
- **Total Trades:** 0
- **Win Rate:** 0.0%
- **Total Commissions:** $0.00
- **Total Slippage Cost:** $0.00
- **% Profitable Days:** 0.0%
- **Largest Losing Day:** 0.00%
- **Max Losing Streak:** 0 days
- **Time to Recovery:** 0 days
- **Profit Factor:** 0.00
- **Result:** **FAIL** (Profit factor below limit)

---

## ROOT CAUSE ANALYSIS

### Why No Trades Occurred

**Primary Constraint:** TopstepStrategy requires **20 days of historical data** for the ATR-based market regime filter.

**Test Window Lengths:**
- Window A: 5 days
- Window B: 4 days
- Window C: 5 days
- Window D: 8 days

**All windows are shorter than the 20-day ATR lookback requirement.**

**Strategy Behavior:**
1. `_check_market_regime()` is called first
2. Requires `len(df) >= ATR_LOOKBACK_DAYS + 1` (21 days minimum)
3. All test windows have < 21 days of data
4. Filter returns: `(False, "Insufficient data for regime filter")`
5. Strategy returns `{"action": "hold", "quantity": 0, "confidence": 0, "reasoning": "Market regime filter: Insufficient data for regime filter"}`

**This is expected behavior.** The strategy correctly refuses to trade when data requirements are not met.

---

## PASS / FAIL EVALUATION

### Summary

| Window | Result | Reason |
|--------|--------|--------|
| A_BASELINE | **FAIL** | No trades (insufficient data for ATR filter) |
| B_HIGH_VOL | **FAIL** | No trades (insufficient data for ATR filter) |
| C_SIDEWAYS | **FAIL** | No trades (insufficient data for ATR filter) |
| D_STRONG_TREND | **FAIL** | No trades (insufficient data for ATR filter) |

**Overall Result:** **FAIL** (0/4 windows passed)

### Failure Mode Analysis

**All windows failed for the same reason:** Strategy cannot trade due to insufficient historical data for the ATR-based market regime filter.

**Threshold Violations:**
- **Profit Factor:** 0.00 < 1.0 (FAIL) - No trades = no profit factor
- **Max Drawdown:** 0.00% < 5.0% (PASS) - No trades = no drawdown
- **Largest Losing Day:** 0.00% < 1.0% (PASS) - No trades = no losses
- **Max Losing Streak:** 0 days < 3 days (PASS) - No trades = no streaks
- **Time to Recovery:** 0 days < 30 days (PASS) - No trades = no recovery needed

---

## WORST WINDOW

**All windows are equivalent** - none produced trades due to the same data constraint.

**Worst Window:** N/A (all windows identical in outcome)

---

## TOP 3 FAILURE MODES

1. **Insufficient Historical Data for ATR Filter**
   - **Frequency:** 4/4 windows (100%)
   - **Impact:** Complete - prevents all trading
   - **Root Cause:** Strategy requires 20 days of data, test windows are 4-8 days
   - **Severity:** CRITICAL

2. **No Trade Execution**
   - **Frequency:** 4/4 windows (100%)
   - **Impact:** Complete - zero PnL, zero metrics
   - **Root Cause:** Market regime filter blocks all trades
   - **Severity:** CRITICAL

3. **Profit Factor Below Threshold**
   - **Frequency:** 4/4 windows (100%)
   - **Impact:** Automatic failure (profit factor = 0.00 < 1.0)
   - **Root Cause:** No trades = no profit factor
   - **Severity:** CRITICAL

---

## OBSERVATIONS

### Data Limitations

1. **Available Data:** Only 22 trading days in ES.csv (2024-01-02 to 2024-01-31)
2. **Strategy Requirement:** 20 days minimum for ATR filter
3. **Test Window Constraint:** Cannot create windows longer than available data
4. **Result:** No windows can satisfy the strategy's data requirements

### Strategy Behavior

1. **Correct Refusal:** Strategy correctly refuses to trade when data is insufficient
2. **No False Signals:** No trades executed despite market conditions
3. **Deterministic:** Behavior is consistent and deterministic
4. **Friction Applied:** Friction parameters are configured but not exercised (no trades)

### Execution Core

1. **Friction Implementation:** Successfully integrated and configurable
2. **Determinism:** Maintained throughout (no randomness)
3. **Capital Constraints:** Enforced (though not tested due to no trades)
4. **Metrics Calculation:** Functional (though all metrics are zero due to no trades)

---

## CONCLUSION

**The Topstep strategy cannot be stress-tested with the available data** due to the 20-day ATR lookback requirement. All test windows are shorter than this requirement, resulting in zero trades across all windows.

**This is a measurement result, not a strategy failure.** The strategy is behaving as designed by refusing to trade when data requirements are not met.

**To conduct a valid stress test, one would need:**
- At least 20+ days of historical data per test window
- Or modify the test methodology to use overlapping windows that include the required lookback period
- Or use a longer historical dataset (e.g., 60+ days) to create non-overlapping windows

**Current Status:** **FAIL** (cannot evaluate strategy performance due to data constraints)

---

**END OF REPORT**
