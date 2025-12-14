"""
Acceptance Continuation Strategy

Hypothesis: Continuation occurs when price expands away from the OR boundary and maintains 
that expansion (does not retrace more than 30% of the expansion distance) within 3 bars, 
indicating acceptance rather than rejection.

This is a new hypothesis test, separate from the pullback strategy.
"""

from __future__ import annotations

from datetime import datetime, time
from typing import Dict, List, Optional, Tuple
import pandas as pd
import numpy as np

from src.tools.api import get_prices, prices_to_df
from src.graph.state import AgentState


class AcceptanceContinuationStrategy:
    """Acceptance continuation strategy: enter on expansion acceptance, not pullback."""
    
    # Strategy parameters (same risk framework as TopstepStrategy)
    RISK_PERCENT = 0.0025  # 0.25% of account per trade
    MAX_RISK_REWARD = 1.5  # 1.5R max profit target
    MAX_TRADES_PER_DAY = 1
    MAX_LOSS_PER_DAY_R = 0.5  # Max 0.5R loss per day
    OR_MINUTES = 15  # Opening range: first 15 minutes (9:30-9:45) = 3 five-minute bars
    TRADING_WINDOW_END = 60  # Trading window ends at 10:30 (60 minutes after open)
    
    # Acceptance continuation parameters
    ACCEPTANCE_BARS = 2  # Next 2 bars after breakout (reduced from 3 to make testable)
    ACCEPTANCE_RETRACE_THRESHOLD = 0.30  # 30% retrace allowed
    MIN_EXPANSION = 0.0  # Minimum expansion in points (0 = no floor initially)
    
    def __init__(self, instrument: str = "ES"):
        """
        Initialize Acceptance Continuation strategy.
        
        Args:
            instrument: "ES" (E-mini S&P 500) or "NQ" (E-mini NASDAQ-100)
        """
        if instrument not in ["ES", "NQ"]:
            raise ValueError(f"Instrument must be 'ES' or 'NQ', got '{instrument}'")
        
        self.instrument = instrument
        self.ticker = "ES" if instrument == "ES" else "NQ"
        
        # Daily state tracking
        self.daily_trades: Dict[str, int] = {}  # date -> trade count
        self.daily_pnl: Dict[str, float] = {}  # date -> P&L in R units
        self.daily_wins: Dict[str, bool] = {}  # date -> True if won today
        
        # OR state (computed once per day after 9:45)
        self.or_state: Optional[Dict] = None  # {high, low, date, timestamp}
        
        # Breakout state (tracked after OR is known)
        self.breakout_state: Optional[Dict] = None  # {side, breakout_ts, E, acceptance_bars: List[Dict]}
        
        # Acceptance tracking (bars N+1 to N+3)
        self.acceptance_bars: List[Dict] = []  # List of {timestamp, high, low, close} for acceptance window
        
        # Diagnostic event logging
        self.diagnostic_events: List[Dict] = []  # List of state transition events
        self.enable_diagnostics: bool = False  # Set to True to enable event logging
        
        # Diagnostic: Track why breakouts die (Option A - research only)
        self.breakout_invalidations: List[Dict] = []  # Track invalidation reasons for each breakout
        
    def _get_price_data(self, ticker: str, start_date: str, end_date: str) -> pd.DataFrame:
        """Get price data as DataFrame."""
        prices = get_prices(ticker, start_date, end_date)
        if not prices:
            return pd.DataFrame()
        return prices_to_df(prices)
    
    def _identify_opening_range(self, df: pd.DataFrame, date: str) -> Optional[Dict]:
        """
        Identify opening range (9:30-9:45 = first 3 five-minute bars).
        
        Returns:
            {high, low, date, timestamp} or None
        """
        if len(df) == 0:
            return None
        
        # Check if data is intraday (has time component)
        is_intraday = isinstance(df.index[0], pd.Timestamp) and (
            hasattr(df.index[0], 'hour') or 
            (isinstance(df.index[0], str) and ' ' in str(df.index[0]))
        )
        
        if is_intraday:
            # Filter to OR window: 9:30-9:45 (first 3 five-minute bars)
            # OR window is bars at 9:30, 9:35, 9:40
            or_bars = []
            for idx, row in df.iterrows():
                ts = idx if isinstance(idx, pd.Timestamp) else pd.Timestamp(idx)
                if ts.hour == 9 and ts.minute in [30, 35, 40]:
                    or_bars.append(row)
            
            if len(or_bars) < 3:
                return None  # Need all 3 OR bars
            
            or_high = max(bar['high'] for bar in or_bars)
            or_low = min(bar['low'] for bar in or_bars)
            or_timestamp = pd.Timestamp(f"{date} 09:45:00")  # End of OR window
            
            return {
                'high': or_high,
                'low': or_low,
                'date': date,
                'timestamp': or_timestamp
            }
        else:
            # Daily data: use approximation (not ideal, but fallback)
            return None
    
    def _detect_breakout(self, df: pd.DataFrame, or_data: Dict, current_bar: pd.Series, current_ts: pd.Timestamp) -> Optional[Dict]:
        """
        Detect breakout: first bar whose high exceeds OR high (long) or low breaks OR low (short).
        
        Returns:
            {side, breakout_ts, E, breakout_bar} or None
        """
        if self.breakout_state is not None:
            return None  # Already have a breakout
        
        bar_high = current_bar['high']
        bar_low = current_bar['low']
        or_high = or_data['high']
        or_low = or_data['low']
        
        # Check for long breakout
        if bar_high > or_high:
            E = bar_high - or_high
            if E >= self.MIN_EXPANSION:
                return {
                    'side': 'long',
                    'breakout_ts': current_ts,
                    'E': E,
                    'breakout_bar': current_bar.copy()
                }
        
        # Check for short breakout
        if bar_low < or_low:
            E = or_low - bar_low
            if E >= self.MIN_EXPANSION:
                return {
                    'side': 'short',
                    'breakout_ts': current_ts,
                    'E': E,
                    'breakout_bar': current_bar.copy()
                }
        
        return None
    
    def _check_acceptance(self, or_data: Dict, breakout_state: Dict) -> Tuple[bool, Optional[str], Optional[Dict]]:
        """
        Check if acceptance condition is met using ROLLING WINDOW logic.
        
        Rolling acceptance: There exists at least ONE contiguous sequence of ≥2 bars
        within the acceptance window where retracement never exceeds 30% of expansion.
        
        This allows for one fast probe followed by stabilization/continuation.
        
        Returns:
            (is_accepted, reason, diagnostic_info)
        """
        if len(self.acceptance_bars) < 2:
            return (False, f"Need at least 2 acceptance bars, have {len(self.acceptance_bars)}", None)
        
        side = breakout_state['side']
        E = breakout_state['E']
        or_high = or_data['high']
        or_low = or_data['low']
        max_retrace = self.ACCEPTANCE_RETRACE_THRESHOLD * E
        
        # Calculate retracement ratio for each bar
        retracement_ratios = []
        for bar in self.acceptance_bars:
            if side == 'long':
                # Long: retrace = (OR_high - bar_low) / E
                retrace = (or_high - bar['low']) / E if E > 0 else 0
            else:  # short
                # Short: retrace = (bar_high - OR_low) / E
                retrace = (bar['high'] - or_low) / E if E > 0 else 0
            retracement_ratios.append(retrace)
        
        # Check for at least one contiguous subsequence of ≥2 bars where all retrace <= 0.30
        # Try all possible contiguous subsequences of length >= 2
        found_valid_sequence = False
        best_sequence_start = None
        best_sequence_length = 0
        
        for start_idx in range(len(retracement_ratios)):
            for end_idx in range(start_idx + 2, len(retracement_ratios) + 1):  # At least 2 bars
                subsequence = retracement_ratios[start_idx:end_idx]
                if all(rt <= self.ACCEPTANCE_RETRACE_THRESHOLD for rt in subsequence):
                    found_valid_sequence = True
                    sequence_length = end_idx - start_idx
                    if sequence_length > best_sequence_length:
                        best_sequence_start = start_idx
                        best_sequence_length = sequence_length
        
        diagnostic_info = {
            'retracement_ratios': retracement_ratios,
            'first_bar_retrace_pct': retracement_ratios[0] * 100 if len(retracement_ratios) > 0 else None,
            'found_valid_sequence': found_valid_sequence,
            'best_sequence_start': best_sequence_start,
            'best_sequence_length': best_sequence_length,
            'bars_to_acceptance': best_sequence_start + best_sequence_length if found_valid_sequence else None
        }
        
        if found_valid_sequence:
            return (True, f"Rolling acceptance confirmed: {best_sequence_length}-bar sequence starting at bar {best_sequence_start}", diagnostic_info)
        else:
            return (False, f"No valid contiguous sequence found: all subsequences violate retracement rule", diagnostic_info)
    
    def _check_invalidation(self, or_data: Dict, breakout_state: Dict, current_bar: pd.Series) -> bool:
        """
        Check if acceptance is invalidated during the acceptance window.
        
        Invalidation triggers:
        - Long: any bar low < OR_high - 0.30*E
        - Short: any bar high > OR_low + 0.30*E
        
        Returns:
            True if invalidated
        """
        side = breakout_state['side']
        E = breakout_state['E']
        or_high = or_data['high']
        or_low = or_data['low']
        max_retrace = self.ACCEPTANCE_RETRACE_THRESHOLD * E
        
        if side == 'long':
            if current_bar['low'] < (or_high - max_retrace):
                return True
        else:  # short
            if current_bar['high'] > (or_low + max_retrace):
                return True
        
        return False
    
    def _calculate_position_size(
        self, entry_price: float, stop_loss: float, account_value: float
    ) -> Tuple[int, float]:
        """
        Calculate position size based on risk.
        
        Risk ≤ 0.25% of account
        1 contract micros preferred (MES / MNQ) until funded
        
        Returns:
            (contracts, r_risk) - number of contracts and risk in R units
        """
        risk_per_contract = abs(entry_price - stop_loss)
        if risk_per_contract <= 0:
            return (0, 0.0)
        
        max_risk_dollars = account_value * self.RISK_PERCENT
        max_contracts = int(max_risk_dollars / risk_per_contract)
        
        # Use 1 contract minimum (micros)
        contracts = max(1, min(max_contracts, 1))  # Start with 1 contract
        
        r_risk = (risk_per_contract * contracts) / account_value if account_value > 0 else 0.0
        
        return (contracts, r_risk)
    
    def _check_daily_limits(self, date: str) -> Tuple[bool, str]:
        """
        Check daily trading limits.
        
        - Max trades per day: 1
        - Max loss per day: 0.5R
        - Max wins per day: 1 (stop after win)
        
        Returns:
            (allowed, reason)
        """
        trades_today = self.daily_trades.get(date, 0)
        if trades_today >= self.MAX_TRADES_PER_DAY:
            return (False, f"Max trades per day ({self.MAX_TRADES_PER_DAY}) reached")
        
        pnl_today = self.daily_pnl.get(date, 0.0)
        if pnl_today <= -self.MAX_LOSS_PER_DAY_R:
            return (False, f"Max daily loss ({self.MAX_LOSS_PER_DAY_R}R) reached")
        
        if self.daily_wins.get(date, False):
            return (False, "Already won today - stop trading")
        
        return (True, "Daily limits OK")
    
    def generate_signal(
        self, state: AgentState, date: str, account_value: float
    ) -> Dict[str, Dict]:
        """
        Generate trading signal based on acceptance continuation hypothesis.
        
        Entry logic:
        1. Identify OR (9:30-9:45)
        2. Detect breakout (first bar breaking OR)
        3. Track acceptance window (next 2 bars)
        4. Enter on close of bar N+2 if acceptance confirmed
        
        Returns:
            {ticker: {action, quantity, confidence, reasoning}} or {ticker: {action: "hold"}}
        """
        ticker = self.ticker
        
        # Reset state at start of new day
        if self.or_state is None or self.or_state.get('date') != date:
            self.or_state = None
            self.breakout_state = None
            self.acceptance_bars = []
        
        # Get price data
        df = self._get_price_data(ticker, date, date)
        if len(df) == 0:
            return {ticker: {"action": "hold", "quantity": 0, "confidence": 0, "reasoning": "No price data"}}
        
        # Check daily limits
        allowed, reason = self._check_daily_limits(date)
        if not allowed:
            return {
                ticker: {
                    "action": "hold",
                    "quantity": 0,
                    "confidence": 0,
                    "reasoning": f"Daily limit: {reason}"
                }
            }
        
        # Step 1: Identify OR (after 9:45 bar closes)
        if self.or_state is None:
            or_data = self._identify_opening_range(df, date)
            if or_data:
                # Check if we're past 9:45
                current_ts = df.index[-1] if len(df) > 0 else None
                if current_ts is not None:
                    ts = current_ts if isinstance(current_ts, pd.Timestamp) else pd.Timestamp(current_ts)
                    if ts.hour > 9 or (ts.hour == 9 and ts.minute >= 45):
                        self.or_state = or_data
            else:
                return {ticker: {"action": "hold", "quantity": 0, "confidence": 0, "reasoning": "Could not identify opening range"}}
        
        if self.or_state is None:
            return {ticker: {"action": "hold", "quantity": 0, "confidence": 0, "reasoning": "Waiting for OR to complete"}}
        
        # Step 2: Detect breakout (after OR is known, before acceptance window completes)
        current_bar = df.iloc[-1]
        current_ts = df.index[-1] if isinstance(df.index[-1], pd.Timestamp) else pd.Timestamp(df.index[-1])
        
        # Only detect breakout if we're past OR window and don't have one yet
        if self.breakout_state is None:
            if current_ts > self.or_state['timestamp']:
                breakout = self._detect_breakout(df, self.or_state, current_bar, current_ts)
                if breakout:
                    # Log breakout event
                    if self.enable_diagnostics:
                        self.diagnostic_events.append({
                            'date': date,
                            'timestamp': current_ts,
                            'event_type': 'breakout_detected',
                            'side': breakout['side'],
                            'or_high': self.or_state['high'],
                            'or_low': self.or_state['low'],
                            'breakout_price': breakout['breakout_bar']['high'] if breakout['side'] == 'long' else breakout['breakout_bar']['low'],
                            'expansion_distance': breakout['E'],
                            'bars_since_breakout': 0,
                            'retrace_pct': None,
                            'decision': 'breakout_set'
                        })
                    
                    # Track invalidation reason for this breakout (Option A diagnostic)
                    if self.enable_diagnostics and self.breakout_state is not None:
                        # Previous breakout was overwritten
                        prev_breakout_ts = self.breakout_state['breakout_ts']
                        bars_until_invalidation = len(self.acceptance_bars)
                        self.breakout_invalidations.append({
                            'date': date,
                            'breakout_timestamp': prev_breakout_ts,
                            'side': self.breakout_state['side'],
                            'expansion_distance': self.breakout_state['E'],
                            'bars_until_invalidation': bars_until_invalidation,
                            'invalidation_reason': 'overwritten_by_new_breakout',
                            'invalidation_timestamp': current_ts
                        })
                    
                    self.breakout_state = breakout
                    self.acceptance_bars = []  # Reset acceptance tracking
                    # Don't enter yet - wait for acceptance window
        
        if self.breakout_state is None:
            return {ticker: {"action": "hold", "quantity": 0, "confidence": 0, "reasoning": "Waiting for breakout"}}
        
        # Step 3: Track acceptance window (bars N+1 to N+3 after breakout)
        breakout_ts = self.breakout_state['breakout_ts']
        
        # Only track bars AFTER the breakout bar
        if current_ts > breakout_ts:
            # Count how many bars have passed since breakout
            bars_after_breakout = df[df.index > breakout_ts]
            bars_count = len(bars_after_breakout)
            
            # Check if we're still within acceptance window (next N bars after breakout)
            if bars_count <= self.ACCEPTANCE_BARS:
                # ROLLING ACCEPTANCE: Don't invalidate early - allow bars that violate 30% rule
                # as long as we can find a valid subsequence later
                # Add current bar to acceptance tracking (if not already added)
                # Use timestamp to avoid duplicates
                bar_already_tracked = any(
                    tracked['timestamp'] == current_ts for tracked in self.acceptance_bars
                )
                if not bar_already_tracked:
                    self.acceptance_bars.append({
                        'timestamp': current_ts,
                        'high': current_bar['high'],
                        'low': current_bar['low'],
                        'close': current_bar['close']
                    })
                
                # Check if we have enough bars to evaluate rolling acceptance (need at least 2)
                # Also check if we've reached the acceptance window limit
                if len(self.acceptance_bars) >= 2:
                    # Check acceptance condition (rolling window logic)
                    is_accepted, reason, diagnostic_info = self._check_acceptance(self.or_state, self.breakout_state)
                    
                    # If acceptance passed, enter immediately (don't wait for full window)
                    # If acceptance hasn't passed yet and we're still within window, continue tracking
                    # If we've exhausted the window and still no acceptance, fail
                    if is_accepted:
                        # Acceptance confirmed - proceed to entry
                        pass  # Will be handled below
                    elif len(self.acceptance_bars) >= self.ACCEPTANCE_BARS:
                        # Window exhausted without acceptance - fail
                        is_accepted = False
                        reason = f"Acceptance window exhausted: no valid sequence found"
                    else:
                        # Still within window, continue tracking
                        return {ticker: {"action": "hold", "quantity": 0, "confidence": 0, "reasoning": f"Tracking rolling acceptance: {len(self.acceptance_bars)}/{self.ACCEPTANCE_BARS} bars"}}
                    
                    # Log acceptance evaluation event (rolling window)
                    if self.enable_diagnostics:
                        side = self.breakout_state['side']
                        E = self.breakout_state['E']
                        or_high = self.or_state['high']
                        or_low = self.or_state['low']
                        
                        # Use diagnostic info from rolling acceptance check
                        first_bar_retrace = diagnostic_info.get('first_bar_retrace_pct') if diagnostic_info else None
                        bars_to_acceptance = diagnostic_info.get('bars_to_acceptance') if diagnostic_info else None
                        
                        self.diagnostic_events.append({
                            'date': date,
                            'timestamp': current_ts,
                            'event_type': 'acceptance_evaluated',
                            'side': side,
                            'or_high': or_high,
                            'or_low': or_low,
                            'breakout_price': self.breakout_state['breakout_bar']['high'] if side == 'long' else self.breakout_state['breakout_bar']['low'],
                            'expansion_distance': E,
                            'bars_since_breakout': len(self.acceptance_bars),
                            'retrace_pct': first_bar_retrace,
                            'decision': 'acceptance_pass' if is_accepted else 'acceptance_fail',
                            'reason': reason,
                            'rolling_acceptance': True,
                            'bars_to_acceptance': bars_to_acceptance,
                            'retracement_ratios': str(diagnostic_info.get('retracement_ratios', [])) if diagnostic_info else None
                        })
                    
                    if is_accepted:
                        # ENTRY: Enter on close of current bar (rolling acceptance confirmed)
                        side = self.breakout_state['side']
                        entry_price = current_bar['close']
                        E = self.breakout_state['E']
                        
                        # Calculate stop (acceptance floor/ceiling)
                        if side == 'long':
                            stop_loss = self.or_state['high'] - (self.ACCEPTANCE_RETRACE_THRESHOLD * E)
                        else:  # short
                            stop_loss = self.or_state['low'] + (self.ACCEPTANCE_RETRACE_THRESHOLD * E)
                        
                        # Calculate target (1.5R)
                        r_risk = abs(entry_price - stop_loss)
                        if side == 'long':
                            target = entry_price + (r_risk * self.MAX_RISK_REWARD)
                        else:  # short
                            target = entry_price - (r_risk * self.MAX_RISK_REWARD)
                        
                        # Calculate position size
                        contracts, r_risk_pct = self._calculate_position_size(entry_price, stop_loss, account_value)
                        
                        if contracts > 0:
                            # Log entry emitted event
                            if self.enable_diagnostics:
                                self.diagnostic_events.append({
                                    'date': date,
                                    'timestamp': current_ts,
                                    'event_type': 'entry_emitted',
                                    'side': side,
                                    'or_high': self.or_state['high'],
                                    'or_low': self.or_state['low'],
                                    'breakout_price': self.breakout_state['breakout_bar']['high'] if side == 'long' else self.breakout_state['breakout_bar']['low'],
                                    'expansion_distance': E,
                                    'bars_since_breakout': self.ACCEPTANCE_BARS,
                                    'retrace_pct': None,
                                    'decision': 'entry_emitted',
                                    'entry_price': entry_price,
                                    'stop_loss': stop_loss,
                                    'target': target,
                                    'quantity': contracts
                                })
                            
                            # Reset breakout state after entry
                            self.breakout_state = None
                            self.acceptance_bars = []
                            
                            # Update daily trade count
                            self.daily_trades[date] = self.daily_trades.get(date, 0) + 1
                            
                            action = "buy" if side == "long" else "short"
                            reasoning = (
                                f"Acceptance Continuation ({side.upper()}): "
                                f"Entry ${entry_price:.2f}, Stop ${stop_loss:.2f}, "
                                f"Target ${target:.2f}, Risk {r_risk_pct:.2%}, "
                                f"Expansion E={E:.2f}, Acceptance confirmed"
                            )
                            
                            return {
                                ticker: {
                                    "action": action,
                                    "quantity": contracts,
                                    "confidence": 75,
                                    "reasoning": reasoning
                                }
                            }
                    else:
                        # Acceptance failed - reset
                        # Track invalidation reason (Option A diagnostic)
                        if self.enable_diagnostics:
                            breakout_ts = self.breakout_state['breakout_ts']
                            bars_until_invalidation = len(self.acceptance_bars)
                            self.breakout_invalidations.append({
                                'date': date,
                                'breakout_timestamp': breakout_ts,
                                'side': self.breakout_state['side'],
                                'expansion_distance': self.breakout_state['E'],
                                'bars_until_invalidation': bars_until_invalidation,
                                'invalidation_reason': 'acceptance_failed',
                                'invalidation_timestamp': current_ts,
                                'failure_reason': reason
                            })
                        
                        self.breakout_state = None
                        self.acceptance_bars = []
                        return {ticker: {"action": "hold", "quantity": 0, "confidence": 0, "reasoning": f"Acceptance failed: {reason}"}}
                else:
                    # Still collecting acceptance bars
                    return {ticker: {"action": "hold", "quantity": 0, "confidence": 0, "reasoning": f"Tracking acceptance: {len(self.acceptance_bars)}/{self.ACCEPTANCE_BARS} bars"}}
            else:
                # Past acceptance window without entry - reset
                # Track invalidation reason (Option A diagnostic)
                if self.enable_diagnostics and self.breakout_state is not None:
                    breakout_ts = self.breakout_state['breakout_ts']
                    bars_until_invalidation = len(self.acceptance_bars)
                    self.breakout_invalidations.append({
                        'date': date,
                        'breakout_timestamp': breakout_ts,
                        'side': self.breakout_state['side'],
                        'expansion_distance': self.breakout_state['E'],
                        'bars_until_invalidation': bars_until_invalidation,
                        'invalidation_reason': 'window_expired',
                        'invalidation_timestamp': current_ts
                    })
                
                self.breakout_state = None
                self.acceptance_bars = []
                return {ticker: {"action": "hold", "quantity": 0, "confidence": 0, "reasoning": "Acceptance window expired without entry"}}
        
        return {ticker: {"action": "hold", "quantity": 0, "confidence": 0, "reasoning": "Processing breakout"}}
