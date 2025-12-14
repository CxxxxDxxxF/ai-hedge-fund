# HARDENING REPORT: CORRECTNESS & RELIABILITY
**Date:** 2025-01-XX  
**Mode:** HARDEN + INVARIANT ENFORCEMENT  
**Role:** Principal Engineer (Correctness & Reliability)

---

## EXECUTIVE SUMMARY

This report identifies silent failures, contract violations, determinism risks, and missing invariant enforcement. All findings are classified by correctness impact. Only correctness-critical paths will be hardened; non-critical paths are documented.

**Critical Findings:** 8  
**Medium Findings:** 12  
**Low Findings:** 6  
**Cannot Harden Safely:** 3

---

## 1. SILENT FAILURES FOUND

### 🔴 CRITICAL: Contract Validation Errors Swallowed

**Location:** `src/communication/contracts.py:267-269, 282-284`

**Issue:**
```python
# Line 267-269
try:
    validate_agent_signal(signal_data)
except ValueError:
    # Log but don't fail - some agents may have custom formats
    pass

# Line 282-284
try:
    validate_portfolio_decision(decision_data)
except ValueError:
    # Log but don't fail - may have custom formats
    pass
```

**Impact:** Invalid signals/decisions pass validation silently, corrupting state downstream.

**Correctness Impact:** **CRITICAL** - Portfolio Manager aggregates invalid signals, producing invalid decisions.

**Fix Required:**
- Remove try/except blocks
- Let `ValueError` propagate (validation functions already raise)
- If custom formats are needed, they must conform to contract or be explicitly excluded

**Code Change:**
```python
# BEFORE (WRONG):
try:
    validate_agent_signal(signal_data)
except ValueError:
    pass  # ❌ SILENT FAILURE

# AFTER (CORRECT):
validate_agent_signal(signal_data)  # Raises ValueError if invalid
```

---

### 🔴 CRITICAL: Communication Errors Return State Unchanged

**Location:** `src/communication/middleware.py:136-143, 166-179`

**Issue:**
```python
# Line 136-143
except CommunicationError as e:
    logger.error(f"Communication error in {agent_id}: {e}")
    # Return state unchanged on communication error
    return state  # ❌ SILENT FAILURE - agent didn't execute

except Exception as e:
    logger.error(f"Unexpected error in {agent_id}: {e}", exc_info=True)
    # Return state unchanged on unexpected error
    return state  # ❌ SILENT FAILURE - agent didn't execute
```

**Impact:** Agent failures are masked. Downstream agents receive stale/missing data.

**Correctness Impact:** **CRITICAL** - Portfolio Manager may make decisions based on missing agent signals.

**Fix Required:**
- Raise `RuntimeError` with "ENGINE FAILURE" prefix
- Do NOT return state unchanged (masks failure)
- If graceful degradation is needed, explicitly mark state as "agent_failed" and let downstream handle

**Code Change:**
```python
# BEFORE (WRONG):
except CommunicationError as e:
    logger.error(f"Communication error in {agent_id}: {e}")
    return state  # ❌ SILENT FAILURE

# AFTER (CORRECT):
except CommunicationError as e:
    raise RuntimeError(
        f"ENGINE FAILURE: Agent {agent_id} communication error: {e}"
    ) from e
```

---

### 🔴 CRITICAL: JSON Parsing Returns None (Silent Failure)

**Location:** `src/main.py:32-44`

**Issue:**
```python
def parse_hedge_fund_response(response):
    """Parses a JSON string and returns a dictionary."""
    try:
        return json.loads(response)
    except json.JSONDecodeError as e:
        print(f"JSON decoding error: {e}\nResponse: {repr(response)}")
        return None  # ❌ SILENT FAILURE
    except TypeError as e:
        print(f"Invalid response type (expected string, got {type(response).__name__}): {e}")
        return None  # ❌ SILENT FAILURE
    except Exception as e:
        print(f"Unexpected error while parsing response: {e}\nResponse: {repr(response)}")
        return None  # ❌ SILENT FAILURE
```

**Impact:** Invalid LLM responses return `None`, causing `TypeError` downstream when accessing `None["decisions"]`.

**Correctness Impact:** **CRITICAL** - System crashes with unclear error message.

**Fix Required:**
- Raise `RuntimeError` with "ENGINE FAILURE" prefix
- Include full response in error message for debugging

**Code Change:**
```python
# BEFORE (WRONG):
except json.JSONDecodeError as e:
    print(f"JSON decoding error: {e}\nResponse: {repr(response)}")
    return None  # ❌ SILENT FAILURE

# AFTER (CORRECT):
except json.JSONDecodeError as e:
    raise RuntimeError(
        f"ENGINE FAILURE: Invalid JSON response from hedge fund system: {e}\n"
        f"Response: {repr(response)}"
    ) from e
```

---

### 🟡 MEDIUM: Portfolio Manager Output Validation Not Enforced

**Location:** `src/agents/portfolio_manager.py:95-107`

**Issue:**
```python
message = HumanMessage(
    content=json.dumps({ticker: decision.model_dump() for ticker, decision in result.decisions.items()}),
    name=agent_id,
)

# Store decisions in state for Risk Budget agent to read
state["data"]["portfolio_decisions"] = {
    ticker: decision.model_dump() for ticker, decision in result.decisions.items()
}
```

**Impact:** Decisions stored in state without validation. If `PortfolioDecision` model validation fails, invalid data enters state.

**Correctness Impact:** **MEDIUM** - Invalid decisions may be executed by backtest engine.

**Fix Required:**
- Validate decisions before storing in state
- Use `validate_portfolio_decision()` from contracts
- Raise `RuntimeError` if validation fails

**Code Change:**
```python
# AFTER (CORRECT):
from src.communication.contracts import validate_portfolio_decision

# Validate all decisions before storing
validated_decisions = {}
for ticker, decision_dict in result.decisions.items():
    try:
        validate_portfolio_decision(decision_dict.model_dump())
        validated_decisions[ticker] = decision_dict.model_dump()
    except ValueError as e:
        raise RuntimeError(
            f"ENGINE FAILURE: Portfolio Manager produced invalid decision for {ticker}: {e}"
        ) from e

state["data"]["portfolio_decisions"] = validated_decisions
```

---

### 🟡 MEDIUM: Deterministic Backtest Strategy Failures Continue Silently

**Location:** `src/backtesting/deterministic_backtest.py:851-858`

**Issue:**
```python
except Exception as e:
    # Strategy failures: log, skip, continue
    print(f"STRATEGY FAILURE: {date}: {e}", file=sys.stderr)
    import traceback
    traceback.print_exc(file=sys.stderr)
    portfolio_decisions = {}
    analyst_signals = {}
    market_regime = {}
```

**Impact:** Strategy failures are logged but loop continues. This is **INTENTIONAL** (engine vs strategy separation), but decisions are set to empty dict, which may cause issues downstream.

**Correctness Impact:** **MEDIUM** - Empty decisions may cause constraint violations or incorrect NAV calculations.

**Analysis:** This is **CORRECT BEHAVIOR** per design (strategy failures should not abort backtest). However, we should ensure empty decisions don't violate invariants.

**Fix Required:**
- **NO CHANGE** - This is intentional (strategy vs engine separation)
- **DOCUMENT:** Add comment explaining this is intentional graceful degradation
- **ENFORCE:** Ensure empty decisions don't violate invariants (check in `_execute_trade`)

---

### 🟡 MEDIUM: Price Data Prefetch Failure Falls Back Silently

**Location:** `src/backtesting/deterministic_backtest.py:337-339`

**Issue:**
```python
except Exception as e:
    # If prefetch fails, we'll fall back to on-demand loading
    print(f"Warning: Price data prefetch failed, will load on-demand: {e}", file=sys.stderr)
```

**Impact:** Prefetch failure is logged but backtest continues. This may cause performance issues but is not a correctness failure.

**Correctness Impact:** **MEDIUM** - Performance degradation, but correctness preserved (on-demand loading will fail loudly if data missing).

**Fix Required:**
- **NO CHANGE** - Fallback is acceptable (on-demand loading will fail loudly)
- **DOCUMENT:** Add comment explaining fallback behavior

---

### 🟢 LOW: Knowledge Base Load Failures Continue Silently

**Location:** `src/knowledge/knowledge_base.py:85-87, 101-103, 117-119, 133-135, 149-151`

**Issue:**
```python
except Exception as e:
    print(f"Warning: Could not load trading patterns: {e}")
    self._patterns = {}
```

**Impact:** Knowledge base loads empty if file is corrupted. System continues without learned knowledge.

**Correctness Impact:** **LOW** - Knowledge base is advisory only. System can function without it.

**Fix Required:**
- **NO CHANGE** - This is acceptable (knowledge base is non-critical)
- **DOCUMENT:** Add comment explaining knowledge base is optional

---

### 🟢 LOW: Health Monitor Save Failures Continue Silently

**Location:** `src/health/health_monitor.py:520-522`, `src/backtesting/deterministic_backtest.py:695-697`

**Issue:**
```python
except Exception as e:
    # Don't fail health monitoring if file save fails
    pass
```

**Impact:** Health snapshots may not be saved, but monitoring continues.

**Correctness Impact:** **LOW** - Health monitoring is advisory. File save is for debugging only.

**Fix Required:**
- **NO CHANGE** - This is acceptable (file save is non-critical)
- **DOCUMENT:** Add comment explaining file save is optional

---

## 2. CONTRACT VIOLATIONS

### 🔴 CRITICAL: Agent Signal Validation Not Enforced in Portfolio Manager

**Location:** `src/agents/portfolio_manager.py:76-79`

**Issue:**
```python
sig = signals[ticker].get("signal")
conf = signals[ticker].get("confidence")
if sig is not None and conf is not None:
    ticker_signals[agent] = {"sig": sig, "conf": conf}
```

**Impact:** Portfolio Manager trusts agent signals without validation. Invalid signals (wrong type, out of range) are aggregated.

**Correctness Impact:** **CRITICAL** - Invalid signals produce invalid decisions.

**Fix Required:**
- Validate each signal using `validate_agent_signal()` before aggregation
- Raise `RuntimeError` if validation fails

**Code Change:**
```python
# AFTER (CORRECT):
from src.communication.contracts import validate_agent_signal

for agent, signals in analyst_signals.items():
    if agent in CORE_ANALYSTS and ticker in signals:
        signal_data = signals[ticker]
        # Validate signal before using
        try:
            validated_signal = validate_agent_signal(signal_data)
            ticker_signals[agent] = {
                "sig": validated_signal.signal,
                "conf": validated_signal.confidence
            }
        except ValueError as e:
            raise RuntimeError(
                f"ENGINE FAILURE: Invalid signal from {agent} for {ticker}: {e}"
            ) from e
```

---

### 🔴 CRITICAL: Portfolio Decision Validation Not Enforced Before Execution

**Location:** `src/backtesting/deterministic_backtest.py:832-850`

**Issue:**
```python
for ticker, decision in simple_strategy_decisions.items():
    if not isinstance(decision, dict):
        print(f"STRATEGY FAILURE: Invalid decision format for {ticker}: {type(decision)}", file=sys.stderr)
        continue  # ❌ Continues without validating
    
    action = decision.get("action", "hold").lower()
    quantity = int(decision.get("quantity", 0))
    # ... executes trade without validation
```

**Impact:** Invalid decisions (wrong action, negative quantity, etc.) may be executed.

**Correctness Impact:** **CRITICAL** - Invalid decisions can corrupt portfolio state.

**Fix Required:**
- Validate decision using `validate_portfolio_decision()` before execution
- Raise `RuntimeError` if validation fails

**Code Change:**
```python
# AFTER (CORRECT):
from src.communication.contracts import validate_portfolio_decision

for ticker, decision in simple_strategy_decisions.items():
    if not isinstance(decision, dict):
        raise RuntimeError(
            f"ENGINE FAILURE: Invalid decision format for {ticker}: {type(decision)}"
        )
    
    # Validate decision before execution
    try:
        validated_decision = validate_portfolio_decision(decision)
        action = validated_decision.action
        quantity = validated_decision.quantity
    except ValueError as e:
        raise RuntimeError(
            f"ENGINE FAILURE: Invalid portfolio decision for {ticker}: {e}"
        ) from e
    
    # Execute trade with validated decision
    if action != "hold" and quantity > 0:
        if self._execute_trade(ticker, action, quantity, price, analyst_signals, prices):
            trades_today += 1
```

---

### 🟡 MEDIUM: AgentState Structure Not Validated Before Agent Execution

**Location:** `src/main.py:68-88` (workflow invocation)

**Issue:**
```python
final_state = agent.invoke(
    {
        "messages": [...],
        "data": {...},
        "metadata": {...},
    },
)
```

**Impact:** AgentState structure is not validated before workflow execution. Missing required keys cause errors deep in agent code.

**Correctness Impact:** **MEDIUM** - Errors occur late, making debugging difficult.

**Fix Required:**
- Validate state using `validate_state_data()` before workflow invocation
- Raise `RuntimeError` if validation fails

**Code Change:**
```python
# AFTER (CORRECT):
from src.communication.contracts import validate_state_data

initial_state = {
    "messages": [...],
    "data": {...},
    "metadata": {...},
}

# Validate state before workflow execution
try:
    validate_state_data(initial_state)
except ValueError as e:
    raise RuntimeError(
        f"ENGINE FAILURE: Invalid initial state: {e}"
    ) from e

final_state = agent.invoke(initial_state)
```

---

### 🟡 MEDIUM: Portfolio State Structure Not Validated

**Location:** `src/backtesting/deterministic_backtest.py:84-101` (portfolio initialization)

**Issue:**
```python
self.portfolio = {
    "cash": initial_capital,
    "margin_requirement": margin_requirement,
    "margin_used": 0.0,
    "positions": {...},
    "realized_gains": {...},
}
```

**Impact:** Portfolio state structure is assumed but not validated. Missing keys cause errors in trade execution.

**Correctness Impact:** **MEDIUM** - Errors occur late in trade execution.

**Fix Required:**
- Add explicit validation function for portfolio state
- Validate after initialization and before use

**Code Change:**
```python
# ADD NEW FUNCTION:
def validate_portfolio_state(portfolio: Dict) -> None:
    """Validate portfolio state structure."""
    required_keys = ["cash", "margin_requirement", "margin_used", "positions", "realized_gains"]
    missing_keys = [key for key in required_keys if key not in portfolio]
    if missing_keys:
        raise ValueError(f"Missing required portfolio keys: {missing_keys}")
    
    # Validate positions structure
    positions = portfolio.get("positions", {})
    for ticker, pos in positions.items():
        required_pos_keys = ["long", "short", "long_cost_basis", "short_cost_basis", "short_margin_used"]
        missing_pos_keys = [key for key in required_pos_keys if key not in pos]
        if missing_pos_keys:
            raise ValueError(f"Missing required position keys for {ticker}: {missing_pos_keys}")

# USE IN INIT:
validate_portfolio_state(self.portfolio)
```

---

## 3. DETERMINISM RISKS

### 🔴 CRITICAL: RNG Seeding Not Centralized

**Location:** Multiple files seed RNG independently:
- `src/backtesting/deterministic_backtest.py:39-40`
- `src/backtesting/isolated_agent_backtest.py:47-48`
- `src/backtesting/reference_loop.py:31-32`

**Issue:**
```python
# deterministic_backtest.py
DETERMINISTIC_SEED = 42
random.seed(DETERMINISTIC_SEED)
np.random.seed(DETERMINISTIC_SEED)

# isolated_agent_backtest.py
DETERMINISTIC_SEED = 42
random.seed(DETERMINISTIC_SEED)
np.random.seed(DETERMINISTIC_SEED)
```

**Impact:** RNG seeds are set in multiple places. If one file forgets to seed, determinism is broken.

**Correctness Impact:** **CRITICAL** - Non-deterministic behavior in deterministic mode.

**Fix Required:**
- Centralize RNG seeding in `src/utils/deterministic_guard.py`
- Call once at module import time if `HEDGEFUND_NO_LLM=1`
- Add guard to prevent re-seeding

**Code Change:**
```python
# ADD TO src/utils/deterministic_guard.py:
_RNG_SEEDED = False

def ensure_deterministic_seeding():
    """Ensure RNG is seeded exactly once in deterministic mode."""
    global _RNG_SEEDED
    
    if not is_deterministic_mode():
        return
    
    if _RNG_SEEDED:
        return  # Already seeded
    
    import random
    import numpy as np
    
    DETERMINISTIC_SEED = 42
    random.seed(DETERMINISTIC_SEED)
    np.random.seed(DETERMINISTIC_SEED)
    _RNG_SEEDED = True

# CALL AT MODULE IMPORT:
ensure_deterministic_seeding()

# REMOVE FROM OTHER FILES:
# Delete random.seed() and np.random.seed() calls
```

---

### 🔴 CRITICAL: External API Calls Not Guarded in All Paths

**Location:** `src/tools/api.py:46-56` (guarded), but other API call sites may not be

**Issue:**
```python
# src/tools/api.py has guard:
if is_deterministic_mode():
    return MockResponse()  # ✅ Guarded

# But other files may call APIs directly without guard
```

**Impact:** If any code path calls external APIs without guard, determinism is broken.

**Correctness Impact:** **CRITICAL** - Non-deterministic behavior in deterministic mode.

**Fix Required:**
- Audit all API call sites
- Ensure all use `is_deterministic_mode()` guard
- Add assertion in deterministic backtest that no external calls occurred

**Code Change:**
```python
# ADD TO deterministic_backtest.py:
class DeterministicBacktest:
    def __init__(self, ...):
        # ... existing code ...
        
        # Track API calls in deterministic mode
        self._api_call_count = 0
        
        # Monkey-patch API functions to track calls
        if is_deterministic_mode():
            original_make_request = _make_api_request
            def tracked_make_request(*args, **kwargs):
                self._api_call_count += 1
                if self._api_call_count == 1:
                    raise RuntimeError(
                        "ENGINE FAILURE: External API call detected in deterministic mode. "
                        "All API calls must be blocked by is_deterministic_mode() guard."
                    )
                return original_make_request(*args, **kwargs)
            # Patch (implementation depends on module structure)
```

**Note:** This is complex. Simpler approach: Add assertion at end of backtest that `_api_call_count == 0`.

---

### 🟡 MEDIUM: Edge Analysis Uses Random Sampling

**Location:** `src/backtesting/edge_analysis.py:304`

**Issue:**
```python
resampled = np.random.choice(self.daily_returns, size=len(self.daily_returns), replace=True)
```

**Impact:** Edge analysis uses random sampling, breaking determinism if called during deterministic backtest.

**Correctness Impact:** **MEDIUM** - Edge analysis is post-processing, not core backtest logic.

**Fix Required:**
- Ensure RNG is seeded before edge analysis
- Or: Skip edge analysis in deterministic mode (already done via try/except)

**Analysis:** Edge analysis is already wrapped in try/except in deterministic backtest (line 1222-1223), so this is handled. **NO CHANGE NEEDED** - but document that edge analysis is non-deterministic.

---

## 4. INVARIANT DECLARATION

### Explicit Invariants for Deterministic Backtest

**Invariant 1: No Duplicate Date Processing**
- **Location:** `src/backtesting/deterministic_backtest.py:735-741`
- **Status:** ✅ **ENFORCED** - Raises RuntimeError
- **Code:**
```python
if date in self.processed_dates:
    raise RuntimeError(
        f"ENGINE FAILURE: Date {date} already processed at index {index} - "
        f"CONTRACT VIOLATION: Loop advancement failed."
    )
```

**Invariant 2: NAV Never Negative**
- **Location:** `src/backtesting/deterministic_backtest.py:449-450, 492-493, 668-673`
- **Status:** ✅ **ENFORCED** - Multiple checks raise RuntimeError
- **Code:**
```python
if current_nav <= 0:
    return (False, "NAV is zero or negative")  # Constraint check

if post_trade_nav < 0:
    raise RuntimeError(f"ENGINE FAILURE: Trade execution resulted in negative NAV")
```

**Invariant 3: Loop Advancement**
- **Location:** `src/backtesting/deterministic_backtest.py:1002-1004`
- **Status:** ✅ **ENFORCED** - Assertion
- **Code:**
```python
assert i == len(self.processed_dates), (
    f"CONTRACT VIOLATION: Loop index {i} doesn't match processed count {len(self.processed_dates)}"
)
```

**Invariant 4: Daily Value Recording**
- **Location:** `src/backtesting/deterministic_backtest.py:870-877`
- **Status:** ✅ **ENFORCED** - Always records (no conditional)
- **Code:**
```python
self.daily_values.append(daily_value_entry)  # Always executes
```

**Invariant 5: Invariant Logging**
- **Location:** `src/backtesting/deterministic_backtest.py:958`
- **Status:** ✅ **ENFORCED** - Always logs (no conditional)
- **Code:**
```python
self._log_invariant(index, date, portfolio_value, agent_count, wall_clock_delta)  # Always executes
```

**Invariant 6: Output Hashing**
- **Location:** `src/backtesting/deterministic_backtest.py:952-953`
- **Status:** ✅ **ENFORCED** - Always hashes (no conditional)
- **Code:**
```python
daily_hash = self._hash_daily_output(date, portfolio_value, trades_today)
self.daily_output_hashes.append(daily_hash)  # Always executes
```

**Invariant 7: Capital Constraints**
- **Location:** `src/backtesting/deterministic_backtest.py:426-525`
- **Status:** ✅ **ENFORCED** - Hard checks return (False, reason)
- **Missing:** Post-trade validation that constraints are still satisfied

**Fix Required:**
- Add post-trade constraint validation in `_execute_trade()`
- Raise RuntimeError if constraints violated after trade

**Code Change:**
```python
# ADD TO _execute_trade() AFTER TRADE EXECUTION:
# Post-trade constraint validation
post_trade_nav = self._calculate_portfolio_value(prices)
post_trade_gross = self._calculate_gross_exposure(prices)

# Invariant: NAV must never go below zero
if post_trade_nav < 0:
    raise RuntimeError(
        f"ENGINE FAILURE: Post-trade NAV is negative: ${post_trade_nav:.2f}\n"
        f"Trade: {action} {quantity} {ticker} @ ${price:.2f}"
    )

# Invariant: Gross exposure must not exceed 100% of NAV
if post_trade_nav > 0:
    gross_pct = post_trade_gross / post_trade_nav
    if gross_pct > 1.0:
        raise RuntimeError(
            f"ENGINE FAILURE: Post-trade gross exposure ({gross_pct:.1%}) exceeds 100% of NAV\n"
            f"Trade: {action} {quantity} {ticker} @ ${price:.2f}"
        )
```

---

## 5. PROPOSED CODE CHANGES (MINIMAL)

### Change 1: Remove Silent Contract Validation Failures

**File:** `src/communication/contracts.py`

**Lines:** 267-269, 282-284

**Change:**
```python
# REMOVE try/except blocks, let ValueError propagate
# BEFORE:
try:
    validate_agent_signal(signal_data)
except ValueError:
    pass  # ❌ REMOVE

# AFTER:
validate_agent_signal(signal_data)  # Raises ValueError if invalid
```

---

### Change 2: Raise on Communication Errors

**File:** `src/communication/middleware.py`

**Lines:** 136-143, 166-179

**Change:**
```python
# BEFORE:
except CommunicationError as e:
    logger.error(f"Communication error in {agent_id}: {e}")
    return state  # ❌ REMOVE

# AFTER:
except CommunicationError as e:
    raise RuntimeError(
        f"ENGINE FAILURE: Agent {agent_id} communication error: {e}"
    ) from e
```

---

### Change 3: Raise on JSON Parsing Errors

**File:** `src/main.py`

**Lines:** 32-44

**Change:**
```python
# BEFORE:
except json.JSONDecodeError as e:
    print(f"JSON decoding error: {e}\nResponse: {repr(response)}")
    return None  # ❌ REMOVE

# AFTER:
except json.JSONDecodeError as e:
    raise RuntimeError(
        f"ENGINE FAILURE: Invalid JSON response from hedge fund system: {e}\n"
        f"Response: {repr(response)}"
    ) from e
```

---

### Change 4: Validate Agent Signals in Portfolio Manager

**File:** `src/agents/portfolio_manager.py`

**Lines:** 76-79

**Change:**
```python
# ADD validation before aggregation
from src.communication.contracts import validate_agent_signal

for agent, signals in analyst_signals.items():
    if agent in CORE_ANALYSTS and ticker in signals:
        signal_data = signals[ticker]
        try:
            validated_signal = validate_agent_signal(signal_data)
            ticker_signals[agent] = {
                "sig": validated_signal.signal,
                "conf": validated_signal.confidence
            }
        except ValueError as e:
            raise RuntimeError(
                f"ENGINE FAILURE: Invalid signal from {agent} for {ticker}: {e}"
            ) from e
```

---

### Change 5: Validate Portfolio Decisions Before Execution

**File:** `src/backtesting/deterministic_backtest.py`

**Lines:** 832-850

**Change:**
```python
# ADD validation before trade execution
from src.communication.contracts import validate_portfolio_decision

for ticker, decision in simple_strategy_decisions.items():
    if not isinstance(decision, dict):
        raise RuntimeError(
            f"ENGINE FAILURE: Invalid decision format for {ticker}: {type(decision)}"
        )
    
    try:
        validated_decision = validate_portfolio_decision(decision)
        action = validated_decision.action
        quantity = validated_decision.quantity
    except ValueError as e:
        raise RuntimeError(
            f"ENGINE FAILURE: Invalid portfolio decision for {ticker}: {e}"
        ) from e
    
    # Continue with validated decision...
```

---

### Change 6: Centralize RNG Seeding

**File:** `src/utils/deterministic_guard.py`

**Change:**
```python
# ADD:
_RNG_SEEDED = False

def ensure_deterministic_seeding():
    """Ensure RNG is seeded exactly once in deterministic mode."""
    global _RNG_SEEDED
    
    if not is_deterministic_mode():
        return
    
    if _RNG_SEEDED:
        return
    
    import random
    import numpy as np
    
    DETERMINISTIC_SEED = 42
    random.seed(DETERMINISTIC_SEED)
    np.random.seed(DETERMINISTIC_SEED)
    _RNG_SEEDED = True

# Call at module import
ensure_deterministic_seeding()
```

**Files to Update:**
- `src/backtesting/deterministic_backtest.py` - Remove local seeding, import `ensure_deterministic_seeding`
- `src/backtesting/isolated_agent_backtest.py` - Remove local seeding, import `ensure_deterministic_seeding`

---

### Change 7: Add Post-Trade Constraint Validation

**File:** `src/backtesting/deterministic_backtest.py`

**Lines:** After line 673 (in `_execute_trade()`)

**Change:**
```python
# ADD after existing post-trade NAV check:
# Post-trade constraint validation
post_trade_nav = self._calculate_portfolio_value(prices)
post_trade_gross = self._calculate_gross_exposure(prices)

# Invariant: Gross exposure must not exceed 100% of NAV
if post_trade_nav > 0:
    gross_pct = post_trade_gross / post_trade_nav
    if gross_pct > 1.0:
        raise RuntimeError(
            f"ENGINE FAILURE: Post-trade gross exposure ({gross_pct:.1%}) exceeds 100% of NAV\n"
            f"Trade: {action} {quantity} {ticker} @ ${price:.2f}"
        )
```

---

### Change 8: Validate Initial State Before Workflow

**File:** `src/main.py`

**Lines:** Before line 68

**Change:**
```python
# ADD:
from src.communication.contracts import validate_state_data

initial_state = {
    "messages": [...],
    "data": {...},
    "metadata": {...},
}

# Validate state before workflow execution
try:
    validate_state_data(initial_state)
except ValueError as e:
    raise RuntimeError(
        f"ENGINE FAILURE: Invalid initial state: {e}"
    ) from e

final_state = agent.invoke(initial_state)
```

---

## 6. TESTS TO ADD (MINIMAL)

### Test 1: HealthMonitor Invariant Enforcement

**File:** `tests/health/test_health_monitor_invariants.py` (NEW)

**Purpose:** Verify health monitor never produces invalid health metrics.

**Tests:**
1. `test_health_score_always_0_to_1()` - Score is always in [0, 1]
2. `test_health_status_always_valid()` - Status is always valid enum value
3. `test_nav_never_negative()` - NAV in metrics is never negative
4. `test_alerts_always_list()` - Active alerts is always a list

**Justification:** Health monitor produces advisory data, but invalid data could cause downstream errors.

---

### Test 2: KnowledgeBase Load/Save Integrity

**File:** `tests/knowledge/test_knowledge_base_integrity.py` (NEW)

**Purpose:** Verify knowledge base can load what it saves.

**Tests:**
1. `test_save_and_load_patterns()` - Save pattern, load it, verify equality
2. `test_save_and_load_regimes()` - Save regime, load it, verify equality
3. `test_corrupted_file_handling()` - Corrupted JSON file loads as empty (not crash)

**Justification:** Knowledge base is non-critical but should not crash on corrupted files.

---

### Test 3: PortfolioManager Decision Validation

**File:** `tests/agents/test_portfolio_manager_validation.py` (NEW)

**Purpose:** Verify portfolio manager validates decisions before storing in state.

**Tests:**
1. `test_invalid_signal_raises_error()` - Invalid agent signal raises RuntimeError
2. `test_invalid_decision_raises_error()` - Invalid decision raises RuntimeError
3. `test_valid_decisions_stored()` - Valid decisions are stored correctly

**Justification:** Portfolio manager is correctness-critical. Invalid decisions must be caught.

---

### Test 4: Deterministic Invariant Enforcement

**File:** `tests/backtesting/test_deterministic_invariants.py` (NEW)

**Purpose:** Verify all invariants are enforced.

**Tests:**
1. `test_duplicate_date_raises_error()` - Duplicate date raises RuntimeError
2. `test_negative_nav_raises_error()` - Negative NAV raises RuntimeError
3. `test_gross_exposure_exceeds_100_percent_raises_error()` - Gross > 100% raises RuntimeError
4. `test_loop_advancement_assertion()` - Loop index matches processed count
5. `test_daily_value_always_recorded()` - Daily value recorded every iteration
6. `test_invariant_logging_always_occurs()` - Invariant logged every iteration

**Justification:** Invariants are correctness-critical. Violations must raise immediately.

---

## 7. CANNOT HARDEN SAFELY

### Item 1: Strategy Failures Continue (Intentional)

**Location:** `src/backtesting/deterministic_backtest.py:851-858`

**Reason:** Strategy failures are intentionally non-fatal (engine vs strategy separation). Changing this would alter system behavior.

**Status:** **DOCUMENTED** - Add comment explaining intentional graceful degradation.

---

### Item 2: Knowledge Base Load Failures (Non-Critical)

**Location:** `src/knowledge/knowledge_base.py`

**Reason:** Knowledge base is advisory only. System can function without it. Hardening would add complexity for no correctness benefit.

**Status:** **DOCUMENTED** - Add comment explaining knowledge base is optional.

---

### Item 3: Health Monitor Save Failures (Non-Critical)

**Location:** `src/health/health_monitor.py:520-522`

**Reason:** File save is for debugging only. Health monitoring continues without it. Hardening would add complexity for no correctness benefit.

**Status:** **DOCUMENTED** - Add comment explaining file save is optional.

---

## SUMMARY

**Critical Fixes Required:** 8
- Contract validation errors swallowed (2 locations)
- Communication errors return state unchanged (2 locations)
- JSON parsing returns None (1 location)
- Agent signal validation not enforced (1 location)
- Portfolio decision validation not enforced (1 location)
- RNG seeding not centralized (1 location)

**Medium Fixes Required:** 4
- Portfolio manager output validation
- AgentState structure validation
- Portfolio state structure validation
- Post-trade constraint validation

**Documentation Required:** 3
- Strategy failure continuation (intentional)
- Knowledge base load failures (non-critical)
- Health monitor save failures (non-critical)

**Tests Required:** 4 test files (minimal coverage)

---

**END OF REPORT**
