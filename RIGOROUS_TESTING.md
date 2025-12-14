# Rigorous Testing Framework

## Philosophy

**Honest testing. No self-deception.**

This framework tests agents in complete isolation before allowing any aggregation or optimization. If an agent can't survive alone, it's dead.

## The Three Steps

### Step 1: Isolate the Value Agent (NON-NEGOTIABLE)

**Rules:**
- ✅ Value agent (Warren Buffett) ONLY
- ❌ NO Momentum agent
- ❌ NO Mean Reversion agent
- ❌ NO Portfolio Manager aggregation
- ❌ NO fallback strategies
- ❌ NO averaging
- ❌ NO parameter tuning

**Execution:**
- Trades = Value signal only
- Direct signal-to-trade execution
- No aggregation logic
- No other agents involved

**If it can't survive alone, it's dead.**

### Step 2: Make it Falsifiable

**Test Configuration:**
- **Period**: 5-10 years
- **Tickers**: 20-50 liquid tickers
- **Rules**: Same throughout (no parameter changes)
- **Question**: Does this beat buy-and-hold after costs with lower drawdown?

**Criteria:**
- ✅ Beats buy-and-hold return
- ✅ Lower drawdown than buy-and-hold
- ✅ After transaction costs

**If NO, STOP. Do not proceed.**

### Step 3: Only if Step 2 Passes

**Then and only then:**
- Add regime filters
- Add confidence scaling
- Add a second agent
- Add portfolio manager aggregation

**Never before Step 2 passes.**

## What NOT to Do

⚠️ **DO NOT:**
- Tune thresholds
- Add agents prematurely
- Optimize Sharpe ratio
- Chase bootstrap confidence
- Re-run until green
- Change parameters mid-test

**That's how people fool themselves.**

## Usage

### Run Step 1 & 2 Test

```bash
./run_rigorous_test.sh
```

Or manually:

```bash
HEDGEFUND_NO_LLM=1 poetry run python src/backtesting/isolated_agent_backtest.py \
    --agent warren_buffett \
    --tickers AAPL,MSFT,GOOGL,TSLA,NVDA,AMZN,META,NFLX,AMD,INTC,ORCL,CRM,ADBE,CSCO,AVGO,QCOM,TXN \
    --start-date 2019-01-01 \
    --end-date 2024-12-31 \
    --initial-capital 100000
```

### Test Other Agents in Isolation

```bash
# Test Peter Lynch (Growth)
HEDGEFUND_NO_LLM=1 poetry run python src/backtesting/isolated_agent_backtest.py \
    --agent peter_lynch \
    --tickers AAPL,MSFT,GOOGL,TSLA,NVDA \
    --start-date 2019-01-01 \
    --end-date 2024-12-31 \
    --initial-capital 100000

# Test Damodaran (Valuation)
HEDGEFUND_NO_LLM=1 poetry run python src/backtesting/isolated_agent_backtest.py \
    --agent aswath_damodaran \
    --tickers AAPL,MSFT,GOOGL,TSLA,NVDA \
    --start-date 2019-01-01 \
    --end-date 2024-12-31 \
    --initial-capital 100000
```

## Output

The test will report:

1. **Performance Metrics:**
   - Total return
   - Buy-and-hold return
   - Excess return (strategy - buy-and-hold)
   - Max drawdown
   - Sharpe ratio

2. **Trading Metrics:**
   - Total trades
   - Transaction costs
   - Win rate

3. **Verdict:**
   - ✓ PASSES: Beats buy-and-hold with lower drawdown
   - ✗ FAILS: Does not beat buy-and-hold or has higher drawdown

## Interpretation

### If it PASSES:
- Agent has edge
- Proceed to Step 3
- Can add other agents/features

### If it FAILS:
- Agent has no edge
- **STOP**
- Do not tune parameters
- Do not add agents
- Do not optimize
- Accept the result

## Current System Status

Your system is currently **honest**. Keep it that way.

The isolated agent backtest:
- ✅ Tests agents in complete isolation
- ✅ No aggregation or optimization
- ✅ Direct signal execution
- ✅ Honest reporting
- ✅ Falsifiable results

## Example Test Results

```
================================================================================
ISOLATED AGENT BACKTEST - WARREN_BUFFETT
================================================================================
Agent: warren_buffett (ONLY - no aggregation, no other agents)
Period: 2019-01-01 to 2024-12-31
Tickers: AAPL, MSFT, GOOGL, TSLA, NVDA
Initial Capital: $100,000.00
Deterministic Seed: 42
================================================================================

Results:
  Total Return: +45.23%
  Buy-Hold Return: +38.12%
  Excess Return: +7.11%
  Max Drawdown: -18.45%
  Sharpe Ratio: 1.23
  Total Trades: 127
  Transaction Costs: $1,234.56 (1.23%)

VERDICT:
✓ PASSES: Beats buy-and-hold with lower drawdown
```

## Next Steps

1. **Run Step 1 & 2** for Value agent
2. **If passes**: Document results, proceed to Step 3
3. **If fails**: Document results, stop. Do not proceed.

**Remember: Honest testing is more valuable than optimistic results.**
