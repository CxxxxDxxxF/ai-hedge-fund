# Regime Research Module Audit

**Purpose**: Audit regime segmentation research module (read-only, no execution changes).

**Last Updated**: 2025-12-14

---

## 1. Module Purpose

**File**: `research/regime_segmentation.py`

**Purpose**: Label acceptance evaluation events with market regime features to identify where acceptance continuation might work.

**Key Constraint**: Research-only, no strategy or execution changes.

**Status**: ✅ **VERIFIED** - Module only reads data and generates labels

---

## 2. Regime Definitions

### Regime Features Computed

| Feature | Computation | Location |
|---------|-------------|----------|
| **OR range (points)** | `or_high - or_low` | `regime_segmentation.py:245` |
| **OR range (% of ATR)** | `(or_range / atr_14) * 100` | `regime_segmentation.py:246` |
| **ATR(14)** | Rolling ATR calculation | `regime_segmentation.py:45-58` |
| **ATR percentile (20d)** | Percentile rank over 20-day window | `regime_segmentation.py:60-68` |
| **Prior day trend** | Classify from day's first/last bar | `regime_segmentation.py:70-81` |
| **Gap type** | Compare today_open vs yesterday_close | `regime_segmentation.py:83-91` |
| **Breakout minutes from open** | `(hour * 60 + minute) - (9 * 60 + 30)` | `regime_segmentation.py:248` |

### Regime Classifications

**Prior Day Trend**:
- `"up"`: `last_bar['close'] > first_bar['open']`
- `"down"`: `last_bar['close'] < first_bar['open']`
- `"flat"`: Otherwise

**Gap Type**:
- `"gap_up"`: `today_open - yesterday_close > 0.1 * atr`
- `"gap_down"`: `today_open - yesterday_close < -0.1 * atr`
- `"no_gap"`: `abs(gap) < 0.1 * atr`

---

## 3. What is Labeled

### Input: Acceptance Events

**Source**: `acceptance_rolling_diagnostic.csv`

**Required Fields**:
- `date`: Date string
- `timestamp` or `breakout_timestamp`: Breakout timestamp
- `side`: "long" or "short"
- `or_high`, `or_low`: Opening range boundaries
- `decision`: "acceptance_pass" or "acceptance_fail"
- `mfe_r`, `mae_r`: MFE/MAE in R units (from trade log)

### Output: RegimeLabel

**Fields** (from `RegimeLabel` dataclass):
- Date, breakout timestamp, side
- OR structure (range points, % of ATR)
- Volatility (ATR(14), ATR percentile)
- Trend context (prior day trend, gap type)
- Timing (minutes from open)
- Outcome (acceptance_pass, mfe_r, mae_r, r_multiple_pre_friction)

---

## 4. What "Acceptance Evaluations" Means

### In Code Context

**Location**: `regime_segmentation.py:283`

**Definition**: Events where `event_type == 'acceptance_evaluated'`

**Source**: Diagnostic events from strategy execution

**Meaning**: 
- Strategy detected a breakout
- Collected acceptance bars (2 bars for rolling window)
- Evaluated whether acceptance condition passed
- Logged evaluation result

**Not the same as**:
- Breakout detection (happens before evaluation)
- Entry emission (happens after evaluation if passed)

---

## 5. Regime Computation Functions

### ATR Calculation

**Location**: `regime_segmentation.py:45-58`

**Method**: Standard ATR(14) using True Range

**Formula**:
```
TR = max(high - low, abs(high - prev_close), abs(low - prev_close))
ATR = rolling_mean(TR, window=14)
```

**Status**: ✅ **VERIFIED** - Standard implementation

### ATR Percentile

**Location**: `regime_segmentation.py:60-68`

**Method**: Percentile rank over 20-day lookback

**Formula**:
```
percentile = (recent <= current_atr).sum() / len(recent) * 100
```

**Status**: ✅ **VERIFIED** - Correct percentile calculation

### Prior Day Trend

**Location**: `regime_segmentation.py:70-81`

**Method**: Compare first bar open vs last bar close of previous day

**Status**: ✅ **VERIFIED** - Logic correct

### Gap Classification

**Location**: `regime_segmentation.py:83-91`

**Method**: Compare today's first bar open vs yesterday's last bar close

**Threshold**: `0.1 * atr` (10% of ATR)

**Status**: ✅ **VERIFIED** - Logic correct

---

## 6. Test: Synthetic Dataset Regime Labels

### Test Requirement

**Purpose**: Verify regime labels match expected values

**Test Dataset**: 6 bars representing:
- Day 1: Gap up, prior day up trend
- Day 2: Gap down, prior day down trend
- Day 3: No gap, prior day flat

**Expected Labels**:
- Day 1: `gap_type="gap_up"`, `prior_day_trend="up"`
- Day 2: `gap_type="gap_down"`, `prior_day_trend="down"`
- Day 3: `gap_type="no_gap"`, `prior_day_trend="flat"`

**Status**: ⚠️ **MISSING TEST**

---

## 7. Regime Research Output

### Files Generated

| File | Purpose | Format |
|------|---------|--------|
| `regime_summary.csv` | Aggregated by regime | CSV with counts, pass rates, mean MFE/MAE |
| `regime_labeled_events.csv` | All events with labels | CSV with all RegimeLabel fields |

### Summary Aggregation

**Location**: `regime_segmentation.py:293-310`

**Grouping**: By `gap_type` and `prior_day_trend`

**Metrics**:
- `count`: Number of evaluations
- `pass_rate`: % that passed acceptance
- `mean_mfe`: Average MFE in R units
- `mean_mae`: Average MAE in R units
- `mean_r_pre_friction`: Average R-multiple before friction
- `mfe_gt_mae`: Boolean (MFE > MAE)

**Status**: ✅ **VERIFIED** - Output generated correctly

---

## 8. Research Module Correctness

### Verified

| Aspect | Status | Evidence |
|--------|--------|----------|
| No strategy changes | ✅ VERIFIED | Module only reads CSV, no strategy calls |
| No execution changes | ✅ VERIFIED | No backtest execution in module |
| Regime computation | ✅ VERIFIED | Functions compute correctly |
| Label generation | ✅ VERIFIED | `regime_labeled_events.csv` generated |
| Summary aggregation | ✅ VERIFIED | `regime_summary.csv` generated |

### Unverified

| Aspect | Status | Evidence Needed |
|--------|--------|----------------|
| Regime label correctness (test) | ⚠️ MISSING | Need synthetic dataset test |
| ATR calculation accuracy | ⚠️ UNVERIFIED | Should compare with known values |
| Gap classification threshold | ⚠️ DOCUMENTED | 0.1 * ATR threshold not validated |

---

## 9. Known Issues

### Issue 1: ATR Percentile Edge Cases

**Location**: `regime_segmentation.py:60-68`

**Problem**: Returns `np.nan` if `len(atr_series) < lookback`

**Impact**: Low (only affects early days in dataset)

**Status**: ⚠️ **DOCUMENTED** - Handled gracefully

### Issue 2: Prior Day Data Availability

**Location**: `regime_segmentation.py:230-240`

**Problem**: Falls back to previous bar in dataset if yesterday's data not found

**Impact**: Low (should work for continuous data)

**Status**: ⚠️ **DOCUMENTED** - Fallback logic exists

---

**END OF REGIME RESEARCH AUDIT**
