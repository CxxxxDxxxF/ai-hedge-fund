# Execution Map - Systems Audit

**Purpose**: Map all execution paths, entry points, and state mutation points in the deterministic backtesting system.

**Last Updated**: 2025-12-14

---

## 1. CLI Entry Points

### Primary Entry Points

| Entry Point | File | Purpose | Deterministic Mode |
|------------|------|---------|-------------------|
| `DeterministicBacktest.run()` | `src/backtesting/deterministic_backtest.py:1200+` | Main backtest execution | Yes (when `HEDGEFUND_NO_LLM=1`) |
| `generate_r_metrics_report.py` | `generate_r_metrics_report.py` | R-metrics analysis script | Yes |
| `run_acceptance_diagnostic.py` | `run_acceptance_diagnostic.py` | Acceptance strategy diagnostic | Yes |
| `run_rolling_acceptance_backtest.py` | `run_rolling_acceptance_backtest.py` | Rolling acceptance backtest | Yes |
| `research/regime_segmentation.py` | `research/regime_segmentation.py` | Regime research (read-only) | N/A (no execution) |

### Secondary Entry Points (Not Used in Deterministic Mode)

| Entry Point | File | Purpose | Notes |
|------------|------|---------|-------|
| `src/main.py` | `src/main.py:242` | CLI hedge fund runner | Uses LLM agents |
| `src/backtester.py` | `src/backtester.py` | Legacy backtester | Uses LLM agents |
| `app/backend/main.py` | `app/backend/main.py` | FastAPI web backend | Uses LLM agents |

---

## 2. DeterministicBacktest Execution Path

### Call Graph: `DeterministicBacktest.run()`

```
DeterministicBacktest.__init__()
  ├─ Initialize portfolio state
  ├─ Initialize PriceCache
  ├─ Initialize strategy (TopstepStrategy OR AcceptanceContinuationStrategy)
  └─ Initialize state tracking (daily_values, trades, active_positions)

DeterministicBacktest.run()
  ├─ Prefetch price data (PriceCache.get_prices_for_range)
  ├─ Detect data granularity (intraday vs daily)
  │
  ├─ IF INTRADAY DATA:
  │   ├─ Collect all bars (sorted by timestamp)
  │   ├─ FOR EACH BAR:
  │   │   └─ _run_intraday_bar()
  │   │       ├─ _check_stops_and_targets() [STATE MUTATION: exits, active_positions]
  │   │       ├─ IF in trading window AND no position AND no trades today:
  │   │       │   └─ strategy.generate_signal()
  │   │       │       ├─ Get price data (filtered to current bar)
  │   │       │       └─ Return decision {action, quantity, reasoning}
  │   │       ├─ IF decision.action != "hold":
  │   │       │   └─ _execute_trade() [STATE MUTATION: cash, positions, PnL]
  │   │       │       ├─ _check_capital_constraints()
  │   │       │       ├─ Apply friction (slippage + spread)
  │   │       │       ├─ Update portfolio (cash, positions, cost basis)
  │   │       │       ├─ Record trade (self.trades)
  │   │       │       └─ Store active position (self.active_positions)
  │   │       └─ Record daily NAV (if end of day)
  │   │
  └─ IF DAILY DATA:
      └─ FOR EACH DAY:
          └─ _run_daily_decision()
              ├─ Get price data
              ├─ Call strategy
              └─ Execute trades

DeterministicBacktest._calculate_metrics()
  └─ Compute performance metrics from daily_values and trades
```

### State Mutation Points (Choke Points)

| Location | Method | What Mutates | When |
|----------|--------|--------------|------|
| `deterministic_backtest.py:937` | `_execute_trade()` | `portfolio["cash"]`, `portfolio["positions"]`, `realized_gains`, `trades[]` | On every trade execution |
| `deterministic_backtest.py:934` | `_check_stops_and_targets()` | `active_positions[]`, `trades[]`, `portfolio` | On every bar (if position active) |
| `deterministic_backtest.py:1050` | `_run_intraday_bar()` → `_execute_trade()` | `active_positions[]`, `trades_today[]` | On entry trade |
| `deterministic_backtest.py:1097` | `_run_intraday_bar()` | `daily_values[]` | End of day or first bar of new day |

---

## 3. Data Flow

### CSV → Cache → Strategy → Execution → Metrics

```
1. DATA LOADING
   src/data/prices/ES.csv (CSV file)
     ↓
   PriceCache._load_ticker_csv()
     ↓
   PriceCache._cache[ticker] (DataFrame with datetime index)
     ↓
   PriceCache.get_prices_for_range(ticker, start, end)
     ↓
   DataFrame (preserves timestamps if intraday)

2. STRATEGY INPUT
   DeterministicBacktest._run_intraday_bar()
     ↓
   strategy_df = price_cache.get_prices_for_range(...)
     ↓
   strategy_df = strategy_df[strategy_df.index <= bar_ts]  [FILTERED TO CURRENT BAR]
     ↓
   strategy._get_price_data() (temporarily overridden)
     ↓
   strategy.generate_signal(state, date, account_value)
     ↓
   Returns: {ticker: {action, quantity, confidence, reasoning}}

3. EXECUTION
   portfolio_decisions[ticker] = decision
     ↓
   _execute_trade(ticker, action, quantity, price, ...)
     ↓
   Apply friction: executed_price = price * (1 ± friction_bps)
     ↓
   Update portfolio:
     - portfolio["cash"] -= cost + commission
     - portfolio["positions"][ticker]["long"] += quantity
     - portfolio["positions"][ticker]["long_cost_basis"] = weighted_avg
     ↓
   Record trade: self.trades.append({date, ticker, action, quantity, price})
     ↓
   Store active position: self.active_positions[ticker] = {side, entry_price, stop_loss, target, ...}

4. METRICS
   _calculate_metrics()
     ↓
   Computes from:
     - self.daily_values (NAV over time)
     - self.trades (all executed trades)
     - self.portfolio["realized_gains"] (cumulative PnL)
```

---

## 4. Strategy Classes and Instantiation

### Strategy Classes

| Class | File | Purpose | How Instantiated |
|-------|------|---------|------------------|
| `TopstepStrategy` | `src/agents/topstep_strategy.py` | OR break + pullback strategy | `TopstepStrategy(instrument="ES")` |
| `AcceptanceContinuationStrategy` | `src/agents/acceptance_continuation_strategy.py` | Acceptance continuation strategy | `AcceptanceContinuationStrategy(instrument="ES")` |

### Strategy Selection Logic

**Location**: `deterministic_backtest.py:177-186`

```python
# Strategy selection (if using ES or NQ)
use_acceptance_strategy = True  # Testing new hypothesis

if any(ticker.upper() in ["ES", "NQ", "MES", "MNQ"] for ticker in tickers):
    for ticker in tickers:
        if ticker.upper() in ["ES", "MES"]:
            if use_acceptance_strategy:
                self.acceptance_strategy = AcceptanceContinuationStrategy(instrument="ES")
            else:
                self.topstep_strategy = TopstepStrategy(instrument="ES")
            break
```

**Current State**: `use_acceptance_strategy = True` (hardcoded)

**Strategy Interface**:
- `generate_signal(state: Dict, date: str, account_value: float) -> Dict[str, Dict]`
- Returns: `{ticker: {action, quantity, confidence, reasoning}}`

---

## 5. Intraday Execution Path Details

### `_run_intraday_bar()` Flow

**Location**: `deterministic_backtest.py:919-1220`

**Input**: Single bar dict with `{ticker, timestamp, open, high, low, close, volume}`

**Steps**:
1. **Stop/Target Check** (lines 933-946)
   - `_check_stops_and_targets(bar, prices)`
   - Returns list of exit trades
   - Executes exits via `_execute_trade()`
   - Clears `active_positions[ticker]`

2. **Strategy Call** (lines 1131-1179)
   - Only if: `in_trading_window AND not has_position AND trades_today == 0`
   - Filters price data to bars up to current bar
   - Calls `strategy.generate_signal()`
   - Extracts decision

3. **Entry Execution** (lines 1202-1230)
   - If `decision.action != "hold"`:
     - `_execute_trade()` → updates portfolio
     - Extract stop/target from reasoning string
     - Store in `active_positions[ticker]`

4. **NAV Recording** (lines 1232-1240)
   - Record daily NAV at end of day

### Stop/Target Execution Details

**Location**: `deterministic_backtest.py:829-917`

**Logic**:
- **Long stops**: `bar_low <= stop_loss` → exit at `stop_loss`
- **Long targets**: `bar_high >= target` → exit at `target`
- **Short stops**: `bar_high >= stop_loss` → exit at `stop_loss`
- **Short targets**: `bar_low <= target` → exit at `target`

**MFE/MAE Tracking**:
- Updated on every bar while position active
- Stored in `active_positions[ticker]['mfe']` and `['mae']`

**Time-Based Invalidation**:
- If `bars_since_entry >= 5` AND `mfe_r < 0.5`:
  - Exit at market (bar close)

---

## 6. Friction Application

**Location**: `deterministic_backtest.py:620-631`

**Formula**:
```python
total_friction_bps = slippage_bps + spread_bps
if action in ["buy", "cover"]:
    executed_price = price * (1.0 + (total_friction_bps / 10000.0))
else:  # sell or short
    executed_price = price * (1.0 - (total_friction_bps / 10000.0))
```

**Tracking**:
- `self.total_slippage_cost` (cumulative)
- `self.total_commissions` (cumulative)
- Applied once per fill

---

## 7. Determinism Enforcement

**Location**: `src/utils/deterministic_guard.py`

**Mechanism**:
- `HEDGEFUND_NO_LLM=1` environment variable
- `initialize_determinism(seed=42)` called at module load
- `get_prices()` routes to `PriceCache` instead of API when deterministic

**Verification**:
- Deterministic hash computed in `_calculate_metrics()`
- Two runs with same seed must produce identical hash

---

## 8. Data Timestamp Preservation

**Path**: CSV → PriceCache → Strategy → Execution

**Key Points**:
1. **CSV Loading** (`price_cache.py:67-70`):
   - `pd.read_csv(..., parse_dates=["date"])` preserves datetime if present
   - Index set to `date` column (can be datetime or date-only)

2. **Intraday Detection** (`deterministic_backtest.py:1250-1260`):
   - Checks if index has time component: `hasattr(df.index[0], 'hour')`

3. **Timestamp Preservation** (`api.py:Price.to_dict()`):
   - Preserves full datetime string if time component exists
   - Falls back to date-only if daily data

4. **Strategy Input** (`deterministic_backtest.py:1139-1142`):
   - Filters DataFrame to `strategy_df.index <= bar_ts`
   - Preserves timestamp index

---

## 9. Daily Limits Enforcement

**Location**: Strategy classes (`topstep_strategy.py`, `acceptance_continuation_strategy.py`)

**Limits**:
- `MAX_TRADES_PER_DAY = 1`
- `MAX_LOSS_PER_DAY_R = 0.5`
- `daily_wins.get(date, False)` → stop after win

**Enforcement**:
- Checked in `strategy._check_daily_limits(date)` before signal generation
- Backtest also checks: `trades_today.get(date_str, 0) == 0` before calling strategy

**State Tracking**:
- `self.daily_trades: Dict[str, int]` (date -> count)
- `self.daily_pnl: Dict[str, float]` (date -> PnL in R units)
- `self.daily_wins: Dict[str, bool]` (date -> True if won)

---

## 10. R-Metrics Tracking

**Location**: `deterministic_backtest.py:964-1055`

**Tracking**:
- `self.r_trade_log: List[Dict]` stores per-trade R metrics
- Computed on exit (stop/target/time_invalidation)
- Fields: `entry_price`, `stop_loss`, `target`, `mfe`, `mae`, `mfe_r`, `mae_r`, `r_multiple_before_friction`, `r_multiple_after_friction`

**Computation**:
- R risk = `abs(entry_price - stop_loss)`
- MFE/MAE updated on each bar in `_check_stops_and_targets()`
- R-multiple = `(exit_price - entry_price) / r_risk` (adjusted for side)

---

## 11. Known Execution Paths

### Path A: Intraday with Active Position
```
Bar arrives → _check_stops_and_targets() → Exit if hit → Clear position
```

### Path B: Intraday Entry
```
Bar arrives → No position → In window → Strategy called → Entry executed → Position stored
```

### Path C: Daily Data (Fallback)
```
Day arrives → _run_daily_decision() → Strategy called → Trade executed
```

---

## 12. State Reset Points

| Reset Point | Location | What Resets |
|-------------|----------|-------------|
| New day | `_run_intraday_bar()` detects `is_new_day` | `trades_today`, `pnl_today` (in strategy) |
| Position exit | `_check_stops_and_targets()` after exit | `active_positions[ticker] = None` |
| Strategy daily reset | `strategy.generate_signal()` start | `or_state`, `breakout_state`, `acceptance_bars` (if new date) |

---

## 13. Error Handling

**Failures are raised as RuntimeError**:
- Invalid price data: `RuntimeError("ENGINE FAILURE: Cannot get price...")`
- Negative NAV: `RuntimeError("ENGINE FAILURE: Trade execution resulted in negative NAV")`
- Constraint violation: `RuntimeError("ENGINE FAILURE: Post-trade gross exposure exceeds...")`

**Strategy failures are logged but don't stop execution**:
- `print(f"STRATEGY FAILURE: {timestamp}: {error}", file=sys.stderr)`
- Execution continues with "hold" decision

---

## 14. Verification Points

**Critical invariants checked**:
1. NAV never negative (post-trade validation)
2. Gross exposure ≤ 100% NAV (post-trade validation)
3. Position size ≤ 20% NAV per ticker (post-trade validation)
4. Bar processing no duplicates (`processed_dates` set)
5. Determinism hash matches across runs

---

**END OF EXECUTION MAP**
