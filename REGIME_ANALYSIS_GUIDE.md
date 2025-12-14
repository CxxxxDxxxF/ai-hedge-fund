# Regime Analysis Guide

## Question: "Where does this system consistently behave differently from random?"

This guide explains how to identify specific conditions, patterns, and regimes where your trading system shows consistent, non-random behavior.

## What is Regime Analysis?

Regime analysis identifies **where** your system has edge, not just **if** it has edge. It answers:

1. **Which market regimes show edge?** (trending, mean-reverting, volatile, calm)
2. **Which agent combinations work best?** (which signals together predict success)
3. **Which ticker characteristics matter?** (which stocks show consistent edge)
4. **What time periods show consistent performance?** (when does the system work)
5. **What signal patterns predict success?** (high confidence, consensus, etc.)

## Running Regime Analysis

Regime analysis runs automatically after every backtest:

```bash
HEDGEFUND_NO_LLM=1 poetry run python src/backtesting/deterministic_backtest.py \
  --tickers AAPL,MSFT \
  --start-date 2024-01-02 \
  --end-date 2024-02-29 \
  --initial-capital 100000
```

The backtest output includes a **Regime Analysis** section showing where the system shows consistent edge.

## Understanding the Analysis

### 1. Performance by Market Regime

**What it shows**: How the system performs in different market conditions

**Regimes**:
- **Trending**: Strong directional movement (ADX > 25, high trend consistency)
- **Mean Reverting**: Weak trend, high RSI oscillation
- **Volatile**: High volatility (>15% of price)
- **Calm**: Low volatility (<5% of price)

**What to look for**:
- Regimes with **Sharpe > 1.0** and **Win Rate > 55%** show consistent edge
- If one regime significantly outperforms others, focus trading there

**Example**:
```
PERFORMANCE BY MARKET REGIME
+----------------+---------------+---------+-----------+---------+------+
| Regime         | Annual Return | Sharpe  | Win Rate  | Trades  | Days |
+================+===============+=========+===========+=========+======+
| trending       | 15.23%        | 1.45    | 58.2%     | 45      | 120  |
| mean_reverting | 8.12%         | 0.89    | 52.1%     | 32      | 95   |
| volatile       | -2.34%        | -0.15   | 48.3%     | 28      | 60   |
| calm           | 12.45%        | 1.23    | 56.8%     | 38      | 150  |
+----------------+---------------+---------+-----------+---------+------+
```

**Interpretation**: System shows edge in **trending** and **calm** regimes, but struggles in **volatile** markets.

### 2. Top Agent Combinations

**What it shows**: Which combinations of agent signals predict success

**What to look for**:
- Combinations with **Sharpe > 1.0** and **high occurrences** (>10)
- Patterns like "Value + Growth + Momentum" working together

**Example**:
```
TOP AGENT COMBINATIONS (by Sharpe Ratio)
+--------------------------------------------------+--------+-----------+-------------+
| Agent Combination                                | Sharpe | Win Rate  | Occurrences |
+==================================================+========+===========+=============+
| warren_buffett_agent:bullish|peter_lynch:bullish | 1.89   | 62.3%     | 23          |
| momentum_agent:bullish|mean_reversion:bearish    | 1.45   | 58.1%     | 18          |
| aswath_damodaran:bullish|warren_buffett:bullish  | 1.23   | 56.2%     | 15          |
+--------------------------------------------------+--------+-----------+-------------+
```

**Interpretation**: When **Value and Growth** both signal bullish, the system shows strong edge.

### 3. Signal Patterns That Predict Success

**What it shows**: Which signal characteristics (confidence, consensus) predict success

**Patterns analyzed**:
- **High confidence signals** (confidence >= 80)
- **Medium confidence signals** (confidence >= 60)
- **Low confidence signals** (confidence < 60)
- **Strong bullish consensus** (3+ agents bullish)
- **Strong bearish consensus** (3+ agents bearish)
- **Mixed signals** (balanced bullish/bearish)

**What to look for**:
- Patterns with **Sharpe > 0.5** and **high occurrences**
- High confidence signals should outperform low confidence

**Example**:
```
SIGNAL PATTERNS THAT PREDICT SUCCESS
+------------------------------+--------+-----------+------------------+-------------+
| Pattern                      | Sharpe | Win Rate  | Avg Daily Return | Occurrences |
+==============================+========+===========+==================+=============+
| high_confidence_bullish      | 1.34   | 59.2%     | 0.045%           | 42          |
| strong_bullish_consensus     | 1.12   | 57.8%     | 0.038%           | 28          |
| medium_confidence_bullish     | 0.89   | 54.3%     | 0.025%           | 65          |
| mixed_signals                | 0.12   | 51.2%     | 0.008%           | 38          |
+------------------------------+--------+-----------+------------------+-------------+
```

**Interpretation**: **High confidence bullish** signals and **strong consensus** show consistent edge.

### 4. Performance by Time Period

**What it shows**: Which time periods show consistent performance vs random periods

**What to look for**:
- Periods with **consistent positive returns** (not just one lucky period)
- Periods with **Sharpe > 1.0** across multiple windows
- If performance is random, periods will vary widely

**Example**:
```
PERFORMANCE BY TIME PERIOD (30-day windows)
+------------+------------+---------+--------+-----------+
| Start      | End        | Return  | Sharpe | Win Rate  |
+============+============+=========+========+===========+
| 2024-01-02 | 2024-02-01 | 3.45%   | 1.23   | 56.2%     |
| 2024-02-02 | 2024-03-03 | 2.12%   | 0.89   | 53.1%     |
| 2024-03-04 | 2024-04-03 | -1.23%  | -0.45  | 48.2%     |
| 2024-04-04 | 2024-05-04 | 4.56%   | 1.67   | 61.3%     |
+------------+------------+---------+--------+-----------+
```

**Interpretation**: System shows consistent edge in 3 of 4 periods, suggesting non-random behavior.

### 5. Consistent Patterns Summary

**What it shows**: Summary of all patterns where system shows edge

**Criteria for "consistent pattern"**:
- Sharpe > 1.0
- Win Rate > 55%
- Sufficient occurrences (>5)

**Example**:
```
CONSISTENT PATTERNS (Where system shows edge)
================================================================================

MARKET_REGIME: trending
  Sharpe: 1.45
  Win Rate: 58.2%

AGENT_COMBINATION: warren_buffett_agent:bullish|peter_lynch:bullish
  Sharpe: 1.89
  Win Rate: 62.3%

SIGNAL_PATTERN: high_confidence_bullish
  Sharpe: 1.34
  Win Rate: 59.2%
```

## How to Use This Information

### 1. Focus Trading on High-Edge Regimes

If **trending** markets show Sharpe 1.45 but **volatile** markets show Sharpe -0.15:
- **Increase exposure** in trending markets
- **Reduce exposure** or **skip trading** in volatile markets
- Use market regime agent to identify current regime

### 2. Weight Agent Combinations

If **Value + Growth** consensus shows Sharpe 1.89:
- **Increase position size** when both signal bullish
- **Reduce position size** when signals disagree
- Consider adding explicit combination logic to Portfolio Manager

### 3. Filter by Signal Quality

If **high confidence** signals show Sharpe 1.34 but **low confidence** shows 0.45:
- **Only trade** when confidence >= 80
- **Skip trades** when confidence < 60
- Use confidence as position sizing factor

### 4. Time Period Insights

If system shows consistent edge in **Q1 and Q4** but struggles in **Q2 and Q3**:
- **Increase capital allocation** in strong periods
- **Reduce allocation** or **hedge** in weak periods
- Investigate why (earnings season, market cycles, etc.)

## Common Findings

### ✓ Good Signs (Consistent Edge)

1. **One regime significantly outperforms** (Sharpe > 1.5 vs others < 0.5)
2. **Specific agent combinations work** (Sharpe > 1.0, occurrences > 10)
3. **High confidence signals outperform** (Sharpe difference > 0.5)
4. **Consistent across time periods** (3+ periods with Sharpe > 1.0)

### ✗ Bad Signs (Random Behavior)

1. **No regime outperforms** (all Sharpe < 0.5)
2. **No agent combinations work** (all Sharpe < 0.5)
3. **High confidence = low confidence** (no difference)
4. **Random time periods** (wide variance, no consistency)

## Next Steps

1. **If patterns found**: 
   - Implement regime-based position sizing
   - Add agent combination filters
   - Use signal quality thresholds

2. **If no patterns found**:
   - System may be random
   - Consider longer backtest period
   - Review strategy logic
   - Test different parameters

## Integration with Edge Analysis

Regime analysis complements edge analysis:
- **Edge Analysis**: "Does the system have edge?" (overall)
- **Regime Analysis**: "Where does the system have edge?" (specific conditions)

Use both together to:
1. Confirm overall edge exists (Edge Analysis)
2. Identify where to focus trading (Regime Analysis)
3. Optimize position sizing and filters (Regime Analysis)
