"""
Diagnostic script for Acceptance Continuation Strategy.

Tracks counters at each gate to identify where strategy is failing.
"""
import os
import sys
import pandas as pd
from datetime import datetime
from typing import Dict, List, Optional, Tuple

os.environ["HEDGEFUND_NO_LLM"] = "1"

from src.agents.acceptance_continuation_strategy import AcceptanceContinuationStrategy
from src.tools.api import get_prices, prices_to_df

class DiagnosticAcceptanceStrategy(AcceptanceContinuationStrategy):
    """Acceptance strategy with diagnostic tracking."""
    
    def __init__(self, instrument: str = "ES"):
        super().__init__(instrument)
        
        # Diagnostic counters
        self.diagnostics = {
            'days_with_or': 0,
            'days_with_breakout': 0,
            'breakouts_total': 0,
            'breakouts_long': 0,
            'breakouts_short': 0,
            'breakouts_with_enough_bars': 0,
            'breakouts_too_late': 0,
            'acceptance_pass': 0,
            'acceptance_fail': 0,
            'acceptance_fail_details': [],  # List of {breakout_ts, side, violation_bar, violation_points, violation_pct}
            'entries_emitted': 0,
            'entries_blocked': {
                'daily_limit': 0,
                'already_in_trade': 0,
                'position_size_zero': 0,
                'other': 0
            },
            'expansion_distribution': {
                'E <= 0': 0,
                '0 < E < 1': 0,
                'E >= 1': 0,
                'E >= 5': 0,
                'E >= 10': 0
            },
            'breakout_timestamps': [],  # List of (date, timestamp, side, E)
        }
    
    def _identify_opening_range(self, df: pd.DataFrame, date: str) -> Optional[Dict]:
        """Override to track OR identification."""
        result = super()._identify_opening_range(df, date)
        if result:
            self.diagnostics['days_with_or'] += 1
        return result
    
    def _detect_breakout(self, df: pd.DataFrame, or_data: Dict, current_bar: pd.Series, current_ts: pd.Timestamp) -> Optional[Dict]:
        """Override to track breakout detection."""
        breakout = super()._detect_breakout(df, or_data, current_bar, current_ts)
        if breakout:
            self.diagnostics['breakouts_total'] += 1
            if breakout['side'] == 'long':
                self.diagnostics['breakouts_long'] += 1
            else:
                self.diagnostics['breakouts_short'] += 1
            
            # Track expansion distribution
            E = breakout['E']
            if E <= 0:
                self.diagnostics['expansion_distribution']['E <= 0'] += 1
            elif E < 1:
                self.diagnostics['expansion_distribution']['0 < E < 1'] += 1
            elif E < 5:
                self.diagnostics['expansion_distribution']['E >= 1'] += 1
            elif E < 10:
                self.diagnostics['expansion_distribution']['E >= 5'] += 1
            else:
                self.diagnostics['expansion_distribution']['E >= 10'] += 1
            
            # Track breakout timestamp
            date_str = current_ts.strftime("%Y-%m-%d") if hasattr(current_ts, 'strftime') else str(current_ts)[:10]
            self.diagnostics['breakout_timestamps'].append({
                'date': date_str,
                'timestamp': current_ts,
                'side': breakout['side'],
                'E': E
            })
        
        return breakout
    
    def _check_acceptance(self, or_data: Dict, breakout_state: Dict) -> Tuple[bool, Optional[str]]:
        """Override to track acceptance pass/fail."""
        is_accepted, reason = super()._check_acceptance(or_data, breakout_state)
        
        if is_accepted:
            self.diagnostics['acceptance_pass'] += 1
        else:
            self.diagnostics['acceptance_fail'] += 1
            
            # Track failure details
            side = breakout_state['side']
            E = breakout_state['E']
            or_high = or_data['high']
            or_low = or_data['low']
            max_retrace = self.ACCEPTANCE_RETRACE_THRESHOLD * E
            
            if side == 'long':
                min_low = min(bar['low'] for bar in self.acceptance_bars)
                acceptance_floor = or_high - max_retrace
                violation_points = acceptance_floor - min_low
                violation_pct = (violation_points / E * 100) if E > 0 else 0
            else:  # short
                max_high = max(bar['high'] for bar in self.acceptance_bars)
                acceptance_ceiling = or_low + max_retrace
                violation_points = max_high - acceptance_ceiling
                violation_pct = (violation_points / E * 100) if E > 0 else 0
            
            # Find first violation bar
            first_violation_bar = None
            for i, bar in enumerate(self.acceptance_bars):
                if side == 'long':
                    if bar['low'] < acceptance_floor:
                        first_violation_bar = i + 1  # Bar N+1, N+2, or N+3
                        break
                else:  # short
                    if bar['high'] > acceptance_ceiling:
                        first_violation_bar = i + 1
                        break
            
            self.diagnostics['acceptance_fail_details'].append({
                'breakout_ts': breakout_state['breakout_ts'],
                'side': side,
                'E': E,
                'violation_bar': first_violation_bar,
                'violation_points': violation_points,
                'violation_pct': violation_pct
            })
        
        return (is_accepted, reason)
    
    def generate_signal(
        self, state: Dict, date: str, account_value: float
    ) -> Dict[str, Dict]:
        """Override to track entry emission and blocking."""
        # Track if we had a breakout today
        had_breakout_before = self.breakout_state is not None
        
        result = super().generate_signal(state, date, account_value)
        
        # Track if we have a breakout now
        if self.breakout_state is not None and not had_breakout_before:
            self.diagnostics['days_with_breakout'] += 1
        
        # Check if entry was emitted
        ticker = self.ticker
        if ticker in result:
            decision = result[ticker]
            if isinstance(decision, dict) and decision.get("action", "hold").lower() != "hold":
                self.diagnostics['entries_emitted'] += 1
            else:
                # Entry was blocked - check reason
                reasoning = decision.get("reasoning", "")
                if "Daily limit" in reasoning:
                    self.diagnostics['entries_blocked']['daily_limit'] += 1
                elif "position size" in reasoning.lower() or "contracts" in reasoning.lower():
                    self.diagnostics['entries_blocked']['position_size_zero'] += 1
                elif "already" in reasoning.lower() or "position" in reasoning.lower():
                    self.diagnostics['entries_blocked']['already_in_trade'] += 1
                else:
                    # Track other reasons
                    self.diagnostics['entries_blocked']['other'] += 1
        
        return result


def run_diagnostic():
    """Run diagnostic on full dataset."""
    print("="*80)
    print("ACCEPTANCE CONTINUATION STRATEGY - DIAGNOSTIC")
    print("="*80)
    print()
    
    strategy = DiagnosticAcceptanceStrategy(instrument="ES")
    
    # Get all trading dates
    start_date = "2025-09-19"
    end_date = "2025-12-12"
    
    dates = pd.bdate_range(start_date, end_date)
    
    print(f"Running diagnostic on {len(dates)} trading days...")
    print()
    
    # Run strategy on each day (process bars sequentially to maintain state)
    for date in dates:
        date_str = date.strftime("%Y-%m-%d")
        
        # Reset strategy state for new day (simulate daily reset)
        strategy.or_state = None
        strategy.breakout_state = None
        strategy.acceptance_bars = []
        
        # Get price data for the day
        df = strategy._get_price_data("ES", date_str, date_str)
        if len(df) == 0:
            continue
        
        # Check if we have intraday data
        is_intraday = isinstance(df.index[0], pd.Timestamp) and (
            hasattr(df.index[0], 'hour') or 
            (isinstance(df.index[0], str) and ' ' in str(df.index[0]))
        )
        
        if not is_intraday:
            continue
        
        # Sort by timestamp to ensure sequential processing
        df = df.sort_index()
        
        # Process each bar in the trading window (9:30-10:30) sequentially
        for idx, row in df.iterrows():
            ts = idx if isinstance(idx, pd.Timestamp) else pd.Timestamp(idx)
            hour = ts.hour
            minute = ts.minute
            
            # Only process bars in trading window
            if hour == 9 and minute >= 30:
                pass  # In window
            elif hour == 10 and minute <= 30:
                pass  # In window
            else:
                continue  # Outside window
            
            # Create state for strategy
            state = {
                "data": {
                    "tickers": ["ES"],
                    "end_date": date_str,
                    "portfolio": {},
                },
                "messages": [],
                "metadata": {}
            }
            
            # Call strategy (it will track diagnostics internally)
            try:
                strategy.generate_signal(state, date_str, 100000.0)
            except Exception as e:
                print(f"Error on {date_str} {ts}: {e}", file=sys.stderr)
                continue
    
    # Count breakouts that had enough bars for acceptance evaluation
    # A breakout has enough bars if it occurs early enough that 3 more bars can fit before 10:30
    for breakout_info in strategy.diagnostics['breakout_timestamps']:
        ts = breakout_info['timestamp']
        if isinstance(ts, str):
            ts = pd.Timestamp(ts)
        
        # Check if breakout happened early enough (need 2 more bars = 10 minutes)
        # Last bar in window is 10:30, so breakout must be at or before 10:20
        if ts.hour < 10 or (ts.hour == 10 and ts.minute <= 20):
            strategy.diagnostics['breakouts_with_enough_bars'] += 1
        else:
            strategy.diagnostics['breakouts_too_late'] += 1
    
    # Print diagnostic results
    print("="*80)
    print("DIAGNOSTIC RESULTS")
    print("="*80)
    print()
    
    diag = strategy.diagnostics
    
    print("GATE COUNTS:")
    print("-" * 80)
    print(f"Days with OR:                    {diag['days_with_or']}")
    print(f"Days with breakout:              {diag['days_with_breakout']}")
    print(f"Breakouts total:                  {diag['breakouts_total']}")
    print(f"  - Long breakouts:              {diag['breakouts_long']}")
    print(f"  - Short breakouts:              {diag['breakouts_short']}")
    print(f"Breakouts with enough bars:       {diag['breakouts_with_enough_bars']}")
    print(f"Breakouts too late:               {diag['breakouts_too_late']}")
    print()
    
    print("ACCEPTANCE EVALUATION:")
    print("-" * 80)
    print(f"Acceptance pass:                  {diag['acceptance_pass']}")
    print(f"Acceptance fail:                  {diag['acceptance_fail']}")
    print()
    
    if diag['acceptance_fail'] > 0:
        print("ACCEPTANCE FAILURE DETAILS (first 10):")
        print("-" * 80)
        for i, detail in enumerate(diag['acceptance_fail_details'][:10]):
            print(f"  {i+1}. {detail['side'].upper()} breakout, E={detail['E']:.2f}, "
                  f"Violated on bar N+{detail['violation_bar']}, "
                  f"{detail['violation_points']:.2f} points ({detail['violation_pct']:.1f}% of E)")
        print()
    
    print("ENTRY EMISSION:")
    print("-" * 80)
    print(f"Entries emitted:                  {diag['entries_emitted']}")
    print(f"Entries blocked:")
    for reason, count in diag['entries_blocked'].items():
        if count > 0:
            print(f"  - {reason}:                    {count}")
    print()
    
    print("EXPANSION SIZE DISTRIBUTION:")
    print("-" * 80)
    for bucket, count in diag['expansion_distribution'].items():
        print(f"{bucket:20s}: {count:3d}")
    print()
    
    # Summary table
    print("="*80)
    print("SUMMARY TABLE")
    print("="*80)
    print()
    print(f"{'Metric':<40} {'Count':>10}")
    print("-" * 50)
    print(f"{'days_with_or':<40} {diag['days_with_or']:>10}")
    print(f"{'days_with_breakout':<40} {diag['days_with_breakout']:>10}")
    print(f"{'breakouts_total':<40} {diag['breakouts_total']:>10}")
    print(f"{'breakouts_with_enough_bars_for_acceptance':<40} {diag['breakouts_with_enough_bars']:>10}")
    print(f"{'acceptance_pass':<40} {diag['acceptance_pass']:>10}")
    print(f"{'acceptance_fail':<40} {diag['acceptance_fail']:>10}")
    print(f"{'entries_emitted':<40} {diag['entries_emitted']:>10}")
    print()
    
    # Check for discrepancies
    print("="*80)
    print("DIAGNOSTIC CHECKS")
    print("="*80)
    print()
    
    if diag['breakouts_total'] > 0 and diag['breakouts_with_enough_bars'] == 0:
        print("⚠️  WARNING: All breakouts occurred too late to complete acceptance window")
        print()
    
    if diag['acceptance_pass'] > 0 and diag['entries_emitted'] == 0:
        print("⚠️  WARNING: Acceptance passed but no entries emitted - check blocking reasons")
        print()
    
    if diag['acceptance_pass'] != diag['entries_emitted']:
        print(f"⚠️  WARNING: Acceptance passes ({diag['acceptance_pass']}) != Entries emitted ({diag['entries_emitted']})")
        print("   Check entries_blocked counts above")
        print()
    
    if diag['breakouts_with_enough_bars'] > 0:
        acceptance_rate = (diag['acceptance_pass'] / diag['breakouts_with_enough_bars']) * 100
        print(f"Acceptance pass rate: {acceptance_rate:.1f}% ({diag['acceptance_pass']}/{diag['breakouts_with_enough_bars']})")
        print()
    
    print("="*80)
    print("END OF DIAGNOSTIC")
    print("="*80)


if __name__ == "__main__":
    try:
        run_diagnostic()
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
