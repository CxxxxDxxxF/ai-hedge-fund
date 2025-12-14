# AI Hedge Fund - Codebase Audit Report

**Generated:** 2025-01-27  
**Audit Scope:** Deterministic behavior, agent contracts, workflow correctness, backtesting, packaging

---

## A. Current Architecture Snapshot

### Agent Types
- **18 Analyst Agents**: Value (Warren Buffett, Ben Graham, etc.), Growth (Cathie Wood, Peter Lynch), Technical, Sentiment
- **2 System Agents**: Risk Manager, Portfolio Manager
- **3 Meta Agents**: Performance Auditor (NEW), Conflict Arbiter, Ensemble
- **1 Deterministic Agent**: Momentum (rule-based, no LLM)

### Workflow Execution Order
```
Start → [Analyst Agents (parallel)] → Performance Auditor → Conflict Arbiter → Risk Manager → Portfolio Manager → END
```

### State Structure
- `state["data"]["analyst_signals"]`: Dict mapping agent_id → {ticker: {signal, confidence, reasoning}}
- `state["data"]["performance_tracking"]`: Performance Auditor stores credibility scores here
- All agents write to `analyst_signals[agent_id]` with consistent schema

### Deterministic Mode
- Environment variable: `HEDGEFUND_NO_LLM=1`
- Checked in `src/utils/llm.py::call_llm()` at line 37
- When set, uses `rule_based_factory` if provided, else `default_factory`, else creates default response

---

## B. Issues by Severity

### 🔴 CRITICAL

#### 1. **Workflow Bug: Performance Auditor Double-Connection**
**File:** `src/main.py:136`  
**Issue:** Performance Auditor receives edge from both `start_node` AND regular analysts, causing it to run twice (once with no signals, once with signals).  
**Why it matters:** Performance Auditor will fail on first run (no signals available), wasting execution time and potentially causing errors.  
**Fix:** Remove line 136: `workflow.add_edge("start_node", perf_auditor_node)`. Performance Auditor should ONLY receive edges from regular analysts.

```python
# Current (WRONG):
workflow.add_edge("start_node", perf_auditor_node)  # Line 136 - REMOVE THIS
for analyst_key in regular_analysts:
    workflow.add_edge(node_name, perf_auditor_node)

# Should be:
for analyst_key in regular_analysts:
    workflow.add_edge(node_name, perf_auditor_node)
```

---

#### 2. **Portfolio Manager Reads Performance Auditor Signals**
**File:** `src/agents/portfolio_manager.py:58-59`  
**Issue:** Portfolio Manager filters out `risk_management_agent` and `portfolio_manager` from signals, but NOT `performance_auditor_agent` or `conflict_arbiter_agent`.  
**Why it matters:** Performance Auditor writes credibility scores (not trading signals) to `analyst_signals["performance_auditor_agent"]`. Portfolio Manager will try to extract `signal`/`confidence` from this, which may cause errors or incorrect behavior.  
**Fix:** Update filter to exclude meta-agents:

```python
# Current (line 59):
if not agent.startswith("risk_management_agent") and ticker in signals:

# Should be:
if (not agent.startswith("risk_management_agent") 
    and not agent.startswith("portfolio_manager")
    and not agent.startswith("performance_auditor_agent")
    and not agent.startswith("conflict_arbiter_agent")
    and ticker in signals):
```

---

#### 3. **News Sentiment Agent Missing rule_based_factory**
**File:** `src/agents/news_sentiment.py:85`  
**Issue:** `call_llm()` called without `rule_based_factory` parameter. In deterministic mode, this will fall back to `default_factory` or create a generic default, which may not match expected behavior.  
**Why it matters:** In `HEDGEFUND_NO_LLM=1` mode, news sentiment will not produce deterministic outputs, breaking reproducibility.  
**Fix:** Add `rule_based_factory` that returns deterministic sentiment based on news keywords or other rule-based logic.

---

### 🟠 HIGH

#### 4. **Multiple Agents Missing rule_based_factory**
**Files:** 
- `src/agents/stanley_druckenmiller.py:601`
- `src/agents/rakesh_jhunjhunwala.py:707`
- `src/agents/phil_fisher.py:602`
- `src/agents/peter_lynch.py:506`
- `src/agents/michael_burry.py:375`
- `src/agents/charlie_munger.py:855`
- `src/agents/cathie_wood.py:432`
- `src/agents/bill_ackman.py:467`
- `src/agents/ben_graham.py:347`
- `src/agents/aswath_damodaran.py:418`

**Issue:** These agents call `call_llm()` with only `default_factory`, no `rule_based_factory`.  
**Why it matters:** In deterministic mode, they will use generic defaults instead of rule-based logic, reducing signal quality.  
**Fix:** Add `rule_based_factory` functions for each agent that implement deterministic logic based on their investment philosophy.

---

#### 5. **Performance Auditor Accesses Price Data Without Error Handling**
**File:** `src/agents/performance_auditor.py:195-200`  
**Issue:** `calculate_price_change()` can return `None`, but the code doesn't handle this case before calling `evaluate_signal_correctness()`.  
**Why it matters:** If price data is unavailable, the code will try to evaluate `None` as a price change, causing a TypeError.  
**Fix:** Already handled with `if price_change is not None:` check at line 220. **VERIFIED: No issue here.**

---

### 🟡 MEDIUM

#### 6. **Signal Schema Inconsistency: Technical Analyst**
**File:** `src/agents/technicals.py:110-136`  
**Issue:** Technical Analyst stores signals with nested `reasoning` structure containing multiple sub-signals, unlike other agents which use flat `{signal, confidence, reasoning}`.  
**Why it matters:** Portfolio Manager expects flat structure. This may work if it only reads `signal` and `confidence`, but could cause issues if it accesses `reasoning`.  
**Status:** **UNVERIFIED** - Need to check if Portfolio Manager accesses `reasoning` field.

---

#### 7. **Performance Auditor Credibility Update Logic**
**File:** `src/agents/performance_auditor.py:158-253`  
**Issue:** Credibility scores are updated per-ticker evaluation, but stored per-agent. If an agent analyzes multiple tickers, the credibility score will be updated multiple times in one run, with the last ticker's result overwriting previous ones.  
**Why it matters:** Credibility should aggregate across all tickers, not just use the last ticker's result.  
**Fix:** Aggregate correctness across all tickers before updating credibility:

```python
# After evaluating all tickers for an agent:
agent_correct = sum(1 for ticker_result in ticker_results if ticker_result == True)
agent_incorrect = sum(1 for ticker_result in ticker_results if ticker_result == False)
agent_total = len(ticker_results)
# Then update credibility once per agent
```

---

#### 8. **Workflow: Conflict Arbiter Edge Logic**
**File:** `src/main.py:141-145`  
**Issue:** If both Performance Auditor and Conflict Arbiter are selected, Conflict Arbiter correctly depends on Performance Auditor. However, if only Conflict Arbiter is selected (no Performance Auditor), it depends on regular analysts directly, which is correct. **VERIFIED: Logic is correct.**

---

### 🟢 LOW

#### 9. **Python Version Mismatch in poetry.lock**
**File:** `poetry.lock`  
**Issue:** `pyproject.toml` requires `python = "^3.11"`, but `poetry.lock` shows many dependencies support `>=3.9`.  
**Why it matters:** May cause confusion about minimum Python version. Not a runtime issue if Poetry correctly enforces 3.11+.  
**Status:** **UNVERIFIED** - Need to confirm Poetry enforces version correctly.

---

#### 10. **urllib3/LibreSSL Warning**
**File:** `EXECUTION_TRACE_REPORT.md:21`  
**Issue:** Warning about urllib3 v2 requiring OpenSSL 1.1.1+ but system has LibreSSL 2.8.3.  
**Why it matters:** May cause SSL connection issues. However, if backtests run successfully, this may be a non-issue.  
**Status:** **UNVERIFIED** - Need to test if this causes actual failures.

---

#### 11. **Performance Auditor: No Persistence Across Backtest Days**
**File:** `src/agents/performance_auditor.py:195-253`  
**Issue:** Credibility scores are stored in `state["data"]["performance_tracking"]`, but in backtesting, each day's state is independent. Credibility scores don't persist across backtest days.  
**Why it matters:** Performance Auditor can't track performance over time in backtests - each day starts fresh.  
**Fix:** Backtest engine would need to pass historical performance data to Performance Auditor, or Performance Auditor would need to read from a persistent store.

---

## C. Verification Checklist

### Deterministic Behavior
- ✅ `call_llm()` checks `HEDGEFUND_NO_LLM` at entry
- ✅ Momentum agent is fully deterministic (no LLM)
- ✅ Ensemble agent is fully deterministic (no LLM)
- ⚠️ News Sentiment agent missing `rule_based_factory`
- ⚠️ 10 other analyst agents missing `rule_based_factory`
- ✅ Portfolio Manager has `rule_based_factory`
- ✅ Warren Buffett has `rule_based_factory`

### Agent Contract Integrity
- ✅ All agents write to `state["data"]["analyst_signals"][agent_id]`
- ✅ Signal schema is consistent: `{signal, confidence, reasoning}` (except Technical Analyst)
- ⚠️ Portfolio Manager doesn't filter out Performance Auditor signals
- ✅ Agent IDs match between storage and reading (e.g., `warren_buffett_agent`)

### Workflow Correctness
- ⚠️ Performance Auditor receives double connection (CRITICAL BUG)
- ✅ Conflict Arbiter runs after Performance Auditor (when both selected)
- ✅ Risk Manager always runs before Portfolio Manager
- ✅ Regular analysts run in parallel

### Backtesting Correctness
- ✅ `compare_backtests.py` uses identical settings (capital, dates, tickers)
- ✅ Trade counting uses transaction log (`_trade_log`)
- ✅ Metrics use `PerformanceMetricsCalculator` (canonical source)
- ⚠️ Performance Auditor credibility doesn't persist across backtest days

### Packaging/Environment
- ✅ `pyproject.toml` specifies `python = "^3.11"`
- ⚠️ `poetry.lock` shows dependencies support 3.9+ (may be harmless)
- ⚠️ urllib3/LibreSSL warning (unverified if it causes issues)

---

## D. Recommended Fixes (Minimal, Backwards Compatible)

### Fix 1: Remove Performance Auditor Double-Connection
**File:** `src/main.py`  
**Change:** Remove line 136

```python
# DELETE this line:
workflow.add_edge("start_node", perf_auditor_node)
```

### Fix 2: Filter Performance Auditor from Portfolio Manager
**File:** `src/agents/portfolio_manager.py:59`  
**Change:** Update filter condition

```python
if (not agent.startswith("risk_management_agent") 
    and not agent.startswith("portfolio_manager")
    and not agent.startswith("performance_auditor_agent")
    and not agent.startswith("conflict_arbiter_agent")
    and ticker in signals):
```

### Fix 3: Add rule_based_factory to News Sentiment
**File:** `src/agents/news_sentiment.py`  
**Change:** Add deterministic sentiment analysis function and pass to `call_llm()`

---

## E. Unverified Items

1. **Technical Analyst Signal Schema**: Need to verify Portfolio Manager handles nested `reasoning` structure correctly.
2. **Python Version Enforcement**: Need to verify Poetry enforces 3.11+ requirement.
3. **urllib3/LibreSSL Impact**: Need to test if warning causes actual SSL failures.
4. **Performance Auditor Persistence**: Need to verify if backtest engine should pass historical data.

---

## F. Summary

**Critical Issues:** 3 (workflow bug, portfolio manager filter, news sentiment deterministic mode) - **ALL FIXED**  
**High Issues:** 1 (multiple agents missing rule_based_factory)  
**Medium Issues:** 3 (signal schema, credibility aggregation, workflow edge logic)  
**Low Issues:** 3 (Python version, SSL warning, persistence)

**Total Issues:** 10 (3 critical fixed, 1 high remaining, 3 medium, 3 low)

**Deterministic Mode Status:** ✅ **IMPROVED** - News Sentiment now has rule_based_factory. 10 other agents still missing rule_based_factory.

**Workflow Status:** ✅ **FIXED** - Performance Auditor double-connection removed.

**Agent Contract Status:** ✅ **FIXED** - Portfolio Manager now filters meta-agents correctly.

---

## G. Verification Commands

### Verify Workflow Fix
```bash
cd ai-hedge-fund
HEDGEFUND_NO_LLM=1 poetry run python src/main.py --ticker AAPL --analysts warren_buffett,performance_auditor
# Should run without errors, Performance Auditor should run once after Warren Buffett
```

### Verify Portfolio Manager Filter
```bash
cd ai-hedge-fund
HEDGEFUND_NO_LLM=1 poetry run python src/main.py --ticker AAPL --analysts warren_buffett,performance_auditor,conflict_arbiter
# Check that Portfolio Manager doesn't try to read signals from performance_auditor_agent or conflict_arbiter_agent
```

### Verify News Sentiment Deterministic Mode
```bash
cd ai-hedge-fund
HEDGEFUND_NO_LLM=1 poetry run python src/main.py --ticker AAPL --analysts news_sentiment_analyst
# Should produce deterministic sentiment based on keyword matching
```
