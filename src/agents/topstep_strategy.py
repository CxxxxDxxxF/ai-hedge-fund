"""
Topstep-Optimized Single Setup Strategy

ES / NQ — One Trade Max — Survival First

Core Philosophy:
- You are not trading to make money
- You are trading to not violate rules until you pass
- If the system skips 70-90% of days, takes 1 trade max, exits early, feels boring → That's correct
"""

from __future__ import annotations

from datetime import datetime, time
from typing import Dict, List, Optional, Tuple
import pandas as pd
import numpy as np

from src.tools.api import get_prices, prices_to_df
from src.graph.state import AgentState


class TopstepStrategy:
    """Topstep-optimized opening range break + pullback continuation strategy."""
    
    # Strategy parameters
    RISK_PERCENT = 0.0025  # 0.25% of account per trade
    MAX_RISK_REWARD = 1.5  # 1.5R max profit
    PARTIAL_PROFIT_R = 1.0  # Take partial profit at 1R
    MAX_TRADES_PER_DAY = 1
    MAX_LOSS_PER_DAY_R = 0.5  # Max 0.5R loss per day
    OR_MINUTES = 15  # Opening range: first 15 minutes (9:30-9:45)
    TRADING_WINDOW_END = 60  # Trading window ends at 10:30 (60 minutes after open)
    
    # Market regime filter parameters
    ATR_PERIOD = 14
    ATR_LOOKBACK_DAYS = 20  # 20-day median for ATR filter
    
    def __init__(self, instrument: str = "ES"):
        """
        Initialize Topstep strategy.
        
        Args:
            instrument: "ES" (E-mini S&P 500) or "NQ" (E-mini NASDAQ-100)
        """
        if instrument not in ["ES", "NQ"]:
            raise ValueError(f"Instrument must be 'ES' or 'NQ', got '{instrument}'")
        
        self.instrument = instrument
        self.ticker = "ES" if instrument == "ES" else "NQ"  # Use ticker symbol
        
        # Daily state tracking
        self.daily_trades: Dict[str, int] = {}  # date -> trade count
        self.daily_pnl: Dict[str, float] = {}  # date -> P&L in R units
        self.daily_wins: Dict[str, bool] = {}  # date -> True if won today
        
        # Position tracking
        self.current_position: Optional[Dict] = None  # {ticker, side, entry_price, stop_loss, target, size, r_risk}
        self.opening_range: Optional[Dict] = None  # {high, low, date}
        
        # Breakout state tracking (for pullback evaluation)
        self.breakout_state: Optional[Dict] = None  # {bar_timestamp, side, high, low, range, date}
        
    def _get_price_data(self, ticker: str, start_date: str, end_date: str) -> pd.DataFrame:
        """Get price data as DataFrame."""
        prices = get_prices(ticker, start_date, end_date)
        if not prices:
            return pd.DataFrame()
        return prices_to_df(prices)
    
    def _is_near_engulfing(
        self, prev: pd.Series, cur: pd.Series, side: str, overlap_threshold: float = 0.80
    ) -> bool:
        """
        Check for near-engulfing pattern (relaxed engulfing with body overlap requirement).
        
        For LONG:
        - Previous candle is bearish or neutral (prev_close <= prev_open)
        - Current candle is bullish or neutral (cur_close >= cur_open)
        - Current body overlaps prior body by at least overlap_threshold (default 80%)
        
        For SHORT:
        - Previous candle is bullish or neutral (prev_close >= prev_open)
        - Current candle is bearish or neutral (cur_close <= cur_open)
        - Current body overlaps prior body by at least overlap_threshold (default 80%)
        
        Args:
            prev: Previous candle (pd.Series with open, high, low, close)
            cur: Current candle (pd.Series with open, high, low, close)
            side: "long" or "short"
            overlap_threshold: Minimum body overlap percentage (default 0.80 = 80%)
        
        Returns:
            True if near-engulfing pattern detected
        """
        if side == "long":
            # Previous candle should be bearish or neutral
            if prev['close'] > prev['open']:
                return False
            # Current candle should be bullish or neutral
            if cur['close'] < cur['open']:
                return False
        else:  # short
            # Previous candle should be bullish or neutral
            if prev['close'] < prev['open']:
                return False
            # Current candle should be bearish or neutral
            if cur['close'] > cur['open']:
                return False
        
        # Calculate body overlap
        prev_body_low = min(prev['open'], prev['close'])
        prev_body_high = max(prev['open'], prev['close'])
        cur_body_low = min(cur['open'], cur['close'])
        cur_body_high = max(cur['open'], cur['close'])
        
        prev_body_size = prev_body_high - prev_body_low
        
        # If previous body has zero size, cannot have overlap
        if prev_body_size <= 0:
            return False
        
        # Calculate overlap
        overlap = max(0.0, min(prev_body_high, cur_body_high) - max(prev_body_low, cur_body_low))
        overlap_pct = overlap / prev_body_size
        
        return overlap_pct >= overlap_threshold
    
    def _calculate_atr(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        """Calculate Average True Range (ATR)."""
        if len(df) < period + 1:
            return pd.Series(dtype=float)
        
        high = df['high']
        low = df['low']
        close = df['close']
        
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean()
        
        return atr
    
    def _check_market_regime(self, df: pd.DataFrame, current_date: str) -> Tuple[bool, str]:
        """
        Market Regime Filter (non-negotiable).
        
        Trade ONLY if:
        1. Opening range (first 15 min) breaks AND holds
        2. ATR(14) on 5-min is above its 20-day median
        3. No major economic release in next 30 min (simplified: always pass for now)
        
        Returns:
            (pass, reason) - pass=True if all filters pass
        """
        if len(df) < self.ATR_LOOKBACK_DAYS + 1:
            return (False, "Insufficient data for regime filter")
        
        # Filter 2: ATR(14) must be above 20-day median
        atr = self._calculate_atr(df, self.ATR_PERIOD)
        if len(atr) < self.ATR_LOOKBACK_DAYS:
            return (False, "Insufficient data for ATR calculation")
        
        # Get last 20 days of ATR
        recent_atr = atr.tail(self.ATR_LOOKBACK_DAYS)
        if len(recent_atr) < self.ATR_LOOKBACK_DAYS:
            return (False, "Insufficient ATR history")
        
        current_atr = atr.iloc[-1]
        median_atr = recent_atr.median()
        
        if pd.isna(current_atr) or pd.isna(median_atr):
            return (False, "ATR calculation returned NaN")
        
        if current_atr <= median_atr:
            return (False, f"ATR ({current_atr:.2f}) not above 20-day median ({median_atr:.2f})")
        
        # Filter 3: Economic releases (simplified - always pass for now)
        # In production, you'd check an economic calendar
        
        # Filter 1 will be checked during setup identification
        return (True, "Market regime filters passed")
    
    def _identify_opening_range(self, df: pd.DataFrame, current_date: str) -> Optional[Dict]:
        """
        Define the Opening Range (9:30-9:45).
        
        Uses actual 9:30-9:45 bars if intraday data is available.
        Falls back to daily approximation if only daily data.
        """
        if len(df) < 1:
            return None
        
        # Check if we have intraday data (timestamps have time components)
        sample_ts = df.index[0]
        has_intraday = hasattr(sample_ts, 'hour') and (sample_ts.hour > 0 or sample_ts.minute > 0)
        
        if has_intraday:
            # Use actual 9:30-9:45 bars
            # Filter to current date
            current_date_obj = pd.Timestamp(current_date)
            bars_today = df[df.index.date == current_date_obj.date()]
            
            if len(bars_today) == 0:
                return None
            
            # Filter to opening range: 9:30-9:45 (first 15 minutes = 3 bars at 5-min resolution)
            or_bars = bars_today[
                (bars_today.index.hour == 9) & 
                (bars_today.index.minute >= 30) & 
                (bars_today.index.minute <= 45)
            ]
            
            if len(or_bars) == 0:
                return None
            
            # OR High = highest high in OR period
            # OR Low = lowest low in OR period
            or_high = or_bars['high'].max()
            or_low = or_bars['low'].min()
            or_open = or_bars.iloc[0]['open']  # First bar's open
            
            if or_high <= or_low:
                return None
            
            return {
                'high': or_high,
                'low': or_low,
                'date': current_date,
                'open': or_open,
            }
        else:
            # Fallback: Daily data approximation
            if len(df) < 2:
                return None
            
            current_day = df.iloc[-1]
            
            # Simulate opening range using first portion of day's range
            day_range_high = current_day['high'] - current_day['open']
            day_range_low = current_day['open'] - current_day['low']
            
            or_high = current_day['open'] + (day_range_high * 0.25)
            or_low = current_day['open'] - (day_range_low * 0.25)
            
            if or_high <= or_low:
                return None
            
            return {
                'high': or_high,
                'low': or_low,
                'date': current_date,
                'open': current_day['open'],
            }
    
    def _check_break_and_acceptance(
        self, df: pd.DataFrame, or_data: Dict, side: str
    ) -> Tuple[bool, Optional[Dict]]:
        """
        Check if price breaks OR level.
        
        Records breakout state for pullback evaluation on subsequent bars.
        
        Args:
            df: Price DataFrame
            or_data: Opening range data {high, low, open}
            side: "long" or "short"
        
        Returns:
            (break_confirmed, breakout_candle_data)
        """
        if len(df) < 1:
            return (False, None)
        
        current = df.iloc[-1]
        breakout_bar_timestamp = df.index[-1]  # Timestamp of current (breakout) bar
        
        if side == "long":
            # For long: price must break OR High
            if current['high'] > or_data['high']:
                breakout_range = current['high'] - current['low']
                # Record breakout state for pullback evaluation
                self.breakout_state = {
                    'bar_timestamp': breakout_bar_timestamp,
                    'side': side,
                    'high': current['high'],
                    'low': current['low'],
                    'range': breakout_range,
                    'date': or_data.get('date'),
                }
                return (True, {
                    'candle': current,
                    'breakout_price': or_data['high'],
                    'breakout_candle_high': current['high'],
                    'breakout_candle_low': current['low'],
                    'breakout_candle_close': current['close'],
                })
        else:  # short
            # For short: price must break OR Low
            if current['low'] < or_data['low']:
                breakout_range = current['high'] - current['low']
                # Record breakout state for pullback evaluation
                self.breakout_state = {
                    'bar_timestamp': breakout_bar_timestamp,
                    'side': side,
                    'high': current['high'],
                    'low': current['low'],
                    'range': breakout_range,
                    'date': or_data.get('date'),
                }
                return (True, {
                    'candle': current,
                    'breakout_price': or_data['low'],
                    'breakout_candle_high': current['high'],
                    'breakout_candle_low': current['low'],
                    'breakout_candle_close': current['close'],
                })
        
        return (False, None)
    
    def _check_pullback_entry(
        self, df: pd.DataFrame, breakout_data: Dict, side: str, or_data: Dict
    ) -> Tuple[bool, Optional[Dict]]:
        """
        Check for pullback entry after breakout.
        
        After the break:
        - Wait for price to pull back 50-70% of breakout candle
        - Enter ONLY on bullish/bearish engulfing OR strong close in direction of trend
        
        Only evaluates on bars AFTER the breakout bar.
        
        Returns:
            (entry_signal, entry_data)
        """
        if len(df) < 2:
            return (False, None)
        
        current_bar_timestamp = df.index[-1]
        
        # Check if we have a valid breakout state
        if self.breakout_state is None:
            return (False, None)
        
        # Only evaluate pullback on bars AFTER the breakout bar (using timestamp comparison)
        breakout_timestamp = self.breakout_state['bar_timestamp']
        if current_bar_timestamp <= breakout_timestamp:
            return (False, None)
        
        # Verify breakout state matches current side
        if self.breakout_state['side'] != side:
            return (False, None)
        
        current = df.iloc[-1]
        prev = df.iloc[-2]
        
        # Use breakout state data (recorded at breakout time)
        breakout_high = self.breakout_state['high']
        breakout_low = self.breakout_state['low']
        breakout_range = self.breakout_state['range']
        
        if side == "long":
            # Pullback: price should retrace 50-70% of breakout candle
            pullback_target_low = breakout_low + (breakout_range * 0.5)
            pullback_target_high = breakout_low + (breakout_range * 0.7)
            
            # Check if current candle is in pullback zone
            if current['low'] <= pullback_target_high and current['low'] >= pullback_target_low:
                # Check for bullish engulfing, near-engulfing, or strong close
                is_bullish_engulfing = (
                    current['open'] < prev['close'] and
                    current['close'] > prev['open'] and
                    current['close'] > current['open']
                )
                is_near_engulfing = self._is_near_engulfing(prev, current, side, overlap_threshold=0.80)
                is_strong_close = current['close'] > (current['high'] + current['low']) / 2
                
                # Determine confirmation type for diagnostic
                if is_bullish_engulfing:
                    confirm_type = "engulf"
                elif is_near_engulfing:
                    confirm_type = "near_engulf"
                elif is_strong_close:
                    confirm_type = "strongclose"
                else:
                    confirm_type = "none"
                
                if is_bullish_engulfing or is_near_engulfing or is_strong_close:
                    return (True, {
                        'entry_price': current['close'],
                        'stop_loss': current['low'] - (current['high'] - current['low']) * 0.1,  # 10% below low
                        'entry_candle': current,
                        'confirm_type': confirm_type,  # Diagnostic tag
                    })
        else:  # short
            # Pullback: price should retrace 50-70% of breakout candle
            pullback_target_low = breakout_high - (breakout_range * 0.7)
            pullback_target_high = breakout_high - (breakout_range * 0.5)
            
            # Check if current candle is in pullback zone
            if current['high'] >= pullback_target_low and current['high'] <= pullback_target_high:
                # Check for bearish engulfing, near-engulfing, or strong close
                is_bearish_engulfing = (
                    current['open'] > prev['close'] and
                    current['close'] < prev['open'] and
                    current['close'] < current['open']
                )
                is_near_engulfing = self._is_near_engulfing(prev, current, side, overlap_threshold=0.80)
                is_strong_close = current['close'] < (current['high'] + current['low']) / 2
                
                # Determine confirmation type for diagnostic
                if is_bearish_engulfing:
                    confirm_type = "engulf"
                elif is_near_engulfing:
                    confirm_type = "near_engulf"
                elif is_strong_close:
                    confirm_type = "strongclose"
                else:
                    confirm_type = "none"
                
                if is_bearish_engulfing or is_near_engulfing or is_strong_close:
                    return (True, {
                        'entry_price': current['close'],
                        'stop_loss': current['high'] + (current['high'] - current['low']) * 0.1,  # 10% above high
                        'entry_candle': current,
                        'confirm_type': confirm_type,  # Diagnostic tag
                    })
        
        return (False, None)
    
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
        self, state: Dict, date: str, account_value: float
    ) -> Dict[str, any]:
        """
        Generate Topstep trading signal for the day.
        
        Args:
            state: State dict with 'data' key containing 'end_date' and 'tickers'
            date: Current trading date
            account_value: Current account value
        
        Returns decision dict compatible with portfolio manager format.
        """
        ticker = self.ticker
        # Get end_date from state, fallback to date if not available
        end_date = state.get("data", {}).get("end_date", date)
        start_date = (datetime.strptime(end_date, "%Y-%m-%d") - pd.Timedelta(days=30)).strftime("%Y-%m-%d")
        
        # Get price data
        df = self._get_price_data(ticker, start_date, end_date)
        if df.empty or len(df) < 2:
            return {
                ticker: {
                    "action": "hold",
                    "quantity": 0,
                    "confidence": 0,
                    "reasoning": "Insufficient price data"
                }
            }
        
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
        
        # Market regime filter
        regime_ok, regime_reason = self._check_market_regime(df, date)
        if not regime_ok:
            return {
                ticker: {
                    "action": "hold",
                    "quantity": 0,
                    "confidence": 0,
                    "reasoning": f"Market regime filter: {regime_reason}"
                }
            }
        
        # Identify opening range
        or_data = self._identify_opening_range(df, date)
        if not or_data:
            return {
                ticker: {
                    "action": "hold",
                    "quantity": 0,
                    "confidence": 0,
                    "reasoning": "Could not identify opening range"
                }
            }
        
        # Reset breakout state at start of new day (if date changed)
        if self.breakout_state and self.breakout_state.get('date') != date:
            self.breakout_state = None
        
        # If we already have a breakout state, check for pullback on subsequent bars
        if self.breakout_state:
            side = self.breakout_state['side']
            # Reconstruct breakout_data for pullback check
            breakout_data = {
                'candle': pd.Series({
                    'high': self.breakout_state['high'],
                    'low': self.breakout_state['low'],
                    'close': self.breakout_state.get('close', self.breakout_state['high']),
                }),
                'breakout_price': or_data['high'] if side == "long" else or_data['low'],
            }
            # Check for pullback entry (only on bars after breakout)
            entry_signal, entry_data = self._check_pullback_entry(df, breakout_data, side, or_data)
            
            if entry_signal:
                # Reset breakout state after successful entry
                self.breakout_state = None
                
                # Calculate position size
                entry_price = entry_data['entry_price']
                stop_loss = entry_data['stop_loss']
                contracts, r_risk = self._calculate_position_size(entry_price, stop_loss, account_value)
                
                if contracts > 0:
                    # Calculate target (1.5R max)
                    risk = abs(entry_price - stop_loss)
                    target = entry_price + (risk * self.MAX_RISK_REWARD) if side == "long" else entry_price - (risk * self.MAX_RISK_REWARD)
                    
                    # Store position info
                    self.current_position = {
                        'ticker': ticker,
                        'side': side,
                        'entry_price': entry_price,
                        'stop_loss': stop_loss,
                        'target': target,
                        'size': contracts,
                        'r_risk': r_risk,
                        'date': date,
                    }
                    
                    # Convert to portfolio manager format
                    action = "buy" if side == "long" else "short"
                    
                    return {
                        ticker: {
                            "action": action,
                            "quantity": contracts,
                            "confidence": 75,
                            "reasoning": (
                                f"Topstep OR Break + Pullback ({side.upper()}): "
                                f"Entry ${entry_price:.2f}, Stop ${stop_loss:.2f}, "
                                f"Target ${target:.2f}, Risk {r_risk:.2%}, "
                                f"Regime: {regime_reason}"
                            )
                        }
                    }
        else:
            # No existing breakout state - check for new breakouts (try both directions)
            for side in ["long", "short"]:
                break_confirmed, breakout_data = self._check_break_and_acceptance(df, or_data, side)
                
                if break_confirmed:
                    # Breakout detected - state is now set, but don't check pullback on same bar
                    # Pullback will be checked on subsequent bars
                    break  # Exit loop after first breakout detected
                
                if entry_signal:
                    # Reset breakout state after successful entry
                    self.breakout_state = None
                    # Calculate position size
                    entry_price = entry_data['entry_price']
                    stop_loss = entry_data['stop_loss']
                    contracts, r_risk = self._calculate_position_size(entry_price, stop_loss, account_value)
                    
                    if contracts > 0:
                        # Calculate target (1.5R max)
                        risk = abs(entry_price - stop_loss)
                        target = entry_price + (risk * self.MAX_RISK_REWARD) if side == "long" else entry_price - (risk * self.MAX_RISK_REWARD)
                        
                        # Store position info
                        self.current_position = {
                            'ticker': ticker,
                            'side': side,
                            'entry_price': entry_price,
                            'stop_loss': stop_loss,
                            'target': target,
                            'size': contracts,
                            'r_risk': r_risk,
                            'date': date,
                        }
                        
                        # Convert to portfolio manager format
                        action = "buy" if side == "long" else "short"
                        
                        # Add confirmation type to reasoning if available
                        confirm_type = entry_data.get('confirm_type', 'unknown')
                        reasoning = (
                            f"Topstep OR Break + Pullback ({side.upper()}): "
                            f"Entry ${entry_price:.2f}, Stop ${stop_loss:.2f}, "
                            f"Target ${target:.2f}, Risk {r_risk:.2%}, "
                            f"Regime: {regime_reason}, confirm={confirm_type}"
                        )
                        
                        return {
                            ticker: {
                                "action": action,
                                "quantity": contracts,
                                "confidence": 75,
                                "reasoning": reasoning
                            }
                        }
        
        # No setup found
        return {
            ticker: {
                "action": "hold",
                "quantity": 0,
                "confidence": 0,
                "reasoning": "No valid setup - system correctly refusing to trade"
            }
        }
    
    def update_daily_state(self, date: str, pnl: float, won: bool = False):
        """Update daily tracking state."""
        if date not in self.daily_trades:
            self.daily_trades[date] = 0
            self.daily_pnl[date] = 0.0
            self.daily_wins[date] = False
        
        self.daily_trades[date] += 1
        self.daily_pnl[date] += pnl
        if won:
            self.daily_wins[date] = True


def topstep_strategy_agent(state: AgentState, agent_id: str = "topstep_strategy_agent") -> AgentState:
    """
    Topstep-optimized strategy agent.
    
    This agent implements the Topstep single setup strategy:
    - Opening Range Break + Pullback Continuation
    - Strict risk management (0.25% risk, 1.5R max)
    - One trade max per day
    - Market regime filters
    """
    from src.utils.progress import progress
    
    data = state["data"]
    tickers = data["tickers"]
    end_date = data["end_date"]
    portfolio = data["portfolio"]
    
    # Initialize strategy (default to ES)
    instrument = "ES"  # Can be made configurable
    strategy = TopstepStrategy(instrument=instrument)
    
    # Calculate account value
    # For simplicity, use cash + positions value
    account_value = portfolio.get("cash", 100000.0)
    
    # Get current date (use end_date as proxy for "today")
    current_date = end_date
    
    # Generate signal
    progress.update_status(agent_id, None, "Generating Topstep signal")
    decisions = strategy.generate_signal(state, current_date, account_value)
    
    # Store decisions in state
    if "analyst_signals" not in state["data"]:
        state["data"]["analyst_signals"] = {}
    
    state["data"]["analyst_signals"][agent_id] = {
        ticker: {
            "signal": "bullish" if d.get("action") == "buy" else "bearish" if d.get("action") == "short" else "neutral",
            "confidence": d.get("confidence", 0),
            "reasoning": d.get("reasoning", "")
        }
        for ticker, d in decisions.items()
    }
    
    # Store portfolio decisions
    if "portfolio_decisions" not in state["data"]:
        state["data"]["portfolio_decisions"] = {}
    
    state["data"]["portfolio_decisions"].update(decisions)
    
    progress.update_status(agent_id, None, "Done")
    
    return state
