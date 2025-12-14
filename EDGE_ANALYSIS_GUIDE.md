# Edge Detection Analysis Guide

## Question: "Does my system have repeatable edge after costs, or is it just noise?"

This guide explains how to use the edge detection analysis to answer this critical question.

## What is Edge Detection?

Edge detection determines whether your trading system's performance is:
1. **Statistically Significant** - Not just random luck
2. **Profitable After Costs** - Transaction costs don't eat all profits
3. **Robust** - Results hold up under bootstrap resampling
4. **Risk-Adjusted** - Good Sharpe ratio (risk-adjusted returns)

## Running Edge Analysis

### Automatic (Default)

Edge analysis runs automatically after every backtest:

```bash
HEDGEFUND_NO_LLM=1 poetry run python src/backtesting/deterministic_backtest.py \
  --tickers AAPL,MSFT \
  --start-date 2024-01-02 \
  --end-date 2024-02-29 \
  --initial-capital 100000
```

### Skip Edge Analysis

If you want to skip edge analysis:

```bash
HEDGEFUND_NO_LLM=1 poetry run python src/backtesting/deterministic_backtest.py \
  --tickers AAPL,MSFT \
  --start-date 2024-01-02 \
  --end-date 2024-02-29 \
  --initial-capital 100000 \
  --no-edge-analysis
```

## Understanding the Metrics

### 1. Edge Assessment

**Has Edge: ✓ YES / ✗ NO**
- **YES**: System shows statistically significant, profitable performance
- **NO**: Results likely due to random chance

**Edge Strength: STRONG / MODERATE / WEAK / NONE**
- **STRONG**: Sharpe > 2.0, highly significant
- **MODERATE**: Sharpe > 1.0, significant
- **WEAK**: Sharpe > 0.5, barely significant
- **NONE**: No detectable edge

### 2. Sharpe Ratio

**What it measures**: Risk-adjusted returns

**Interpretation**:
- **> 2.0**: Excellent (top hedge funds)
- **> 1.0**: Good (professional level)
- **> 0.5**: Acceptable (beats market)
- **< 0.5**: Poor (not worth the risk)

**Formula**: (Annual Return - Risk-Free Rate) / Annual Volatility

### 3. Statistical Significance

**P-Value**: Probability that results are due to random chance
- **< 0.05**: Significant (5% chance it's random)
- **< 0.01**: Highly significant (1% chance it's random)
- **> 0.05**: Not significant (likely random)

**T-Statistic**: How many standard deviations from zero
- **> 2.0**: Significant
- **> 3.0**: Highly significant

### 4. Transaction Costs

**Components**:
- **Commission**: $0.01 per share (typical retail)
- **Slippage**: 5 basis points (0.05%) per trade
- **Bid-Ask Spread**: 3 basis points (0.03%) for liquid stocks

**Impact**: Costs reduce returns. System must be profitable AFTER costs.

### 5. Bootstrap Analysis

**What it does**: Resamples returns 1000 times to test robustness

**P(Sharpe > 0)**: Probability that Sharpe ratio is positive
- **> 80%**: Robust
- **> 50%**: Somewhat robust
- **< 50%**: Not robust (results may be fluke)

### 6. Information Ratio (if benchmark available)

**What it measures**: Alpha vs benchmark (e.g., SPY)

**Interpretation**:
- **> 1.0**: Excellent alpha
- **> 0.5**: Good alpha
- **< 0.5**: Poor alpha

## Example Output

```
EDGE DETECTION ANALYSIS
================================================================================

Question: Does this system have repeatable edge after costs, or is it just noise?

--------------------------------------------------------------------------------
EDGE ASSESSMENT
--------------------------------------------------------------------------------
Has Edge: ✓ YES
Edge Strength: MODERATE

RISK-ADJUSTED RETURNS (Sharpe Ratio)
--------------------------------------------------------------------------------
Sharpe Ratio: 1.45
  Interpretation: Good (>1)
Annual Return: 12.34%
Annual Volatility: 8.52%
Excess Return (vs Risk-Free): 7.90%

STATISTICAL SIGNIFICANCE
--------------------------------------------------------------------------------
Significant (p < 0.05): ✓ YES
P-Value: 0.0234
T-Statistic: 2.34
95% Confidence Interval: [2.15%, 22.53%]
Mean Annual Return: 12.34%

TRANSACTION COSTS
--------------------------------------------------------------------------------
Total Cost: $1,234.56
Cost as % of Capital: 1.23%
Cost per Trade: $12.35
  Commission: $456.78
  Slippage: $567.89
  Bid-Ask Spread: $209.89

RETURNS AFTER COSTS
--------------------------------------------------------------------------------
Before Cost Return: 12.34%
After Cost Return: 11.11%
Cost Impact: -1.23%

BOOTSTRAP ROBUSTNESS TEST
--------------------------------------------------------------------------------
Bootstrap Sharpe Mean: 1.42
Bootstrap Sharpe Std: 0.15
95% Confidence Interval: [1.12, 1.72]
P(Sharpe > 0): 95.2%

================================================================================
VERDICT
================================================================================
✓ SYSTEM HAS DETECTABLE EDGE
  Edge Strength: MODERATE
  Sharpe Ratio: 1.45 (Good)
  Statistically Significant: Yes
  Profitable After Costs: Yes
================================================================================
```

## What to Look For

### ✓ Good Signs (Has Edge)

1. **Sharpe Ratio > 1.0**
2. **P-Value < 0.05** (statistically significant)
3. **After-cost return > 0%**
4. **Bootstrap P(Sharpe > 0) > 80%**
5. **Information Ratio > 0.5** (if benchmark available)

### ✗ Bad Signs (No Edge)

1. **Sharpe Ratio < 0.5**
2. **P-Value > 0.05** (not significant)
3. **After-cost return < 0%**
4. **Bootstrap P(Sharpe > 0) < 50%**
5. **High transaction costs** eating profits

## Common Issues

### 1. "Not Statistically Significant"

**Problem**: P-value > 0.05 means results could be random.

**Solutions**:
- Test over longer time period (more data points)
- Reduce noise (improve signal quality)
- Increase sample size (more trades)

### 2. "Not Profitable After Costs"

**Problem**: Transaction costs exceed returns.

**Solutions**:
- Reduce trading frequency
- Focus on higher-conviction trades
- Negotiate better commission rates
- Trade more liquid stocks (lower spread)

### 3. "Low Bootstrap Confidence"

**Problem**: Results not robust (may be fluke).

**Solutions**:
- Test over multiple time periods
- Use out-of-sample validation
- Reduce overfitting
- Increase sample size

## Next Steps

1. **If Has Edge**: 
   - Scale up carefully
   - Monitor performance
   - Consider live trading (paper trade first)

2. **If No Edge**:
   - Review strategy logic
   - Test different parameters
   - Consider different markets/timeframes
   - Improve signal quality

## Dependencies

Edge analysis requires:
- `numpy` (for calculations)
- `pandas` (for data handling)
- `scipy` (for statistical tests) - optional, has fallback

Install with:
```bash
poetry add scipy
```

## References

- **Sharpe Ratio**: Risk-adjusted return metric
- **Bootstrap Analysis**: Resampling technique for robustness
- **T-Test**: Statistical significance test
- **Information Ratio**: Alpha vs benchmark metric
