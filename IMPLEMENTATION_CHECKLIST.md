# Implementation Checklist: 10-Agent Restructure

**Status:** In Progress  
**Target:** Reduce from 30 agents to 10 agents  
**Date:** 2025-01-XX

---

## Phase 1: File Removal (17 files)

### Value Cluster Merges (4 files → merge into warren_buffett.py)
- [ ] Remove `src/agents/ben_graham.py`
- [ ] Remove `src/agents/charlie_munger.py`
- [ ] Remove `src/agents/michael_burry.py`
- [ ] Remove `src/agents/mohnish_pabrai.py`

### Growth Cluster Merges (3 files → merge into peter_lynch.py)
- [ ] Remove `src/agents/cathie_wood.py`
- [ ] Remove `src/agents/phil_fisher.py`
- [ ] Remove `src/agents/growth_agent.py`

### Redundant Analysts (5 files)
- [ ] Remove `src/agents/valuation.py` (redundant with aswath_damodaran)
- [ ] Remove `src/agents/sentiment.py` (redundant with news_sentiment)
- [ ] Remove `src/agents/rakesh_jhunjhunwala.py` (redundant with druckenmiller)
- [ ] Remove `src/agents/fundamentals.py` (redundant with value/valuation)
- [ ] Remove `src/agents/bill_ackman.py` (too narrow strategy)

### Meta-Agents (2 files)
- [ ] Remove `src/agents/ensemble.py` (Portfolio Manager aggregates)
- [ ] Remove `src/agents/conflict_arbiter.py` (Portfolio Manager handles conflicts)

### System Agent Merge (1 file)
- [ ] Remove `src/agents/risk_manager.py` (merge volatility into portfolio_allocator)

### Advisory Agents (2 files - removed from $1M fund)
- [ ] Remove `src/agents/technicals.py` (too noisy)
- [ ] Remove `src/agents/news_sentiment.py` (too noisy)
- [ ] Remove `src/agents/stanley_druckenmiller.py` (too broad)

**Total Removed: 17 files**

---

## Phase 2: Composite Agent Enhancement

### Value Composite (warren_buffett.py)
- [ ] Enhance `analyze_fundamentals()` to incorporate:
  - Graham: Margin of safety emphasis (debt-to-equity, current ratio)
  - Munger: Quality business focus (ROE, consistency)
  - Burry: Deep value metrics (P/B, cash/debt)
  - Pabrai: Dhandho principles (low risk, high reward)
- [ ] Update `create_rule_based_ben_graham_signal()` to be part of composite
- [ ] Update agent description to "Value Composite Analyst"
- [ ] Ensure deterministic fallback incorporates all value principles
- [ ] Test composite value analysis

### Growth Composite (peter_lynch.py)
- [ ] Enhance `analyze_lynch_growth()` to incorporate:
  - Wood: Disruption/innovation focus (R&D intensity, market disruption)
  - Fisher: Scuttlebutt research (management quality, competitive position)
  - Growth Analyst: Growth rate consistency
- [ ] Update agent description to "Growth Composite Analyst"
- [ ] Ensure deterministic fallback incorporates all growth principles
- [ ] Test composite growth analysis

---

## Phase 3: Analyst Registration Update

### Update `src/utils/analysts.py`
- [ ] Remove all deprecated agents from `ANALYST_CONFIG`:
  - ben_graham, charlie_munger, michael_burry, mohnish_pabrai
  - cathie_wood, phil_fisher, growth_analyst
  - valuation_analyst, sentiment_analyst, rakesh_jhunjhunwala
  - fundamentals_analyst, bill_ackman
  - ensemble, conflict_arbiter
  - technical_analyst, news_sentiment_analyst, stanley_druckenmiller
- [ ] Update remaining agent descriptions:
  - warren_buffett: "Value Composite Analyst"
  - peter_lynch: "Growth Composite Analyst"
- [ ] Update order values to reflect new hierarchy
- [ ] Remove imports for deprecated agents

---

## Phase 4: Portfolio Manager Weighting

### Update `src/agents/portfolio_manager.py`
- [ ] Filter signal aggregation to only use 5 core analysts:
  - warren_buffett_agent (30% weight)
  - peter_lynch_agent (25% weight)
  - aswath_damodaran_agent (20% weight)
  - momentum_agent (15% weight, regime-adjusted)
  - mean_reversion_agent (10% weight, regime-adjusted)
- [ ] Update `generate_trading_decision_rule_based()` to:
  - Apply explicit weights: 30/25/20/15/10
  - Filter out advisory agents (market_regime, performance_auditor)
  - Keep regime-based weighting for Momentum/Mean Reversion
- [ ] Update signal filtering logic to exclude:
  - All deprecated agents
  - Advisory agents (market_regime, performance_auditor)
  - System agents (risk_management, portfolio_manager, risk_budget, portfolio_allocator)
- [ ] Test weighted aggregation

---

## Phase 5: Advisory Agent Enforcement

### Market Regime Analyst (already correct)
- [ ] Verify `market_regime.py` does NOT write to `analyst_signals`
- [ ] Verify it only writes to `state["data"]["market_regime"]`
- [ ] No changes needed ✅

### Performance Auditor (already correct)
- [ ] Verify `performance_auditor.py` does NOT write to `analyst_signals`
- [ ] Verify it only writes to `state["data"]["agent_credibility"]`
- [ ] No changes needed ✅

### News Sentiment (needs modification)
- [ ] Modify `news_sentiment.py` to NOT write to `analyst_signals`
- [ ] Write advisory data to `state["data"]["advisory"]["news_sentiment"]`
- [ ] Update Portfolio Manager to read advisory data (for context only)

### Stanley Druckenmiller (needs modification)
- [ ] Modify `stanley_druckenmiller.py` to NOT write to `analyst_signals`
- [ ] Write advisory data to `state["data"]["advisory"]["macro"]`
- [ ] Update Portfolio Manager to read advisory data (for context only)

### Technical Analyst (needs modification)
- [ ] Modify `technicals.py` to NOT write to `analyst_signals`
- [ ] Write advisory data to `state["data"]["advisory"]["technical"]`
- [ ] Update Portfolio Manager to read advisory data (for context only)

**Note:** Actually, per CTO plan, these 3 are removed entirely for $1M fund.

---

## Phase 6: Risk Manager Merge

### Update `src/agents/portfolio_allocator.py`
- [ ] Add volatility limit calculation from `risk_manager.py`
- [ ] Integrate volatility-adjusted position limits
- [ ] Update constraint enforcement to include volatility limits
- [ ] Remove dependency on risk_manager signals

### Update `src/main.py`
- [ ] Remove `risk_management_agent` node from workflow
- [ ] Update workflow: Analysts → Portfolio Manager → Risk Budget → Portfolio Allocator → END
- [ ] Remove risk_manager import

---

## Phase 7: Testing & Verification

### Functional Tests
- [ ] Verify 5 core analysts generate signals
- [ ] Verify Portfolio Manager uses only 5 core analysts
- [ ] Verify weights are applied correctly (30/25/20/15/10)
- [ ] Verify regime weights apply to Momentum/Mean Reversion
- [ ] Verify Market Regime does NOT emit trade signals
- [ ] Verify Performance Auditor does NOT emit trade signals
- [ ] Verify Portfolio Allocator enforces constraints
- [ ] Test deterministic mode (`HEDGEFUND_NO_LLM=1`)

### Integration Tests
- [ ] Full workflow: Analysts → PM → Risk Budget → Allocator
- [ ] Verify no deprecated agents are called
- [ ] Verify advisory agents provide context only
- [ ] Verify signal aggregation works correctly

---

## Final Agent Count Verification

### Core Analysts (5):
1. ✅ Value Composite (warren_buffett)
2. ✅ Growth Composite (peter_lynch)
3. ✅ Valuation (aswath_damodaran)
4. ✅ Momentum
5. ✅ Mean Reversion

### Advisory (2):
6. ✅ Market Regime
7. ✅ Performance Auditor

### System (3):
8. ✅ Portfolio Manager
9. ✅ Risk Budget
10. ✅ Portfolio Allocator

**Total: 10 agents** ✅

---

## File Change Summary

### Files Removed: 17
- Value cluster: 4 files
- Growth cluster: 3 files
- Redundant: 5 files
- Meta-agents: 2 files
- System merge: 1 file
- Advisory removal: 2 files

### Files Modified: 6
- `warren_buffett.py` (composite enhancement)
- `peter_lynch.py` (composite enhancement)
- `portfolio_manager.py` (weighting update)
- `portfolio_allocator.py` (risk manager merge)
- `analysts.py` (registry update)
- `main.py` (workflow update)

### Files Unchanged: 5
- `aswath_damodaran.py`
- `momentum.py`
- `mean_reversion.py`
- `market_regime.py`
- `performance_auditor.py`
- `risk_budget.py`

---

## Rollback Plan

If issues arise:
1. Keep deprecated files in `.deprecated/` folder
2. Maintain git history for all changes
3. Can restore individual agents if needed
4. Test incrementally (one phase at a time)

---

## Notes

- All changes maintain backward compatibility with existing data structures
- Deterministic mode must continue to work
- No new data sources required
- Focus on traceability and simplicity
