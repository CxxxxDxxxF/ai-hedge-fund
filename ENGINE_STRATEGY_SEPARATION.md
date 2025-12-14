# Engine vs Strategy Separation: Formal Contract

## Principle

**A bad strategy cannot corrupt the engine.**

**Engine correctness can be validated without any strategy logic.**

## Separation Boundaries

### Engine Responsibilities (Must Never Fail)

1. **Loop Advancement**
   - Explicit index tracking
   - Duplicate date prevention
   - Guaranteed iteration

2. **State Management**
   - Portfolio state consistency
   - Date tracking
   - Snapshot creation

3. **Invariant Logging**
   - One line per iteration
   - Always to stderr
   - Always flushed

4. **Determinism Enforcement**
   - RNG seeding
   - Output hashing
   - Verification

5. **Failure Handling**
   - Engine failure detection
   - Strategy failure isolation
   - Guaranteed summary

### Strategy Responsibilities (Can Fail Safely)

1. **Signal Generation**
   - Agent logic
   - Data analysis
   - Decision making

2. **Trade Execution**
   - Position management
   - PnL calculation
   - Risk checks

3. **Data Processing**
   - Price fetching
   - Metric calculation
   - Regime analysis

## Interface Contract

### Engine → Strategy Interface

**Narrow Interface**:
```python
def _run_daily_decision(self, date: str, index: int) -> Tuple[bool, int]:
    """
    Engine calls strategy for one day.
    
    Returns:
        (is_engine_failure, agent_count)
    
    Contract:
    - If strategy raises RuntimeError("ENGINE FAILURE: ..."), engine aborts
    - If strategy raises other exceptions, engine continues (strategy failure)
    - Engine always records daily value, even on strategy failure
    """
```

**What Engine Provides**:
- Date (string)
- Index (int)
- Portfolio state (copy, not reference)

**What Engine Expects**:
- Boolean: is_engine_failure
- Integer: agent_count (for logging)

### Strategy → Engine Interface

**No Direct Engine Access**:
- Strategy cannot modify `processed_dates`
- Strategy cannot modify `iteration_log`
- Strategy cannot skip invariant logging
- Strategy cannot bypass determinism

**Strategy Can**:
- Read portfolio state (copy)
- Return decisions
- Raise exceptions (handled by engine)

## Shared Mutable State: FORBIDDEN

**Current State** (needs improvement):
- `self.portfolio` is modified by strategy via `_execute_trade()`
- This couples engine and strategy

**Future Improvement**:
- Strategy returns decisions
- Engine applies decisions atomically
- No shared mutable state

## Validation Without Strategy

The engine can be validated by:
1. **Reference Loop**: `reference_loop.py` shows engine pattern without strategy
2. **Mock Strategy**: Strategy that always returns neutral decisions
3. **Determinism Test**: Two runs with same inputs must produce same hashes

## Failure Isolation

**Strategy Failure**:
```python
try:
    result = run_hedge_fund(...)  # Strategy call
except Exception as e:
    # Strategy failed - log and continue
    print(f"STRATEGY FAILURE: {e}", file=sys.stderr)
    # Engine continues, records partial day
```

**Engine Failure**:
```python
if date in self.processed_dates:
    # Engine contract violated - abort
    raise RuntimeError("ENGINE FAILURE: Duplicate date")
```

## Current Coupling Points

1. **Portfolio Mutation**: `_execute_trade()` modifies `self.portfolio`
   - **Risk**: Strategy can corrupt engine state
   - **Mitigation**: Engine validates trades before execution

2. **Date Tracking**: Strategy doesn't directly track dates
   - **Safe**: Engine controls this

3. **Invariant Logging**: Strategy doesn't control logging
   - **Safe**: Engine always logs

## Future Decoupling

**Ideal Interface**:
```python
# Strategy returns decisions (immutable)
decisions = strategy.generate_decisions(date, portfolio_copy)

# Engine applies decisions (atomic)
engine.apply_decisions(decisions)

# No shared mutable state
```

This would make engine correctness provable without strategy logic.
