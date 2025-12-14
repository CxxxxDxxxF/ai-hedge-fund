# AI Hedge Fund - Employee Roster Audit

**Date:** 2025-01-XX  
**Purpose:** Factual capability audit of all agents in the ai-hedge-fund codebase  
**Scope:** All registered agents, their roles, capabilities, and limitations

---

## Executive Summary

**Total Employees:** 30 agents

**Breakdown by Function:**
- **Signal Generators (Analysts):** 22 agents
- **Signal Managers (Meta-Analysts):** 3 agents
- **Capital Allocators:** 2 agents
- **Risk Controllers:** 2 agents
- **Portfolio Decision Makers:** 1 agent

**Deterministic vs LLM-Dependent:**
- **Fully Deterministic:** 8 agents
- **LLM-Dependent (with fallbacks):** 14 agents
- **Hybrid (LLM with deterministic fallback):** 8 agents

---

## Detailed Employee Roster

### SIGNAL GENERATORS (Analyst Agents)

#### 1. Aswath Damodaran Agent
- **File:** `src/agents/aswath_damodaran.py`
- **Registered Key:** `aswath_damodaran`
- **Role:** Valuation Specialist / The Dean of Valuation
- **Decision Authority:** Signal only
- **Data Inputs:**
  - Financial metrics (PE, PB, EV/EBITDA, ROE, ROIC)
  - Line items (revenue, earnings, cash flow, debt)
  - Market cap
  - Historical valuation multiples
- **Outputs:** `signal` (bullish/bearish/neutral), `confidence` (0-100), `reasoning`
- **Deterministic:** No (LLM-dependent, has `rule_based_factory` fallback)
- **Capabilities:**
  - ✅ Generate trade direction
  - ❌ Size positions
  - ❌ Veto trades
  - ❌ Modify other agents' influence
- **Limitations:** Requires financial data; fallback may be less sophisticated

#### 2. Ben Graham Agent
- **File:** `src/agents/ben_graham.py`
- **Registered Key:** `ben_graham`
- **Role:** Value Investor / The Father of Value Investing
- **Decision Authority:** Signal only
- **Data Inputs:**
  - Financial metrics (PE, PB, debt-to-equity, current ratio)
  - Line items (book value, earnings, dividends)
  - Market cap
- **Outputs:** `signal`, `confidence`, `reasoning`
- **Deterministic:** No (LLM-dependent, has `rule_based_factory` fallback)
- **Capabilities:**
  - ✅ Generate trade direction
  - ❌ Size positions
  - ❌ Veto trades
  - ❌ Modify other agents' influence
- **Limitations:** Focuses on deep value; may miss growth opportunities

#### 3. Bill Ackman Agent
- **File:** `src/agents/bill_ackman.py`
- **Registered Key:** `bill_ackman`
- **Role:** Activist Investor
- **Decision Authority:** Signal only
- **Data Inputs:**
  - Financial metrics
  - Line items
  - Insider trades
  - Company news
- **Outputs:** `signal`, `confidence`, `reasoning`
- **Deterministic:** No (LLM-dependent, has `rule_based_factory` fallback)
- **Capabilities:**
  - ✅ Generate trade direction
  - ❌ Size positions
  - ❌ Veto trades
  - ❌ Modify other agents' influence
- **Limitations:** Activist strategy may not apply to all companies

#### 4. Cathie Wood Agent
- **File:** `src/agents/cathie_wood.py`
- **Registered Key:** `cathie_wood`
- **Role:** Growth Investor / The Queen of Growth Investing
- **Decision Authority:** Signal only
- **Data Inputs:**
  - Financial metrics (revenue growth, margins)
  - Line items (R&D, capex, revenue)
  - Market cap
  - Company news
- **Outputs:** `signal`, `confidence`, `reasoning`
- **Deterministic:** No (LLM-dependent, has `rule_based_factory` fallback)
- **Capabilities:**
  - ✅ Generate trade direction
  - ❌ Size positions
  - ❌ Veto trades
  - ❌ Modify other agents' influence
- **Limitations:** High-growth focus; may overvalue speculative companies

#### 5. Charlie Munger Agent
- **File:** `src/agents/charlie_munger.py`
- **Registered Key:** `charlie_munger`
- **Role:** Value Investor / The Rational Thinker
- **Decision Authority:** Signal only
- **Data Inputs:**
  - Financial metrics
  - Line items
  - Market cap
- **Outputs:** `signal`, `confidence`, `reasoning`
- **Deterministic:** No (LLM-dependent, has `rule_based_factory` fallback)
- **Capabilities:**
  - ✅ Generate trade direction
  - ❌ Size positions
  - ❌ Veto trades
  - ❌ Modify other agents' influence
- **Limitations:** Quality-focused; may miss value opportunities

#### 6. Michael Burry Agent
- **File:** `src/agents/michael_burry.py`
- **Registered Key:** `michael_burry`
- **Role:** Contrarian Value Investor / The Big Short Contrarian
- **Decision Authority:** Signal only
- **Data Inputs:**
  - Financial metrics
  - Line items (debt, cash, FCF)
  - Insider trades
  - Company news
- **Outputs:** `signal`, `confidence`, `reasoning`
- **Deterministic:** No (LLM-dependent, has `rule_based_factory` fallback)
- **Capabilities:**
  - ✅ Generate trade direction
  - ❌ Size positions
  - ❌ Veto trades
  - ❌ Modify other agents' influence
- **Limitations:** Contrarian approach; may be early/late to trends

#### 7. Mohnish Pabrai Agent
- **File:** `src/agents/mohnish_pabrai.py`
- **Registered Key:** `mohnish_pabrai`
- **Role:** Value Investor / The Dhandho Investor
- **Decision Authority:** Signal only
- **Data Inputs:**
  - Financial metrics
  - Line items
  - Market cap
- **Outputs:** `signal`, `confidence`, `reasoning`
- **Deterministic:** No (LLM-dependent, has `rule_based_factory` fallback)
- **Capabilities:**
  - ✅ Generate trade direction
  - ❌ Size positions
  - ❌ Veto trades
  - ❌ Modify other agents' influence
- **Limitations:** Value-focused; may miss growth trends

#### 8. Peter Lynch Agent
- **File:** `src/agents/peter_lynch.py`
- **Registered Key:** `peter_lynch`
- **Role:** Growth Investor / The 10-Bagger Investor
- **Decision Authority:** Signal only
- **Data Inputs:**
  - Financial metrics (PEG ratio, growth rates)
  - Line items (revenue, earnings, FCF)
  - Market cap
  - Insider trades
  - Company news
- **Outputs:** `signal`, `confidence`, `reasoning`
- **Deterministic:** No (LLM-dependent, has `rule_based_factory` fallback)
- **Capabilities:**
  - ✅ Generate trade direction
  - ❌ Size positions
  - ❌ Veto trades
  - ❌ Modify other agents' influence
- **Limitations:** Growth-focused; requires understandable business models

#### 9. Phil Fisher Agent
- **File:** `src/agents/phil_fisher.py`
- **Registered Key:** `phil_fisher`
- **Role:** Growth Investor / The Scuttlebutt Investor
- **Decision Authority:** Signal only
- **Data Inputs:**
  - Financial metrics
  - Line items
  - Company news
  - Market cap
- **Outputs:** `signal`, `confidence`, `reasoning`
- **Deterministic:** No (LLM-dependent, has `rule_based_factory` fallback)
- **Capabilities:**
  - ✅ Generate trade direction
  - ❌ Size positions
  - ❌ Veto trades
  - ❌ Modify other agents' influence
- **Limitations:** Management quality focus; hard to quantify

#### 10. Rakesh Jhunjhunwala Agent
- **File:** `src/agents/rakesh_jhunjhunwala.py`
- **Registered Key:** `rakesh_jhunjhunwala`
- **Role:** Macro Investor / The Big Bull Of India
- **Decision Authority:** Signal only
- **Data Inputs:**
  - Financial metrics
  - Line items
  - Market cap
- **Outputs:** `signal`, `confidence`, `reasoning`
- **Deterministic:** No (LLM-dependent, has `rule_based_factory` fallback)
- **Capabilities:**
  - ✅ Generate trade direction
  - ❌ Size positions
  - ❌ Veto trades
  - ❌ Modify other agents' influence
- **Limitations:** Emerging markets focus; may not apply to all markets

#### 11. Stanley Druckenmiller Agent
- **File:** `src/agents/stanley_druckenmiller.py`
- **Registered Key:** `stanley_druckenmiller`
- **Role:** Macro Investor
- **Decision Authority:** Signal only
- **Data Inputs:**
  - Financial metrics
  - Line items
  - Market cap
- **Outputs:** `signal`, `confidence`, `reasoning`
- **Deterministic:** No (LLM-dependent, has `rule_based_factory` fallback)
- **Capabilities:**
  - ✅ Generate trade direction
  - ❌ Size positions
  - ❌ Veto trades
  - ❌ Modify other agents' influence
- **Limitations:** Macro focus; may miss company-specific factors

#### 12. Warren Buffett Agent
- **File:** `src/agents/warren_buffett.py`
- **Registered Key:** `warren_buffett`
- **Role:** Value Investor / The Oracle of Omaha
- **Decision Authority:** Signal only
- **Data Inputs:**
  - Financial metrics (ROE, margins, debt ratios)
  - Line items (book value, earnings, FCF, dividends)
  - Market cap
- **Outputs:** `signal`, `confidence`, `reasoning`
- **Deterministic:** No (LLM-dependent, has `rule_based_factory` fallback)
- **Capabilities:**
  - ✅ Generate trade direction
  - ❌ Size positions
  - ❌ Veto trades
  - ❌ Modify other agents' influence
- **Limitations:** Long-term focus; may miss short-term opportunities

#### 13. Technical Analyst Agent
- **File:** `src/agents/technicals.py`
- **Registered Key:** `technical_analyst`
- **Role:** Chart Pattern Specialist
- **Decision Authority:** Signal only
- **Data Inputs:**
  - Price data (OHLCV)
  - Technical indicators (RSI, MACD, moving averages)
- **Outputs:** `signal`, `confidence`, `reasoning`
- **Deterministic:** No (LLM-dependent, has `rule_based_factory` fallback)
- **Capabilities:**
  - ✅ Generate trade direction
  - ❌ Size positions
  - ❌ Veto trades
  - ❌ Modify other agents' influence
- **Limitations:** Technical only; ignores fundamentals

#### 14. Fundamentals Analyst Agent
- **File:** `src/agents/fundamentals.py`
- **Registered Key:** `fundamentals_analyst`
- **Role:** Financial Statement Specialist
- **Decision Authority:** Signal only
- **Data Inputs:**
  - Financial metrics
  - Line items
  - Market cap
- **Outputs:** `signal`, `confidence`, `reasoning`
- **Deterministic:** No (LLM-dependent, has `rule_based_factory` fallback)
- **Capabilities:**
  - ✅ Generate trade direction
  - ❌ Size positions
  - ❌ Veto trades
  - ❌ Modify other agents' influence
- **Limitations:** Fundamental only; may miss market sentiment

#### 15. Growth Analyst Agent
- **File:** `src/agents/growth_agent.py`
- **Registered Key:** `growth_analyst`
- **Role:** Growth Specialist
- **Decision Authority:** Signal only
- **Data Inputs:**
  - Financial metrics (growth rates)
  - Line items (revenue, earnings)
  - Market cap
- **Outputs:** `signal`, `confidence`, `reasoning`
- **Deterministic:** No (LLM-dependent, has `rule_based_factory` fallback)
- **Capabilities:**
  - ✅ Generate trade direction
  - ❌ Size positions
  - ❌ Veto trades
  - ❌ Modify other agents' influence
- **Limitations:** Growth-focused; may overvalue high-growth companies

#### 16. News Sentiment Analyst Agent
- **File:** `src/agents/news_sentiment.py`
- **Registered Key:** `news_sentiment_analyst`
- **Role:** News Sentiment Specialist
- **Decision Authority:** Signal only
- **Data Inputs:**
  - Company news (headlines, content)
- **Outputs:** `signal`, `confidence`, `reasoning`
- **Deterministic:** No (LLM-dependent, has `rule_based_factory` with keyword matching)
- **Capabilities:**
  - ✅ Generate trade direction
  - ❌ Size positions
  - ❌ Veto trades
  - ❌ Modify other agents' influence
- **Limitations:** Sentiment-based; may be noisy or lagging

#### 17. Sentiment Analyst Agent
- **File:** `src/agents/sentiment.py`
- **Registered Key:** `sentiment_analyst`
- **Role:** Market Sentiment Specialist
- **Decision Authority:** Signal only
- **Data Inputs:**
  - Market sentiment indicators
  - Price data
- **Outputs:** `signal`, `confidence`, `reasoning`
- **Deterministic:** No (LLM-dependent, has `rule_based_factory` fallback)
- **Capabilities:**
  - ✅ Generate trade direction
  - ❌ Size positions
  - ❌ Veto trades
  - ❌ Modify other agents' influence
- **Limitations:** Sentiment-based; may be subjective

#### 18. Valuation Analyst Agent
- **File:** `src/agents/valuation.py`
- **Registered Key:** `valuation_analyst`
- **Role:** Company Valuation Specialist
- **Decision Authority:** Signal only
- **Data Inputs:**
  - Financial metrics
  - Line items
  - Market cap
- **Outputs:** `signal`, `confidence`, `reasoning`
- **Deterministic:** No (LLM-dependent, has `rule_based_factory` fallback)
- **Capabilities:**
  - ✅ Generate trade direction
  - ❌ Size positions
  - ❌ Veto trades
  - ❌ Modify other agents' influence
- **Limitations:** Valuation models may vary; requires assumptions

#### 19. Momentum Agent
- **File:** `src/agents/momentum.py`
- **Registered Key:** `momentum`
- **Role:** Momentum Trader / 20-Day Price Momentum Specialist
- **Decision Authority:** Signal only
- **Data Inputs:**
  - Price data (20-day lookback)
- **Outputs:** `signal`, `confidence`, `reasoning`
- **Deterministic:** ✅ Yes (fully rule-based, no LLM)
- **Capabilities:**
  - ✅ Generate trade direction
  - ❌ Size positions
  - ❌ Veto trades
  - ❌ Modify other agents' influence
- **Limitations:** Short-term focus; may miss reversals

#### 20. Mean Reversion Agent
- **File:** `src/agents/mean_reversion.py`
- **Registered Key:** `mean_reversion`
- **Role:** Mean Reversion Trader / Statistical Mean Reversion Specialist
- **Decision Authority:** Signal only
- **Data Inputs:**
  - Price data (RSI, moving averages)
- **Outputs:** `signal`, `confidence`, `reasoning`
- **Deterministic:** ✅ Yes (fully rule-based, no LLM)
- **Capabilities:**
  - ✅ Generate trade direction
  - ❌ Size positions
  - ❌ Veto trades
  - ❌ Modify other agents' influence
- **Limitations:** Contrarian; may fight strong trends

---

### SIGNAL MANAGERS (Meta-Analyst Agents)

#### 21. Market Regime Analyst Agent
- **File:** `src/agents/market_regime.py`
- **Registered Key:** `market_regime`
- **Role:** Market Condition Classifier (Advisory Only)
- **Decision Authority:** Advisory only
- **Data Inputs:**
  - Price data (ADX, volatility, RSI oscillation)
- **Outputs:**
  - `regime` (trending/mean_reverting/volatile/calm)
  - `weights` (momentum, mean_reversion strategy weights)
  - `risk_multiplier` (0.8-1.0)
  - `reasoning`
- **Deterministic:** ✅ Yes (fully rule-based, no LLM)
- **Capabilities:**
  - ❌ Generate trade direction
  - ❌ Size positions
  - ❌ Veto trades
  - ✅ Modify other agents' influence (via strategy weights)
- **Limitations:** Advisory only; Portfolio Manager must apply weights

#### 22. Ensemble Agent
- **File:** `src/agents/ensemble.py`
- **Registered Key:** `ensemble`
- **Role:** Combined Signal Specialist
- **Decision Authority:** Signal only (aggregates other signals)
- **Data Inputs:**
  - Warren Buffett agent signals
  - Momentum agent signals
  - Agent credibility scores (optional)
- **Outputs:** `signal`, `confidence`, `reasoning`
- **Deterministic:** ✅ Yes (fully rule-based, no LLM)
- **Capabilities:**
  - ✅ Generate trade direction (weighted combination)
  - ❌ Size positions
  - ❌ Veto trades
  - ✅ Modify other agents' influence (via credibility weighting)
- **Limitations:** Only combines Buffett + Momentum; fixed weights

#### 23. Conflict Arbiter Agent
- **File:** `src/agents/conflict_arbiter.py`
- **Registered Key:** `conflict_arbiter`
- **Role:** Signal Conflict Resolution Specialist
- **Decision Authority:** Signal only (adjusts confidence)
- **Data Inputs:**
  - All analyst signals
  - Agent credibility scores (optional)
- **Outputs:** Adjusted `signal`, `confidence`, `reasoning` per ticker
- **Deterministic:** ✅ Yes (fully rule-based, no LLM)
- **Capabilities:**
  - ✅ Generate trade direction (adjusted signals)
  - ❌ Size positions
  - ❌ Veto trades
  - ✅ Modify other agents' influence (reduces confidence on conflicts)
- **Limitations:** Only adjusts confidence; doesn't change direction

#### 24. Performance Auditor Agent
- **File:** `src/agents/performance_auditor.py`
- **Registered Key:** `performance_auditor`
- **Role:** Performance Tracking Specialist
- **Decision Authority:** Advisory only
- **Data Inputs:**
  - Analyst signals (historical)
  - Price data (for signal correctness evaluation)
- **Outputs:**
  - `agent_credibility` (0.0-1.0 per agent)
  - Performance metrics (correct/incorrect signals, totals)
- **Deterministic:** ✅ Yes (fully rule-based, no LLM)
- **Capabilities:**
  - ❌ Generate trade direction
  - ❌ Size positions
  - ❌ Veto trades
  - ✅ Modify other agents' influence (via credibility scores)
- **Limitations:** Requires historical data; gradual score updates

---

### CAPITAL ALLOCATORS

#### 25. Portfolio Manager Agent
- **File:** `src/agents/portfolio_manager.py`
- **Registered Key:** `portfolio_manager` (system agent, always runs)
- **Role:** Chief Investment Officer / Final Decision Maker
- **Decision Authority:** Capital allocation (generates trading decisions)
- **Data Inputs:**
  - All analyst signals (aggregated)
  - Risk Manager position limits
  - Market Regime weights (applied to Momentum/Mean Reversion)
  - Current portfolio state
  - Current prices
- **Outputs:**
  - `decisions` (action: buy/sell/short/cover/hold, quantity, confidence, reasoning)
  - Stored in `state["data"]["portfolio_decisions"]`
- **Deterministic:** Hybrid (has `rule_based_factory` for deterministic mode)
- **Capabilities:**
  - ✅ Generate trade direction
  - ✅ Size positions (quantity)
  - ❌ Veto trades (doesn't veto, makes decisions)
  - ✅ Modify other agents' influence (aggregates with regime weights)
- **Limitations:** LLM-dependent in normal mode; rule-based fallback may be simpler

#### 26. Risk Budget Agent
- **File:** `src/agents/risk_budget.py`
- **Registered Key:** `risk_budget_agent` (system agent, always runs)
- **Role:** Risk-Based Position Sizer
- **Decision Authority:** Capital allocation (position sizing only, no direction)
- **Data Inputs:**
  - Portfolio Manager decisions (direction)
  - Market Regime risk_multiplier
  - Price data (for ATR/volatility calculation)
  - Portfolio value
- **Outputs:**
  - `risk_budget` (base_risk_pct, volatility_adjustment, regime_multiplier, final_risk_pct, reasoning)
  - Stored in `state["data"]["risk_budget"]`
- **Deterministic:** ✅ Yes (fully rule-based, no LLM)
- **Capabilities:**
  - ❌ Generate trade direction (reads from PM)
  - ✅ Size positions (risk-based allocation)
  - ❌ Veto trades
  - ❌ Modify other agents' influence
- **Limitations:** Advisory only; doesn't modify PM decisions directly

---

### RISK CONTROLLERS

#### 27. Risk Manager Agent
- **File:** `src/agents/risk_manager.py`
- **Registered Key:** `risk_management_agent` (system agent, always runs)
- **Role:** Risk Manager / Volatility & Correlation Specialist
- **Decision Authority:** Risk control (sets position limits)
- **Data Inputs:**
  - Price data (for volatility calculation)
  - Portfolio state
  - Current positions
- **Outputs:**
  - Position limits per ticker (volatility-adjusted)
  - Correlation metrics
  - Stored in `state["data"]["analyst_signals"]["risk_management_agent"]`
- **Deterministic:** ✅ Yes (fully rule-based, no LLM)
- **Capabilities:**
  - ❌ Generate trade direction
  - ❌ Size positions (sets limits, not sizes)
  - ✅ Veto trades (via position limits = 0)
  - ❌ Modify other agents' influence
- **Limitations:** Volatility-based only; doesn't enforce portfolio-level constraints

#### 28. Portfolio Allocator Agent
- **File:** `src/agents/portfolio_allocator.py`
- **Registered Key:** `portfolio_allocator_agent` (system agent, always runs)
- **Role:** Portfolio Constraint Enforcer
- **Decision Authority:** Risk control (enforces portfolio-level limits)
- **Data Inputs:**
  - Portfolio Manager decisions
  - Risk Budget allocations
  - Price data (for correlation calculation)
  - Company facts (for sector classification)
  - Portfolio state
- **Outputs:**
  - Adjusted decisions (after constraint enforcement)
  - Constraint analysis (gross/net exposure, sector limits, correlations)
  - Stored in `state["data"]["portfolio_allocation"]`
- **Deterministic:** ✅ Yes (fully rule-based, no LLM)
- **Capabilities:**
  - ❌ Generate trade direction (reads from PM)
  - ✅ Size positions (adjusts quantities to meet constraints)
  - ✅ Veto trades (can reduce quantities to 0)
  - ❌ Modify other agents' influence
- **Limitations:** Enforces constraints but doesn't optimize allocation

---

## System Capabilities Summary

### What the System Can Do End-to-End Today

1. **Signal Generation:**
   - 22 analyst agents generate trading signals (bullish/bearish/neutral) with confidence scores
   - Mix of fundamental, technical, sentiment, and quantitative strategies
   - Both LLM-powered and deterministic agents

2. **Signal Management:**
   - Market Regime classification and strategy weight recommendations
   - Ensemble combination of selected signals
   - Conflict resolution between disagreeing analysts
   - Performance tracking and credibility scoring

3. **Capital Allocation:**
   - Portfolio Manager aggregates signals and makes trading decisions (buy/sell/short/cover/hold)
   - Risk Budget calculates position sizes based on risk metrics
   - Both direction and sizing decisions

4. **Risk Control:**
   - Volatility-adjusted position limits (Risk Manager)
   - Portfolio-level constraints (Portfolio Allocator):
     - Gross/net exposure limits (200% gross, ±50% net)
     - Sector concentration caps (30% per sector)
     - Correlation limits (max 0.70 between positions)

5. **Deterministic Operation:**
   - Full pipeline can run in `HEDGEFUND_NO_LLM=1` mode
   - All system agents (Risk Manager, Portfolio Manager, Risk Budget, Portfolio Allocator) are deterministic
   - Most analyst agents have rule-based fallbacks

### Critical Hedge Fund Roles Missing

1. **Execution Agent:**
   - **Missing:** Order routing, execution quality, slippage modeling
   - **Current State:** Decisions are generated but not executed
   - **Impact:** No real-world trade execution simulation

2. **Portfolio Construction Agent:**
   - **Missing:** Optimal portfolio construction (mean-variance optimization, risk parity, factor models)
   - **Current State:** Portfolio Manager aggregates signals but doesn't optimize portfolio weights
   - **Impact:** Suboptimal capital allocation across positions

3. **Compliance Agent:**
   - **Missing:** Regulatory compliance checks (position limits, restricted securities, insider trading rules)
   - **Current State:** No compliance enforcement
   - **Impact:** System may generate non-compliant trades

4. **Risk Analytics Agent:**
   - **Missing:** Advanced risk metrics (VaR, CVaR, stress testing, scenario analysis)
   - **Current State:** Basic volatility and correlation only
   - **Impact:** Limited risk visibility

5. **Performance Attribution Agent:**
   - **Missing:** Performance decomposition (factor attribution, sector attribution, security selection)
   - **Current State:** Performance Auditor tracks signal correctness but not PnL attribution
   - **Impact:** Limited understanding of what drives returns

6. **Liquidity Manager:**
   - **Missing:** Liquidity analysis, market impact modeling, execution cost estimation
   - **Current State:** No liquidity considerations
   - **Impact:** May size positions too large for illiquid securities

7. **Tax Optimizer:**
   - **Missing:** Tax-loss harvesting, wash sale rules, holding period optimization
   - **Current State:** No tax considerations
   - **Impact:** Suboptimal after-tax returns

8. **Cash Manager:**
   - **Missing:** Cash management, margin optimization, collateral management
   - **Current State:** Basic cash tracking only
   - **Impact:** Inefficient capital utilization

9. **Market Maker / Execution Quality:**
   - **Missing:** Bid-ask spread analysis, market depth, execution venue selection
   - **Current State:** Assumes perfect execution at last price
   - **Impact:** Unrealistic execution assumptions

10. **Research Coordinator:**
    - **Missing:** Research prioritization, information flow management, analyst coordination
    - **Current State:** All analysts run in parallel, no coordination
    - **Impact:** Potential redundant analysis, no research efficiency

---

## Agent Interaction Matrix

| Agent | Generates Direction | Sizes Positions | Vetoes Trades | Modifies Influence |
|-------|-------------------|----------------|---------------|-------------------|
| Analyst Agents (1-20) | ✅ | ❌ | ❌ | ❌ |
| Market Regime | ❌ | ❌ | ❌ | ✅ (weights) |
| Ensemble | ✅ | ❌ | ❌ | ✅ (credibility) |
| Conflict Arbiter | ✅ (adjusted) | ❌ | ❌ | ✅ (confidence) |
| Performance Auditor | ❌ | ❌ | ❌ | ✅ (credibility) |
| Portfolio Manager | ✅ | ✅ | ❌ | ✅ (aggregation) |
| Risk Budget | ❌ | ✅ | ❌ | ❌ |
| Risk Manager | ❌ | ❌ | ✅ (limits) | ❌ |
| Portfolio Allocator | ❌ | ✅ (adjusts) | ✅ (reduces) | ❌ |

---

## Data Dependency Map

| Data Type | Used By | Source |
|-----------|---------|--------|
| Price Data (OHLCV) | All agents | `get_prices()` API |
| Financial Metrics | 14 analyst agents | `get_financial_metrics()` API |
| Line Items | 12 analyst agents | `search_line_items()` API |
| Market Cap | 10 analyst agents | `get_market_cap()` API |
| Company News | 4 analyst agents | `get_company_news()` API |
| Insider Trades | 3 analyst agents | `get_insider_trades()` API |
| Company Facts (Sector) | Portfolio Allocator | `get_company_facts()` API |
| Portfolio State | Portfolio Manager, Risk Budget, Portfolio Allocator | `state["data"]["portfolio"]` |
| Analyst Signals | Portfolio Manager, Conflict Arbiter, Ensemble | `state["data"]["analyst_signals"]` |
| Market Regime | Portfolio Manager, Risk Budget | `state["data"]["market_regime"]` |
| Risk Budget | Portfolio Allocator | `state["data"]["risk_budget"]` |
| Agent Credibility | Ensemble, Conflict Arbiter | `state["data"]["agent_credibility"]` |

---

## Deterministic Capability Matrix

| Agent | Deterministic Mode | LLM Mode | Fallback Quality |
|-------|-------------------|----------|------------------|
| Momentum | ✅ Full | N/A | N/A |
| Mean Reversion | ✅ Full | N/A | N/A |
| Market Regime | ✅ Full | N/A | N/A |
| Ensemble | ✅ Full | N/A | N/A |
| Conflict Arbiter | ✅ Full | N/A | N/A |
| Performance Auditor | ✅ Full | N/A | N/A |
| Risk Manager | ✅ Full | N/A | N/A |
| Risk Budget | ✅ Full | N/A | N/A |
| Portfolio Allocator | ✅ Full | N/A | N/A |
| Portfolio Manager | ✅ Rule-based | ✅ LLM | Good (uses same logic) |
| Analyst Agents (1-20) | ⚠️ Fallback | ✅ LLM | Varies (some sophisticated, some basic) |

**Legend:**
- ✅ Full: Fully deterministic, no LLM dependency
- ⚠️ Fallback: Has rule-based fallback, but LLM is primary
- ✅ LLM: LLM-dependent, may have fallback

---

## Conclusion

The ai-hedge-fund system has a **robust foundation** with 30 agents covering:
- ✅ Diverse signal generation (22 analysts)
- ✅ Signal management and conflict resolution (3 meta-analysts)
- ✅ Capital allocation (2 allocators)
- ✅ Risk control (2 controllers)

**Key Strengths:**
- Strong deterministic capability (8 fully deterministic agents)
- Clear separation of concerns (signal → allocation → risk)
- Institutional-grade constraint enforcement

**Key Gaps:**
- No execution layer
- No portfolio optimization
- No compliance enforcement
- Limited risk analytics
- No performance attribution
- No liquidity management

The system is **production-ready for signal generation and risk-controlled allocation** but would need additional agents for **real-world execution and compliance**.
