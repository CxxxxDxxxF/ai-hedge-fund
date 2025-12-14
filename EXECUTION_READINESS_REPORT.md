# EXECUTION READINESS REPORT
**Date:** 2025-01-XX  
**Mode:** EXECUTION READINESS AUDIT  
**Role:** Quant Engineer / Systems Auditor

---

## EXECUTIVE SUMMARY

**VERDICT: ❌ NOT READY**

The system is **NOT ready** to correctly backtest an intraday strategy on real market data. Critical gaps exist in data handling, execution engine granularity, and strategy expectations that prevent proper intraday strategy evaluation.

**Primary Blockers:**
1. **Data Time Loss** (BLOCKER): Intraday timestamps are stripped when converting to Price objects
2. **Daily Execution Loop** (BLOCKER): Backtest iterates over business days, not intraday bars
3. **Strategy Expectation Mismatch** (BLOCKER): TopstepStrategy expects intraday bars but receives daily aggregates
4. **No Intraday Execution** (BLOCKER): Trades execute once per day, cannot execute intraday
5. **No Stop/Target Execution** (BLOCKER): Stop losses and profit targets are never checked or executed

---

## PHASE 1: DATA READINESS

### ✅ What Is Correct

- **Intraday Data Resolution:** ES.csv contains 5-minute bars with timestamps (e.g., "2025-09-19 09:30:00")
- **OHLC Integrity:** All OHLC relationships are valid (high >= low, etc.)
- **Volume Column:** Present and numeric
- **Chronological Sorting:** Data is sorted ascending by timestamp
- **No Missing Bars in OR Window:** Opening range bars (9:30-9:45) are present
- **Deterministic Reload:** PriceCache loads data deterministically (hash-stable)

### ❌ What Is Missing or Broken

#### BLOCKER: Time Component Loss in Data Conversion
- **File:** `src/tools/api.py::get_prices()` (line 88)
- **Issue:** When converting DataFrame to Price objects, datetime is converted to date string:
  ```python
  time=date.strftime("%Y-%m-%d")  # LOSES TIME COMPONENT!
  ```
- **Impact:** Intraday timestamps like "2025-09-19 09:30:00" become "2025-09-19", losing all time information
- **Severity:** BLOCKER
- **Type:** Data issue

#### HIGH: No Timezone Handling
- **File:** `src/data/prices/ES.csv`
- **Issue:** Timestamps are naive (no timezone). Assumes ET but not explicit.
- **Impact:** Ambiguous timezone could cause issues with market hours detection
- **Severity:** HIGH
- **Type:** Data issue

#### MEDIUM: PriceCache Date Range Filtering
- **File:** `src/data/price_cache.py::get_prices_for_range()` (line 225)
- **Issue:** Filters by `df.index >= start_ts & df.index <= end_ts` where timestamps are datetime objects
- **Impact:** Works for intraday data but may have edge cases at day boundaries
- **Severity:** MEDIUM
- **Type:** Data issue

### Explicit Confirmations

- **Can PriceCache serve intraday slices by day?** ✅ YES - `get_prices_for_range()` returns all bars for a date range, including intraday bars
- **Any implicit daily assumptions?** ❌ YES - `get_prices()` strips time component when converting to Price objects

---

## PHASE 2: EXECUTION ENGINE COMPATIBILITY

### ✅ What Is Correct

- **Trade Execution Location:** `_execute_trade()` in `deterministic_backtest.py` (line 540)
- **Friction Application:** Applied at execution time (slippage, spread, commission)
- **Capital Constraints:** Enforced post-trade (NAV > 0, gross <= 100%, position <= 20%)

### ❌ What Is Missing or Broken

#### BLOCKER: Daily Iteration Loop
- **File:** `src/backtesting/deterministic_backtest.py::run()` (line 1081)
- **Issue:** Loop iterates over business days only:
  ```python
  dates = pd.bdate_range(self.start_date, self.end_date)
  for i in range(total_days):
      date = dates[i]
      date_str = date.strftime("%Y-%m-%d")
      # Process one day at a time
  ```
- **Impact:** Strategy sees only one decision point per day, not intraday bars
- **Severity:** BLOCKER
- **Type:** Engine issue

#### BLOCKER: No Intraday Execution
- **File:** `src/backtesting/deterministic_backtest.py::_run_daily_decision()` (line 806)
- **Issue:** `_run_daily_decision()` is called once per business day, not per intraday bar
- **Impact:** Trades can only execute at end-of-day, not during trading hours
- **Severity:** BLOCKER
- **Type:** Engine issue

#### BLOCKER: Strategy Never Sees Multiple Bars Per Day
- **File:** `src/backtesting/deterministic_backtest.py::_run_daily_decision()` (line 806)
- **Issue:** Strategy is called once per day with a single price point (last bar of day)
- **Impact:** Strategy cannot see sequential price action, opening range, or intraday patterns
- **Severity:** BLOCKER
- **Type:** Engine issue

#### BLOCKER: "1 Trade Per Day" Enforced at Wrong Granularity
- **File:** `src/agents/topstep_strategy.py::_check_daily_limits()` (line 298)
- **Issue:** Daily limits are checked, but execution happens once per day, not per bar
- **Impact:** Cannot enforce "1 trade per day" correctly if execution were intraday
- **Severity:** BLOCKER
- **Type:** Engine issue

#### BLOCKER: No Stop Loss / Target Execution
- **File:** `src/backtesting/deterministic_backtest.py`
- **Issue:** No logic to check if stop loss or profit target is hit intraday
- **Impact:** Positions are never exited via stops or targets, only via strategy signals
- **Severity:** BLOCKER
- **Type:** Engine issue

### Adapters/Shims/Hacks

#### HACK: Intraday Data Collapsed to Daily Prices
- **File:** `src/backtesting/deterministic_backtest.py::_get_current_prices()` (line 354)
- **Issue:** Uses last bar of day as "current price" for daily iteration
- **Impact:** Intraday data is effectively collapsed to daily prices
- **Severity:** BLOCKER
- **Type:** Engine issue (adapter masking incompatibility)

---

## PHASE 3: STRATEGY EXPECTATION MATCH

### TopstepStrategy Assumptions

#### ✅ What Strategy Expects (from code comments and logic)

1. **Ordered Intraday Bars:** Strategy expects DataFrame with sequential 5-minute bars
2. **Real Opening Range Bars:** Comments say "In production with intraday data, you'd use actual 9:30-9:45 bars"
3. **ATR on Intraday Bars:** Strategy calculates ATR on 5-minute bars (line 68-84)
4. **Candle Sequences:** Strategy checks for engulfing patterns and pullbacks (line 205-270)

#### ❌ What Strategy Actually Receives

1. **Daily Aggregates:** Strategy receives daily data via `get_prices()` which strips time component
2. **Approximated Opening Range:** Strategy approximates OR from daily range (line 126-161):
   ```python
   # Since we're working with daily data, we simulate the OR using:
   # OR High = first 25% of day's range (approximates first 15 min)
   ```
3. **Daily ATR:** ATR is calculated on daily bars, not 5-minute bars
4. **No Candle Sequences:** Strategy sees one bar per day, not sequential candles

### Violated Assumptions

#### BLOCKER: Opening Range Approximation
- **File:** `src/agents/topstep_strategy.py::_identify_opening_range()` (line 126)
- **Issue:** Strategy approximates OR from daily range instead of using actual 9:30-9:45 bars
- **Code:** Uses `(high - open) * 0.25` to approximate first 15 minutes
- **Impact:** Opening range break detection is inaccurate
- **Severity:** BLOCKER
- **Type:** Strategy expectation mismatch

#### BLOCKER: ATR Calculated on Wrong Granularity
- **File:** `src/agents/topstep_strategy.py::_calculate_atr()` (line 68)
- **Issue:** ATR is calculated on whatever DataFrame is passed (daily bars, not 5-minute bars)
- **Impact:** ATR values are incorrect for intraday strategy
- **Severity:** BLOCKER
- **Type:** Strategy expectation mismatch

#### BLOCKER: No Sequential Price Action
- **File:** `src/agents/topstep_strategy.py::_check_break_and_acceptance()` (line 163)
- **Issue:** Strategy checks for breakout on last bar of DataFrame, but only sees one bar per day
- **Impact:** Cannot detect breakouts that occur intraday
- **Severity:** BLOCKER
- **Type:** Strategy expectation mismatch

### Silent "HOLD Forever" Failure Modes

#### HIGH: Strategy Returns HOLD When Data Doesn't Match Expectations
- **File:** `src/agents/topstep_strategy.py::generate_signal()` (line 322)
- **Issue:** Strategy returns "hold" when:
  - Insufficient data (line 342)
  - Daily limits reached (line 353)
  - Market regime filter fails (line 365)
  - No opening range identified (line 377)
  - No breakout detected (line 389)
  - No pullback entry (line 394)
- **Impact:** Strategy correctly refuses to trade, but cannot evaluate if conditions are actually met
- **Severity:** HIGH
- **Type:** Strategy expectation mismatch

---

## PHASE 4: FRICTION & RISK APPLICATION

### ✅ What Is Correct

- **Slippage Applied:** Applied at execution time in `_execute_trade()` (line 560-567)
- **Spread Applied:** Applied directionally (buy/cover: +, sell/short: -) (line 560-567)
- **Commission Deducted:** Deducted deterministically from cash (line 579, 598, 636, 650)
- **Friction Per Fill:** Applied per trade execution, not per day
- **No Randomness:** All friction calculations are deterministic

### ❌ What Is Missing or Broken

#### MEDIUM: Daily Loss Limits Not Enforced Intraday
- **File:** `src/agents/topstep_strategy.py::_check_daily_limits()` (line 298)
- **Issue:** Daily loss limits are checked before trade, but not enforced during intraday execution
- **Impact:** If execution were intraday, daily loss limits could be violated
- **Severity:** MEDIUM (not applicable with current daily execution)
- **Type:** Risk application issue

#### MEDIUM: Stop-After-Win Logic Not Enforced Per Session
- **File:** `src/agents/topstep_strategy.py::_check_daily_limits()` (line 317)
- **Issue:** Checks `daily_wins.get(date, False)` but this is only updated at end of day
- **Impact:** If execution were intraday, stop-after-win might not work correctly
- **Severity:** MEDIUM (not applicable with current daily execution)
- **Type:** Risk application issue

### Confirmations

- **No Randomness:** ✅ Confirmed - all friction calculations are deterministic
- **No Double-Counting:** ✅ Confirmed - friction applied once per trade
- **No Missed Costs:** ✅ Confirmed - all trades have commission, slippage, and spread applied

---

## PHASE 5: METRICS & OBSERVABILITY

### ✅ What Is Available

- **Trade-Level Logs:** `self.trades` list contains all executed trades (line 657-666)
- **Daily PnL Series:** `self.daily_values` contains daily NAV (line 105)
- **Daily Drawdown Tracking:** Calculated in `_calculate_metrics()` (line 1171-1174)
- **Largest Losing Day:** Can be derived from daily PnL series
- **Losing Streak Detection:** Can be derived from daily PnL series
- **Time-to-Recovery:** Can be calculated from daily NAV series

### ❌ What Is Missing

#### HIGH: No Entry/Exit Timestamps
- **File:** `src/backtesting/deterministic_backtest.py::_execute_trade()` (line 657)
- **Issue:** Trade records contain date but not intraday timestamp
- **Impact:** Cannot determine exact entry/exit time for intraday analysis
- **Severity:** HIGH
- **Type:** Metrics gap

#### HIGH: No Intraday Drawdown Tracking
- **File:** `src/backtesting/deterministic_backtest.py::_calculate_metrics()` (line 1171)
- **Issue:** Drawdown calculated only on daily NAV, not intraday
- **Impact:** Cannot detect intraday drawdown spikes
- **Severity:** HIGH
- **Type:** Metrics gap

#### MEDIUM: No Stop/Target Hit Tracking
- **File:** `src/backtesting/deterministic_backtest.py`
- **Issue:** No logic to track if stops or targets are hit (because they're not executed)
- **Impact:** Cannot analyze stop/target effectiveness
- **Severity:** MEDIUM
- **Type:** Metrics gap

#### MEDIUM: No Intraday NAV Series
- **File:** `src/backtesting/deterministic_backtest.py::daily_values` (line 105)
- **Issue:** Only daily NAV recorded, not intraday NAV
- **Impact:** Cannot analyze intraday performance or drawdown
- **Severity:** MEDIUM
- **Type:** Metrics gap

### Funded-Account Critical Metrics

| Metric | Status | Notes |
|--------|--------|-------|
| Max Drawdown | ✅ Available | Daily granularity only |
| Largest Losing Day | ✅ Available | Daily granularity only |
| Losing Streaks | ✅ Available | Daily granularity only |
| Time to Recovery | ✅ Available | Daily granularity only |
| % Profitable Days | ✅ Available | Daily granularity only |
| Intraday Drawdown | ❌ Missing | No intraday NAV tracking |
| Stop/Target Hit Rate | ❌ Missing | No stop/target execution |

---

## PHASE 6: DETERMINISM & SAFETY

### ✅ What Is Correct

- **Deterministic Data Loading:** PriceCache loads data deterministically (hash-stable)
- **No External Calls:** All external API calls blocked in deterministic mode
- **Fail-Fast Behavior:** Invalid data raises RuntimeError (no silent failures)
- **No Mutable Global State:** Each backtest instance is independent

### ❌ What Is Missing or Broken

#### LOW: No Explicit Timezone Handling
- **File:** `src/data/prices/ES.csv`
- **Issue:** Timestamps are naive (no timezone)
- **Impact:** Ambiguous timezone could cause issues if data spans DST changes
- **Severity:** LOW
- **Type:** Determinism issue

---

## PHASE 7: GAP SUMMARY

### BLOCKER Gaps (Must Fix Before Intraday Backtesting)

1. **Data Time Loss in Conversion** (`src/tools/api.py::get_prices()` line 88)
   - **Severity:** BLOCKER
   - **Type:** Data issue
   - **Impact:** Intraday timestamps lost when converting to Price objects

2. **Daily Execution Loop** (`src/backtesting/deterministic_backtest.py::run()` line 1081)
   - **Severity:** BLOCKER
   - **Type:** Engine issue
   - **Impact:** Strategy sees only one decision point per day, not intraday bars

3. **No Intraday Execution** (`src/backtesting/deterministic_backtest.py::_run_daily_decision()` line 806)
   - **Severity:** BLOCKER
   - **Type:** Engine issue
   - **Impact:** Trades can only execute at end-of-day, not during trading hours

4. **Strategy Expects Intraday But Receives Daily** (`src/agents/topstep_strategy.py`)
   - **Severity:** BLOCKER
   - **Type:** Strategy expectation mismatch
   - **Impact:** Strategy logic assumes intraday bars but receives daily aggregates

5. **No Stop/Target Execution** (`src/backtesting/deterministic_backtest.py`)
   - **Severity:** BLOCKER
   - **Type:** Engine issue
   - **Impact:** Positions never exit via stops or targets

6. **Opening Range Approximation** (`src/agents/topstep_strategy.py::_identify_opening_range()` line 126)
   - **Severity:** BLOCKER
   - **Type:** Strategy expectation mismatch
   - **Impact:** OR break detection is inaccurate

### HIGH Gaps (Significant Impact)

7. **No Timezone Handling** (`src/data/prices/ES.csv`)
   - **Severity:** HIGH
   - **Type:** Data issue
   - **Impact:** Ambiguous timezone could cause issues

8. **No Entry/Exit Timestamps** (`src/backtesting/deterministic_backtest.py::_execute_trade()` line 657)
   - **Severity:** HIGH
   - **Type:** Metrics gap
   - **Impact:** Cannot determine exact entry/exit time

9. **No Intraday Drawdown Tracking** (`src/backtesting/deterministic_backtest.py::_calculate_metrics()` line 1171)
   - **Severity:** HIGH
   - **Type:** Metrics gap
   - **Impact:** Cannot detect intraday drawdown spikes

### MEDIUM Gaps (Moderate Impact)

10. **Daily Loss Limits Not Enforced Intraday** (`src/agents/topstep_strategy.py::_check_daily_limits()` line 298)
    - **Severity:** MEDIUM
    - **Type:** Risk application issue
    - **Impact:** Not applicable with current daily execution, but would be issue if intraday execution added

11. **No Stop/Target Hit Tracking** (`src/backtesting/deterministic_backtest.py`)
    - **Severity:** MEDIUM
    - **Type:** Metrics gap
    - **Impact:** Cannot analyze stop/target effectiveness

12. **No Intraday NAV Series** (`src/backtesting/deterministic_backtest.py::daily_values` line 105)
    - **Severity:** MEDIUM
    - **Type:** Metrics gap
    - **Impact:** Cannot analyze intraday performance

### LOW Gaps (Minor Impact)

13. **No Explicit Timezone Handling** (`src/data/prices/ES.csv`)
    - **Severity:** LOW
    - **Type:** Determinism issue
    - **Impact:** Ambiguous timezone, but works for current use case

---

## FINAL VERDICT

### ❌ NOT READY

**The system is NOT ready to correctly backtest an intraday strategy on real market data.**

### Blocking Issues

1. **Data Pipeline Loses Time Component:** Intraday timestamps are stripped when converting to Price objects
2. **Execution Engine is Daily-Only:** Backtest loop iterates over business days, not intraday bars
3. **Strategy Cannot See Intraday Bars:** Strategy receives daily aggregates, not sequential 5-minute bars
4. **No Intraday Execution:** Trades execute once per day, cannot execute during trading hours
5. **No Stop/Target Execution:** Stop losses and profit targets are never checked or executed
6. **Opening Range Approximation:** Strategy approximates OR from daily data instead of using actual bars

### What Is Already Correct

- ✅ Intraday data exists in CSV (5-minute bars with timestamps)
- ✅ PriceCache can load intraday data
- ✅ Friction is applied correctly (slippage, spread, commission)
- ✅ Capital constraints are enforced
- ✅ Determinism is preserved
- ✅ Daily metrics are available
- ✅ Trade logging exists (though without intraday timestamps)

### Path to Readiness

To make the system ready for intraday strategy backtesting, the following must be addressed:

1. **Fix data conversion** to preserve time component in Price objects
2. **Modify execution loop** to iterate over intraday bars, not business days
3. **Enable intraday execution** so trades can execute during trading hours
4. **Implement stop/target execution** to check and execute stops/targets intraday
5. **Fix strategy data access** to receive actual intraday bars, not daily aggregates
6. **Update opening range logic** to use actual 9:30-9:45 bars, not approximations

**Current Status:** System is designed for daily backtesting, not intraday. Significant architectural changes required for intraday support.

---

**END OF REPORT**
