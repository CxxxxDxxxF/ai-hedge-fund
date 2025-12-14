# New Strategy Agents

## Overview

Five new trading strategy agents have been created to implement advanced quantitative strategies:

1. **Cross-Sectional Momentum** - Ranks stocks relative to each other
2. **Mean Reversion with Volatility Gating** - Enhanced mean reversion that only trades in low volatility
3. **Market-Neutral Long/Short** - Dollar-neutral pairs trading
4. **Regime-Conditional Trend Following** - Trend following adjusted by market regime
5. **Capital Preservation / Drawdown Minimization** - Focuses on protecting capital

## Agents Created

### 1. Cross-Sectional Momentum (`cross_sectional_momentum.py`)

**Strategy**: Ranks all tickers by 20-day return and generates signals based on relative performance.

**Key Features**:
- Calculates returns for all tickers
- Ranks tickers by performance
- Top 20%: Strong bullish (long)
- Bottom 20%: Strong bearish (short)
- Middle 60%: Neutral

**Signal Logic**:
- Percentile rank determines signal strength
- Top performers get bullish signals
- Bottom performers get bearish signals

**Usage**:
```python
from src.agents.cross_sectional_momentum import cross_sectional_momentum_agent
```

### 2. Mean Reversion with Volatility Gating (`mean_reversion_volatility_gated.py`)

**Strategy**: Enhanced mean reversion that only trades when volatility is low.

**Key Features**:
- Calculates 20-day annualized volatility
- Volatility threshold: 30%
- High volatility (>30%): Neutral (mean reversion less reliable)
- Low volatility (≤30%): Normal mean reversion signals

**Signal Logic**:
- Uses RSI, price deviations from MAs (same as standard mean reversion)
- But gates signals when volatility is high
- Only trades when volatility is below threshold

**Usage**:
```python
from src.agents.mean_reversion_volatility_gated import mean_reversion_volatility_gated_agent
```

### 3. Market-Neutral Long/Short (`market_neutral_ls.py`)

**Strategy**: Generates market-neutral pairs by ranking tickers and pairing top (long) with bottom (short).

**Key Features**:
- Calculates composite strength score (momentum + trend + volatility)
- Ranks all tickers by strength
- Top half: Bullish (long)
- Bottom half: Bearish (short)
- Maintains dollar-neutral exposure

**Signal Logic**:
- Strength score = (momentum × 60%) + (trend × 30%) + (volatility × 10%)
- Median rank splits longs and shorts
- Higher rank = stronger signal

**Usage**:
```python
from src.agents.market_neutral_ls import market_neutral_ls_agent
```

### 4. Regime-Conditional Trend Following (`regime_trend_following.py`)

**Strategy**: Trend following adjusted by market regime from Market Regime Analyst.

**Key Features**:
- Calculates trend strength (MA alignment + momentum)
- Adjusts signals based on market regime:
  - **Trending regime**: Strong trend following signals
  - **Mean-reverting regime**: Weak/no trend signals
  - **Volatile regime**: Reduced confidence
  - **Calm regime**: Normal trend following

**Signal Logic**:
- Trend strength = (MA alignment × 70%) + (momentum × 30%)
- Regime determines signal strength and confidence
- Only trades trends when regime is favorable

**Usage**:
```python
from src.agents.regime_trend_following import regime_trend_following_agent
```

### 5. Capital Preservation / Drawdown Minimization (`capital_preservation.py`)

**Strategy**: Focuses on protecting capital and minimizing drawdowns.

**Key Features**:
- Monitors portfolio drawdown
- Reduces position sizes when drawdown occurs
- Exits positions when drawdown exceeds threshold
- Prefers defensive positions during high volatility

**Signal Logic**:
- Drawdown thresholds:
  - Severe (>-15%): Exit all positions (multiplier = 0.0)
  - Moderate (>-8%): Reduce to 25% (multiplier = 0.25)
  - Mild (>-3%): Reduce to 50% (multiplier = 0.50)
- High volatility (>40%): Reduce positions even without drawdown
- Only trades strong, low-risk opportunities

**Usage**:
```python
from src.agents.capital_preservation import capital_preservation_agent
```

## Integration

These agents are **not yet registered** in `ANALYST_CONFIG`. To use them:

1. **Add to `src/utils/analysts.py`**:
```python
from src.agents.cross_sectional_momentum import cross_sectional_momentum_agent
from src.agents.mean_reversion_volatility_gated import mean_reversion_volatility_gated_agent
from src.agents.market_neutral_ls import market_neutral_ls_agent
from src.agents.regime_trend_following import regime_trend_following_agent
from src.agents.capital_preservation import capital_preservation_agent

# Add to ANALYST_CONFIG
ANALYST_CONFIG["cross_sectional_momentum"] = {
    "display_name": "Cross-Sectional Momentum",
    "description": "Ranks stocks relative to each other",
    "agent_func": cross_sectional_momentum_agent,
    # ...
}
```

2. **Update workflow** to include these agents

3. **Test in isolated backtests** before adding to main portfolio

## Testing

Each agent can be tested in isolation using the isolated agent backtest:

```bash
# Test cross-sectional momentum
HEDGEFUND_NO_LLM=1 poetry run python src/backtesting/isolated_agent_backtest.py \
    --agent cross_sectional_momentum \
    --tickers AAPL,MSFT,GOOGL,TSLA,NVDA \
    --start-date 2020-01-02 \
    --end-date 2024-12-30 \
    --initial-capital 100000
```

## Notes

- All agents are **deterministic** (rule-based) and work in `HEDGEFUND_NO_LLM=1` mode
- All agents use price data only (no external APIs required)
- All agents follow the same signal format: `{"signal": "bullish/bearish/neutral", "confidence": 0-100, "reasoning": "..."}`
- Agents can be combined with existing agents in the Portfolio Manager
