# Capability Audit: Evidence-Based System Analysis

**Date**: 2024-12-19  
**Method**: Codebase scan, no speculation  
**Baseline**: Current implementation only

---

## Capability Map

### ✅ Production-Ready

1. **Deterministic Backtest Loop**
   - **Evidence**: `src/backtesting/deterministic_backtest.py` (843 lines)
   - **Status**: Fully functional, hardened with contracts
   - **Capabilities**:
     - Processes trading days sequentially
     - Tracks portfolio state (cash, positions, PnL)
     - Records daily values, trades, agent contributions
     - Enforces determinism (seeding, hashing)
     - Handles errors (engine vs strategy separation)
     - Generates summary metrics

2. **Portfolio State Management**
   - **Evidence**: `_execute_trade()`, `_calculate_portfolio_value()` in `deterministic_backtest.py`
   - **Status**: Functional
   - **Capabilities**:
     - Executes buy/sell/short/cover trades
     - Tracks long/short positions with cost basis
     - Calculates realized gains
     - Manages margin (if enabled)
     - Updates cash balances

3. **Simple Deterministic Strategy**
   - **Evidence**: `_generate_simple_strategy_decisions()` in `deterministic_backtest.py` (lines 145-227)
   - **Status**: Functional, tested
   - **Capabilities**:
     - Buys on first day, sells on last day
     - Uses fixed position sizing (10 shares or 5% cash)
     - Generates measurable PnL
     - Fully deterministic

4. **Invariant Logging & Observability**
   - **Evidence**: `_log_invariant()`, `_save_snapshot()` in `deterministic_backtest.py`
   - **Status**: Functional
   - **Capabilities**:
     - One log line per iteration (date, PV, agents, time)
     - State snapshots for crash recovery
     - Full tracebacks on errors
     - Guaranteed summary printing

5. **Performance Metrics Calculation**
   - **Evidence**: `_calculate_metrics()` in `deterministic_backtest.py` (lines ~550-650)
   - **Status**: Functional
   - **Capabilities**:
     - Cumulative PnL
     - Max drawdown
     - Win rate
     - Sharpe ratio
     - Agent contribution attribution

### ⚠️ Technically Works But Not Meaningful

1. **Analyst Signal Generation (Deterministic Mode)**
   - **Evidence**: All 5 core agents have `create_rule_based_*_signal()` functions
   - **Status**: Returns signals, but quality is questionable
   - **Issues**:
     - **Warren Buffett (Value Composite)**: Uses price data only (no financials in deterministic mode)
     - **Peter Lynch (Growth Composite)**: Returns neutral immediately in deterministic mode (`is_deterministic_mode()` check)
     - **Aswath Damodaran (Valuation)**: Uses price data only, has None guards but no real valuation
     - **Momentum**: Uses price data (functional)
     - **Mean Reversion**: Uses price data (functional)
   - **Reality**: Only 2/5 agents (Momentum, Mean Reversion) generate meaningful signals in deterministic mode

2. **Portfolio Manager Decision Making**
   - **Evidence**: `generate_trading_decision_rule_based()` in `portfolio_manager.py` (lines 198-348)
   - **Status**: Functional but limited
   - **Capabilities**:
     - Aggregates signals with weights
     - Generates buy/sell/hold decisions
     - Respects position limits
   - **Reality**: 
     - Most signals are neutral (due to agent limitations)
     - Falls back to "hold" in most cases
     - Simple strategy override generates actual trades

3. **Price Data Retrieval**
   - **Evidence**: `_get_current_prices()` in `deterministic_backtest.py` (lines 229-249)
   - **Status**: Attempts to fetch, but often fails
   - **Reality**: 
     - Calls `get_price_data()` which may return empty DataFrame
     - Falls back to `0.0` on failure
     - Simple strategy uses mock price ($100) when unavailable
   - **Impact**: Backtest runs but with unrealistic prices

4. **Edge Detection Analysis**
   - **Evidence**: `src/backtesting/edge_analysis.py` (comprehensive implementation)
   - **Status**: Code exists, but depends on data quality
   - **Capabilities**:
     - Sharpe ratio calculation
     - Information ratio
     - Statistical significance (t-test, p-value)
     - Bootstrap analysis
     - Transaction costs impact
   - **Reality**: 
     - Requires `scipy` (has fallback if missing)
     - Only meaningful if backtest has real trades and price data
     - Currently runs on mock/simple strategy data

5. **Regime Analysis**
   - **Evidence**: `src/backtesting/regime_analysis.py`
   - **Status**: Code exists
   - **Capabilities**:
     - Analyzes performance by market regime
     - Agent combination analysis
     - Signal pattern analysis
   - **Reality**: Depends on meaningful regime data and agent signals (limited in deterministic mode)

### 🔶 Partially Implemented

1. **Financial Data Fetching**
   - **Evidence**: `get_financial_metrics()`, `get_insider_trades()`, `get_company_news()` in `api.py`
   - **Status**: API functions exist but blocked in deterministic mode
   - **Reality**: 
     - `_make_api_request()` returns `MockResponse` when `HEDGEFUND_NO_LLM=1`
     - All external data calls return empty results
     - Agents that need financials return neutral signals

2. **Market Regime Classification**
   - **Evidence**: `src/agents/market_regime.py` (278 lines)
   - **Status**: Has rule-based logic
   - **Reality**: 
     - Uses price data only (ATR, volatility)
     - Classifies regimes (trending, mean-reverting, volatile, calm)
     - Provides weight adjustments for momentum/mean-reversion
     - But regime data may not be meaningful without real price data

3. **Risk Budget & Portfolio Allocator**
   - **Evidence**: `risk_budget.py`, `portfolio_allocator.py`
   - **Status**: Code exists, integrated into workflow
   - **Reality**: 
     - Risk budget calculates position sizes based on confidence/regime/volatility
     - Portfolio allocator enforces constraints (exposure, sector, correlation)
     - But both depend on portfolio manager decisions (which are mostly "hold")
     - Not actively constraining trades in current simple strategy

4. **Agent Contribution Attribution**
   - **Evidence**: `agent_contributions` tracking in `deterministic_backtest.py`
   - **Status**: Tracks PnL per agent
   - **Reality**: 
     - Only tracks when agents contribute to decisions
     - Simple strategy bypasses agents, so attribution is empty
     - Would work if portfolio manager generated real trades

### ❌ Not Implemented But Implied

1. **Real Financial Data Integration**
   - **Evidence**: API functions exist but return empty in deterministic mode
   - **Reality**: No actual financial data (balance sheets, income statements, insider trades) is used

2. **LLM-Based Decision Making**
   - **Evidence**: `call_llm()` in `utils/llm.py`, LLM factories in agents
   - **Reality**: 
     - Completely disabled when `HEDGEFUND_NO_LLM=1`
     - Agents use `rule_based_factory` instead
     - No LLM calls in deterministic mode

3. **Multi-Ticker Portfolio Optimization**
   - **Evidence**: Code supports multiple tickers
   - **Reality**: 
     - Simple strategy works per-ticker independently
     - No cross-ticker correlation analysis in practice
     - Portfolio allocator exists but not actively used

4. **Transaction Cost Modeling**
   - **Evidence**: Edge analysis mentions transaction costs
   - **Reality**: No actual cost deduction in trade execution
     - `_execute_trade()` doesn't subtract commissions/fees
     - Edge analysis calculates "after-cost returns" but costs aren't applied to portfolio

---

## Hard Limitations

### 1. **No Real Price Data in Deterministic Mode**
- **Evidence**: `_get_current_prices()` returns `0.0` on failure, simple strategy uses mock $100
- **Impact**: Backtests run but with unrealistic prices
- **Location**: `deterministic_backtest.py:229-249`, `deterministic_backtest.py:156-158`

### 2. **No Financial Data in Deterministic Mode**
- **Evidence**: `_make_api_request()` returns `MockResponse` when `HEDGEFUND_NO_LLM=1`
- **Impact**: Value/Growth agents return neutral signals
- **Location**: `tools/api.py:373-385`, `agents/peter_lynch.py:early_return_check`

### 3. **Most Agents Generate Neutral Signals**
- **Evidence**: 
  - Peter Lynch: Returns neutral immediately in deterministic mode
  - Warren Buffett: Uses price-only data (no financials)
  - Aswath Damodaran: Uses price-only data (no financials)
- **Impact**: Portfolio manager generates "hold" decisions, falls back to simple strategy
- **Location**: `agents/peter_lynch.py`, `agents/warren_buffett.py`, `agents/aswath_damodaran.py`

### 4. **Simple Strategy Uses Mock Prices**
- **Evidence**: `if current_price <= 0: current_price = 100.0`
- **Impact**: Trades execute but at unrealistic prices
- **Location**: `deterministic_backtest.py:156-158`

### 5. **No Transaction Costs**
- **Evidence**: `_execute_trade()` doesn't subtract fees
- **Impact**: Returns are overstated
- **Location**: `deterministic_backtest.py:271-279`

### 6. **Limited Time Horizon Validation**
- **Evidence**: Tested on 7-day windows
- **Impact**: Unknown behavior on 500+ day runs
- **Status**: Code supports it, but not validated

---

## Misleading Signals

### 1. **"5 Core Agents"**
- **Reality**: Only 2 (Momentum, Mean Reversion) generate meaningful signals in deterministic mode
- **Others**: Return neutral or use price-only data

### 2. **"Edge Detection Analysis"**
- **Reality**: Code exists and works, but analyzes mock strategy data
- **Value**: Only meaningful with real trades and real prices

### 3. **"Regime Analysis"**
- **Reality**: Code exists but regime classifications may not be meaningful without real price data

### 4. **"Risk Budget & Portfolio Allocator"**
- **Reality**: Code exists and is integrated, but not actively constraining trades (simple strategy bypasses)

### 5. **"Deterministic Strategy"**
- **Reality**: Works but uses mock prices, so PnL is not realistic

---

## Direct Answers to Questions

### Can this system generate trades deterministically?
**YES** - But with caveats:
- ✅ Simple strategy generates trades (buy first day, sell last day)
- ✅ Fully deterministic (same inputs → same outputs)
- ⚠️ Uses mock prices when real data unavailable
- ⚠️ Portfolio manager generates mostly "hold" (agents return neutral)

**Evidence**: `deterministic_backtest.py:145-227`, test results show 2 trades executed

### Can it measure profitability correctly?
**PARTIALLY**:
- ✅ Calculates portfolio value correctly
- ✅ Tracks realized gains
- ✅ Computes metrics (PnL, return %, Sharpe)
- ❌ No transaction costs applied
- ❌ Uses mock prices (unrealistic)

**Evidence**: `_calculate_portfolio_value()`, `_calculate_metrics()`, `_execute_trade()`

### Can it detect statistical edge vs randomness?
**CODE EXISTS, BUT LIMITED BY DATA**:
- ✅ Edge analysis code is comprehensive (`edge_analysis.py`)
- ✅ Calculates Sharpe, Information Ratio, p-values, bootstrap
- ⚠️ Only meaningful with real trades and real prices
- ⚠️ Currently analyzes mock strategy data

**Evidence**: `src/backtesting/edge_analysis.py` (full implementation with scipy fallback)

### Can it scale to long time horizons?
**UNKNOWN - NOT VALIDATED**:
- ✅ Code supports arbitrary date ranges
- ✅ Loop structure is sound (explicit index, no duplication)
- ❓ Not tested on 500+ day runs
- ❓ Performance/memory not validated

**Evidence**: `deterministic_backtest.py:482-513` (loop structure), tested on 7-day windows

### Does it currently rely on LLMs for decision-making?
**NO - COMPLETELY DISABLED**:
- ✅ `HEDGEFUND_NO_LLM=1` blocks all LLM calls
- ✅ `_make_api_request()` returns mock responses
- ✅ Agents use `rule_based_factory` instead
- ✅ Fully deterministic

**Evidence**: `tools/api.py:373-385`, `utils/deterministic_guard.py`, all agents have rule-based fallbacks

---

## Single Biggest Bottleneck

**NO REAL PRICE DATA IN DETERMINISTIC MODE**

**Evidence**:
- `_get_current_prices()` returns `0.0` on failure
- Simple strategy uses mock $100 price
- All profitability calculations use unrealistic prices

**Impact**:
- Backtests run but results are meaningless
- Cannot validate strategy effectiveness
- Cannot measure real profitability

**Root Cause**:
- `get_price_data()` API call may fail (network, data availability)
- No fallback to historical data file
- No cached price data

**Location**: `deterministic_backtest.py:229-249`, `deterministic_backtest.py:156-158`

---

## Recommended Next Step

**Add Historical Price Data Caching/File-Based Lookup**

**Why**:
- Enables realistic backtests without external API calls
- Removes dependency on network/data availability
- Makes deterministic mode truly deterministic
- Allows validation of strategy effectiveness
- **Current blocker**: System uses mock prices ($100) when real data unavailable

**Minimal Implementation**:
1. Download/cache historical price data (CSV files or local DB)
2. Modify `_get_current_prices()` to read from cache first
3. Fall back to API only if cache miss (or skip in deterministic mode)

**Files to Modify**:
- `src/backtesting/deterministic_backtest.py:229-249` (`_get_current_prices()`)
- Add `src/data/prices/` directory with CSV files
- Or use `yfinance` library to fetch and cache locally

**Expected Impact**:
- Realistic price data → Realistic PnL calculations
- Enables meaningful edge detection analysis
- Makes backtest results interpretable
- No architecture changes required
- **Immediate value**: Simple strategy would produce realistic results instead of mock $100 trades

---

## Summary

**What Works**: Backtest loop, portfolio management, simple strategy, metrics calculation, observability

**What's Limited**: Agent signals (most return neutral), price data (mock), financial data (blocked)

**What's Missing**: Real price data, transaction costs, meaningful agent signals in deterministic mode

**Biggest Gap**: No real price data → unrealistic backtest results

**Next Step**: Add historical price data caching for deterministic mode
