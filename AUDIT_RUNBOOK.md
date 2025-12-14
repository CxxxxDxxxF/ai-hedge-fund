# Audit Runbook

**Purpose**: Exact commands to verify system capabilities and correctness.

**Last Updated**: 2025-12-14

---

## Prerequisites

```bash
cd /Users/cristianruizjr/moneymaker/ai-hedge-fund
export HEDGEFUND_NO_LLM=1
```

---

## 1. Baseline Test Suite

### Run All Hardening Tests

```bash
poetry run pytest tests/hardening/ -v
```

**Expected**: All tests pass

**Critical Tests**:
- `test_execution_friction.py` - Friction correctness
- `test_deterministic_invariants.py` - Determinism enforcement
- `test_near_engulfing.py` - Strategy logic
- `test_near_engulfing_regression.py` - Regression prevention

---

## 2. Targeted Hardening Test Suite

### Test Execution Friction

```bash
poetry run pytest tests/hardening/test_execution_friction.py -v
```

**Expected Output**:
- `test_execution_friction_changes_results` ✅ PASS
- `test_execution_friction_is_deterministic` ✅ PASS

### Test Deterministic Invariants

```bash
poetry run pytest tests/hardening/test_deterministic_invariants.py -v
```

**Expected Output**:
- All 4 tests pass ✅

---

## 3. End-to-End Backtest Run

### Run Full Backtest with Fixed Seed

```bash
cd /Users/cristianruizjr/moneymaker/ai-hedge-fund
HEDGEFUND_NO_LLM=1 poetry run python generate_r_metrics_report.py > backtest_run_1.log 2>&1
```

**Expected**:
- Backtest completes without errors
- Metrics calculated
- `r_trade_log.csv` generated
- Final NAV, trade count, R-metrics printed

**Key Metrics to Verify**:
- Total trades: 13 (or current count)
- Final NAV: ~$99,774 (or current value)
- Determinism hash: Computed and printed

---

## 4. Determinism Check

### Run Backtest Twice and Compare

```bash
# Run 1
HEDGEFUND_NO_LLM=1 poetry run python generate_r_metrics_report.py > run1.log 2>&1
grep "Output Hash" run1.log

# Run 2
HEDGEFUND_NO_LLM=1 poetry run python generate_r_metrics_report.py > run2.log 2>&1
grep "Output Hash" run2.log

# Compare
diff run1.log run2.log | head -20
```

**Expected**:
- Output hashes match exactly
- Final NAV matches
- Trade counts match
- All metrics identical

**Verification Command**:
```bash
hash1=$(grep "Output Hash" run1.log | awk '{print $NF}')
hash2=$(grep "Output Hash" run2.log | awk '{print $NF}')
if [ "$hash1" == "$hash2" ]; then echo "✅ Determinism verified"; else echo "❌ Determinism broken"; fi
```

---

## 5. Capability Verification Commands

### Verify Intraday Execution

```bash
HEDGEFUND_NO_LLM=1 poetry run python generate_r_metrics_report.py 2>&1 | grep "Intraday execution mode"
```

**Expected**: "Intraday execution mode: 4644 bars" (or current count)

### Verify R-Metrics Tracking

```bash
HEDGEFUND_NO_LLM=1 poetry run python generate_r_metrics_report.py 2>&1 | grep -A 5 "R-MULTIPLE STATISTICS"
```

**Expected**: Mean R, MFE, MAE values printed

### Verify Stop/Target Execution

```bash
cat r_trade_log.csv | cut -d',' -f10 | sort | uniq -c
```

**Expected**: Counts of 'stop_loss', 'target', 'time_invalidation'

### Verify Friction Application

```bash
HEDGEFUND_NO_LLM=1 poetry run python generate_r_metrics_report.py 2>&1 | grep -A 3 "FRICTION IMPACT"
```

**Expected**: Total commissions, slippage, friction cost printed

---

## 6. Data Contract Verification

### Verify Timestamp Preservation

```bash
head -5 r_trade_log.csv | cut -d',' -f1,2
```

**Expected**: Full datetime strings (e.g., "2025-09-22 09:55:00")

### Verify CSV Format

```bash
head -1 src/data/prices/ES.csv
```

**Expected**: "date,open,high,low,close,volume"

---

## 7. Strategy Interface Verification

### Verify Strategy Receives Filtered Data

**Manual Check**: Add print statement in strategy to log DataFrame length

**Command**: (Requires code modification - not recommended for audit)

**Alternative**: Review code at `deterministic_backtest.py:1141-1142`

---

## 8. Regime Research Verification

### Run Regime Segmentation

```bash
cd /Users/cristianruizjr/moneymaker/ai-hedge-fund
HEDGEFUND_NO_LLM=1 poetry run python research/regime_segmentation.py
```

**Expected**:
- Loads acceptance events
- Labels events with regime features
- Generates `regime_summary.csv` and `regime_labeled_events.csv`
- Prints summary table

**Verify Output**:
```bash
cat regime_summary.csv
cat regime_labeled_events.csv | head -5
```

---

## 9. Failure Triage

### If Determinism Breaks

**Likely Causes**:
1. External API call made (check `HEDGEFUND_NO_LLM=1`)
2. Random number generation not seeded
3. Timestamp parsing inconsistency
4. Floating point precision issues

**Where to Look**:
- `src/utils/deterministic_guard.py` - Check seeding
- `src/tools/api.py` - Verify PriceCache routing
- `deterministic_backtest.py:1526-1528` - Hash computation

**Debug Command**:
```bash
HEDGEFUND_NO_LLM=1 poetry run python -c "
from src.backtesting.deterministic_backtest import DeterministicBacktest
bt1 = DeterministicBacktest(tickers=['ES'], start_date='2025-09-19', end_date='2025-09-23', initial_capital=100000.0)
m1 = bt1.run()
print('Hash:', m1.get('determinism', {}).get('output_hash', 'N/A'))
"
```

### If Intraday Stops Do Not Trigger

**Likely Causes**:
1. `active_positions[ticker]` is None (position not stored)
2. Stop/target not extracted from reasoning
3. Bar high/low not crossing stop/target
4. Stop check logic error

**Where to Look**:
- `deterministic_backtest.py:849-917` - Stop/target check logic
- `deterministic_backtest.py:1303-1314` - Position storage
- `r_trade_log.csv` - Check if exits recorded

**Debug Command**:
```bash
# Check active positions
grep "active_positions" src/backtesting/deterministic_backtest.py -A 5

# Check stop/target extraction
grep "Stop \$" src/backtesting/deterministic_backtest.py -A 2
```

### If Strategy Doesn't Receive Filtered Data

**Likely Causes**:
1. DataFrame filtering not applied
2. `bar_ts` timestamp incorrect
3. Index comparison fails

**Where to Look**:
- `deterministic_backtest.py:1139-1142` - Filtering logic
- Strategy `generate_signal()` - Check DataFrame length

---

## 10. Complete Audit Execution

### Full Audit Run

```bash
cd /Users/cristianruizjr/moneymaker/ai-hedge-fund

# 1. Baseline tests
poetry run pytest tests/hardening/ -v --tb=short

# 2. End-to-end backtest
HEDGEFUND_NO_LLM=1 poetry run python generate_r_metrics_report.py > audit_backtest.log 2>&1

# 3. Determinism check
HEDGEFUND_NO_LLM=1 poetry run python generate_r_metrics_report.py > audit_backtest2.log 2>&1
hash1=$(grep "Output Hash" audit_backtest.log | awk '{print $NF}')
hash2=$(grep "Output Hash" audit_backtest2.log | awk '{print $NF}')
echo "Determinism: $([ "$hash1" == "$hash2" ] && echo "✅ PASS" || echo "❌ FAIL")"

# 4. Regime research
HEDGEFUND_NO_LLM=1 poetry run python research/regime_segmentation.py > regime_audit.log 2>&1

# 5. Generate summary
echo "=== AUDIT SUMMARY ===" > audit_summary.txt
echo "Tests: $(poetry run pytest tests/hardening/ -q --tb=no | tail -1)" >> audit_summary.txt
echo "Backtest trades: $(grep "Total Trades" audit_backtest.log | awk '{print $NF}')" >> audit_summary.txt
echo "Determinism: $([ "$hash1" == "$hash2" ] && echo "PASS" || echo "FAIL")" >> audit_summary.txt
cat audit_summary.txt
```

---

## 11. Expected Results

### Successful Audit

- ✅ All hardening tests pass
- ✅ Backtest completes without errors
- ✅ Determinism hash matches across runs
- ✅ R-metrics computed correctly
- ✅ Regime research generates outputs
- ✅ No execution errors or warnings

### Failure Indicators

- ❌ Tests fail
- ❌ Determinism hash differs
- ❌ Backtest crashes
- ❌ Missing output files
- ❌ NaN or invalid values in metrics

---

**END OF AUDIT RUNBOOK**
