# Upgrade Summary: Deterministic Intelligence & Credibility Weighting

**Date:** 2025-01-27  
**Changes:** Part A (Broaden deterministic intelligence) + Part B (Deepen decision quality with credibility weighting)

---

## Part A: Broadened Deterministic Intelligence

### Agents Updated (8 total)

Added `rule_based_factory` functions to the following analyst agents to enable deterministic operation when `HEDGEFUND_NO_LLM=1`:

1. **Ben Graham** (`src/agents/ben_graham.py`)
2. **Charlie Munger** (`src/agents/charlie_munger.py`)
3. **Peter Lynch** (`src/agents/peter_lynch.py`)
4. **Michael Burry** (`src/agents/michael_burry.py`)
5. **Stanley Druckenmiller** (`src/agents/stanley_druckenmiller.py`)
6. **Phil Fisher** (`src/agents/phil_fisher.py`)
7. **Bill Ackman** (`src/agents/bill_ackman.py`)
8. **Aswath Damodaran** (`src/agents/aswath_damodaran.py`)

### Selection Rationale

These 8 agents were selected because they:
- Represent core investment philosophies (value, growth, contrarian, macro, valuation)
- Are frequently used in backtests and comparisons
- Already compute deterministic scores/signals internally
- Were missing `rule_based_factory` implementations

### Deterministic Rules Added

Each agent's `rule_based_factory` function:

1. **Uses existing analysis data**: Leverages the same `analysis_data` structure that the LLM would receive
2. **Computes signal from score ratio**: 
   - `score_ratio = total_score / max_score`
   - `signal = "bullish"` if `score_ratio >= 0.7`
   - `signal = "bearish"` if `score_ratio <= 0.3`
   - `signal = "neutral"` otherwise
3. **Calculates confidence deterministically**:
   - Bullish: `confidence = min(85, 50 + int(score_ratio * 50))`
   - Bearish: `confidence = min(85, 50 + int((1 - score_ratio) * 50))`
   - Neutral: `confidence = 50`
4. **Builds reasoning from analysis components**: Includes key sub-analysis scores (growth, valuation, quality, etc.)
5. **Handles missing data gracefully**: Returns neutral signal with clear explanation if data is insufficient

### Example: Ben Graham Rule-Based Logic

```python
def create_rule_based_ben_graham_signal():
    ticker_data = analysis_data.get(ticker, {})
    total_score = ticker_data.get("score", 0)
    max_score = ticker_data.get("max_score", 15)
    
    score_ratio = total_score / max_score
    
    if score_ratio >= 0.7:
        signal = "bullish"
        confidence = min(85, 50 + int(score_ratio * 50))
    elif score_ratio <= 0.3:
        signal = "bearish"
        confidence = min(85, 50 + int((1 - score_ratio) * 50))
    else:
        signal = "neutral"
        confidence = 50
    
    # Build reasoning from earnings, strength, valuation analyses
    reasoning = f"Graham analysis: Score {total_score:.1f}/{max_score} ({score_ratio:.1%})..."
    
    return BenGrahamSignal(signal=signal, confidence=float(confidence), reasoning=reasoning)
```

---

## Part B: Credibility-Weighted Signal Combination

### Changes Made

1. **Performance Auditor** (`src/agents/performance_auditor.py`):
   - Now stores credibility scores in `state["data"]["agent_credibility"]`
   - Format: `{agent_name: credibility_score (0.0-1.0)}`
   - Example: `{"warren_buffett_agent": 0.75, "momentum_agent": 0.60}`

2. **Ensemble Agent** (`src/agents/ensemble.py`):
   - Updated `calculate_ensemble_signal_rule_based()` to accept `agent_credibility` parameter
   - Applies credibility weighting to base weights before combination
   - Normalizes weights to sum to 1.0 after credibility adjustment

3. **Conflict Arbiter** (`src/agents/conflict_arbiter.py`):
   - Updated `adjust_signal_for_conflict()` to accept `agent_credibility` parameter
   - Applies credibility weighting to signal confidences in all conflict resolution rules
   - Uses credibility-adjusted confidences for weighted averages and deferral decisions

### Credibility Weighting Formula

**Single equation for all credibility weighting:**

```
adjusted_weight = base_weight * max(CREDIBILITY_FLOOR, credibility_score)
```

Where:
- `base_weight`: Original weight (e.g., 0.6 for Buffett, 0.4 for Momentum)
- `credibility_score`: Performance Auditor credibility (0.0-1.0)
- `CREDIBILITY_FLOOR`: 0.2 (prevents zeroing out agents completely)

**For Ensemble Agent:**
```
buffett_weight_cred = WARREN_BUFFETT_WEIGHT * max(0.2, buffett_credibility)
momentum_weight_cred = MOMENTUM_WEIGHT * max(0.2, momentum_credibility)

# Normalize to sum to 1.0
total = buffett_weight_cred + momentum_weight_cred
buffett_final = buffett_weight_cred / total
momentum_final = momentum_weight_cred / total
```

**For Conflict Arbiter:**
```
# Weight each signal by: confidence * credibility
weight = (confidence / 100.0) * max(CREDIBILITY_FLOOR, credibility_score)
```

### Behavior

- **If credibility missing**: Defaults to 1.0 (no adjustment)
- **If credibility < 0.2**: Floored at 0.2 (prevents complete exclusion)
- **If credibility = 1.0**: No change from base weights
- **If credibility < 1.0**: Reduces agent's influence proportionally

### Example: Ensemble with Credibility

**Base weights:**
- Buffett: 0.6
- Momentum: 0.4

**With credibility scores:**
- Buffett credibility: 0.75
- Momentum credibility: 0.90

**Adjusted weights:**
- Buffett: 0.6 × 0.75 = 0.45
- Momentum: 0.4 × 0.90 = 0.36
- Total: 0.81

**Normalized:**
- Buffett: 0.45 / 0.81 = 0.556 (55.6%)
- Momentum: 0.36 / 0.81 = 0.444 (44.4%)

Result: Momentum gets slightly more weight due to higher credibility, even though base weight is lower.

---

## Verification Commands

### 1. CLI Deterministic Run with Multiple Agents

```bash
cd ai-hedge-fund
HEDGEFUND_NO_LLM=1 poetry run python src/main.py \
  --ticker AAPL,MSFT \
  --analysts ben_graham,charlie_munger,peter_lynch,warren_buffett,momentum,ensemble,performance_auditor
```

**Expected behavior:**
- All agents run deterministically (no LLM calls)
- Performance Auditor computes credibility scores
- Ensemble combines Buffett + Momentum with credibility weighting
- Output shows credibility-adjusted weights in reasoning

### 2. Backtest Compare Run

```bash
cd ai-hedge-fund
HEDGEFUND_NO_LLM=1 poetry run python src/compare_backtests.py \
  --tickers AAPL,MSFT \
  --start-date 2024-01-01 \
  --end-date 2024-12-31 \
  --initial-capital 100000
```

**Expected behavior:**
- All strategies run deterministically
- Performance Auditor tracks credibility across backtest days
- Ensemble and Conflict Arbiter use credibility-weighted signals
- Results are reproducible across runs

### 3. Verify Credibility Storage

```bash
cd ai-hedge-fund
HEDGEFUND_NO_LLM=1 poetry run python src/main.py \
  --ticker AAPL \
  --analysts warren_buffett,momentum,performance_auditor,ensemble
```

**Check output:**
- Look for `agent_credibility` in state (if debugging enabled)
- Ensemble reasoning should show credibility values: `(cred: Buffett=0.XX, Momentum=0.XX)`
- Credibility scores should be between 0.0 and 1.0

---

## Files Modified

### Part A (Deterministic Intelligence)
- `src/agents/ben_graham.py` - Added `create_rule_based_ben_graham_signal()`
- `src/agents/charlie_munger.py` - Added `_rule_based()` function
- `src/agents/peter_lynch.py` - Added `create_rule_based_peter_lynch_signal()`
- `src/agents/michael_burry.py` - Added `create_rule_based_michael_burry_signal()`
- `src/agents/stanley_druckenmiller.py` - Added `create_rule_based_druckenmiller_signal()`
- `src/agents/phil_fisher.py` - Added `create_rule_based_phil_fisher_signal()`
- `src/agents/bill_ackman.py` - Added `create_rule_based_bill_ackman_signal()`
- `src/agents/aswath_damodaran.py` - Added `create_rule_based_damodaran_signal()`

### Part B (Credibility Weighting)
- `src/agents/performance_auditor.py` - Stores `agent_credibility` in state
- `src/agents/ensemble.py` - Updated to weight by credibility
- `src/agents/conflict_arbiter.py` - Updated to weight by credibility

---

## Backward Compatibility

✅ **Fully backward compatible:**
- All changes are additive (new parameters with defaults)
- If `agent_credibility` is missing, defaults to 1.0 (no change in behavior)
- Existing workflows continue to work unchanged
- No changes to `AgentState` structure (only additions to `state["data"]`)

---

## Summary

**Part A:** 8 analyst agents now have deterministic `rule_based_factory` functions, enabling full deterministic operation in `HEDGEFUND_NO_LLM=1` mode.

**Part B:** Performance Auditor credibility scores now influence signal weighting in Ensemble and Conflict Arbiter agents, improving decision quality based on historical performance.

**Total agents with deterministic mode:** 11 (Warren Buffett, Momentum, Ensemble, News Sentiment, + 8 new)

**Credibility weighting:** Active in Ensemble and Conflict Arbiter when Performance Auditor is included in workflow.
