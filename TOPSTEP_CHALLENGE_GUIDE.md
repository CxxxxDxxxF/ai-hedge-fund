# Topstep Challenge Guide: Using This Strategy to Pass

## ✅ Yes, This Strategy Can Pass a Topstep Challenge

The strategy is designed specifically for Topstep's rules. Here's what you need to know:

## What's Already Built (Topstep-Compliant)

### ✅ Risk Management
- **0.25% risk per trade** (Topstep-safe, well below typical 1-2% limits)
- **1.5R max profit** (prevents overtrading)
- **Hard stops only** (no mental stops)
- **Fixed stop behind pullback** (mechanical, no discretion)

### ✅ Daily Limits
- **1 trade max per day** (prevents revenge trading)
- **0.5R max loss per day** (stops you before hitting daily loss limit)
- **Stop after win** (prevents giving back profits)

### ✅ Market Regime Filters
- **ATR filter** (only trades when volatility is expanding)
- **Opening range validation** (ensures clean setups)
- **Refuses to trade 70-90% of days** (survival first)

### ✅ Position Sizing
- **Micro contracts (MES/MNQ)** until funded
- **Risk-based sizing** (scales with account, not fixed)
- **Never exceeds 0.25% risk**

## What You Need to Add for Live Trading

### 1. Real-Time Data Feed
**Current**: Uses daily OHLC data (simulated intraday)
**Needed**: 5-minute intraday bars for accurate:
- Opening range identification (9:30-9:45)
- Breakout detection (real-time)
- Pullback entry (real-time)

**Options**:
- Interactive Brokers API
- Alpaca API
- Polygon.io
- TradingView (via webhook)

### 2. Economic Calendar Integration
**Current**: Simplified (always passes)
**Needed**: Check for major economic releases in next 30 minutes

**Options**:
- Trading Economics API
- FRED API (Federal Reserve)
- ForexFactory calendar
- Custom calendar database

### 3. Order Execution
**Current**: Simulated execution
**Needed**: Real order placement with:
- Market orders for entries
- Stop-loss orders (GTC)
- Take-profit orders (GTC)
- Partial profit at 1R (optional)

**Topstep Platforms**:
- NinjaTrader
- TradingView
- MetaTrader
- cTrader

### 4. Daily P&L Tracking
**Current**: Tracks in strategy state
**Needed**: Real-time tracking to enforce:
- Daily loss limit (0.5R)
- Daily win limit (stop after win)
- Trailing drawdown monitoring

**Implementation**:
```python
# Add to TopstepStrategy class
def update_daily_pnl(self, date: str, trade_pnl: float):
    """Update daily P&L and enforce limits."""
    if date not in self.daily_pnl:
        self.daily_pnl[date] = 0.0
    
    self.daily_pnl[date] += trade_pnl
    
    # Check if we hit daily loss limit
    if self.daily_pnl[date] <= -self.MAX_LOSS_PER_DAY_R:
        # Stop trading for the day
        return False
    
    # Check if we won (1R or more)
    if self.daily_pnl[date] >= 1.0:
        self.daily_wins[date] = True
        # Stop trading after win
        return False
    
    return True
```

### 5. Trailing Drawdown Monitoring
**Current**: Not implemented
**Needed**: Track account high and enforce trailing drawdown

**Topstep Rules** (example):
- $50K account: $2,500 trailing drawdown
- Account high: $52,500 → drawdown = $50,000
- If account drops to $50,000 → challenge failed

**Implementation**:
```python
class TopstepAccount:
    def __init__(self, initial_balance: float, trailing_drawdown: float):
        self.initial_balance = initial_balance
        self.trailing_drawdown = trailing_drawdown
        self.account_high = initial_balance
        self.current_balance = initial_balance
    
    def update_balance(self, new_balance: float) -> bool:
        """Update balance and check trailing drawdown."""
        self.current_balance = new_balance
        
        # Update account high
        if new_balance > self.account_high:
            self.account_high = new_balance
        
        # Calculate trailing drawdown limit
        drawdown_limit = self.account_high - self.trailing_drawdown
        
        # Check if we violated trailing drawdown
        if new_balance < drawdown_limit:
            return False  # Challenge failed
        
        return True  # Still in challenge
```

### 6. Time Window Enforcement
**Current**: Not enforced (uses daily data)
**Needed**: Only trade during 9:30-10:30 ET

**Implementation**:
```python
from datetime import datetime, time
import pytz

def is_trading_window_open() -> bool:
    """Check if current time is within trading window."""
    et = pytz.timezone('US/Eastern')
    now = datetime.now(et)
    current_time = now.time()
    
    # Trading window: 9:30 AM - 10:30 AM ET
    window_start = time(9, 30)
    window_end = time(10, 30)
    
    # Only trade on weekdays
    if now.weekday() >= 5:  # Saturday = 5, Sunday = 6
        return False
    
    return window_start <= current_time <= window_end
```

## Topstep Challenge Requirements (Verify)

### Phase 1: Evaluation
- **Profit Target**: Usually 6-10% of account
- **Daily Loss Limit**: Usually 5% of account
- **Trailing Drawdown**: Usually 5% of account
- **Trading Days**: Usually 5-10 days minimum
- **Max Contracts**: Usually limited (e.g., 3-5 contracts)

### Phase 2: Funded Account
- **Profit Target**: Usually 5-8% of account
- **Daily Loss Limit**: Usually 5% of account
- **Trailing Drawdown**: Usually 5% of account
- **Trading Days**: Usually 5-10 days minimum
- **Max Contracts**: Usually limited (e.g., 3-5 contracts)

**Your Strategy Settings**:
- Risk: 0.25% per trade (well below 5% daily limit)
- Max trades: 1 per day (prevents overtrading)
- Max loss: 0.5R per day (conservative, well below 5%)
- Position size: 1 contract (micros until funded)

## Recommended Settings for Topstep

### Conservative (Recommended for First Challenge)
```python
RISK_PERCENT = 0.0025  # 0.25% per trade
MAX_RISK_REWARD = 1.5  # 1.5R max
MAX_TRADES_PER_DAY = 1
MAX_LOSS_PER_DAY_R = 0.3  # Even more conservative: 0.3R
```

### Moderate (After Passing First Challenge)
```python
RISK_PERCENT = 0.005  # 0.5% per trade
MAX_RISK_REWARD = 2.0  # 2R max
MAX_TRADES_PER_DAY = 1
MAX_LOSS_PER_DAY_R = 0.5  # 0.5R
```

## Testing Before Live Trading

### 1. Paper Trading
- Test with real-time data feed
- Verify order execution
- Test stop-loss and take-profit orders
- Verify daily P&L tracking

### 2. Topstep Simulator
- Use Topstep's practice account
- Test with their platform
- Verify all rules are enforced
- Practice for 1-2 weeks minimum

### 3. Backtest Validation
- Run backtest on 6+ months of data
- Verify strategy doesn't violate rules
- Check win rate and risk-adjusted returns
- Ensure strategy skips most days (70-90%)

## Expected Performance

### What to Expect
- **Win Rate**: 40-60% (depends on market conditions)
- **Average Win**: 1.0-1.5R
- **Average Loss**: 1.0R (fixed stop)
- **Trading Days**: 10-30% of days (70-90% skipped)
- **Monthly Trades**: 5-15 trades (very conservative)

### Why This Works
- **Small losses**: 0.25% risk per trade
- **Capped losses**: 0.5R max per day
- **Quality setups**: ATR filter ensures volatility
- **No overtrading**: 1 trade max per day
- **Survival first**: Refuses to trade on most days

## Common Mistakes to Avoid

### ❌ Don't Do This
1. **Increase position size** after a win (revenge trading)
2. **Trade outside 9:30-10:30** window
3. **Ignore market regime filters** (trade in low volatility)
4. **Take more than 1 trade per day** (overtrading)
5. **Move stops** (mental stops = account killer)
6. **Trade both ES and NQ** (pick one)

### ✅ Do This
1. **Stick to the rules** (they're there for a reason)
2. **Trust the filters** (if it says no trade, don't trade)
3. **Accept boring days** (skipping 70-90% of days is correct)
4. **Take partial profits** at 1R (optional but recommended)
5. **Stop after win** (don't give back profits)
6. **Track everything** (daily P&L, account high, trailing drawdown)

## Integration Checklist

Before going live, verify:

- [ ] Real-time 5-minute data feed connected
- [ ] Economic calendar integration working
- [ ] Order execution tested (market, stop, limit)
- [ ] Daily P&L tracking implemented
- [ ] Trailing drawdown monitoring active
- [ ] Time window enforcement (9:30-10:30 ET)
- [ ] Paper trading for 1-2 weeks
- [ ] Topstep practice account tested
- [ ] All rules verified and enforced
- [ ] Emergency stop mechanism (manual override)

## Final Notes

**This strategy is designed to pass Topstep challenges**, but:

1. **Test thoroughly** before going live
2. **Start with smallest account size** (e.g., $50K)
3. **Use micro contracts** (MES/MNQ) until funded
4. **Trust the system** (if it says no trade, don't trade)
5. **Be patient** (skipping 70-90% of days is correct)

**Remember**: You're not trading to make money. You're trading to not violate rules until you pass.

Good luck! 🎯
