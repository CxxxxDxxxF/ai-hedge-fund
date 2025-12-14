"""
REGIME SEGMENTATION — RESEARCH ONLY

Purpose:
Label each acceptance breakout with market regime features
to determine where (if anywhere) acceptance continuation survives.

NO STRATEGY CHANGES.
NO EXECUTION CHANGES.
"""

from dataclasses import dataclass, asdict
from typing import Optional, List
import pandas as pd
import numpy as np
import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.data.price_cache import PriceCache


@dataclass
class RegimeLabel:
    date: str
    breakout_ts: pd.Timestamp
    side: str

    # OR structure
    or_range_points: float
    or_range_pct_of_atr: float

    # Volatility
    atr_14: float
    atr_percentile_20d: float

    # Trend context
    prior_day_trend: str  # "up", "down", "flat"
    gap_type: str         # "gap_up", "gap_down", "no_gap"

    # Timing
    breakout_minutes_from_open: int

    # Outcome
    acceptance_pass: bool
    mfe_r: Optional[float] = None
    mae_r: Optional[float] = None
    r_multiple_pre_friction: Optional[float] = None


def compute_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Compute ATR(14) from price DataFrame."""
    high = df['high']
    low = df['low']
    close = df['close']
    
    tr1 = high - low
    tr2 = abs(high - close.shift())
    tr3 = abs(low - close.shift())
    
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=period, min_periods=1).mean()
    
    return atr


def compute_atr_percentile(atr_series: pd.Series, lookback: int = 20) -> float:
    """Compute ATR percentile over lookback period."""
    if len(atr_series) < lookback:
        return np.nan
    recent = atr_series.iloc[-lookback:]
    if len(recent) == 0:
        return np.nan
    current_atr = recent.iloc[-1]
    percentile = (recent <= current_atr).sum() / len(recent) * 100
    return percentile


def classify_prior_day_trend(df: pd.DataFrame, date: str) -> str:
    """Classify prior day trend from price data."""
    # Get all bars for the date
    date_bars = df[df.index.date == pd.to_datetime(date).date()]
    if len(date_bars) == 0:
        return "unknown"
    
    # Get first and last bar of the day
    first_bar = date_bars.iloc[0]
    last_bar = date_bars.iloc[-1]
    
    if last_bar['close'] > first_bar['open']:
        return "up"
    if last_bar['close'] < first_bar['open']:
        return "down"
    return "flat"


def classify_gap(today_open: float, yesterday_close: float, atr: float) -> str:
    """Classify gap type."""
    if pd.isna(today_open) or pd.isna(yesterday_close) or pd.isna(atr) or atr <= 0:
        return "unknown"
    
    gap = today_open - yesterday_close
    if abs(gap) < 0.1 * atr:
        return "no_gap"
    return "gap_up" if gap > 0 else "gap_down"


def load_acceptance_events(path: str = "acceptance_rolling_diagnostic.csv") -> pd.DataFrame:
    """Load acceptance diagnostic events."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"Acceptance events file not found: {path}")
    
    df = pd.read_csv(path)
    
    # Parse timestamps
    if 'timestamp' in df.columns:
        df['timestamp'] = pd.to_datetime(df['timestamp'])
    if 'breakout_timestamp' in df.columns:
        df['breakout_timestamp'] = pd.to_datetime(df['breakout_timestamp'])
    
    return df


def load_price_data(ticker: str = "ES", start_date: str = "2025-09-19", end_date: str = "2025-12-12") -> pd.DataFrame:
    """Load price data for regime analysis from cache."""
    cache = PriceCache()
    df = cache.get_prices_for_range(ticker, start_date, end_date)
    return df if df is not None else pd.DataFrame()


def label_event(event: pd.Series, price_df: pd.DataFrame, atr_series: pd.Series, r_trade_log: Optional[pd.DataFrame] = None) -> RegimeLabel:
    """Label a single acceptance evaluation event with regime features."""
    date = event.get("date", "")
    breakout_ts = pd.to_datetime(event.get("timestamp", event.get("breakout_timestamp", "")))
    
    if pd.isna(breakout_ts):
        raise ValueError(f"Invalid breakout timestamp in event: {event}")
    
    # Get day data
    day_date = pd.to_datetime(date).date()
    day_bars = price_df[price_df.index.date == day_date]
    
    if len(day_bars) == 0:
        # Try to get from full dataframe
        day_bars = price_df[price_df.index.date == breakout_ts.date()]
    
    if len(day_bars) == 0:
        raise ValueError(f"No price data for date {date}")
    
    # Get OR values from event
    or_high = event.get("or_high", np.nan)
    or_low = event.get("or_low", np.nan)
    or_range = or_high - or_low if not pd.isna(or_high) and not pd.isna(or_low) else np.nan
    
    # Get ATR at breakout time
    atr_at_breakout = atr_series.loc[breakout_ts] if breakout_ts in atr_series.index else atr_series.iloc[-1] if len(atr_series) > 0 else np.nan
    
    # Compute ATR percentile (need historical ATR series up to breakout)
    atr_up_to_breakout = atr_series[atr_series.index <= breakout_ts]
    atr_percentile = compute_atr_percentile(atr_up_to_breakout, lookback=20)
    
    # Classify prior day trend
    prior_day_trend = classify_prior_day_trend(price_df, date)
    
    # Classify gap
    today_first_bar = day_bars.iloc[0]
    today_open = today_first_bar['open']
    
    # Get yesterday's last bar
    prev_date = pd.to_datetime(date) - pd.Timedelta(days=1)
    prev_bars = price_df[price_df.index.date == prev_date.date()]
    if len(prev_bars) > 0:
        yesterday_close = prev_bars.iloc[-1]['close']
    else:
        # Fallback: use previous bar in full dataset
        bars_before = price_df[price_df.index < breakout_ts]
        if len(bars_before) > 0:
            yesterday_close = bars_before.iloc[-1]['close']
        else:
            yesterday_close = np.nan
    
    gap_type = classify_gap(today_open, yesterday_close, atr_at_breakout)
    
    # Timing
    breakout_minutes_from_open = (breakout_ts.hour * 60 + breakout_ts.minute) - (9 * 60 + 30)
    
    # Outcome
    acceptance_pass = event.get("decision", "") == "acceptance_pass"
    
    # Get MFE/MAE from trade log if available
    mfe_r = None
    mae_r = None
    r_multiple_pre_friction = None
    
    if r_trade_log is not None and len(r_trade_log) > 0:
        # Match by date and side
        matching_trades = r_trade_log[
            (r_trade_log['entry_timestamp'].dt.date == day_date) &
            (r_trade_log['side'] == event.get("side", ""))
        ]
        if len(matching_trades) > 0:
            trade = matching_trades.iloc[0]
            mfe_r = trade.get('mfe_r', None)
            mae_r = trade.get('mae_r', None)
            r_multiple_pre_friction = trade.get('r_multiple_before_friction', None)
    
    return RegimeLabel(
        date=date,
        breakout_ts=breakout_ts,
        side=event.get("side", ""),
        or_range_points=or_range,
        or_range_pct_of_atr=(or_range / atr_at_breakout * 100) if not pd.isna(atr_at_breakout) and atr_at_breakout > 0 else np.nan,
        atr_14=atr_at_breakout,
        atr_percentile_20d=atr_percentile,
        prior_day_trend=prior_day_trend,
        gap_type=gap_type,
        breakout_minutes_from_open=breakout_minutes_from_open,
        acceptance_pass=acceptance_pass,
        mfe_r=mfe_r,
        mae_r=mae_r,
        r_multiple_pre_friction=r_multiple_pre_friction
    )


def summarize_by_regime(labels: List[RegimeLabel]) -> pd.DataFrame:
    """Aggregate regime labels by regime features."""
    df = pd.DataFrame([asdict(label) for label in labels])
    
    if len(df) == 0:
        return pd.DataFrame()
    
    # Convert breakout_ts to string for grouping
    df['breakout_ts'] = df['breakout_ts'].astype(str)
    
    # Group by regime features
    summary = df.groupby([
        "gap_type",
        "prior_day_trend"
    ]).agg(
        count=("acceptance_pass", "count"),
        pass_rate=("acceptance_pass", "mean"),
        mean_mfe=("mfe_r", "mean"),
        mean_mae=("mae_r", "mean"),
        mean_r_pre_friction=("r_multiple_pre_friction", "mean")
    ).sort_values("count", ascending=False)
    
    # Add MFE > MAE indicator
    summary['mfe_gt_mae'] = summary['mean_mfe'] > summary['mean_mae']
    
    return summary


def run_regime_research():
    """Run regime segmentation research."""
    print("="*80)
    print("REGIME SEGMENTATION RESEARCH")
    print("="*80)
    print()
    
    # Load acceptance events
    print("Loading acceptance events...")
    events_path = "acceptance_rolling_diagnostic.csv"
    if not os.path.exists(events_path):
        events_path = os.path.join("ai-hedge-fund", events_path)
    
    events = load_acceptance_events(events_path)
    print(f"Loaded {len(events)} events")
    
    # Filter to acceptance evaluations only
    acceptance_evals = events[events['event_type'] == 'acceptance_evaluated']
    print(f"Acceptance evaluations: {len(acceptance_evals)}")
    print()
    
    if len(acceptance_evals) == 0:
        print("No acceptance evaluations found. Cannot perform regime analysis.")
        return
    
    # Load price data
    print("Loading price data...")
    price_df = load_price_data("ES", "2025-09-19", "2025-12-12")
    print(f"Loaded {len(price_df)} price bars")
    
    # Compute ATR
    print("Computing ATR...")
    atr_series = compute_atr(price_df, period=14)
    print(f"Computed ATR for {len(atr_series)} bars")
    print()
    
    # Load R trade log if available
    r_trade_log = None
    r_log_path = "r_trade_log.csv"
    if os.path.exists(r_log_path):
        r_trade_log = pd.read_csv(r_log_path, parse_dates=['entry_timestamp', 'exit_timestamp'])
        print(f"Loaded R trade log: {len(r_trade_log)} trades")
    print()
    
    # Label each event
    print("Labeling events with regime features...")
    labels = []
    for idx, event in acceptance_evals.iterrows():
        try:
            label = label_event(event, price_df, atr_series, r_trade_log)
            labels.append(label)
        except Exception as e:
            print(f"Warning: Failed to label event {idx}: {e}")
            continue
    
    print(f"Labeled {len(labels)} events")
    print()
    
    # Aggregate by regime
    print("Aggregating by regime...")
    summary = summarize_by_regime(labels)
    
    print("REGIME SUMMARY:")
    print("="*80)
    print(summary.to_string())
    print()
    
    # Save outputs
    summary.to_csv("regime_summary.csv")
    print("Saved: regime_summary.csv")
    
    labels_df = pd.DataFrame([asdict(label) for label in labels])
    # Convert timestamp to string for CSV
    labels_df['breakout_ts'] = labels_df['breakout_ts'].astype(str)
    labels_df.to_csv("regime_labeled_events.csv", index=False)
    print("Saved: regime_labeled_events.csv")
    print()
    
    # Success/Stop analysis
    print("="*80)
    print("SUCCESS/STOP ANALYSIS")
    print("="*80)
    print()
    
    # Check for winning regimes
    winning_regimes = summary[
        (summary['pass_rate'] >= 0.40) &
        (summary['mfe_gt_mae'] == True) &
        (summary['count'] >= 5)
    ]
    
    if len(winning_regimes) > 0:
        print("✅ WINNING REGIMES FOUND:")
        print("-" * 80)
        print(winning_regimes.to_string())
        print()
        print("Proceed: One or more regime clusters show structural inversion (MFE > MAE)")
        print("         with non-trivial sample size.")
    else:
        print("❌ NO WINNING REGIMES FOUND")
        print()
        print("Stop conditions met:")
        print("  - No regime has pass_rate ≥ 40% AND MFE > MAE AND count ≥ 5")
        print()
        
        # Show what we have
        print("Available regimes:")
        for idx, row in summary.iterrows():
            print(f"  {idx}: count={row['count']:.0f}, pass_rate={row['pass_rate']:.1%}, "
                  f"MFE>MAE={row['mfe_gt_mae']}, mean_R={row['mean_r_pre_friction']:.3f}")
    
    print()
    print("="*80)
    print("END OF REGIME RESEARCH")
    print("="*80)


if __name__ == "__main__":
    try:
        run_regime_research()
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
