# Topstep-Optimized Single Setup Strategy

## Overview

This strategy implements a Topstep-optimized trading system designed for **survival first, not profit maximization**. The core philosophy is:

> **You are not trading to make money. You are trading to not violate rules until you pass.**

If the system:
- Skips 70–90% of days
- Takes 1 trade max per day
- Exits early
- Feels boring

**That's correct.**

## Strategy Details

### Instrument & Session
- **Market**: ES (E-mini S&P 500) or NQ (E-mini NASDAQ-100) - pick one, not both
- **Session**: NY Open only
- **Time Window**: 9:30–10:30 ET
- **Outside this window**: NO TRADING

### Market Regime Filter (Non-Negotiable)

Before looking for a trade, the system checks:

1. **Opening Range Break & Hold**: First 15 minutes (9:30-9:45) must break and hold
2. **ATR Filter**: ATR(14) on 5-min must be above its 20-day median
3. **Economic Releases**: No major economic release in next 30 min (simplified in implementation)

**If any fail → FLAT DAY**

### The ONE Setup: Opening Range Break + Pullback Continuation

#### 1. Define the Opening Range
- Use 9:30–9:45 (first 15 minutes)
- Mark: OR High and OR Low
- No trades before 9:45

#### 2. Break & Acceptance
- Price must break OR High (for long) or OR Low (for short)
- Close a 5-min candle outside the range
- **Wicks do NOT count**

#### 3. Pullback Entry (Key)
- After the break: Wait for price to pull back 50–70% of breakout candle
- Enter ONLY on:
  - Bullish/bearish engulfing
  - OR strong close in direction of trend
- **No pullback → no trade**

### Risk Rules (Topstep-Safe)

#### Position Sizing
- Risk ≤ 0.25% of account per trade
- 1 contract micros preferred (MES / MNQ) until funded

#### Stop Loss
- Fixed stop behind pullback low/high
- Hard stop only. No mental stops.

#### Take Profit
- 1.5R max
- Partial at 1R (optional)
- Never trail aggressively

**You are not swinging. You are extracting permission to survive.**

### Daily Limits

- **Max trades per day**: 1
- **Max loss per day**: 0.5R
- **Max wins per day**: 1 (stop after win)

**This feels restrictive. That's why it works.**

## Implementation

### Files

- **Strategy Implementation**: `src/agents/topstep_strategy.py`
- **Integration**: `src/backtesting/deterministic_backtest.py`

### Usage

The strategy is automatically activated when running a backtest with ES or NQ tickers:

```python
from src.backtesting.deterministic_backtest import DeterministicBacktest

backtest = DeterministicBacktest(
    tickers=["ES"],  # or ["NQ"]
    start_date="2024-01-01",
    end_date="2024-12-31",
    initial_capital=100000.0,
)

metrics = backtest.run()
```

### Strategy Behavior

The strategy will:
1. **Refuse to trade** on most days (70-90% of days)
2. **Take maximum 1 trade per day** when setup is valid
3. **Enforce strict risk management** (0.25% risk, 1.5R max)
4. **Stop trading after a win** for the day
5. **Stop trading after 0.5R loss** for the day

### Expected Performance

**This setup will not look impressive in hedge-fund metrics. That is a feature, not a bug.**

The strategy is designed for:
- **Trailing drawdown stays far away**
- **No overtrading**
- **Small, capped losses**
- **Winners when volatility expands**
- **Survival through bad weeks**

## Technical Notes

### Daily Data Limitation

The current implementation works with **daily OHLC data** and simulates intraday logic:
- Opening Range is approximated using the first 25% of the day's range
- Breakout detection uses daily candle closes
- Pullback detection uses daily candle patterns

For production use with actual Topstep accounts, you would need:
- **5-minute intraday data** for accurate OR identification
- **Real-time price feeds** for entry/exit execution
- **Economic calendar integration** for release filtering

### Position Management

The strategy tracks:
- Daily trade count (max 1)
- Daily P&L in R units (max -0.5R loss, stop after +1R win)
- Current position state (entry, stop, target)

### Market Regime Filter

The ATR filter ensures the strategy only trades when:
- Current ATR(14) > 20-day median ATR
- This filters out low-volatility, choppy days
- Reduces false breakouts and whipsaws

## Why This Works for Topstep

1. **Trailing drawdown stays far away**: Small, controlled risk per trade
2. **No overtrading**: 1 trade max per day prevents revenge trading
3. **Losses are small and capped**: 0.5R max daily loss prevents account blowups
4. **Winners happen when volatility expands**: ATR filter ensures quality setups
5. **You survive bad weeks**: Strict daily limits prevent emotional trading

## Configuration

To modify strategy parameters, edit `src/agents/topstep_strategy.py`:

```python
class TopstepStrategy:
    RISK_PERCENT = 0.0025  # 0.25% of account per trade
    MAX_RISK_REWARD = 1.5  # 1.5R max profit
    MAX_TRADES_PER_DAY = 1
    MAX_LOSS_PER_DAY_R = 0.5  # Max 0.5R loss per day
    ATR_PERIOD = 14
    ATR_LOOKBACK_DAYS = 20  # 20-day median for ATR filter
```

## Testing

To test the strategy:

```bash
# Run backtest with ES
python src/backtesting/deterministic_backtest_cli.py \
    --tickers ES \
    --start-date 2024-01-01 \
    --end-date 2024-12-31 \
    --initial-cash 100000
```

The strategy will automatically activate when ES or NQ tickers are detected.

## Notes

- The strategy is **deterministic** and works in backtesting mode
- It integrates seamlessly with the existing backtest infrastructure
- For live trading, you would need to add real-time data feeds and execution logic
- The strategy correctly refuses to trade on most days - this is expected behavior
