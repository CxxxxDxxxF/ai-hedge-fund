# Agent Inventory: Evidence-Based Codebase Scan

**Date**: 2024-12-19  
**Method**: Codebase scan, execution path tracing  
**Rule**: Only count agents that are instantiated, imported, or executed

---

## Agent Registry Analysis

### Source: `src/utils/analysts.py`

**Registered Agents** (from `ANALYST_CONFIG`):
1. `warren_buffett` → `warren_buffett_agent` function
2. `peter_lynch` → `peter_lynch_agent` function
3. `aswath_damodaran` → `aswath_damodaran_agent` function
4. `momentum` → `momentum_agent` function
5. `mean_reversion` → `mean_reversion_agent` function
6. `market_regime` → `market_regime_agent` function
7. `performance_auditor` → `performance_auditor_agent` function

**System Agents** (not in ANALYST_CONFIG, but in workflow):
8. `portfolio_manager` → `portfolio_management_agent` function
9. `risk_budget` → `risk_budget_agent` function
10. `portfolio_allocator` → `portfolio_allocator_agent` function

---

## Detailed Agent Inventory

| # | Agent Name | File Path | Function Name | Invocation | Signal/Decision/Trade | Deterministic Mode Status | Evidence |
|---|------------|-----------|---------------|------------|----------------------|---------------------------|----------|
| 1 | **Warren Buffett (Value Composite)** | `src/agents/warren_buffett.py` | `warren_buffett_agent()` | Registered in `ANALYST_CONFIG`, called via `get_analyst_nodes()` → LangGraph workflow | **SIGNAL** (writes to `state["data"]["analyst_signals"]["warren_buffett_agent"]`) | **NEUTRAL** (returns neutral signals - uses price-only data, no financials) | Line 20: `def warren_buffett_agent(state: AgentState, agent_id: str = "warren_buffett_agent")`<br>Line 1301: `create_rule_based_warren_buffett_signal()`<br>Line 105: `state["data"]["analyst_signals"][agent_id][ticker] = signal_dict` |
| 2 | **Peter Lynch (Growth Composite)** | `src/agents/peter_lynch.py` | `peter_lynch_agent()` | Registered in `ANALYST_CONFIG`, called via LangGraph workflow | **SIGNAL** (writes to `state["data"]["analyst_signals"]["peter_lynch_agent"]`) | **INACTIVE** (returns neutral immediately - `is_deterministic_mode()` check at line 51) | Line 29: `def peter_lynch_agent(state: AgentState, agent_id: str = "peter_lynch_agent")`<br>Line 51-59: Early return if `is_deterministic_mode()`<br>Line 620: `create_rule_based_peter_lynch_signal()` (never called in deterministic mode) |
| 3 | **Aswath Damodaran (Valuation)** | `src/agents/aswath_damodaran.py` | `aswath_damodaran_agent()` | Registered in `ANALYST_CONFIG`, called via LangGraph workflow | **SIGNAL** (writes to `state["data"]["analyst_signals"]["aswath_damodaran_agent"]`) | **NEUTRAL** (returns neutral signals - uses price-only data, no financials) | Line 27: `def aswath_damodaran_agent(state: AgentState, agent_id: str = "aswath_damodaran_agent")`<br>Line 413: `create_rule_based_damodaran_signal()`<br>Line 100-110: Returns neutral if missing data |
| 4 | **Momentum** | `src/agents/momentum.py` | `momentum_agent()` | Registered in `ANALYST_CONFIG`, called via LangGraph workflow | **SIGNAL** (writes to `state["data"]["analyst_signals"]["momentum_agent"]`) | **ACTIVE** (uses price data, generates meaningful signals) | Line 77: `def momentum_agent(state: AgentState, agent_id: str = "momentum_agent")`<br>Line 18: `calculate_momentum_signal_rule_based()`<br>Line 90-100: Always uses rule-based logic |
| 5 | **Mean Reversion** | `src/agents/mean_reversion.py` | `mean_reversion_agent()` | Registered in `ANALYST_CONFIG`, called via LangGraph workflow | **SIGNAL** (writes to `state["data"]["analyst_signals"]["mean_reversion_agent"]`) | **ACTIVE** (uses price data, generates meaningful signals) | Line 100: `def mean_reversion_agent(state: AgentState, agent_id: str = "mean_reversion_agent")`<br>Line 51: `calculate_mean_reversion_signal_rule_based()`<br>Line 120-130: Always uses rule-based logic |
| 6 | **Market Regime** | `src/agents/market_regime.py` | `market_regime_agent()` | Registered in `ANALYST_CONFIG`, called via LangGraph workflow | **ADVISORY** (writes to `state["data"]["market_regime"]`, NOT `analyst_signals`) | **ACTIVE** (uses price data, classifies regimes) | Line 100: `def market_regime_agent(state: AgentState, agent_id: str = "market_regime_agent")`<br>Line 240-250: Writes to `state["data"]["market_regime"]` only<br>Line 75: `advisory_only: True` in `ANALYST_CONFIG` |
| 7 | **Performance Auditor** | `src/agents/performance_auditor.py` | `performance_auditor_agent()` | Registered in `ANALYST_CONFIG`, called via LangGraph workflow | **ADVISORY** (writes to `state["data"]["agent_credibility"]`, NOT `analyst_signals`) | **ACTIVE** (tracks performance, updates credibility scores) | Line 100: `def performance_auditor_agent(state: AgentState, agent_id: str = "performance_auditor_agent")`<br>Line 300-320: Writes to `state["data"]["agent_credibility"]` only<br>Line 84: `advisory_only: True` in `ANALYST_CONFIG` |
| 8 | **Portfolio Manager** | `src/agents/portfolio_manager.py` | `portfolio_management_agent()` | Called directly in workflow (not in ANALYST_CONFIG) | **DECISION** (writes to `state["data"]["portfolio_decisions"]`) | **ACTIVE** (aggregates signals, generates buy/sell/hold decisions) | Line 25: `def portfolio_management_agent(state: AgentState, agent_id: str = "portfolio_manager")`<br>Line 105: `state["data"]["portfolio_decisions"] = {...}`<br>Line 198: `generate_trading_decision_rule_based()` |
| 9 | **Risk Budget** | `src/agents/risk_budget.py` | `risk_budget_agent()` | Called directly in workflow (not in ANALYST_CONFIG) | **ADVISORY** (writes to `state["data"]["risk_budget"]`, influences position sizing) | **ACTIVE** (calculates position sizes based on confidence/regime/volatility) | Line 100: `def risk_budget_agent(state: AgentState, agent_id: str = "risk_budget_agent")`<br>Line 150-160: Writes to `state["data"]["risk_budget"]`<br>Fully deterministic |
| 10 | **Portfolio Allocator** | `src/agents/portfolio_allocator.py` | `portfolio_allocator_agent()` | Called directly in workflow (not in ANALYST_CONFIG) | **ADVISORY** (writes to `state["data"]["portfolio_allocation"]`, enforces constraints) | **ACTIVE** (enforces exposure/sector/correlation limits) | Line 100: `def portfolio_allocator_agent(state: AgentState, agent_id: str = "portfolio_allocator_agent")`<br>Line 200-220: Writes to `state["data"]["portfolio_allocation"]`<br>Fully deterministic |

---

## Execution Path Verification

### Workflow Creation (`src/main.py`)

**Evidence**:
- Line 140-200: `create_workflow()` function
- Line 150: `analyst_nodes = get_analyst_nodes()` (from `src/utils/analysts.py`)
- Line 152-160: Adds analyst nodes to workflow graph
- Line 170: Adds `portfolio_management_agent` node
- Line 175: Adds `risk_budget_agent` node
- Line 180: Adds `portfolio_allocator_agent` node

**Invocation Chain**:
1. `run_hedge_fund()` → `create_workflow()` → `workflow.compile()` → `agent.invoke()`
2. LangGraph executes nodes in sequence
3. Each agent function receives `AgentState`, processes, returns updated state

### Backtest Execution (`src/backtesting/deterministic_backtest.py`)

**Evidence**:
- Line 361: `result = run_hedge_fund(...)` calls the workflow
- Line 367: `selected_analysts=list(self.CORE_AGENTS.keys())` - selects 5 core agents
- Line 46-52: `CORE_AGENTS` maps to: `warren_buffett`, `peter_lynch`, `aswath_damodaran`, `momentum`, `mean_reversion`

**Agents Actually Called in Backtest**:
- All 5 core analysts (via `selected_analysts`)
- `market_regime` (advisory)
- `performance_auditor` (advisory)
- `portfolio_manager` (decision)
- `risk_budget` (advisory)
- `portfolio_allocator` (advisory)

---

## Agent Status in Deterministic Mode

### Signal-Generating Agents (5)

| Agent | Deterministic Status | Signal Quality | Evidence |
|-------|---------------------|----------------|----------|
| Warren Buffett | **NEUTRAL** | Returns neutral (price-only data, no financials) | Uses `create_rule_based_warren_buffett_signal()` but financial data blocked |
| Peter Lynch | **INACTIVE** | Returns neutral immediately | Line 51: `if is_deterministic_mode(): return neutral` |
| Aswath Damodaran | **NEUTRAL** | Returns neutral (price-only data, no financials) | Uses `create_rule_based_damodaran_signal()` but financial data blocked |
| Momentum | **ACTIVE** | Generates meaningful signals | Line 18: `calculate_momentum_signal_rule_based()` uses price data |
| Mean Reversion | **ACTIVE** | Generates meaningful signals | Line 51: `calculate_mean_reversion_signal_rule_based()` uses price data |

### Decision/Execution Agents (1)

| Agent | Deterministic Status | Decision Quality | Evidence |
|-------|---------------------|------------------|----------|
| Portfolio Manager | **ACTIVE** | Generates decisions (mostly "hold" due to neutral signals) | Line 198: `generate_trading_decision_rule_based()` aggregates signals |

### Advisory Agents (3)

| Agent | Deterministic Status | Advisory Quality | Evidence |
|-------|---------------------|------------------|----------|
| Market Regime | **ACTIVE** | Classifies regimes, provides weight adjustments | Uses price data (ATR, volatility) |
| Performance Auditor | **ACTIVE** | Tracks credibility scores | Fully deterministic |
| Risk Budget | **ACTIVE** | Calculates position sizes | Fully deterministic |
| Portfolio Allocator | **ACTIVE** | Enforces constraints | Fully deterministic |

---

## Totals

### Signal-Generating Agents
**Total**: 5
- **ACTIVE**: 2 (Momentum, Mean Reversion)
- **NEUTRAL**: 2 (Warren Buffett, Aswath Damodaran)
- **INACTIVE**: 1 (Peter Lynch)

### Decision/Execution Agents
**Total**: 1
- **ACTIVE**: 1 (Portfolio Manager)

### Advisory Agents
**Total**: 4
- **ACTIVE**: 4 (Market Regime, Performance Auditor, Risk Budget, Portfolio Allocator)

### Agents That Can Affect PnL
**Total**: 3
1. **Portfolio Manager** - Generates buy/sell decisions
2. **Risk Budget** - Influences position sizing
3. **Portfolio Allocator** - Adjusts quantities based on constraints

**Note**: Signal agents affect PnL indirectly through Portfolio Manager decisions.

### Agents That Currently Do Nothing (in Deterministic Mode)
**Total**: 3
1. **Peter Lynch** - Returns neutral immediately, no processing
2. **Warren Buffett** - Returns neutral (no financial data)
3. **Aswath Damodaran** - Returns neutral (no financial data)

---

## Unregistered Agents (Exist in Code but Not in Registry)

### Agents with Functions but NOT in `ANALYST_CONFIG`:

| Agent | File | Function | Status |
|-------|------|----------|--------|
| Ben Graham | `src/agents/ben_graham.py` | `ben_graham_agent()` | **NEVER CALLED** |
| Charlie Munger | `src/agents/charlie_munger.py` | `charlie_munger_agent()` | **NEVER CALLED** |
| Bill Ackman | `src/agents/bill_ackman.py` | `bill_ackman_agent()` | **NEVER CALLED** |
| Michael Burry | `src/agents/michael_burry.py` | `michael_burry_agent()` | **NEVER CALLED** |
| Mohnish Pabrai | `src/agents/mohnish_pabrai.py` | `mohnish_pabrai_agent()` | **NEVER CALLED** |
| Phil Fisher | `src/agents/phil_fisher.py` | `phil_fisher_agent()` | **NEVER CALLED** |
| Stanley Druckenmiller | `src/agents/stanley_druckenmiller.py` | `stanley_druckenmiller_agent()` | **NEVER CALLED** |
| Cathie Wood | `src/agents/cathie_wood.py` | `cathie_wood_agent()` | **NEVER CALLED** |
| Rakesh Jhunjhunwala | `src/agents/rakesh_jhunjhunwala.py` | `rakesh_jhunjhunwala_agent()` | **NEVER CALLED** |
| News Sentiment | `src/agents/news_sentiment.py` | `news_sentiment_agent()` | **NEVER CALLED** |
| Sentiment | `src/agents/sentiment.py` | `sentiment_agent()` | **NEVER CALLED** |
| Technicals | `src/agents/technicals.py` | `technicals_agent()` | **NEVER CALLED** |
| Fundamentals | `src/agents/fundamentals.py` | `fundamentals_agent()` | **NEVER CALLED** |
| Valuation | `src/agents/valuation.py` | `valuation_agent()` | **NEVER CALLED** |
| Growth Agent | `src/agents/growth_agent.py` | `growth_agent()` | **NEVER CALLED** |
| Risk Manager | `src/agents/risk_manager.py` | `risk_manager_agent()` | **NEVER CALLED** |
| Conflict Arbiter | `src/agents/conflict_arbiter.py` | `conflict_arbiter_agent()` | **NEVER CALLED** |
| Ensemble | `src/agents/ensemble.py` | `ensemble_agent()` | **NEVER CALLED** |

**Total Unregistered Agents**: 18

**Evidence**: These files exist but are NOT imported in `src/utils/analysts.py` and NOT added to workflow in `src/main.py`.

---

## Agents Claimed But Not Executed

### From README.md Claims:
- "Ben Graham Agent" - **EXISTS but NEVER CALLED**
- "Bill Ackman Agent" - **EXISTS but NEVER CALLED**
- "Cathie Wood Agent" - **EXISTS but NEVER CALLED**
- "Charlie Munger Agent" - **EXISTS but NEVER CALLED**
- "Michael Burry Agent" - **EXISTS but NEVER CALLED**
- "Mohnish Pabrai Agent" - **EXISTS but NEVER CALLED**
- "Phil Fisher Agent" - **EXISTS but NEVER CALLED**
- "Rakesh Jhunjhunwala Agent" - **EXISTS but NEVER CALLED**
- "Stanley Druckenmiller Agent" - **EXISTS but NEVER CALLED**
- "Valuation Agent" - **EXISTS but NEVER CALLED**
- "Sentiment Agent" - **EXISTS but NEVER CALLED**
- "Fundamentals Agent" - **EXISTS but NEVER CALLED**
- "Technicals Agent" - **EXISTS but NEVER CALLED**

**Note**: These are mentioned in documentation but not in the active workflow.

---

## Single Agent Dominating Decision-Making

### Portfolio Manager

**Evidence**:
- Line 25-114 in `portfolio_manager.py`: `portfolio_management_agent()` function
- Line 105: `state["data"]["portfolio_decisions"] = {...}` - Only agent that writes trading decisions
- Line 198-348: `generate_trading_decision_rule_based()` - Aggregates all analyst signals
- Line 297-346: Decision logic (buy/sell/hold) based on weighted signals

**Decision Authority**:
- **ONLY** agent that generates `portfolio_decisions` (buy/sell/hold actions)
- All other agents provide signals or advisory data
- Backtest executes trades from `portfolio_decisions` only

**Current Behavior**:
- Aggregates signals from 5 core analysts
- Most signals are neutral → Most decisions are "hold"
- Falls back to simple strategy if all "hold"

**Dominance**: **100%** of trading decisions flow through Portfolio Manager

---

## Summary

### Active Agents (Actually Executed)

**Total**: 10 agents
- **Signal Generators**: 5 (2 active, 2 neutral, 1 inactive)
- **Decision Maker**: 1 (Portfolio Manager)
- **Advisory**: 4 (Market Regime, Performance Auditor, Risk Budget, Portfolio Allocator)

### Inactive Agents (Never Called)

**Total**: 18 agents
- Exist in codebase but not registered in `ANALYST_CONFIG`
- Not added to workflow in `create_workflow()`
- Never executed in backtests

### Signal Quality in Deterministic Mode

- **Meaningful Signals**: 2/5 (Momentum, Mean Reversion)
- **Neutral Signals**: 2/5 (Warren Buffett, Aswath Damodaran)
- **Inactive**: 1/5 (Peter Lynch)

### Decision-Making Dominance

- **Portfolio Manager**: 100% of trading decisions
- All other agents provide inputs (signals, advisory data)
- Simple strategy override generates trades when Portfolio Manager produces all "hold"

### Key Finding

**Only 2 out of 5 signal-generating agents produce meaningful signals in deterministic mode** (Momentum, Mean Reversion). The other 3 return neutral, leading Portfolio Manager to generate mostly "hold" decisions, which triggers the simple strategy fallback.


