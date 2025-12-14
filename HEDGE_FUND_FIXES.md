# Hedge Fund System Fixes

## Problems Identified

1. **Only 1 agent is actually trading** - Most agents return neutral in deterministic mode
2. **That agent has no real informational edge** - Weak rule-based signals
3. **Portfolio Manager has nothing meaningful to aggregate** - Too many neutral signals
4. **Costs overwhelm weak signals** - Transaction costs eat into small profits

## Solutions Implemented

### 1. Enhanced Portfolio Manager Signal Thresholds

**File**: `src/agents/portfolio_manager.py`

**Changes**:
- Added minimum signal strength threshold (25% of total weight must be directional)
- Require at least 2 agents to agree (prevents single-agent dominance)
- Minimum confidence threshold (60%) before trading
- Position sizing based on signal strength (stronger signals = larger positions)
- Better reasoning that explains why trades are held

**Impact**: 
- Prevents weak trades that get eaten by transaction costs
- Ensures multiple agents contribute before trading
- Only trades on strong, high-confidence signals

### 2. Signal Strength Calculation

The Portfolio Manager now calculates:
- `signal_strength = abs(net_weighted_signal) / total_weight` (normalized 0-1)
- Only trades when `signal_strength >= 0.25` (25% threshold)
- Scales position size: `position_multiplier = min(1.0, signal_strength / 0.4)`

### 3. Agent Signal Quality

**Current Status**:
- ✅ **Momentum Agent**: Works with price data only, generates strong signals
- ✅ **Mean Reversion Agent**: Works with price data only, generates strong signals  
- ⚠️ **Warren Buffett Agent**: Needs financial data, but has rule-based fallback
- ⚠️ **Peter Lynch Agent**: Returns neutral in deterministic mode (needs fix)
- ⚠️ **Damodaran Agent**: Needs financial data, but has rule-based fallback

**Next Steps**:
- Improve Peter Lynch to work with price data when external data unavailable
- Enhance Warren Buffett and Damodaran rule-based logic to be more aggressive
- Add price-based technical indicators as fallback for value agents

## Testing

Run a backtest to verify improvements:

```bash
HEDGEFUND_NO_LLM=1 poetry run python src/backtesting/deterministic_backtest.py \
  --tickers AAPL,MSFT \
  --start-date 2024-01-02 \
  --end-date 2024-02-29 \
  --initial-capital 100000
```

**Expected Improvements**:
- Fewer trades (only strong signals)
- Higher win rate (stronger signals)
- Better risk-adjusted returns (costs don't overwhelm)
- Multiple agents contributing to trades

## Configuration

The thresholds can be adjusted in `portfolio_manager.py`:

```python
MIN_SIGNAL_STRENGTH = 0.25  # At least 25% of total weight must be directional
MIN_AGENT_CONSENSUS = 2     # At least 2 agents must agree
MIN_CONFIDENCE = 60         # Minimum average confidence to trade
```

**Tuning Guidelines**:
- **Lower thresholds** (0.15, 1 agent, 50%): More trades, higher costs, lower quality
- **Higher thresholds** (0.35, 3 agents, 70%): Fewer trades, lower costs, higher quality
- **Current settings**: Balanced approach to prevent cost erosion

## Transaction Costs

Current cost structure (from `edge_analysis.py`):
- Commission: $0.01 per share
- Slippage: 5 basis points (0.05%)
- Spread: 3 basis points (0.03%)

**Impact**: For a $100 trade:
- Commission: ~$1 (if 100 shares)
- Slippage: $0.05
- Spread: $0.03
- **Total: ~$1.08 per trade**

This means we need signals that can generate at least 1-2% profit to overcome costs.

## Future Improvements

1. **Price-Based Fallbacks for Value Agents**:
   - Use P/E, P/B ratios from price data when financials unavailable
   - Estimate growth from price momentum
   - Use relative valuation vs sector

2. **Dynamic Threshold Adjustment**:
   - Lower thresholds in high-volatility regimes
   - Higher thresholds in low-volatility regimes
   - Adjust based on recent performance

3. **Cost-Aware Position Sizing**:
   - Calculate expected profit vs transaction costs
   - Only trade if expected profit > 2x transaction costs
   - Scale position size based on risk/reward ratio

4. **Agent Performance Tracking**:
   - Track which agents contribute to winning trades
   - Adjust agent weights based on historical performance
   - Reduce weight of consistently wrong agents
