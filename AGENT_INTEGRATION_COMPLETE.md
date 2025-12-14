# New Strategy Agents - Integration Complete

## Status: ✅ Integrated and Ready for Testing

All five new strategy agents have been integrated into the system and are ready for isolated testing.

## Integration Steps Completed

### 1. ✅ Agents Added to `ANALYST_CONFIG`

All five agents are now registered in `src/utils/analysts.py`:

- **cross_sectional_momentum** (Order: 8, Weight: 0.05)
- **mean_reversion_volatility_gated** (Order: 9, Weight: 0.05)
- **market_neutral_ls** (Order: 10, Weight: 0.05)
- **regime_trend_following** (Order: 11, Weight: 0.05)
- **capital_preservation** (Order: 12, Weight: 0.05)

**Note**: All new agents are marked as `experimental: True` and have low initial weights (5%) until tested.

### 2. ✅ Portfolio Manager Updated

The Portfolio Manager now includes experimental agents if they have weights defined in `ANALYST_CONFIG`. This allows the new agents to participate in signal aggregation when selected.

**Location**: `src/agents/portfolio_manager.py`

### 3. ✅ Test Script Created

Created `test_new_agents.sh` to test all new agents in isolation.

## Testing the New Agents

### Option 1: Test All Agents (Automated)

```bash
cd ai-hedge-fund
./test_new_agents.sh
```

This will run isolated backtests for all five new agents sequentially.

### Option 2: Test Individual Agent

```bash
cd ai-hedge-fund

# Test cross-sectional momentum
HEDGEFUND_NO_LLM=1 poetry run python src/backtesting/isolated_agent_backtest.py \
    --agent cross_sectional_momentum \
    --tickers AAPL,MSFT \
    --start-date 2020-01-02 \
    --end-date 2024-12-30 \
    --initial-capital 100000

# Test mean reversion with volatility gating
HEDGEFUND_NO_LLM=1 poetry run python src/backtesting/isolated_agent_backtest.py \
    --agent mean_reversion_volatility_gated \
    --tickers AAPL,MSFT \
    --start-date 2020-01-02 \
    --end-date 2024-12-30 \
    --initial-capital 100000

# Test market-neutral long/short
HEDGEFUND_NO_LLM=1 poetry run python src/backtesting/isolated_agent_backtest.py \
    --agent market_neutral_ls \
    --tickers AAPL,MSFT,GOOGL,TSLA,NVDA \
    --start-date 2020-01-02 \
    --end-date 2024-12-30 \
    --initial-capital 100000

# Test regime-conditional trend following
HEDGEFUND_NO_LLM=1 poetry run python src/backtesting/isolated_agent_backtest.py \
    --agent regime_trend_following \
    --tickers AAPL,MSFT \
    --start-date 2020-01-02 \
    --end-date 2024-12-30 \
    --initial-capital 100000

# Test capital preservation
HEDGEFUND_NO_LLM=1 poetry run python src/backtesting/isolated_agent_backtest.py \
    --agent capital_preservation \
    --tickers AAPL,MSFT \
    --start-date 2020-01-02 \
    --end-date 2024-12-30 \
    --initial-capital 100000
```

### Option 3: Include in Main Workflow

To include new agents in the main hedge fund workflow:

```python
# In your code or CLI
selected_analysts = [
    "warren_buffett",
    "peter_lynch",
    "aswath_damodaran",
    "momentum",
    "mean_reversion",
    "cross_sectional_momentum",  # Add new agent
    "market_regime",  # Required for regime_trend_following
    "performance_auditor",
]
```

## Agent Details

### 1. Cross-Sectional Momentum
- **Best for**: Multi-ticker universes (needs 2+ tickers)
- **Strategy**: Ranks tickers by performance, longs top, shorts bottom
- **Minimum tickers**: 2

### 2. Mean Reversion (Volatility Gated)
- **Best for**: Low volatility environments
- **Strategy**: Mean reversion only when volatility ≤ 30%
- **Minimum tickers**: 1

### 3. Market-Neutral Long/Short
- **Best for**: Market-neutral strategies
- **Strategy**: Dollar-neutral pairs (long top half, short bottom half)
- **Minimum tickers**: 2 (better with 5+)

### 4. Regime-Conditional Trend Following
- **Best for**: Trending markets
- **Strategy**: Trend following adjusted by market regime
- **Requires**: Market Regime Analyst (automatically included)
- **Minimum tickers**: 1

### 5. Capital Preservation
- **Best for**: Risk management and drawdown control
- **Strategy**: Reduces positions during drawdowns, exits when severe
- **Minimum tickers**: 1

## Next Steps

1. **Run isolated tests** for each agent to verify they work correctly
2. **Evaluate performance** against buy-and-hold benchmark
3. **Adjust weights** in `ANALYST_CONFIG` based on test results
4. **Remove experimental flag** once validated
5. **Integrate into main workflow** if performance is acceptable

## Notes

- All agents are **deterministic** (work with `HEDGEFUND_NO_LLM=1`)
- All agents use **price data only** (no external APIs)
- All agents follow **standard signal format**
- Agents can be **combined** with existing agents in Portfolio Manager
- **Regime-conditional trend following** requires Market Regime Analyst (automatically included in workflow)

## Files Modified

1. `src/utils/analysts.py` - Added 5 new agents to ANALYST_CONFIG
2. `src/agents/portfolio_manager.py` - Updated to include experimental agents
3. `test_new_agents.sh` - Created test script

## Files Created

1. `src/agents/cross_sectional_momentum.py`
2. `src/agents/mean_reversion_volatility_gated.py`
3. `src/agents/market_neutral_ls.py`
4. `src/agents/regime_trend_following.py`
5. `src/agents/capital_preservation.py`
6. `NEW_STRATEGY_AGENTS.md` - Documentation
7. `AGENT_INTEGRATION_COMPLETE.md` - This file
