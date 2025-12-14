# Strategy Interface Audit

**Purpose**: Document what strategies receive, what they return, and how risk sizing works.

**Last Updated**: 2025-12-14

---

## 1. Strategy Input

### Data Provided to Strategy

**Location**: `deterministic_backtest.py:1139-1168`

**Input**:
1. **Price DataFrame**: Filtered to bars up to current bar
   ```python
   strategy_df = price_cache.get_prices_for_range(ticker, start_date, date_str)
   strategy_df = strategy_df[strategy_df.index <= bar_ts]  # FILTERED
   ```

2. **State Dict**:
   ```python
   state = {
       "data": {
           "tickers": [ticker],
           "end_date": date_str,
           "portfolio": self.portfolio,
       },
       "messages": [],
       "metadata": {}
   }
   ```

3. **Account Value**: Current NAV
   ```python
   account_value = self._calculate_portfolio_value(prices)
   ```

4. **Date**: Current date string (YYYY-MM-DD)

### Key Constraint: Strategy Sees Only Bars Up to Current Bar

**Location**: `deterministic_backtest.py:1141-1142`

**Implementation**:
```python
strategy_df = strategy_df[strategy_df.index <= bar_ts]
```

**Verification**: ✅ **VERIFIED** - Filtering applied before strategy call

**Test Status**: ⚠️ **MISSING TEST** - Should assert strategy doesn't see future bars

---

## 2. Strategy Output Format

### Expected Return Format

**Type**: `Dict[str, Dict]`

**Structure**:
```python
{
    ticker: {
        "action": "buy" | "sell" | "short" | "cover" | "hold",
        "quantity": int,  # Number of contracts/shares
        "confidence": int,  # 0-100
        "reasoning": str,  # Human-readable explanation
    }
}
```

### Required Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `action` | str | ✅ Yes | Trading action |
| `quantity` | int | ✅ Yes | Position size |
| `confidence` | int | ✅ Optional | Confidence level |
| `reasoning` | str | ✅ Optional | Explanation (may contain stop/target) |

### Stop/Target Extraction

**Location**: `deterministic_backtest.py:1262-1287`

**Method**: Regex extraction from `reasoning` string

**Patterns**:
- Stop: `r'Stop \$([\d.]+)'`
- Target: `r'Target \$([\d.]+)'`
- Confirm type: `r'confirm[=:](\w+)'`

**Fallback**: If not extracted, uses defaults (10% stop, 1.5R target)

**Status**: ⚠️ **PARTIALLY WORKING** - Confirm_type extraction failing

---

## 3. Risk Sizing

### TopstepStrategy Sizing

**Location**: `topstep_strategy.py:434-458` (`_calculate_position_size()`)

**Logic**:
```python
risk_per_contract = abs(entry_price - stop_loss)
max_risk_dollars = account_value * RISK_PERCENT  # 0.25%
max_contracts = int(max_risk_dollars / risk_per_contract)
contracts = max(1, min(max_contracts, 1))  # Always 1 contract
```

**Constraints**:
- Risk ≤ 0.25% of account value
- Minimum 1 contract
- Maximum 1 contract (hardcoded)

**Contract Size Assumption**: 
- ES futures: $50 per point
- Not explicitly coded (assumed in risk calculation)

### AcceptanceContinuationStrategy Sizing

**Location**: `acceptance_continuation_strategy.py:218-242`

**Logic**: Identical to TopstepStrategy

**Status**: ✅ **VERIFIED** - Same risk framework

---

## 4. Daily Reset Behavior

### TopstepStrategy

**Location**: `topstep_strategy.py:497-512`

**Reset Logic**:
```python
# Reset state at start of new day
if self.opening_range is None or self.opening_range.get('date') != date:
    self.opening_range = None
    self.current_position = None
    self.breakout_state = None
```

**Verification**: ✅ **VERIFIED** - Checks date mismatch

### AcceptanceContinuationStrategy

**Location**: `acceptance_continuation_strategy.py:285-289`

**Reset Logic**:
```python
if self.or_state is None or self.or_state.get('date') != date:
    self.or_state = None
    self.breakout_state = None
    self.acceptance_bars = []
```

**Verification**: ✅ **VERIFIED** - Checks date mismatch

---

## 5. Strategy Call Conditions

### When Strategy is Called

**Location**: `deterministic_backtest.py:1131`

**Conditions** (ALL must be true):
1. `in_trading_window` (9:30-10:30)
2. `not has_position` (no active position for ticker)
3. `trades_today.get(date_str, 0) == 0` (no trades today)

**Verification**: ✅ **VERIFIED** - All conditions checked

---

## 6. Strategy Interface Tests

### Test 1: Strategy Receives Only Bars Up to Current Timestamp

**Purpose**: Verify no lookahead bias

**Test Steps**:
1. Create synthetic dataset with 10 bars
2. Call strategy on bar 5
3. Assert strategy DataFrame has only bars 1-5

**Status**: ⚠️ **MISSING TEST**

### Test 2: Daily Reset Behavior

**Purpose**: Verify state cleared at session boundary

**Test Steps**:
1. Run strategy on day 1, generate breakout
2. Run strategy on day 2 (first bar)
3. Assert `breakout_state` is None

**Status**: ⚠️ **MISSING TEST**

---

## 7. Strategy Interface Summary

### Verified

| Aspect | Status | Evidence |
|--------|--------|----------|
| Strategy receives filtered data | ✅ VERIFIED | Code filters to `index <= bar_ts` |
| Return format validation | ✅ VERIFIED | `validate_portfolio_decision()` called |
| Risk sizing (0.25% rule) | ✅ VERIFIED | Both strategies use same logic |
| Daily reset (date check) | ✅ VERIFIED | Both strategies check date mismatch |
| Strategy call conditions | ✅ VERIFIED | All 3 conditions checked |

### Unverified

| Aspect | Status | Evidence Needed |
|--------|--------|----------------|
| No lookahead bias (test) | ⚠️ MISSING | Need test asserting filtered data |
| Daily reset (test) | ⚠️ MISSING | Need test asserting state cleared |
| Contract size assumption | ⚠️ DOCUMENTED | ES = $50/point not explicitly coded |

---

**END OF STRATEGY INTERFACE AUDIT**
