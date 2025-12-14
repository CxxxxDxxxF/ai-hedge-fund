# Backtesting Performance Optimization Plan

## Current Bottlenecks

### 1. **`run_hedge_fund()` Called Every Day** (Biggest Bottleneck)
- **Issue**: Creates workflow, compiles agent, invokes LangGraph for every trading day
- **Impact**: ~1-5 seconds per day × 1303 days = 20-100 minutes
- **Location**: `isolated_agent_backtest.py:448`, `deterministic_backtest.py:642`

### 2. **Price Data Loading**
- **Issue**: `_get_current_prices()` called every day, doing individual lookups
- **Impact**: ~10-50ms per day × 1303 days = 13-65 seconds
- **Location**: `isolated_agent_backtest.py:103`

### 3. **Portfolio Copying**
- **Issue**: `self.portfolio.copy()` for every `run_hedge_fund()` call
- **Impact**: ~1-5ms per day × 1303 days = 1-6 seconds
- **Location**: `isolated_agent_backtest.py:452`

### 4. **Buy-and-Hold Calculation**
- **Issue**: Loops through every date in DataFrame
- **Impact**: ~10-50ms for full calculation
- **Location**: `isolated_agent_backtest.py:661-679`

### 5. **Redundant NAV Calculations**
- **Issue**: NAV calculated multiple times per day
- **Impact**: ~1-5ms per calculation × multiple calls
- **Location**: Multiple locations

## Optimization Strategies

### Strategy 1: Pre-load All Price Data (Quick Win)
**Impact**: 10-50x speedup for price lookups
**Effort**: Low
**Risk**: Low

Load all price data into memory at start:
```python
def __init__(self, ...):
    # Pre-load all price data
    self.price_data = {}  # {ticker: DataFrame indexed by date}
    cache = get_price_cache()
    for ticker in self.tickers:
        self.price_data[ticker] = cache.get_prices_for_range(
            ticker, self.start_date, self.end_date
        ).set_index('date')
```

Then `_get_current_prices()` becomes:
```python
def _get_current_prices(self, date: str) -> Dict[str, float]:
    prices = {}
    for ticker in self.tickers:
        if date in self.price_data[ticker].index:
            prices[ticker] = float(self.price_data[ticker].loc[date, 'close'])
        else:
            prices[ticker] = 0.0
    return prices
```

### Strategy 2: Cache Agent Signals (Deterministic Mode)
**Impact**: 100-1000x speedup (eliminates workflow creation)
**Effort**: Medium
**Risk**: Medium (must ensure determinism)

In deterministic mode, same inputs = same outputs. Cache signals:
```python
def __init__(self, ...):
    self.signal_cache = {}  # {(date, agent_name): signals}

def _get_agent_signal(self, date: str) -> Dict[str, Dict]:
    cache_key = (date, self.agent_name)
    if cache_key in self.signal_cache:
        return self.signal_cache[cache_key]
    
    # ... existing logic ...
    self.signal_cache[cache_key] = agent_signals
    return agent_signals
```

### Strategy 3: Vectorize Buy-and-Hold Calculation
**Impact**: 10-100x speedup
**Effort**: Low
**Risk**: Low

Use pandas vectorized operations:
```python
# Instead of looping through dates
price_cols = [f"{ticker}_Price" for ticker in self.tickers]
initial_prices = df.loc[df.index[0], price_cols]
current_prices = df[price_cols]
returns = current_prices.div(initial_prices)
ticker_allocation = initial_value / len(self.tickers)
df["BuyHold"] = (returns.sum(axis=1) * ticker_allocation)
```

### Strategy 4: Reduce Portfolio Copies
**Impact**: 1-5% speedup
**Effort**: Low
**Risk**: Low

Only copy portfolio when necessary, or pass reference if agent doesn't modify it.

### Strategy 5: Batch Process Days (Advanced)
**Impact**: 2-10x speedup
**Effort**: High
**Risk**: High (complexity)

Process multiple days in parallel or batch agent calls.

## Recommended Implementation Order

1. **Pre-load price data** (Strategy 1) - Quick win, low risk
2. **Vectorize buy-and-hold** (Strategy 3) - Quick win, low risk
3. **Cache agent signals** (Strategy 2) - Big win, medium risk
4. **Reduce portfolio copies** (Strategy 4) - Small win, low risk
5. **Batch processing** (Strategy 5) - Future optimization

## Expected Performance Gains

| Optimization | Current Time | Optimized Time | Speedup |
|-------------|--------------|---------------|---------|
| Baseline | 20-100 min | - | 1x |
| + Price pre-load | 20-100 min | 19-99 min | 1.05x |
| + Vectorized B&H | 19-99 min | 19-98 min | 1.05x |
| + Signal caching | 19-98 min | **1-5 min** | **20-100x** |
| + Portfolio opt | 1-5 min | 1-4.5 min | 1.1x |

**Total expected speedup: 20-100x** (from 20-100 minutes to 1-5 minutes)

## Implementation Notes

- **Determinism**: All optimizations must preserve determinism
- **Memory**: Pre-loading price data increases memory usage (acceptable for backtests)
- **Testing**: Verify results match before/after optimization
- **Gradual rollout**: Implement one optimization at a time, test, then proceed
