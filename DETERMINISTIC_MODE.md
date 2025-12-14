# Deterministic Non-LLM Execution Mode

## Overview

This implementation adds a deterministic, rule-based execution mode that bypasses all LLM calls when the `HEDGEFUND_NO_LLM` environment variable is set. This mode is useful for:
- Testing and debugging without API costs
- Reproducible results
- CI/CD pipelines
- Environments without LLM API access

## How to Enable

Set the environment variable before running:

```bash
# Bash/Zsh
export HEDGEFUND_NO_LLM=1
poetry run python src/main.py --ticker AAPL --analysts warren_buffett

# Or inline
HEDGEFUND_NO_LLM=1 poetry run python src/main.py --ticker AAPL --analysts warren_buffett

# Windows CMD
set HEDGEFUND_NO_LLM=1
poetry run python src/main.py --ticker AAPL --analysts warren_buffett

# Windows PowerShell
$env:HEDGEFUND_NO_LLM=1
poetry run python src/main.py --ticker AAPL --analysts warren_buffett
```

Accepted values: `1`, `true`, `yes` (case-insensitive)

## Implementation Details

### 1. Core LLM Wrapper (`src/utils/llm.py`)

**Changes:**
- Added `rule_based_factory` parameter to `call_llm()`
- Early return when `HEDGEFUND_NO_LLM` is set
- Falls back to `default_factory` if `rule_based_factory` not provided

**Control Flow:**
```
call_llm() called
    ↓
Check HEDGEFUND_NO_LLM env var
    ↓
If set:
    ├─ Use rule_based_factory if provided
    ├─ Else use default_factory if provided
    └─ Else use create_default_response()
If not set:
    └─ Continue with normal LLM call
```

### 2. Warren Buffett Agent (`src/agents/warren_buffett.py`)

**New Function:** `generate_buffett_output_rule_based()`

**Rule-Based Logic:**
- **Bullish (85% confidence)**: Score ratio > 70% AND margin of safety > 20%
- **Bullish (70% confidence)**: Score ratio > 60% AND margin of safety > 0%
- **Bearish (60% confidence)**: Score ratio < 40% OR margin of safety < -20%
- **Neutral (50% confidence)**: All other cases

**Score Calculation:**
- `score_ratio = score / max_score`
- Uses fundamental analysis, moat, management, pricing power, book value scores
- Margin of safety = (intrinsic_value - market_cap) / market_cap

**Example Output:**
```python
WarrenBuffettSignal(
    signal="bullish",
    confidence=85,
    reasoning="Strong business (score 75%) with 25% margin of safety"
)
```

### 3. Portfolio Manager (`src/agents/portfolio_manager.py`)

**New Function:** `generate_trading_decision_rule_based()`

**Rule-Based Logic:**
1. **Aggregate Signals**:
   - Count bullish, bearish, neutral signals per ticker
   - Calculate average confidence

2. **Decision Rules**:
   - **Buy**: More bullish signals AND "buy" in allowed actions
   - **Sell**: More bearish signals AND "sell" in allowed actions (has long position)
   - **Short**: More bearish signals AND "short" in allowed actions (no long position)
   - **Hold**: Mixed signals OR no valid action available

3. **Quantity Calculation**:
   - Uses `min(allowed_action_qty, max_shares)` to respect constraints
   - Respects portfolio cash and margin limits

**Example Output:**
```python
PortfolioDecision(
    action="buy",
    quantity=10,
    confidence=75,
    reasoning="Bullish consensus (3 bullish, 1 bearish)"
)
```

## Code Changes Summary

### File: `src/utils/llm.py`

**Line ~10**: Added `rule_based_factory` parameter
```python
def call_llm(
    ...
    rule_based_factory=None,
) -> BaseModel:
```

**Lines ~30-45**: Added deterministic mode check
```python
# Check for deterministic mode
if os.getenv("HEDGEFUND_NO_LLM", "").lower() in ("1", "true", "yes"):
    if rule_based_factory:
        ...
        return rule_based_factory()
    ...
```

### File: `src/agents/warren_buffett.py`

**Lines ~746-790**: Added `generate_buffett_output_rule_based()` function

**Line ~826**: Modified `call_llm()` call to include `rule_based_factory`
```python
return call_llm(
    ...
    rule_based_factory=create_rule_based_warren_buffett_signal,
)
```

### File: `src/agents/portfolio_manager.py`

**Lines ~177-250**: Added `generate_trading_decision_rule_based()` function

**Line ~256**: Modified `call_llm()` call to include `rule_based_factory`
```python
llm_out = call_llm(
    ...
    rule_based_factory=create_rule_based_portfolio_output,
)
```

## Behavior Guarantees

### ✅ Preserved Behavior

- **AgentState structure**: Unchanged
- **Normal mode**: Works exactly as before when `HEDGEFUND_NO_LLM` is not set
- **Error handling**: Falls back to defaults if rule-based factory fails
- **Progress tracking**: Shows "Using rule-based logic (NO_LLM mode)" status

### ✅ Deterministic Outputs

- Same inputs → Same outputs (no randomness)
- No API calls made
- No external dependencies
- Fast execution (< 1ms per decision)

### ✅ Backward Compatibility

- Existing code continues to work
- No breaking changes to function signatures (new parameter is optional)
- Default behavior unchanged

## Testing

### Test 1: Enable Deterministic Mode

```bash
export HEDGEFUND_NO_LLM=1
poetry run python src/main.py --ticker AAPL --analysts warren_buffett --model gpt-4.1
```

**Expected**: 
- No LLM API calls
- Rule-based signals generated
- Progress shows "Using rule-based logic (NO_LLM mode)"

### Test 2: Disable Deterministic Mode

```bash
unset HEDGEFUND_NO_LLM
poetry run python src/main.py --ticker AAPL --analysts warren_buffett --model gpt-4.1
```

**Expected**:
- Normal LLM calls made
- LLM-generated signals
- Progress shows normal agent status

### Test 3: Verify Deterministic Outputs

```bash
export HEDGEFUND_NO_LLM=1
poetry run python src/main.py --ticker AAPL --analysts warren_buffett --model gpt-4.1 > run1.txt
poetry run python src/main.py --ticker AAPL --analysts warren_buffett --model gpt-4.1 > run2.txt
diff run1.txt run2.txt
```

**Expected**: No differences (identical outputs)

## Extension Points

### Adding Rule-Based Logic to Other Agents

1. Create rule-based function:
```python
def generate_agent_output_rule_based(ticker: str, analysis_data: dict) -> AgentSignal:
    # Your deterministic logic here
    return AgentSignal(...)
```

2. Add factory in agent's `call_llm()`:
```python
def create_rule_based_agent_signal():
    return generate_agent_output_rule_based(ticker, analysis_data)

return call_llm(
    ...
    rule_based_factory=create_rule_based_agent_signal,
)
```

## Limitations

1. **Only Warren Buffett and Portfolio Manager**: Other agents still use LLM or defaults
2. **Simplified Logic**: Rule-based decisions are simpler than LLM reasoning
3. **No Context Awareness**: Doesn't consider market conditions, news, etc.

## Future Enhancements

- Add rule-based logic for all agents
- Configurable rule parameters
- Rule-based backtesting mode
- Rule validation and testing framework

