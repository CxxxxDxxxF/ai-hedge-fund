# Communication Foundation - Secure Inter-Department Communication

## Overview

A secure foundation has been established for effective communication between departments (agents, portfolio manager, risk manager, backtesting engine).

## Architecture

### Communication Layers

```
┌─────────────────────────────────────────────────────────┐
│              Communication Contracts                    │
│  (Data structures, validation, type safety)            │
└─────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│              Communication Interfaces                    │
│  (Protocols that departments must implement)             │
└─────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│              Communication Middleware                   │
│  (Validation, error handling, logging)                   │
└─────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│              Departments                                 │
│  (Agents, Portfolio Manager, Risk Manager, Backtest)    │
└─────────────────────────────────────────────────────────┘
```

## Data Contracts

### 1. Agent Signal Contract

**Location**: `src/communication/contracts.py::AgentSignal`

**Format**:
```python
{
    "signal": "bullish" | "bearish" | "neutral",
    "confidence": 0-100,
    "reasoning": "Human-readable explanation"
}
```

**Validation**:
- Signal must be one of: bullish, bearish, neutral
- Confidence must be 0-100
- Reasoning must be a string

**Usage**: All agents must produce signals in this format.

### 2. Portfolio Decision Contract

**Location**: `src/communication/contracts.py::PortfolioDecision`

**Format**:
```python
{
    "action": "buy" | "sell" | "short" | "cover" | "hold",
    "quantity": int >= 0,
    "confidence": 0-100,
    "reasoning": "Human-readable explanation"
}
```

**Validation**:
- Action must be one of: buy, sell, short, cover, hold
- Quantity must be >= 0
- Hold action must have quantity = 0
- Confidence must be 0-100

**Usage**: Portfolio Manager must produce decisions in this format.

### 3. Market Regime Contract

**Location**: `src/communication/contracts.py::MarketRegimeData`

**Format**:
```python
{
    "regime": "trending" | "mean_reverting" | "volatile" | "calm",
    "weights": {"momentum": 1.5, "mean_reversion": 0.5},
    "risk_multiplier": 0.0-2.0,
    "reasoning": "Explanation"
}
```

**Usage**: Market Regime Analyst produces this, Portfolio Manager reads it.

### 4. Risk Budget Contract

**Location**: `src/communication/contracts.py::RiskBudgetData`

**Format**:
```python
{
    "ticker": "AAPL",
    "base_risk_pct": 0.0-1.0,
    "volatility_adjustment": float >= 0.0,
    "regime_multiplier": 0.0-2.0,
    "final_risk_pct": 0.0-1.0,
    "reasoning": "Explanation"
}
```

**Usage**: Risk Budget Agent produces this, Portfolio Allocator reads it.

### 5. Health Metrics Contract

**Location**: `src/communication/contracts.py::HealthMetrics`

**Format**:
```python
{
    "overall_score": 0.0-1.0,
    "overall_status": "excellent" | "healthy" | "caution" | "warning" | "critical",
    "nav": float,
    "nav_pct_of_initial": float,
    "active_alerts": ["alert1", "alert2"]
}
```

**Usage**: Health Monitor produces this for monitoring and alerting.

## Communication Interfaces

### Agent Interface

**Protocol**: `AgentInterface`

**Contract**:
- Must write to: `state["data"]["analyst_signals"][agent_id][ticker]`
- Signal format: `AgentSignal` contract
- Returns: Updated state dict

**Implementation**: All agents must follow this protocol.

### Portfolio Manager Interface

**Protocol**: `PortfolioManagerInterface`

**Contract**:
- Reads: `state["data"]["analyst_signals"]`
- Writes: `state["data"]["portfolio_decisions"]`
- Decision format: `PortfolioDecision` contract

**Implementation**: Portfolio Manager must follow this protocol.

### Risk Manager Interface

**Protocol**: `RiskManagerInterface`

**Contract**:
- Reads: `state["data"]["portfolio_decisions"]`, `state["data"]["market_regime"]`
- Writes: `state["data"]["risk_budget"]`
- Risk budget format: `RiskBudgetData` contract

**Implementation**: Risk Manager must follow this protocol.

### Backtest Interface

**Protocol**: `BacktestInterface`

**Contract**:
- Reads: `portfolio_decisions`, `prices`, `portfolio` state
- Writes: `trades`, `daily_values`, `metrics`
- Must implement: `execute_trade()`, `calculate_portfolio_value()`

**Implementation**: Backtesting Engine must follow this protocol.

## Validation Middleware

### Agent Output Validation

**Function**: `validate_agent_output(agent_name, output)`

**Validates**:
- Output has `data` key
- `analyst_signals` structure is correct
- Each signal matches `AgentSignal` contract

**Error Handling**:
- Raises `InvalidSignalError` if validation fails
- Logs errors for debugging

### Portfolio Manager Output Validation

**Function**: `validate_portfolio_manager_output(output)`

**Validates**:
- Output has `data` key
- `portfolio_decisions` structure is correct
- Each decision matches `PortfolioDecision` contract

**Error Handling**:
- Raises `InvalidDecisionError` if validation fails
- Logs errors for debugging

### Safe Agent Call

**Function**: `safe_agent_call(agent_func, state, agent_id)`

**Features**:
- Validates input state
- Calls agent function
- Validates output
- Handles errors gracefully
- Returns state unchanged on error

**Usage**: Wrap agent calls with this for safe execution.

## Data Flow

### Standard Flow

```
1. Agents → state["data"]["analyst_signals"]
   └─> Format: {agent_name: {ticker: AgentSignal}}

2. Portfolio Manager → state["data"]["portfolio_decisions"]
   └─> Format: {ticker: PortfolioDecision}
   └─> Reads: analyst_signals

3. Risk Manager → state["data"]["risk_budget"]
   └─> Format: {ticker: RiskBudgetData}
   └─> Reads: portfolio_decisions, market_regime

4. Portfolio Allocator → Final decisions
   └─> Reads: portfolio_decisions, risk_budget
   └─> Applies constraints

5. Backtesting Engine → Executes trades
   └─> Reads: portfolio_decisions, prices
   └─> Writes: trades, daily_values, metrics
```

## Error Handling

### Communication Errors

**Types**:
- `CommunicationError`: Base exception
- `InvalidSignalError`: Agent signal doesn't match contract
- `InvalidDecisionError`: Portfolio decision doesn't match contract

**Handling**:
- Logged for debugging
- State unchanged on error
- Backtest continues (graceful degradation)

### Validation Failures

**When validation fails**:
1. Error is logged
2. Invalid data is skipped
3. System continues with valid data
4. No silent failures

## Benefits

### 1. Type Safety
- Pydantic models ensure correct data types
- TypedDicts provide structure validation
- Type hints improve IDE support

### 2. Clear Contracts
- Explicit interfaces between departments
- No ambiguity about data formats
- Easy to understand and maintain

### 3. Error Prevention
- Validation catches errors early
- Prevents invalid data from propagating
- Clear error messages

### 4. Documentation
- Contracts serve as documentation
- Clear examples of data formats
- Easy to understand communication flow

### 5. Maintainability
- Changes to contracts are explicit
- Easy to find all usages
- Clear upgrade path

## Usage Examples

### Agent Writing Signals

```python
from src.communication.contracts import AgentSignal

# Agent must produce signals in this format
signal = AgentSignal(
    signal="bullish",
    confidence=75,
    reasoning="Strong positive momentum"
)

# Write to state
state["data"]["analyst_signals"][agent_id][ticker] = signal.dict()
```

### Portfolio Manager Reading Signals

```python
from src.communication.contracts import validate_agent_signal

# Read signals
analyst_signals = state["data"]["analyst_signals"]

# Validate and use
for agent_name, ticker_signals in analyst_signals.items():
    for ticker, signal_data in ticker_signals.items():
        signal = validate_agent_signal(signal_data)
        # Use signal...
```

### Safe Agent Execution

```python
from src.communication.middleware import safe_agent_call

# Wrap agent call with validation
result = safe_agent_call(
    agent_func=momentum_agent,
    state=state,
    agent_id="momentum_agent"
)
```

## Migration Path

### Current State
- Agents write to `state["data"]["analyst_signals"]` (loose format)
- Portfolio Manager reads signals (no validation)
- No clear contracts

### Target State
- All agents use `AgentSignal` contract
- All validation enabled
- Clear error handling
- Type safety throughout

### Migration Steps
1. ✅ Contracts defined
2. ✅ Interfaces defined
3. ✅ Middleware created
4. ⏳ Update agents to use contracts (gradual)
5. ⏳ Enable validation (optional initially)
6. ⏳ Add type hints throughout

## Files Created

1. `src/communication/__init__.py` - Module exports
2. `src/communication/contracts.py` - Data contracts
3. `src/communication/interfaces.py` - Communication protocols
4. `src/communication/middleware.py` - Validation and error handling
5. `COMMUNICATION_FOUNDATION.md` - This documentation

## Next Steps

1. **Gradually adopt contracts** in existing agents
2. **Enable validation** in critical paths
3. **Add type hints** throughout codebase
4. **Document** department-specific communication patterns
5. **Test** validation with invalid data

## Notes

- Contracts are **optional initially** - system works without them
- Validation can be **enabled gradually** - start with critical paths
- **Backward compatible** - existing code continues to work
- **No breaking changes** - contracts are additive
