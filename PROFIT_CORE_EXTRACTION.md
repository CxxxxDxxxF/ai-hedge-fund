# PROFIT CORE EXTRACTION REPORT
**Date:** 2025-01-XX  
**Mode:** PROFIT CORE EXTRACTION  
**Role:** Quant Engineer (PnL First)

---

## PHASE 1: EXECUTION CORE IDENTIFICATION

### Minimal Execution Core (REQUIRED for Profit Testing)

**Entry Point:**
- `src/backtesting/deterministic_backtest.py::DeterministicBacktest`

**Core Modules (REQUIRED):**

| Module | File | Purpose | Execution Dependency |
|--------|------|---------|---------------------|
| **Price Data** | `src/data/price_cache.py` | CSV-based price data (deterministic) | ✅ REQUIRED |
| **Trade Execution** | `src/backtesting/deterministic_backtest.py::_execute_trade()` | Executes buy/sell/short/cover | ✅ REQUIRED |
| **Portfolio State** | `src/backtesting/deterministic_backtest.py::portfolio` | Tracks cash, positions, cost basis, realized gains | ✅ REQUIRED |
| **Capital Constraints** | `src/backtesting/deterministic_backtest.py::_check_capital_constraints()` | Enforces NAV>0, gross≤100%, position≤20% | ✅ REQUIRED |
| **NAV Calculation** | `src/backtesting/deterministic_backtest.py::_calculate_portfolio_value()` | Calculates total portfolio value | ✅ REQUIRED |
| **Exposure Calculation** | `src/backtesting/deterministic_backtest.py::_calculate_gross_exposure()` | Calculates gross/net exposure | ✅ REQUIRED |
| **Determinism Guard** | `src/utils/deterministic_guard.py` | Blocks external I/O, seeds RNGs | ✅ REQUIRED |
| **Contract Validation** | `src/communication/contracts.py::validate_portfolio_decision()` | Validates trade decisions | ✅ REQUIRED |

**Total Core Modules:** 8 files/functions

---

### Research-Only Modules (NOT REQUIRED for Execution)

| Module | File | Purpose | Execution Dependency |
|--------|------|---------|---------------------|
| **LLM Integration** | `src/utils/llm.py`, `src/llm/*` | LLM API calls | ❌ NOT REQUIRED (blocked in deterministic mode) |
| **Agent Workflow** | `src/main.py::run_hedge_fund()`, `src/graph/state.py` | LangGraph workflow, agent orchestration | ⚠️ PARTIALLY REQUIRED (used but returns empty in deterministic mode) |
| **Financial Data API** | `src/tools/api.py` | External financial data fetching | ❌ NOT REQUIRED (blocked in deterministic mode) |
| **Knowledge Base** | `src/knowledge/*` | Learned patterns, agent performance history | ❌ NOT REQUIRED (advisory only) |
| **Health Monitor** | `src/health/*` | Portfolio health tracking | ❌ NOT REQUIRED (advisory only) |
| **Edge Analysis** | `src/backtesting/edge_analysis.py` | Statistical edge detection | ❌ NOT REQUIRED (post-processing) |
| **Regime Analysis** | `src/backtesting/regime_analysis.py` | Market regime classification | ❌ NOT REQUIRED (post-processing) |
| **Learning Engine** | `src/knowledge/learning_engine.py` | Extracts insights from backtests | ❌ NOT REQUIRED (post-processing) |
| **Web Application** | `app/*` | Web UI, API endpoints | ❌ NOT REQUIRED (UI only) |
| **Individual Agents** | `src/agents/*.py` (except topstep_strategy.py) | Individual agent implementations | ⚠️ PARTIALLY REQUIRED (used but return neutral in deterministic mode) |
| **Performance Auditor** | `src/agents/performance_auditor.py` | Tracks agent credibility | ❌ NOT REQUIRED (advisory only) |
| **Market Regime Agent** | `src/agents/market_regime.py` | Market condition classifier | ❌ NOT REQUIRED (advisory only) |
| **Intelligence Agent** | `src/agents/intelligence_agent.py` | Pattern detection | ❌ NOT REQUIRED (advisory only) |

**Note:** The deterministic backtest calls `run_hedge_fund()` which triggers the agent workflow, but in deterministic mode (`HEDGEFUND_NO_LLM=1`):
- All LLM calls are blocked
- All external API calls are blocked
- Agents return neutral signals or use rule-based fallbacks
- The workflow is effectively bypassed for actual decision-making

**Actual Strategy Execution:** Happens in `_generate_topstep_strategy_decisions()` or `_generate_simple_strategy_decisions()` - these are rule-based, no LLMs.

---

## PHASE 2: STRATEGY ISOLATION

### Existing Deterministic Strategies

**Strategy 1: Topstep Strategy** (Primary Profit Candidate)
- **File:** `src/agents/topstep_strategy.py::TopstepStrategy`
- **Tickers:** ES, NQ, MES, MNQ only
- **Status:** ✅ Implemented, rule-based, no LLMs

**Strategy 2: Simple Strategy** (Fallback)
- **File:** `src/backtesting/deterministic_backtest.py::_generate_simple_strategy_decisions()`
- **Tickers:** All tickers (except ES/NQ when Topstep active)
- **Status:** ✅ Implemented, rule-based, no LLMs

**Strategy 3: Portfolio Manager Rule-Based** (Aggregation)
- **File:** `src/agents/portfolio_manager.py::generate_trading_decision_rule_based()`
- **Tickers:** All tickers
- **Status:** ✅ Implemented, rule-based, aggregates 5 core agent signals

---

### PRIMARY STRATEGY SPEC: Topstep Strategy

**File:** `src/agents/topstep_strategy.py::TopstepStrategy`

**Entry Rules:**
1. **Market Regime Filter:**
   - ATR(14) on 5-min must be above 20-day median
   - If filter fails → HOLD

2. **Opening Range Identification:**
   - OR = first 15 minutes (9:30-9:45)
   - OR High = open + (high - open) * 0.25
   - OR Low = open - (open - low) * 0.25

3. **Breakout Confirmation:**
   - **Long:** Price breaks OR High AND closes above OR High
   - **Short:** Price breaks OR Low AND closes below OR Low
   - If no breakout → HOLD

4. **Pullback Entry:**
   - **Long:** Price retraces 50-70% of breakout candle, bullish engulfing OR strong close
   - **Short:** Price retraces 50-70% of breakout candle, bearish engulfing OR strong close
   - Entry price = close of pullback candle
   - Stop loss = 10% below/above pullback candle low/high

**Exit Rules:**
1. **Profit Target:** 1.5R max (risk * 1.5)
2. **Partial Profit:** Take partial at 1R (if implemented)
3. **Stop Loss:** Entry stop loss (10% below/above pullback candle)

**Sizing Rules:**
1. **Risk Per Trade:** 0.25% of account value
2. **Position Size:** `max_risk_dollars / risk_per_contract`
3. **Minimum:** 1 contract (micros: MES/MNQ)
4. **Maximum:** 1 contract (until funded)

**Risk Limits:**
1. **Max Trades Per Day:** 1
2. **Max Loss Per Day:** 0.5R
3. **Stop After Win:** Yes (if won today, no more trades)
4. **Daily Limits Check:** Before every trade attempt

**Code Location:**
- Entry: `TopstepStrategy.generate_signal()` (line 322)
- Regime Filter: `_check_market_regime()` (line 86)
- Opening Range: `_identify_opening_range()` (line 126)
- Breakout: `_check_break_and_acceptance()` (line 163)
- Pullback: `_check_pullback_entry()` (line 205)
- Sizing: `_calculate_position_size()` (line 272)
- Daily Limits: `_check_daily_limits()` (line 298)

---

### FALLBACK STRATEGY SPEC: Simple Strategy

**File:** `src/backtesting/deterministic_backtest.py::_generate_simple_strategy_decisions()`

**Entry Rules:**
1. **First Day Buy:** Buy 10 shares (or 5% of cash, whichever smaller) on first trading day
2. **Last Day Sell:** Sell all positions on last trading day
3. **Momentum Entry:** Buy if price increase > 1% (if price history available)
4. **Momentum Exit:** Sell if price decrease > 1% (if position exists)

**Exit Rules:**
1. **Last Day:** Always exit on last day
2. **Momentum:** Exit on >1% price decrease

**Sizing Rules:**
1. **Fixed Size:** 10 shares OR 5% of cash (whichever smaller)
2. **No Risk Management:** No stop loss, no position sizing based on risk

**Risk Limits:**
1. **None:** No explicit risk limits (relies on capital constraints)

**Code Location:**
- `_generate_simple_strategy_decisions()` (line 222)

**Status:** ⚠️ **TEST STRATEGY ONLY** - Not suitable for profit testing (no risk management)

---

## PHASE 3: FRICTION ANALYSIS

### Current State: Transaction Costs & Slippage

**Deterministic Backtest (`deterministic_backtest.py`):**
- ❌ **NOT IMPLEMENTED** - No transaction costs applied
- ❌ **NOT IMPLEMENTED** - No slippage applied
- ⚠️ **ESTIMATED ONLY** - 0.1% cost estimate used in constraint checking (line 470) but NOT deducted from cash

**Isolated Agent Backtest (`isolated_agent_backtest.py`):**
- ✅ **IMPLEMENTED** - Transaction costs applied:
  - `COMMISSION_PER_SHARE = 0.01` (line 99)
  - `SLIPPAGE_BPS = 5` (0.05%) (line 100)
  - `SPREAD_BPS = 3` (0.03%) (line 101)
- ✅ **APPLIED** - Costs deducted from cash in `_execute_trade_with_costs()` (line 330)

**Edge Analysis (`edge_analysis.py`):**
- ✅ **CALCULATED** - Transaction costs calculated for analysis:
  - `COMMISSION_PER_TRADE = 0.01` (line 39)
  - `SLIPPAGE_BPS = 5` (line 40)
- ⚠️ **POST-PROCESSING ONLY** - Not applied during execution, only for analysis

---

### Friction Implementation Status

| Component | Commission | Slippage | Applied to Execution | Deterministic |
|-----------|------------|----------|---------------------|---------------|
| `deterministic_backtest.py` | ❌ None | ❌ None | ❌ No | ✅ Yes |
| `isolated_agent_backtest.py` | ✅ $0.01/share | ✅ 0.05% | ✅ Yes | ✅ Yes |
| `edge_analysis.py` | ✅ $0.01/share | ✅ 0.05% | ❌ Post-processing | ✅ Yes |

**Gap:** Deterministic backtest does NOT apply transaction costs or slippage to actual trade execution.

**Required Fix:** Add configurable friction to `_execute_trade()` in `deterministic_backtest.py`.

---

## PHASE 4: PROFIT METRICS

### Existing Metrics

**Location:** `src/backtesting/deterministic_backtest.py::_calculate_metrics()` (line 1090)

**Metrics Calculated:**

| Metric | Calculation | Funded-Account Relevance |
|--------|-------------|-------------------------|
| **Cumulative PnL** | `final_value - initial_value` | ✅ Critical |
| **Total Return %** | `(final_value / initial_value - 1) * 100` | ✅ Critical |
| **Max Drawdown %** | `min((value - running_max) / running_max) * 100` | ✅ Critical (funded accounts have drawdown limits) |
| **Max Drawdown Date** | Date of max drawdown | ✅ Useful |
| **Win Rate %** | `profitable_trades / total_closing_trades * 100` | ✅ Useful |
| **Sharpe Ratio** | `(mean_return / std_return) * sqrt(252)` | ✅ Useful |
| **Total Trades** | Count of executed trades | ✅ Useful |

**Missing Metrics (Funded-Account Critical):**

| Metric | Status | Why Needed |
|--------|--------|------------|
| **Time to Recovery** | ❌ Missing | Funded accounts require recovery within X days |
| **Losing Streaks** | ❌ Missing | Consecutive losing days/trades (funded account limits) |
| **% Profitable Days** | ❌ Missing | Daily win rate (funded accounts track this) |
| **Daily PnL Distribution** | ❌ Missing | Understanding daily profit/loss patterns |
| **Largest Winning Day** | ❌ Missing | Understanding best-case scenarios |
| **Largest Losing Day** | ❌ Missing | Understanding worst-case scenarios (risk) |
| **Average Win** | ❌ Missing | R-multiple analysis |
| **Average Loss** | ❌ Missing | R-multiple analysis |
| **Profit Factor** | ❌ Missing | Gross profit / gross loss |
| **Expectancy** | ❌ Missing | (Win% * AvgWin) - (Loss% * AvgLoss) |

**Metrics Location:** `src/backtesting/metrics.py::PerformanceMetricsCalculator`
- Calculates: Sharpe, Sortino, max drawdown
- Missing: All funded-account specific metrics above

---

## PHASE 5: EXECUTION CORE SUMMARY

### What Runs Trades (Execution Core)

**Minimal Execution Path:**
```
1. DeterministicBacktest.__init__()
   - Load price cache (CSV files)
   - Initialize portfolio state
   - Initialize strategy (TopstepStrategy or Simple Strategy)

2. DeterministicBacktest.run()
   - For each business day:
     a. Get current prices (from price cache)
     b. Generate strategy decisions (TopstepStrategy or Simple Strategy)
     c. Validate decisions (contract validation)
     d. Execute trades (_execute_trade)
     e. Enforce capital constraints (_check_capital_constraints)
     f. Calculate NAV (_calculate_portfolio_value)
     g. Record daily value
     h. Log invariants

3. DeterministicBacktest._calculate_metrics()
   - Calculate performance metrics
   - Return metrics dict
```

**Dependencies:**
- ✅ `src/data/price_cache.py` - Price data (CSV files)
- ✅ `src/agents/topstep_strategy.py` - Topstep strategy (if ES/NQ)
- ✅ `src/backtesting/deterministic_backtest.py` - Execution engine
- ✅ `src/utils/deterministic_guard.py` - Determinism enforcement
- ✅ `src/communication/contracts.py` - Decision validation

**Total Core Files:** 5

---

### What Is Excluded (Research-Only)

**Excluded from Execution Core:**
- ❌ All LLM modules (`src/llm/*`, `src/utils/llm.py`)
- ❌ All external API calls (`src/tools/api.py` - blocked in deterministic mode)
- ❌ Knowledge base (`src/knowledge/*`)
- ❌ Health monitor (`src/health/*`)
- ❌ Edge analysis (`src/backtesting/edge_analysis.py`)
- ❌ Regime analysis (`src/backtesting/regime_analysis.py`)
- ❌ Learning engine (`src/knowledge/learning_engine.py`)
- ❌ Web application (`app/*`)
- ❌ Individual agent implementations (return neutral in deterministic mode)
- ❌ Performance auditor (advisory only)
- ❌ Market regime agent (advisory only)
- ❌ Intelligence agent (advisory only)

**Note:** The agent workflow (`src/main.py::run_hedge_fund()`) is called but:
- Returns empty/neutral signals in deterministic mode
- Actual decisions come from TopstepStrategy or Simple Strategy
- Workflow is effectively bypassed

---

## STRATEGY SPECIFICATION

### PRIMARY STRATEGY: Topstep Opening Range Break + Pullback

**Instrument:** ES (E-mini S&P 500) or NQ (E-mini NASDAQ-100)

**Entry Rules:**
1. Market Regime: ATR(14) > 20-day median ATR
2. Opening Range: First 15 minutes (9:30-9:45)
3. Breakout: Price breaks OR High (long) or OR Low (short) AND closes outside range
4. Pullback: Price retraces 50-70% of breakout candle
5. Entry Signal: Bullish/bearish engulfing OR strong close in trend direction

**Exit Rules:**
1. Profit Target: 1.5R (risk * 1.5)
2. Stop Loss: 10% below/above pullback candle low/high
3. Partial Profit: 1R (if implemented)

**Sizing Rules:**
1. Risk: 0.25% of account value per trade
2. Position: `max_risk_dollars / risk_per_contract`
3. Minimum: 1 contract (micros: MES/MNQ)
4. Maximum: 1 contract (until funded)

**Risk Limits:**
1. Max Trades/Day: 1
2. Max Loss/Day: 0.5R
3. Stop After Win: Yes

**Code:** `src/agents/topstep_strategy.py::TopstepStrategy.generate_signal()`

---

## METRICS CHECKLIST (Funded-Account Survival)

### Existing Metrics (✅ Implemented)

- [x] Max Drawdown %
- [x] Max Drawdown Date
- [x] Total Return %
- [x] Cumulative PnL
- [x] Sharpe Ratio
- [x] Win Rate %
- [x] Total Trades

### Missing Metrics (❌ Not Implemented)

- [ ] Time to Recovery (days from drawdown to new high)
- [ ] Losing Streaks (consecutive losing days/trades)
- [ ] % Profitable Days (daily win rate)
- [ ] Largest Winning Day ($)
- [ ] Largest Losing Day ($)
- [ ] Average Win ($)
- [ ] Average Loss ($)
- [ ] Profit Factor (gross profit / gross loss)
- [ ] Expectancy ($) = (Win% * AvgWin) - (Loss% * AvgLoss)
- [ ] R-Multiple Distribution (if R-based sizing)
- [ ] Daily PnL Distribution (histogram)

**Priority for Funded Accounts:**
1. **Max Drawdown** ✅ (exists)
2. **Time to Recovery** ❌ (critical - funded accounts have recovery deadlines)
3. **Losing Streaks** ❌ (critical - funded accounts limit consecutive losses)
4. **% Profitable Days** ❌ (important - funded accounts track daily consistency)
5. **Largest Losing Day** ❌ (important - risk management)

---

## EXECUTION CORE DEPENDENCY GRAPH

```
DeterministicBacktest
    ├── PriceCache (CSV files)
    ├── TopstepStrategy (if ES/NQ) OR Simple Strategy (fallback)
    ├── _execute_trade()
    │   ├── _check_capital_constraints()
    │   ├── Portfolio state mutation
    │   └── Post-trade validation
    ├── _calculate_portfolio_value()
    ├── _calculate_gross_exposure()
    └── _calculate_metrics()
        └── PerformanceMetricsCalculator (Sharpe, Sortino, drawdown)
```

**External Dependencies:**
- `pandas` - Data manipulation
- `numpy` - Numerical calculations
- `hashlib` - Determinism hashing
- `datetime` - Date handling

**No External Dependencies:**
- ❌ No LLM APIs
- ❌ No financial data APIs
- ❌ No network calls
- ❌ No file I/O (except price CSV reads)

---

## FRICTION REQUIREMENTS

### Current State
- **Transaction Costs:** ❌ NOT APPLIED in deterministic_backtest.py
- **Slippage:** ❌ NOT APPLIED in deterministic_backtest.py
- **Spread:** ❌ NOT APPLIED in deterministic_backtest.py

### Required Implementation

**Location:** `src/backtesting/deterministic_backtest.py::_execute_trade()`

**Add:**
1. Configurable commission (default: $0.01 per share)
2. Configurable slippage (default: 0.05% = 5 bps)
3. Configurable spread (default: 0.03% = 3 bps)
4. Apply costs deterministically (no randomness)
5. Deduct from cash on trade execution

**Reference Implementation:** `src/backtesting/isolated_agent_backtest.py::_execute_trade_with_costs()` (line 330)

---

## PROFIT CORE SUMMARY

### Execution Core (5 Files)

1. `src/backtesting/deterministic_backtest.py` - Main execution engine
2. `src/data/price_cache.py` - Price data (CSV)
3. `src/agents/topstep_strategy.py` - Primary strategy (ES/NQ)
4. `src/utils/deterministic_guard.py` - Determinism enforcement
5. `src/communication/contracts.py` - Decision validation

### Strategy (1 Primary)

- **Topstep Strategy** - Opening Range Break + Pullback (ES/NQ only)
- **Simple Strategy** - Fallback (all tickers, test-only)

### Friction (0 Implemented)

- ❌ Transaction costs: NOT APPLIED
- ❌ Slippage: NOT APPLIED
- ⚠️ Estimated 0.1% used in constraints only (not deducted)

### Metrics (7 Implemented, 10 Missing)

**Implemented:** Max drawdown, total return, Sharpe, win rate, cumulative PnL, total trades, drawdown date

**Missing:** Time to recovery, losing streaks, % profitable days, largest win/loss days, average win/loss, profit factor, expectancy, R-multiple distribution, daily PnL distribution

---

## CAPABILITY STATEMENT

**What the Execution Core Can Do Today:**

1. ✅ Execute deterministic backtests with rule-based strategies
2. ✅ Track portfolio state (cash, positions, cost basis, realized gains)
3. ✅ Enforce capital constraints (NAV>0, gross≤100%, position≤20%)
4. ✅ Calculate basic performance metrics (Sharpe, drawdown, win rate)
5. ✅ Run Topstep strategy for ES/NQ futures
6. ✅ Run simple fallback strategy for other tickers

**What the Execution Core Cannot Do Today:**

1. ❌ Apply transaction costs to trades (costs not deducted)
2. ❌ Apply slippage to trades (execution at exact price)
3. ❌ Calculate funded-account critical metrics (time to recovery, losing streaks)
4. ❌ Track R-multiples (if using R-based sizing)
5. ❌ Calculate profit factor or expectancy

**What Is Excluded from Execution:**

1. ❌ LLM calls (blocked in deterministic mode)
2. ❌ External API calls (blocked in deterministic mode)
3. ❌ Knowledge base reads (advisory only)
4. ❌ Health monitoring (advisory only)
5. ❌ Edge/regime analysis (post-processing only)
6. ❌ Learning engine (post-processing only)
7. ❌ Web application (UI only)

---

**END OF REPORT**
