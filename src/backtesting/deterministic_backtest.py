"""
Deterministic Backtest Runner for 5-Core-Agent System

Runs backtests using only rule-based logic (no LLMs).
Tracks performance metrics and agent contributions.

ENFORCES DETERMINISM: Identical inputs produce identical outputs.
"""

from __future__ import annotations

import os
import sys
import hashlib
import json
import random
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from collections import defaultdict

import pandas as pd
from dateutil.relativedelta import relativedelta

from src.main import run_hedge_fund
from src.tools.api import get_price_data, get_prices
from src.utils.analysts import ANALYST_CONFIG
from src.backtesting.edge_analysis import EdgeAnalysis
from src.backtesting.regime_analysis import RegimeAnalysis
from src.data.price_cache import get_price_cache
from src.agents.topstep_strategy import TopstepStrategy
from src.agents.acceptance_continuation_strategy import AcceptanceContinuationStrategy
from src.communication.contracts import validate_portfolio_decision


# Force deterministic mode
os.environ["HEDGEFUND_NO_LLM"] = "1"

# HARDENING: Use centralized determinism initializer
from src.utils.deterministic_guard import initialize_determinism
DETERMINISTIC_SEED = 42
initialize_determinism(DETERMINISTIC_SEED)


class DeterministicBacktest:
    """Deterministic backtest runner for 5-core-agent system."""

    # Core agents to track (using canonical registry keys)
    # Note: Signals are stored with "_agent" suffix in analyst_signals, but we use registry keys for selection
    CORE_AGENTS = {
        "warren_buffett": "Value",
        "peter_lynch": "Growth",
        "aswath_damodaran": "Valuation",
        "momentum": "Momentum",
        "mean_reversion": "Mean Reversion",
    }
    
    # Map registry keys to node names (for looking up signals in analyst_signals)
    AGENT_NODE_NAMES = {
        "warren_buffett": "warren_buffett_agent",
        "peter_lynch": "peter_lynch_agent",
        "aswath_damodaran": "aswath_damodaran_agent",
        "momentum": "momentum_agent",
        "mean_reversion": "mean_reversion_agent",
    }

    def __init__(
        self,
        tickers: List[str],
        start_date: str,
        end_date: str,
        initial_capital: float = 100000.0,
        margin_requirement: float = 0.0,
        disable_progress: bool = True,  # Default: disable progress rendering in backtests
        snapshot_dir: Optional[str] = None,  # Directory for state snapshots
        commission_per_trade: float = 0.0,  # Commission per trade (dollars)
        slippage_bps: float = 0.0,  # Slippage in basis points (0.01% per bps)
        spread_bps: float = 0.0,  # Spread in basis points (0.01% per bps)
    ):
        self.tickers = tickers
        self.start_date = start_date
        self.end_date = end_date
        self.initial_capital = initial_capital
        self.margin_requirement = margin_requirement
        self.disable_progress = disable_progress
        self.snapshot_dir = snapshot_dir
        
        # Execution friction (deterministic)
        self.commission_per_trade = commission_per_trade
        self.slippage_bps = slippage_bps
        self.spread_bps = spread_bps
        
        # Friction tracking
        self.total_commissions = 0.0
        self.total_slippage_cost = 0.0

        # Active positions with stops/targets (for intraday execution)
        # Format: {ticker: {side: "long"/"short", entry_price: float, stop_loss: float, target: float, quantity: int, entry_bar: timestamp, mfe: float, mae: float, confirm_type: str, bars_since_entry: int}}
        self.active_positions: Dict[str, Optional[Dict]] = {ticker: None for ticker in tickers}
        
        # Time-based invalidation parameters
        self.TIME_INVALIDATION_BARS = 5  # Exit if +0.5R MFE not reached within N bars
        self.TIME_INVALIDATION_MFE_THRESHOLD = 0.5  # MFE threshold in R units
        
        # R-multiple trade log (for detailed analysis)
        # Format: List of dicts with entry_price, stop_loss, target, exit_price, mfe, mae, r_multiple, confirm_type, etc.
        self.r_trade_log: List[Dict] = []
        
        # Daily state tracking (for TopstepStrategy daily limits)
        self.current_day: Optional[str] = None
        self.trades_today: Dict[str, int] = {}  # date -> trade count
        self.pnl_today: Dict[str, float] = {}  # date -> PnL in dollars
        
        # Current bar timestamp (for trade recording)
        self._current_bar_timestamp: Optional[pd.Timestamp] = None

        # Portfolio state
        self.portfolio = {
            "cash": initial_capital,
            "margin_requirement": margin_requirement,
            "margin_used": 0.0,
            "positions": {
                ticker: {
                    "long": 0,
                    "short": 0,
                    "long_cost_basis": 0.0,
                    "short_cost_basis": 0.0,
                    "short_margin_used": 0.0,
                }
                for ticker in tickers
            },
            "realized_gains": {
                ticker: {"long": 0.0, "short": 0.0} for ticker in tickers
            },
        }

        # Performance tracking
        self.daily_values: List[Dict] = []
        self.trades: List[Dict] = []
        # Initialize agent contributions with canonical agent names (defensive)
        self.agent_contributions: Dict[str, Dict[str, float]] = {
            agent_name: {"pnl": 0.0, "trades": 0}
            for agent_name in self.CORE_AGENTS.values()
        }
        
        # Regime analysis data collection
        self.analyst_signals_history: List[Dict] = []
        self.market_regime_history: List[Dict] = []
        
        # Health monitoring
        self.health_monitor = None
        self.health_history: List[Dict] = []
        
        # Safety: Track processed dates/bars to prevent duplicate processing
        # For intraday: stores timestamp strings (e.g., "2025-09-19 09:30:00")
        # For daily: stores date strings (e.g., "2025-09-19")
        self.processed_dates: set = set()
        
        # Determinism: Track output hashes for verification
        self.daily_output_hashes: List[str] = []
        
        # Invariant logging: Track iteration state
        self.iteration_log: List[Dict] = []
        self.last_good_state: Optional[Dict] = None
        
        # Simple strategy: Price history tracking
        self._price_history: Dict[str, float] = {}
        
        # Price cache for deterministic historical data
        self._price_cache = get_price_cache()
        
        # OPTIMIZATION: Prefetch all price data for the entire backtest period
        # This avoids repeated CSV reads during the loop
        self._price_data_cache: Dict[str, pd.DataFrame] = {}
        self._prefetch_price_data()
        
        # Strategy selection (if using ES or NQ)
        self.topstep_strategy: Optional[TopstepStrategy] = None
        self.acceptance_strategy: Optional[AcceptanceContinuationStrategy] = None
        
        # Use acceptance continuation strategy for new hypothesis testing
        use_acceptance_strategy = True  # Testing new hypothesis
        
        if any(ticker.upper() in ["ES", "NQ", "MES", "MNQ"] for ticker in tickers):
            # Initialize strategy for first ES/NQ ticker found
            for ticker in tickers:
                if ticker.upper() in ["ES", "MES"]:
                    if use_acceptance_strategy:
                        self.acceptance_strategy = AcceptanceContinuationStrategy(instrument="ES")
                    else:
                        self.topstep_strategy = TopstepStrategy(instrument="ES")
                    break
                elif ticker.upper() in ["NQ", "MNQ"]:
                    if use_acceptance_strategy:
                        self.acceptance_strategy = AcceptanceContinuationStrategy(instrument="NQ")
                    else:
                        self.topstep_strategy = TopstepStrategy(instrument="NQ")
                    break

    def _generate_topstep_strategy_decisions(
        self, date: str, prices: Dict[str, float], portfolio_decisions: Dict, day_index: int
    ) -> Dict:
        """
        Topstep-optimized strategy: Opening Range Break + Pullback Continuation.
        
        Core Philosophy: Survival first, not profit maximization.
        - One trade max per day
        - 0.25% risk per trade
        - 1.5R max profit
        - Market regime filters
        - System correctly refuses to trade 70-90% of days
        """
        decisions = dict(portfolio_decisions)  # Start with portfolio manager decisions
        
        # Check if we have any non-hold decisions - if so, use those
        has_trades = any(
            isinstance(d, dict) and d.get("action", "hold").lower() != "hold" and d.get("quantity", 0) > 0
            for d in decisions.values()
        )
        
        # If portfolio manager already generated trades, use those
        if has_trades:
            return decisions
        
        # Use Topstep strategy if available and ticker matches
        if self.topstep_strategy:
            # Check if we have ES/NQ ticker
            topstep_ticker = None
            for ticker in self.tickers:
                if ticker.upper() in ["ES", "NQ", "MES", "MNQ"]:
                    topstep_ticker = ticker
                    break
            
            if topstep_ticker:
                # Calculate account value
                account_value = self._calculate_portfolio_value(prices)
                
                # Create state for Topstep strategy (minimal structure needed)
                state = {
                    "data": {
                        "tickers": [topstep_ticker],
                        "end_date": date,
                        "portfolio": self.portfolio,
                    },
                    "messages": [],
                    "metadata": {}
                }
                
                # Generate Topstep signal
                try:
                    topstep_decisions = self.topstep_strategy.generate_signal(
                        state, date, account_value
                    )
                    
                    # Merge Topstep decisions
                    for ticker, decision in topstep_decisions.items():
                        if isinstance(decision, dict) and decision.get("action", "hold").lower() != "hold":
                            decisions[ticker] = decision
                except Exception as e:
                    # Strategy failures are OK - log and continue
                    print(f"STRATEGY FAILURE: Topstep strategy error on {date}: {e}", file=sys.stderr)
                    import traceback
                    traceback.print_exc(file=sys.stderr)
        
        # Fallback to simple strategy for non-ES/NQ tickers
        return self._generate_simple_strategy_decisions(date, prices, decisions, day_index)
    
    def _generate_simple_strategy_decisions(
        self, date: str, prices: Dict[str, float], portfolio_decisions: Dict, day_index: int
    ) -> Dict:
        """
        Simple deterministic trading strategy for testing profitability (fallback).
        
        Strategy: Buy on first day, sell on last day (or price momentum if available)
        - Buy 10 shares on first trading day (if price available)
        - Sell all positions on last trading day
        - OR use price momentum: buy on price increase, sell on price decrease
        
        This is a test strategy to validate the backtest system can execute trades and track PnL.
        """
        decisions = dict(portfolio_decisions)  # Start with portfolio manager decisions
        
        # Check if we have any non-hold decisions - if so, use those
        has_trades = any(
            isinstance(d, dict) and d.get("action", "hold").lower() != "hold" and d.get("quantity", 0) > 0
            for d in decisions.values()
        )
        
        # If portfolio manager already generated trades, use those
        if has_trades:
            return decisions
        
        # Get trading dates to identify first and last day
        trading_dates = pd.bdate_range(self.start_date, self.end_date)
        is_first_day = day_index == 0
        is_last_day = day_index == len(trading_dates) - 1
        
        # Simple strategy: Buy on first day, sell on last day
        for ticker in self.tickers:
            # Skip ES/NQ if Topstep strategy is active
            if self.topstep_strategy and ticker.upper() in ["ES", "NQ", "MES", "MNQ"]:
                continue
            
            current_price = prices.get(ticker, 0.0)
            cash = self.portfolio["cash"]
            current_long = self.portfolio["positions"][ticker]["long"]
            
            # Price must be valid (no mock fallback)
            # If price is 0 or negative, this is an error condition
            if current_price <= 0:
                raise RuntimeError(
                    f"ENGINE FAILURE: Invalid price ${current_price:.2f} for {ticker} on {date}\n"
                    f"Price data must be available and valid. Check src/data/prices/{ticker.upper()}.csv"
                )
            
            # Calculate position size: 10 shares or 5% of cash, whichever is smaller
            max_shares_by_cash = int((cash * 0.05) // current_price) if current_price > 0 else 0
            fixed_shares = 10
            position_size = min(fixed_shares, max_shares_by_cash) if max_shares_by_cash > 0 else fixed_shares
            
            # Strategy 1: Buy on first day (always execute if we have cash)
            if is_first_day and current_long == 0 and position_size > 0:
                # Use available cash to determine actual position size
                actual_qty = min(position_size, int(cash // current_price)) if current_price > 0 else position_size
                if actual_qty > 0:
                    decisions[ticker] = {
                        "action": "buy",
                        "quantity": actual_qty,
                        "confidence": 70,
                        "reasoning": f"Simple strategy: Buy on first day ({date}) - {actual_qty} shares @ ${current_price:.2f}"
                    }
                    continue
            
            # Strategy 2: Sell on last day (if we have a position)
            if is_last_day and current_long > 0:
                decisions[ticker] = {
                    "action": "sell",
                    "quantity": current_long,
                    "confidence": 70,
                    "reasoning": f"Simple strategy: Sell on last day ({date}) - {current_long} shares @ ${current_price:.2f}"
                }
                continue
            
            # Strategy 3: Price momentum (if we have price history)
            if hasattr(self, '_price_history') and ticker in self._price_history:
                prev_price = self._price_history[ticker]
                if prev_price > 0:
                    price_change_pct = ((current_price - prev_price) / prev_price) * 100
                    
                    # Buy on price increase > 1%
                    if price_change_pct > 1.0 and current_long == 0 and position_size > 0 and cash >= (current_price * position_size):
                        decisions[ticker] = {
                            "action": "buy",
                            "quantity": position_size,
                            "confidence": 60,
                            "reasoning": f"Simple strategy: Price up {price_change_pct:.2f}% (${prev_price:.2f} -> ${current_price:.2f})"
                        }
                    # Sell on price decrease > 1% (if we have a position)
                    elif price_change_pct < -1.0 and current_long > 0:
                        decisions[ticker] = {
                            "action": "sell",
                            "quantity": min(current_long, position_size),
                            "confidence": 60,
                            "reasoning": f"Simple strategy: Price down {price_change_pct:.2f}% (${prev_price:.2f} -> ${current_price:.2f})"
                        }
            
            # Store current price for next iteration
            if not hasattr(self, '_price_history'):
                self._price_history = {}
            self._price_history[ticker] = current_price
        
        return decisions

    def _prefetch_price_data(self):
        """
        OPTIMIZATION: Prefetch all price data for the entire backtest period.
        This avoids repeated CSV file reads during the loop.
        """
        try:
            for ticker in self.tickers:
                # Get price data for entire backtest range
                df = self._price_cache.get_prices_for_range(ticker, self.start_date, self.end_date)
                self._price_data_cache[ticker] = df
        except Exception as e:
            # If prefetch fails, we'll fall back to on-demand loading
            print(f"Warning: Price data prefetch failed, will load on-demand: {e}", file=sys.stderr)
    
    def _get_current_prices(self, date: str) -> Dict[str, float]:
        """
        Get current prices for all tickers on a given date.
        
        OPTIMIZATION: Uses prefetched price data if available, otherwise falls back to cache.
        """
        prices = {}
        target_date = pd.Timestamp(date)
        
        for ticker in self.tickers:
            try:
                # OPTIMIZATION: Use prefetched data if available (much faster)
                if ticker in self._price_data_cache:
                    df = self._price_data_cache[ticker]
                    # Find exact date or nearest previous date
                    # For intraday data: look for bars on the target date (or last bar before end of day)
                    if target_date in df.index:
                        price = float(df.loc[target_date, "close"])
                    else:
                        # Check if we have intraday data (timestamps have time components)
                        has_intraday = any(hasattr(ts, 'hour') and ts.hour > 0 for ts in df.index[:10] if len(df) > 0)
                        
                        if has_intraday:
                            # For intraday data: find last bar of the target date
                            target_date_only = target_date.date()
                            bars_on_date = df.index[df.index.date == target_date_only]
                            if len(bars_on_date) > 0:
                                # Use last bar of the day
                                price = float(df.loc[bars_on_date[-1], "close"])
                            else:
                                # Fallback: find nearest previous date
                                previous_dates = df.index[df.index.date <= target_date_only]
                                if len(previous_dates) > 0:
                                    price = float(df.loc[previous_dates[-1], "close"])
                                else:
                                    raise ValueError(f"No price data available for {ticker} on or before {date}")
                        else:
                            # For daily data: find exact date or nearest previous date
                            previous_dates = df.index[df.index <= target_date]
                            if len(previous_dates) > 0:
                                price = float(df.loc[previous_dates[-1], "close"])
                            else:
                                raise ValueError(f"No price data available for {ticker} on or before {date}")
                    prices[ticker] = price
                else:
                    # Fallback to cache (slower, but works if prefetch failed)
                    price = self._price_cache.get_price(ticker, date)
                    prices[ticker] = price
            except (FileNotFoundError, ValueError) as e:
                # Fail loudly - no silent fallbacks
                raise RuntimeError(
                    f"ENGINE FAILURE: Cannot get price for {ticker} on {date}\n"
                    f"Error: {e}\n"
                    f"Price data must be available in src/data/prices/{ticker.upper()}.csv\n"
                    f"Format: date,open,high,low,close,volume"
                ) from e
            except Exception as e:
                # Unexpected errors also fail loudly
                raise RuntimeError(
                    f"ENGINE FAILURE: Unexpected error getting price for {ticker} on {date}: {e}"
                ) from e
        return prices

    def _calculate_portfolio_value(self, prices: Dict[str, float]) -> float:
        """Calculate total portfolio value (NAV)."""
        total_value = self.portfolio["cash"]

        for ticker in self.tickers:
            pos = self.portfolio["positions"][ticker]
            price = prices.get(ticker, 0.0)

            # Long positions
            if pos["long"] > 0:
                total_value += pos["long"] * price

            # Short positions
            # When you short, you sold at short_cost_basis and owe shares at current price
            # P&L = (sale_price - current_price) * quantity = (short_cost_basis - current_price) * quantity
            if pos["short"] > 0:
                # You sold at short_cost_basis, owe at current price
                # If price went up, you lose: (current_price - short_cost_basis) * quantity
                # If price went down, you gain: (short_cost_basis - current_price) * quantity
                short_pnl = (pos["short_cost_basis"] - price) * pos["short"]
                total_value += short_pnl

        return total_value
    
    def _calculate_gross_exposure(self, prices: Dict[str, float]) -> float:
        """Calculate gross exposure (sum of long + short positions)."""
        gross_exposure = 0.0
        
        for ticker in self.tickers:
            pos = self.portfolio["positions"][ticker]
            price = prices.get(ticker, 0.0)
            
            # Long positions
            if pos["long"] > 0:
                gross_exposure += pos["long"] * price
            
            # Short positions (notional value)
            if pos["short"] > 0:
                gross_exposure += pos["short"] * price
        
        return gross_exposure
    
    def _check_capital_constraints(
        self,
        ticker: str,
        action: str,
        quantity: int,
        price: float,
        prices: Dict[str, float],
    ) -> tuple[bool, str]:
        """
        Check if trade violates capital and leverage constraints.
        
        Constraints:
        1. Portfolio value must never go below zero
        2. Max gross exposure ≤ 100% of NAV
        3. Max position size per ticker ≤ 20% of NAV
        4. No new positions if NAV ≤ 50% of initial capital
        
        Returns:
            (allowed, reason) - allowed=True if trade passes all constraints
        """
        current_nav = self._calculate_portfolio_value(prices)
        
        # Constraint 1: NAV must never go below zero
        if current_nav <= 0:
            return (False, "NAV is zero or negative")
        
        # Constraint 4: No new positions if NAV ≤ 50% of initial capital
        nav_pct = current_nav / self.initial_capital
        if nav_pct <= 0.5:
            pos = self.portfolio["positions"][ticker]
            is_new_position = (
                (action == "buy" and pos["long"] == 0) or
                (action == "short" and pos["short"] == 0)
            )
            if is_new_position:
                return (False, f"NAV ({nav_pct:.1%}) ≤ 50% of initial capital - no new positions allowed")
        
        # Calculate what NAV would be after this trade
        trade_value = quantity * price
        
        # Estimate post-trade NAV (simplified - actual NAV depends on price changes)
        # For constraint checking, we assume no price change and minimal transaction costs
        # In deterministic_backtest, transaction costs are not tracked separately,
        # so we use a conservative estimate
        estimated_cost = trade_value * 0.001  # 0.1% estimate for costs
        post_trade_nav = current_nav
        
        if action == "buy":
            # Buying: cash decreases, position value increases
            # Net: NAV decreases by costs only (assuming no price change)
            post_trade_nav -= estimated_cost
        elif action == "sell":
            # Selling: cash increases, position value decreases
            # Net: NAV decreases by costs only
            post_trade_nav -= estimated_cost
        elif action == "short":
            # Shorting: margin used, short position created
            # Net: NAV decreases by costs only (margin is collateral)
            margin_needed = trade_value * self.margin_requirement
            post_trade_nav -= estimated_cost
        elif action == "cover":
            # Covering: cash decreases, short position closed
            # Net: NAV decreases by costs only
            post_trade_nav -= estimated_cost
        
        # Constraint 1: Post-trade NAV must be > 0
        if post_trade_nav <= 0:
            return (False, f"Trade would make NAV negative (${post_trade_nav:.2f})")
        
        # Calculate what gross exposure would be after this trade
        post_trade_gross = self._calculate_gross_exposure(prices)
        
        if action == "buy":
            post_trade_gross += trade_value
        elif action == "sell":
            post_trade_gross -= trade_value
        elif action == "short":
            post_trade_gross += trade_value
        elif action == "cover":
            post_trade_gross -= trade_value
        
        # Constraint 2: Max gross exposure ≤ 100% of NAV
        gross_exposure_pct = post_trade_gross / post_trade_nav if post_trade_nav > 0 else 0
        if gross_exposure_pct > 1.0:
            return (False, f"Gross exposure ({gross_exposure_pct:.1%}) would exceed 100% of NAV")
        
        # Constraint 3: Max position size per ticker ≤ 20% of NAV
        pos = self.portfolio["positions"][ticker]
        if action == "buy":
            new_long_value = (pos["long"] + quantity) * price
            position_pct = new_long_value / post_trade_nav if post_trade_nav > 0 else 0
            if position_pct > 0.20:
                return (False, f"Long position size ({position_pct:.1%}) would exceed 20% of NAV")
        elif action == "short":
            new_short_value = (pos["short"] + quantity) * price
            position_pct = new_short_value / post_trade_nav if post_trade_nav > 0 else 0
            if position_pct > 0.20:
                return (False, f"Short position size ({position_pct:.1%}) would exceed 20% of NAV")
        
        return (True, "OK")

    def _execute_trade(
        self,
        ticker: str,
        action: str,
        quantity: int,
        price: float,
        agent_signals: Dict,
        prices: Dict[str, float] = None,
    ) -> bool:
        """
        Execute a trade and track agent contributions.
        Enforces strict capital and leverage constraints.
        """
        if quantity <= 0 or price <= 0:
            return False

        # Get current prices for constraint checking
        if prices is None:
            prices = self._get_current_prices(self.current_date)
        
        # Check capital and leverage constraints BEFORE executing
        allowed, reason = self._check_capital_constraints(ticker, action, quantity, price, prices)
        if not allowed:
            # Trade rejected due to constraints - this is expected behavior
            return False

        # EXECUTION FRICTION: Apply slippage and spread deterministically
        # BUY or COVER: Pay more (slippage + spread increases price)
        # SELL or SHORT: Receive less (slippage + spread decreases price)
        total_friction_bps = self.slippage_bps + self.spread_bps
        if action in ["buy", "cover"]:
            executed_price = price * (1.0 + (total_friction_bps / 10000.0))
        else:  # sell or short
            executed_price = price * (1.0 - (total_friction_bps / 10000.0))
        
        # Calculate slippage cost (difference between executed and quoted price)
        slippage_cost = abs(executed_price - price) * quantity
        self.total_slippage_cost += slippage_cost

        pos = self.portfolio["positions"][ticker]
        cost = quantity * executed_price

        # Track which agents contributed to this trade
        # Use node names (with "_agent" suffix) to look up signals
        contributing_agents = []
        for registry_key, agent_name in self.CORE_AGENTS.items():
            node_name = self.AGENT_NODE_NAMES.get(registry_key)
            if node_name and node_name in agent_signals:
                signal = agent_signals[node_name].get(ticker, {})
                if signal and signal.get("signal") in ["bullish", "bearish"]:
                    contributing_agents.append(agent_name)

        if action == "buy":
            if cost > self.portfolio["cash"]:
                return False  # Insufficient cash
            # Deduct commission
            self.portfolio["cash"] -= self.commission_per_trade
            self.total_commissions += self.commission_per_trade
            # Deduct trade cost
            self.portfolio["cash"] -= cost
            old_cost = pos["long_cost_basis"]
            old_qty = pos["long"]
            pos["long"] += quantity
            pos["long_cost_basis"] = (
                (old_cost * old_qty + cost) / pos["long"] if pos["long"] > 0 else 0
            )

            # Track agent contribution (defensive: ensure agent exists in dict)
            for agent in contributing_agents:
                if agent in self.agent_contributions:
                    self.agent_contributions[agent]["trades"] += 1

        elif action == "sell":
            if pos["long"] < quantity:
                return False  # Insufficient shares
            proceeds = quantity * executed_price
            # Deduct commission
            self.portfolio["cash"] -= self.commission_per_trade
            self.total_commissions += self.commission_per_trade
            # Add proceeds
            self.portfolio["cash"] += proceeds
            pnl = (executed_price - pos["long_cost_basis"]) * quantity
            self.portfolio["realized_gains"][ticker]["long"] += pnl
            pos["long"] -= quantity
            if pos["long"] == 0:
                pos["long_cost_basis"] = 0.0

            # Track agent contribution (defensive: ensure agent exists in dict)
            for agent in contributing_agents:
                if agent in self.agent_contributions:
                    self.agent_contributions[agent]["pnl"] += pnl

        elif action == "short":
            # Shorting: sell shares you don't own
            # 1. Receive proceeds from sale (cash increases)
            # 2. Put up margin as collateral (cash decreases)
            # 3. Pay transaction costs (cash decreases)
            # Net: cash increases by (proceeds - margin - costs)
            margin_needed = cost * self.margin_requirement
            # Note: We'll receive proceeds, but need margin upfront
            if margin_needed > self.portfolio["cash"]:
                return False  # Insufficient margin
            
            # Deduct commission
            self.portfolio["cash"] -= self.commission_per_trade
            self.total_commissions += self.commission_per_trade
            # Receive proceeds from short sale, pay margin
            self.portfolio["cash"] += cost  # Receive proceeds (at executed_price)
            self.portfolio["cash"] -= margin_needed  # Pay margin
            # Net cash change: cost - margin_needed
            
            self.portfolio["margin_used"] += margin_needed
            old_cost = pos["short_cost_basis"]
            old_qty = pos["short"]
            pos["short"] += quantity
            # cost is already calculated with executed_price
            pos["short_cost_basis"] = (
                (old_cost * old_qty + cost) / pos["short"] if pos["short"] > 0 else 0
            )
            pos["short_margin_used"] += margin_needed

            # Track agent contribution (defensive: ensure agent exists in dict)
            for agent in contributing_agents:
                if agent in self.agent_contributions:
                    self.agent_contributions[agent]["trades"] += 1

        elif action == "cover":
            if pos["short"] < quantity:
                return False  # Insufficient short position
            cost_to_cover = quantity * executed_price
            if cost_to_cover > self.portfolio["cash"]:
                return False  # Insufficient cash
            # Deduct commission
            self.portfolio["cash"] -= self.commission_per_trade
            self.total_commissions += self.commission_per_trade
            # Deduct cost to cover
            self.portfolio["cash"] -= cost_to_cover
            # Short PnL: profit when price goes down (cost basis > current price)
            # You sold at short_cost_basis, buying back at executed_price
            # P&L = (sale_price - buy_price) * quantity
            avg_short_price = pos["short_cost_basis"] if pos["short"] > 0 else executed_price
            pnl = (avg_short_price * quantity) - cost_to_cover
            self.portfolio["realized_gains"][ticker]["short"] += pnl
            # Return margin (proportional to quantity being covered)
            margin_returned = (pos["short_margin_used"] / pos["short"]) * quantity if pos["short"] > 0 else 0
            self.portfolio["cash"] += margin_returned
            self.portfolio["margin_used"] -= margin_returned
            pos["short"] -= quantity
            if pos["short"] == 0:
                pos["short_cost_basis"] = 0.0
                pos["short_margin_used"] = 0.0

            # Track agent contribution (defensive: ensure agent exists in dict)
            for agent in contributing_agents:
                if agent in self.agent_contributions:
                    self.agent_contributions[agent]["pnl"] += pnl

        # Record trade (use executed_price, not quoted price)
        # For intraday execution, record timestamp if available
        trade_date = self.current_date
        if hasattr(self, '_current_bar_timestamp') and self._current_bar_timestamp:
            # Use bar timestamp for intraday trades
            trade_date_obj = self._current_bar_timestamp
        else:
            # Fallback to date string
            trade_date_obj = datetime.strptime(trade_date, "%Y-%m-%d")
        
        self.trades.append(
            {
                "date": trade_date_obj,
                "ticker": ticker,
                "action": action,
                "quantity": quantity,
                "price": executed_price,  # Record executed price (with slippage)
                "agents": ", ".join(contributing_agents) if contributing_agents else "None",
            }
        )

        # HARDENING: Post-trade validation - enforce all capital constraints
        post_trade_nav = self._calculate_portfolio_value(prices)
        if post_trade_nav < 0:
            raise RuntimeError(
                f"ENGINE FAILURE: Trade execution resulted in negative NAV: ${post_trade_nav:.2f}\n"
                f"Trade: {action} {quantity} {ticker} @ ${executed_price:.2f} (quoted: ${price:.2f})"
            )
        
        # Invariant: Gross exposure must not exceed 100% of NAV
        post_trade_gross = self._calculate_gross_exposure(prices)
        if post_trade_nav > 0:
            gross_pct = post_trade_gross / post_trade_nav
            if gross_pct > 1.0:
                raise RuntimeError(
                    f"ENGINE FAILURE: Post-trade gross exposure ({gross_pct:.1%}) exceeds 100% of NAV\n"
                    f"Trade: {action} {quantity} {ticker} @ ${executed_price:.2f} (quoted: ${price:.2f})\n"
                    f"NAV: ${post_trade_nav:.2f}, Gross Exposure: ${post_trade_gross:.2f}"
                )
        
        # Invariant: Position size must not exceed 20% of NAV per ticker
        pos = self.portfolio["positions"][ticker]
        position_value = max(
            pos["long"] * price if pos["long"] > 0 else 0,
            pos["short"] * price if pos["short"] > 0 else 0
        )
        if post_trade_nav > 0:
            position_pct = position_value / post_trade_nav
            if position_pct > 0.20:
                raise RuntimeError(
                    f"ENGINE FAILURE: Post-trade position size ({position_pct:.1%}) exceeds 20% of NAV\n"
                    f"Trade: {action} {quantity} {ticker} @ ${executed_price:.2f} (quoted: ${price:.2f})\n"
                    f"NAV: ${post_trade_nav:.2f}, Position Value: ${position_value:.2f}"
                )

        return True

    def _save_snapshot(self, date: str, index: int) -> None:
        """Save last known good state snapshot."""
        if not self.snapshot_dir:
            return
        
        try:
            os.makedirs(self.snapshot_dir, exist_ok=True)
            snapshot = {
                "date": date,
                "index": index,
                "portfolio": self.portfolio.copy(),
                "daily_values_count": len(self.daily_values),
                "trades_count": len(self.trades),
                "processed_dates": sorted(list(self.processed_dates)),
            }
            snapshot_path = os.path.join(self.snapshot_dir, f"snapshot_{date}.json")
            with open(snapshot_path, "w") as f:
                json.dump(snapshot, f, indent=2, default=str)
        except Exception as e:
            # Don't let snapshot failures break the backtest
            pass

    def _log_invariant(self, index: int, date: str, portfolio_value: float, agent_count: int, wall_clock_delta: float) -> None:
        """Log one invariant line per iteration."""
        log_entry = {
            "index": index,
            "date": date,
            "portfolio_value": portfolio_value,
            "agent_count": agent_count,
            "wall_clock_delta": wall_clock_delta,
        }
        self.iteration_log.append(log_entry)
        # Print to stderr (doesn't interfere with summary output)
        print(f"[{index:4d}] {date} | PV=${portfolio_value:,.0f} | Agents={agent_count} | Δt={wall_clock_delta:.2f}s", file=sys.stderr, flush=True)

    def _hash_daily_output(self, date: str, portfolio_value: float, trades_today: int) -> str:
        """Hash daily output for determinism verification."""
        # Create deterministic hash of daily state
        state_str = f"{date}:{portfolio_value:.2f}:{trades_today}:{len(self.daily_values)}"
        return hashlib.md5(state_str.encode()).hexdigest()

    def _check_stops_and_targets(self, bar: Dict, prices: Dict[str, float]) -> List[Dict]:
        """
        Check if any active positions hit stop loss or profit target.
        Also updates MFE (max favorable excursion) and MAE (max adverse excursion).
        
        Returns list of exit trades to execute.
        """
        exits = []
        ticker = bar['ticker']
        bar_high = bar['high']
        bar_low = bar['low']
        bar_close = bar['close']
        bar_time = bar['timestamp']
        
        if ticker not in self.active_positions or self.active_positions[ticker] is None:
            return exits
        
        pos = self.active_positions[ticker]
        side = pos['side']
        stop_loss = pos['stop_loss']
        target = pos['target']
        quantity = pos['quantity']
        entry_price = pos['entry_price']
        
        # Initialize MFE/MAE and bars_since_entry if not present
        if 'mfe' not in pos:
            pos['mfe'] = 0.0
        if 'mae' not in pos:
            pos['mae'] = 0.0
        if 'bars_since_entry' not in pos:
            pos['bars_since_entry'] = 0
        
        # Increment bars since entry
        pos['bars_since_entry'] += 1
        
        # Calculate R risk for time-based invalidation check
        if side == "long":
            r_risk = abs(entry_price - stop_loss)
        else:  # short
            r_risk = abs(stop_loss - entry_price)
        
        # Update MFE and MAE based on current bar
        if side == "long":
            # Long: MFE = max price above entry, MAE = min price below entry
            favorable = max(bar_high - entry_price, 0.0)
            adverse = max(entry_price - bar_low, 0.0)
            pos['mfe'] = max(pos['mfe'], favorable)
            pos['mae'] = max(pos['mae'], adverse)
            
            # Calculate MFE in R units for time-based invalidation
            mfe_r = pos['mfe'] / r_risk if r_risk > 0 else 0.0
            
            # Check stop loss and target FIRST (priority)
            if bar_low <= stop_loss:
                # Stop hit - exit at stop price
                exits.append({
                    'ticker': ticker,
                    'action': 'sell',
                    'quantity': quantity,
                    'price': stop_loss,
                    'reason': 'stop_loss',
                })
            elif bar_high >= target:
                # Target hit - exit at target price
                exits.append({
                    'ticker': ticker,
                    'action': 'sell',
                    'quantity': quantity,
                    'price': target,
                    'reason': 'target',
                })
            # TIME-BASED INVALIDATION: Check if N bars passed and MFE < threshold
            elif pos['bars_since_entry'] >= self.TIME_INVALIDATION_BARS and mfe_r < self.TIME_INVALIDATION_MFE_THRESHOLD:
                # Exit at market (current bar close)
                exits.append({
                    'ticker': ticker,
                    'action': 'sell',
                    'quantity': quantity,
                    'price': bar_close,  # Market exit at current close
                    'reason': 'time_invalidation',
                })
        else:  # short
            # Short: MFE = max price below entry, MAE = min price above entry
            favorable = max(entry_price - bar_low, 0.0)
            adverse = max(bar_high - entry_price, 0.0)
            pos['mfe'] = max(pos['mfe'], favorable)
            pos['mae'] = max(pos['mae'], adverse)
            
            # Calculate MFE in R units for time-based invalidation
            mfe_r = pos['mfe'] / r_risk if r_risk > 0 else 0.0
            
            # Check stop loss and target FIRST (priority)
            if bar_high >= stop_loss:
                # Stop hit - exit at stop price
                exits.append({
                    'ticker': ticker,
                    'action': 'cover',
                    'quantity': quantity,
                    'price': stop_loss,
                    'reason': 'stop_loss',
                })
            elif bar_low <= target:
                # Target hit - exit at target price
                exits.append({
                    'ticker': ticker,
                    'action': 'cover',
                    'quantity': quantity,
                    'price': target,
                    'reason': 'target',
                })
            # TIME-BASED INVALIDATION: Check if N bars passed and MFE < threshold
            elif pos['bars_since_entry'] >= self.TIME_INVALIDATION_BARS and mfe_r < self.TIME_INVALIDATION_MFE_THRESHOLD:
                # Exit at market (current bar close)
                exits.append({
                    'ticker': ticker,
                    'action': 'cover',
                    'quantity': quantity,
                    'price': bar_close,  # Market exit at current close
                    'reason': 'time_invalidation',
                })
        
        return exits
    
    def _run_intraday_bar(
        self, bar: Dict, date_str: str, time_str: str, bar_index: int, 
        is_new_day: bool, is_last_bar_of_day: bool
    ) -> Tuple[bool, int]:
        """
        Process a single intraday bar.
        
        Returns:
            (is_engine_failure, agent_count)
        """
        ticker = bar['ticker']
        bar_ts = bar['timestamp']
        bar_close = bar['close']
        
        # Store current bar timestamp for trade recording
        self._current_bar_timestamp = bar_ts
        
        # Track processed bars (use timestamp string to avoid duplicates)
        bar_key = time_str
        if bar_key in self.processed_dates:
            raise RuntimeError(
                f"ENGINE FAILURE: Bar {bar_key} already processed - "
                f"CONTRACT VIOLATION: Bar processing failed"
            )
        self.processed_dates.add(bar_key)
        
        self.current_date = date_str
        start_time = datetime.now()
        
        # Get current prices (for all tickers, use bar price for this ticker)
        prices = {}
        for t in self.tickers:
            if t == ticker:
                prices[t] = bar_close
            else:
                # For other tickers, get last available price
                prices[t] = self._get_current_prices(date_str).get(t, 0.0)
        
        # Check stops and targets FIRST (before new entries)
        exits = self._check_stops_and_targets(bar, prices)
        for exit_trade in exits:
            ticker = exit_trade['ticker']
            exit_price = exit_trade['price']
            exit_reason = exit_trade['reason']
            
            # Get position data before clearing
            pos = self.active_positions[ticker]
            entry_price = pos['entry_price']
            stop_loss = pos['stop_loss']
            target = pos['target']
            quantity = pos['quantity']
            side = pos['side']
            mfe = pos.get('mfe', 0.0)
            mae = pos.get('mae', 0.0)
            confirm_type = pos.get('confirm_type', 'unknown')
            entry_bar = pos.get('entry_bar', bar_ts)
            
            # Calculate R (risk per unit)
            if side == "long":
                r_risk = abs(entry_price - stop_loss)
            else:  # short
                r_risk = abs(stop_loss - entry_price)
            
            # Calculate R-multiple (PnL in R units, before friction)
            if r_risk > 0:
                if side == "long":
                    pnl_before_friction = exit_price - entry_price
                else:  # short
                    pnl_before_friction = entry_price - exit_price
                r_multiple = pnl_before_friction / r_risk
            else:
                r_multiple = 0.0
            
            # Calculate MFE and MAE in R units
            mfe_r = mfe / r_risk if r_risk > 0 else 0.0
            mae_r = mae / r_risk if r_risk > 0 else 0.0
            
            # Execute exit
            self._execute_trade(
                ticker,
                exit_trade['action'],
                exit_trade['quantity'],
                exit_trade['price'],
                {},  # No agent signals for stop/target exits
                prices
            )
            
            # Log R metrics (exit price will be adjusted by slippage in _execute_trade, but we log the intended exit)
            # For accurate R calculation, we need the actual executed exit price
            # We'll approximate it here (actual executed price = exit_price adjusted by slippage)
            total_friction_bps = self.slippage_bps + self.spread_bps
            if exit_trade['action'] in ['sell', 'cover']:
                executed_exit_price = exit_price * (1.0 - (total_friction_bps / 10000.0))
            else:
                executed_exit_price = exit_price * (1.0 + (total_friction_bps / 10000.0))
            
            # Recalculate R-multiple with executed exit price
            if r_risk > 0:
                if side == "long":
                    pnl_after_friction = executed_exit_price - entry_price
                else:  # short
                    pnl_after_friction = entry_price - executed_exit_price
                r_multiple_after_friction = pnl_after_friction / r_risk
            else:
                r_multiple_after_friction = 0.0
            
            # Calculate friction cost in R units
            friction_cost = abs(executed_exit_price - exit_price) * quantity
            friction_r = friction_cost / (r_risk * quantity) if r_risk > 0 and quantity > 0 else 0.0
            
            # Log R trade metrics
            self.r_trade_log.append({
                'entry_timestamp': entry_bar,
                'exit_timestamp': bar_ts,
                'ticker': ticker,
                'side': side,
                'entry_price': entry_price,
                'stop_loss': stop_loss,
                'target': target,
                'exit_price': exit_price,  # Intended exit price
                'executed_exit_price': executed_exit_price,  # Actual exit price after friction
                'exit_reason': exit_reason,
                'quantity': quantity,
                'r_risk': r_risk,
                'mfe': mfe,
                'mae': mae,
                'mfe_r': mfe_r,
                'mae_r': mae_r,
                'r_multiple_before_friction': r_multiple,
                'r_multiple_after_friction': r_multiple_after_friction,
                'friction_cost': friction_cost,
                'friction_r': friction_r,
                'confirm_type': confirm_type,
            })
            
            # Clear active position
            self.active_positions[ticker] = None
            # Update daily trade count
            if date_str in self.trades_today:
                self.trades_today[date_str] += 1
        
        # Check if we should call strategy (only during trading window: 9:30-10:30)
        hour = bar_ts.hour
        minute = bar_ts.minute
        in_trading_window = (hour == 9 and minute >= 30) or (hour == 10 and minute <= 30)
        
        # Also check if we already have a position (don't enter new trades if position exists)
        has_position = (self.active_positions.get(ticker) is not None or
                       self.portfolio["positions"][ticker]["long"] > 0 or
                       self.portfolio["positions"][ticker]["short"] > 0)
        
        agent_count = 0
        portfolio_decisions = {}
        analyst_signals = {}
        
        # Only call strategy if:
        # 1. Within trading window (9:30-10:30)
        # 2. No existing position for this ticker
        # 3. Not already traded today (max 1 trade per day)
        if in_trading_window and not has_position and self.trades_today.get(date_str, 0) == 0:
            try:
                # Call strategy - it will get price data via get_prices() which now preserves time
                # Prefer acceptance strategy if available (new hypothesis), fallback to topstep
                # Enable diagnostics if strategy supports it
                if self.acceptance_strategy and ticker.upper() in ["ES", "NQ", "MES", "MNQ"]:
                    # Enable diagnostic event logging if available
                    if hasattr(self.acceptance_strategy, 'enable_diagnostics'):
                        self.acceptance_strategy.enable_diagnostics = True
                    account_value = self._calculate_portfolio_value(prices)
                    
                    # Get price data up to current bar for strategy
                    strategy_df = self._price_cache.get_prices_for_range(ticker, self.start_date, date_str)
                    # Filter to bars up to and including current bar
                    if len(strategy_df) > 0:
                        strategy_df = strategy_df[strategy_df.index <= bar_ts]
                    else:
                        strategy_df = pd.DataFrame()
                    
                    # Temporarily override _get_price_data to return filtered DataFrame
                    original_get_price_data = self.acceptance_strategy._get_price_data
                    def filtered_get_price_data(t, start, end):
                        if t == ticker and len(strategy_df) > 0:
                            return strategy_df
                        return original_get_price_data(t, start, end)
                    self.acceptance_strategy._get_price_data = filtered_get_price_data
                    
                    try:
                        state = {
                            "data": {
                                "tickers": [ticker],
                                "end_date": date_str,
                                "portfolio": self.portfolio,
                            },
                            "messages": [],
                            "metadata": {}
                        }
                        
                        # Generate signal - strategy will use filtered DataFrame
                        strategy_decisions = self.acceptance_strategy.generate_signal(
                            state, date_str, account_value
                        )
                        
                        # Extract decision
                        if ticker in strategy_decisions:
                            decision = strategy_decisions[ticker]
                            if isinstance(decision, dict) and decision.get("action", "hold").lower() != "hold":
                                portfolio_decisions[ticker] = decision
                                agent_count = 1
                    finally:
                        # Restore original method
                        self.acceptance_strategy._get_price_data = original_get_price_data
                elif self.topstep_strategy and ticker.upper() in ["ES", "NQ", "MES", "MNQ"]:
                    account_value = self._calculate_portfolio_value(prices)
                    
                    # Get price data up to current bar for strategy
                    # Strategy needs historical bars for ATR, OR, etc., but only up to current bar
                    # Get all available data and filter to current bar
                    strategy_df = self._price_cache.get_prices_for_range(ticker, self.start_date, date_str)
                    # Filter to bars up to and including current bar
                    if len(strategy_df) > 0:
                        strategy_df = strategy_df[strategy_df.index <= bar_ts]
                    else:
                        strategy_df = pd.DataFrame()
                    
                    # Temporarily override _get_price_data to return filtered DataFrame
                    # This ensures strategy sees only bars up to current bar
                    original_get_price_data = self.topstep_strategy._get_price_data
                    def filtered_get_price_data(t, start, end):
                        # Return the pre-filtered DataFrame
                        if t == ticker and len(strategy_df) > 0:
                            return strategy_df
                        return original_get_price_data(t, start, end)
                    self.topstep_strategy._get_price_data = filtered_get_price_data
                    
                    try:
                        state = {
                            "data": {
                                "tickers": [ticker],
                                "end_date": date_str,
                                "portfolio": self.portfolio,
                            },
                            "messages": [],
                            "metadata": {}
                        }
                        
                        # Generate signal - strategy will use filtered DataFrame
                        topstep_decisions = self.topstep_strategy.generate_signal(
                            state, date_str, account_value
                        )
                        
                        # Extract decision
                        if ticker in topstep_decisions:
                            decision = topstep_decisions[ticker]
                            if isinstance(decision, dict) and decision.get("action", "hold").lower() != "hold":
                                portfolio_decisions[ticker] = decision
                                agent_count = 1
                    finally:
                        # Restore original method
                        self.topstep_strategy._get_price_data = original_get_price_data
            except Exception as e:
                # Strategy failures are OK - log and continue
                print(f"STRATEGY FAILURE: {time_str}: {e}", file=sys.stderr)
        
        # Execute new entries from strategy
        for ticker, decision in portfolio_decisions.items():
            if not isinstance(decision, dict):
                raise RuntimeError(
                    f"ENGINE FAILURE: Invalid decision format for {ticker}: {type(decision)}"
                )
            
            try:
                validated_decision = validate_portfolio_decision(decision)
                action = validated_decision.action
                quantity = validated_decision.quantity
            except ValueError as e:
                raise RuntimeError(
                    f"ENGINE FAILURE: Invalid portfolio decision for {ticker}: {e}\n"
                    f"Decision data: {decision}"
                ) from e
            
            price = prices.get(ticker, 0.0)
            if price <= 0:
                raise RuntimeError(
                    f"ENGINE FAILURE: Invalid price ${price:.2f} for {ticker} at {time_str}"
                )
            
            if action != "hold" and quantity > 0:
                # Execute trade
                executed_price = price  # Will be adjusted by slippage in _execute_trade
                if self._execute_trade(ticker, action, quantity, price, analyst_signals, prices):
                    # Extract stop/target from decision reasoning
                    # TopstepStrategy embeds stop/target in reasoning string
                    # Format: "Entry $X.XX, Stop $Y.YY, Target $Z.ZZ"
                    stop_loss = None
                    target = None
                    confirm_type = 'unknown'
                    reasoning = decision.get("reasoning", "")
                    if reasoning:
                        import re
                        # Extract stop and target from reasoning
                        stop_match = re.search(r'Stop \$([\d.]+)', reasoning)
                        target_match = re.search(r'Target \$([\d.]+)', reasoning)
                        if stop_match:
                            stop_loss = float(stop_match.group(1))
                        if target_match:
                            target = float(target_match.group(1))
                        
                        # Extract confirm_type from reasoning
                        # Format: "confirm=engulf" or "confirm=near_engulf" or "confirm=strongclose"
                        # Try multiple patterns to be robust
                        confirm_match = re.search(r'confirm[=:](\w+)', reasoning, re.IGNORECASE)
                        if confirm_match:
                            confirm_type = confirm_match.group(1).lower()
                        else:
                            # Fallback: check if confirm_type is in decision dict directly
                            confirm_type = decision.get('confirm_type', 'unknown')
                    
                    # If no stop/target extracted, use defaults (should not happen with TopstepStrategy)
                    if not stop_loss or not target:
                        # Fallback: 10% stop, 1.5R target
                        if action in ["buy"]:
                            stop_loss = price * 0.90
                            risk = price - stop_loss
                            target = price + (risk * 1.5)
                        else:  # short
                            stop_loss = price * 1.10
                            risk = stop_loss - price
                            target = price - (risk * 1.5)
                    
                    # Store active position with stops/targets and R tracking
                    side = "long" if action in ["buy"] else "short"
                    self.active_positions[ticker] = {
                        'side': side,
                        'entry_price': executed_price,
                        'stop_loss': stop_loss,
                        'target': target,
                        'quantity': quantity,
                        'entry_bar': bar_ts,
                        'mfe': 0.0,  # Will be updated on each bar
                        'mae': 0.0,  # Will be updated on each bar
                        'bars_since_entry': 0,  # Will be incremented on each bar
                        'confirm_type': confirm_type,
                    }
                    # Update daily trade count
                    if date_str in self.trades_today:
                        self.trades_today[date_str] += 1
        
        # Calculate NAV
        current_nav = self._calculate_portfolio_value(prices)
        
        # Record daily NAV at end of day (or start of new day for first bar)
        if is_last_bar_of_day or (is_new_day and len(self.daily_values) == 0):
            self.daily_values.append({
                "Date": date_str,
                "Portfolio Value": current_nav,
            })
            # Hash daily output
            trades_today = self.trades_today.get(date_str, 0)
            daily_hash = self._hash_daily_output(date_str, current_nav, trades_today)
            self.daily_output_hashes.append(daily_hash)
        
        # Log invariant (every bar for intraday to match processed_dates count)
        wall_clock_delta = (datetime.now() - start_time).total_seconds()
        self._log_invariant(bar_index, time_str, current_nav, agent_count, wall_clock_delta)
        
        return (False, agent_count)  # No engine failure
    
    def _run_daily_decision(self, date: str, index: int) -> Tuple[bool, int]:
        """
        Run trading decision for a single day.
        
        CONTRACT: This method must never process the same date twice.
        CONTRACT: This method must always log an invariant.
        CONTRACT: This method must always record a daily value.
        
        Returns:
            (is_engine_failure, agent_count)
            - is_engine_failure: True if engine failure (should abort), False if strategy failure (continue)
            - agent_count: Number of agents that processed successfully
        
        Violations raise RuntimeError("ENGINE FAILURE: ...") and abort the backtest.
        """
        # CONTRACT VIOLATION: Duplicate date processing is impossible
        # This is a bug, not a recoverable event
        if date in self.processed_dates:
            raise RuntimeError(
                f"ENGINE FAILURE: Date {date} already processed at index {index} - "
                f"CONTRACT VIOLATION: Loop advancement failed. "
                f"Processed dates: {sorted(list(self.processed_dates))}"
            )
        self.processed_dates.add(date)
        
        self.current_date = date
        start_time = datetime.now()

        # Get current prices
        prices = self._get_current_prices(date)
        
        # Constraint validation: NAV must never go below zero (pre-trade check)
        current_nav = self._calculate_portfolio_value(prices)
        if current_nav < 0:
            raise RuntimeError(
                f"ENGINE FAILURE: Portfolio value is negative: ${current_nav:.2f} on {date}\n"
                f"This should never happen - previous trade execution violated constraints"
            )
        
        # OPTIMIZATION: Fast-path for days when trading is not possible
        # If NAV is too low, skip expensive agent execution
        nav_pct = current_nav / self.initial_capital if self.initial_capital > 0 else 0.0
        skip_agents = nav_pct <= 0.5  # NAV ≤ 50% of initial - no new positions allowed anyway
        
        agent_count = 0
        trades_today = 0
        
        # OPTIMIZATION: Skip agent execution if NAV too low (no new positions possible)
        if skip_agents:
            # Still need to record daily value and check for exits
            portfolio_decisions = {}
            analyst_signals = {}
            market_regime = {}
        else:
            try:
                # Run hedge fund system for this date
                # Use a lookback period for analysis (agents need historical data)
                lookback_date = (datetime.strptime(date, "%Y-%m-%d") - relativedelta(days=30)).strftime("%Y-%m-%d")
                
                result = run_hedge_fund(
                    tickers=self.tickers,
                    start_date=lookback_date,
                    end_date=date,
                    portfolio=self.portfolio.copy(),
                    show_reasoning=False,
                    selected_analysts=list(self.CORE_AGENTS.keys()),  # Use canonical registry keys
                    model_name="deterministic",
                    model_provider="deterministic",
                )

                # CONTRACT VIOLATION: Malformed data from strategy is engine failure
                # Strategy must return dict, anything else violates interface contract
                if not isinstance(result, dict):
                    raise RuntimeError(
                        f"ENGINE FAILURE: run_hedge_fund returned non-dict: {type(result)} - "
                        f"CONTRACT VIOLATION: Strategy interface contract broken"
                    )
                
                # Execute trades from portfolio decisions
                portfolio_decisions = result.get("portfolio_decisions", {})
                analyst_signals = result.get("analyst_signals", {})
                market_regime = result.get("market_regime", {})

                # Count agents that processed
                agent_count = len([k for k in analyst_signals.keys() if k.endswith("_agent")])

                # Collect data for regime analysis
                self.analyst_signals_history.append({
                    "date": date,
                    "signals": analyst_signals,
                })
                if market_regime:
                    regime_with_date = {ticker: {**regime_data, "date": date} for ticker, regime_data in market_regime.items()}
                    self.market_regime_history.append(regime_with_date)
            except RuntimeError as e:
                # Engine failures: crash loudly, abort run
                if "ENGINE FAILURE" in str(e):
                    raise
                # Other RuntimeErrors treated as strategy failures
                print(f"STRATEGY FAILURE: {date}: {e}", file=sys.stderr)
                import traceback
                traceback.print_exc(file=sys.stderr)
                portfolio_decisions = {}
                analyst_signals = {}
                market_regime = {}

            # Topstep-optimized strategy: If no trades from portfolio manager, use Topstep strategy
            # Falls back to simple strategy for non-ES/NQ tickers
            try:
                simple_strategy_decisions = self._generate_topstep_strategy_decisions(
                    date, prices, portfolio_decisions, index
                )
                
                # Execute trades (strategy logic - failures here are strategy failures, not engine failures)
                for ticker, decision in simple_strategy_decisions.items():
                    if not isinstance(decision, dict):
                        raise RuntimeError(
                            f"ENGINE FAILURE: Invalid decision format for {ticker}: {type(decision)}"
                        )
                    
                    # HARDENING: Validate decision before execution
                    try:
                        validated_decision = validate_portfolio_decision(decision)
                        action = validated_decision.action
                        quantity = validated_decision.quantity
                    except ValueError as e:
                        raise RuntimeError(
                            f"ENGINE FAILURE: Invalid portfolio decision for {ticker}: {e}\n"
                            f"Decision data: {decision}"
                        ) from e
                    
                    price = prices.get(ticker, 0.0)
                    
                    # Price must be valid (no mock fallback)
                    if price <= 0:
                        raise RuntimeError(
                            f"ENGINE FAILURE: Invalid price ${price:.2f} for {ticker} on {date}\n"
                            f"Price data must be available and valid. Check src/data/prices/{ticker.upper()}.csv"
                        )

                    if action != "hold" and quantity > 0:
                        if self._execute_trade(ticker, action, quantity, price, analyst_signals, prices):
                            trades_today += 1
            except Exception as e:
                # Strategy failures: log, skip, continue
                print(f"STRATEGY FAILURE: {date}: {e}", file=sys.stderr)
                import traceback
                traceback.print_exc(file=sys.stderr)
                portfolio_decisions = {}
                analyst_signals = {}
                market_regime = {}

        # Calculate portfolio value (always, even on strategy failure)
        portfolio_value = self._calculate_portfolio_value(prices)
        
        # Calculate exposures for health monitoring
        long_exposure = sum(self.portfolio["positions"][t]["long"] * prices.get(t, 0.0) for t in self.tickers)
        short_exposure = sum(self.portfolio["positions"][t]["short"] * prices.get(t, 0.0) for t in self.tickers)
        gross_exposure = long_exposure + short_exposure
        net_exposure = long_exposure - short_exposure

        # Record daily value (always record, even on failure)
        daily_value_entry = {
            "Date": datetime.strptime(date, "%Y-%m-%d"),
            "Portfolio Value": portfolio_value,
            "Cash": self.portfolio["cash"],
            "Long Exposure": long_exposure,
            "Short Exposure": short_exposure,
        }
        self.daily_values.append(daily_value_entry)
        
        # OPTIMIZATION: Health monitoring - run less frequently (every 5 days or on status changes)
        # This reduces overhead while still tracking health
        should_check_health = (
            index % 5 == 0 or  # Every 5 days
            len(self.health_history) == 0 or  # First day
            (len(self.health_history) > 0 and 
             self.health_history[-1].get("overall_status") in ["critical", "warning"])  # Previous day had issues
        )
        
        if should_check_health:
            try:
                from src.health.health_monitor import HealthMonitor
                
                # Initialize health monitor if not already done
                if self.health_monitor is None:
                    self.health_monitor = HealthMonitor(
                        initial_capital=self.initial_capital,
                        health_history_dir=os.path.join(self.snapshot_dir, "health") if self.snapshot_dir else None,
                    )
                
                # Calculate daily return
                daily_return = None
                if len(self.daily_values) > 1:
                    prev_value = self.daily_values[-2]["Portfolio Value"]
                    if prev_value > 0:
                        daily_return = (portfolio_value - prev_value) / prev_value
                
                # Check for constraint violations
                constraint_violations = []
                nav_pct = portfolio_value / self.initial_capital if self.initial_capital > 0 else 0.0
                if nav_pct > 1.0:
                    gross_exposure_pct = gross_exposure / portfolio_value if portfolio_value > 0 else 0.0
                    if gross_exposure_pct > 1.0:
                        constraint_violations.append(f"Gross exposure ({gross_exposure_pct:.1%}) exceeds 100% of NAV")
                
                # Calculate health metrics
                health_metrics = self.health_monitor.calculate_overall_health(
                    nav=portfolio_value,
                    cash=self.portfolio["cash"],
                    margin_used=self.portfolio.get("margin_used", 0.0),
                    gross_exposure=gross_exposure,
                    net_exposure=net_exposure,
                    positions=self.portfolio["positions"],
                    prices=prices,
                    daily_return=daily_return,
                    constraint_violations=constraint_violations,
                )
                
                # Store health metrics
                self.health_history.append({
                    "date": date,
                    "overall_score": health_metrics.overall_score,
                    "overall_status": health_metrics.overall_status.value,
                    "nav": health_metrics.nav,
                    "nav_pct": health_metrics.nav_pct_of_initial,
                    "alerts_count": len(health_metrics.active_alerts),
                })
                
                # Log health warnings to stderr
                if health_metrics.overall_status.value in ["critical", "warning"]:
                    print(
                        f"HEALTH {health_metrics.overall_status.value.upper()}: "
                        f"Score {health_metrics.overall_score:.2f}, "
                        f"NAV {health_metrics.nav_pct_of_initial:.1%}, "
                        f"Alerts: {len(health_metrics.active_alerts)}",
                        file=sys.stderr,
                        flush=True,
                    )
            except Exception as e:
                # Don't let health monitoring failures break the backtest
                print(f"Warning: Health monitoring failed: {e}", file=sys.stderr)

        # CONTRACT: Every iteration must hash output for determinism
        daily_hash = self._hash_daily_output(date, portfolio_value, trades_today)
        self.daily_output_hashes.append(daily_hash)

        # CONTRACT: Every iteration must log exactly one invariant line
        # Violation: If this doesn't execute, iteration completed without logging (BUG)
        wall_clock_delta = (datetime.now() - start_time).total_seconds()
        self._log_invariant(index, date, portfolio_value, agent_count, wall_clock_delta)
        
        # CONTRACT: Every iteration must record daily value
        # This happens above in daily_values.append() - if it didn't, that's a bug

        # Save snapshot (last known good state)
        self._save_snapshot(date, index)
        self.last_good_state = {
            "date": date,
            "index": index,
            "portfolio": self.portfolio.copy(),
            "daily_values_count": len(self.daily_values),
        }

        return (False, agent_count)  # No engine failure, return agent count

    def run(self) -> Dict:
        """Run the backtest."""
        print(f"Running deterministic backtest from {self.start_date} to {self.end_date}...")
        print(f"Tickers: {', '.join(self.tickers)}")
        print(f"Initial Capital: ${self.initial_capital:,.2f}")
        print(f"Deterministic Seed: {DETERMINISTIC_SEED}")
        print(f"Progress rendering: {'DISABLED' if self.disable_progress else 'ENABLED'}\n")

        # INTRADAY EXECUTION: Get all intraday bars for the date range
        # Check if we have intraday data by examining the first ticker's data
        all_bars = []
        has_intraday = False
        
        for ticker in self.tickers:
            df = self._price_cache.get_prices_for_range(ticker, self.start_date, self.end_date)
            if len(df) > 0:
                # Check if timestamps have time components (intraday data)
                sample_ts = df.index[0]
                if hasattr(sample_ts, 'hour') and (sample_ts.hour > 0 or sample_ts.minute > 0):
                    has_intraday = True
                    # Collect all bars with ticker info
                    for ts, row in df.iterrows():
                        all_bars.append({
                            'timestamp': ts,
                            'ticker': ticker,
                            'open': float(row['open']),
                            'high': float(row['high']),
                            'low': float(row['low']),
                            'close': float(row['close']),
                            'volume': int(row['volume']) if pd.notna(row['volume']) else 0,
                        })
                    # Continue to collect bars for all tickers (if multiple)
                    # But only check intraday once
                    if not has_intraday:
                        break
        
        if has_intraday and all_bars:
            # Sort bars by timestamp
            all_bars.sort(key=lambda x: x['timestamp'])
            total_bars = len(all_bars)
            print(f"Intraday execution mode: {total_bars} bars\n")
            
            # Track last day processed for daily NAV recording
            last_day = None
            bar_index = 0
            
            # CONTRACT: Loop must advance exactly once per iteration
            for i, bar in enumerate(all_bars):
                bar_ts = bar['timestamp']
                bar_date_str = bar_ts.strftime("%Y-%m-%d")
                bar_time_str = bar_ts.strftime("%Y-%m-%d %H:%M:%S")
                
                # Record daily NAV at start of new day or end of day
                is_new_day = (last_day is None or bar_date_str != last_day)
                is_last_bar_of_day = (i == len(all_bars) - 1 or 
                                     all_bars[i+1]['timestamp'].strftime("%Y-%m-%d") != bar_date_str)
                
                if is_new_day:
                    self.current_day = bar_date_str
                    self.trades_today[bar_date_str] = 0
                    self.pnl_today[bar_date_str] = 0.0
                
                try:
                    is_engine_failure, agent_count = self._run_intraday_bar(
                        bar, bar_date_str, bar_time_str, i, is_new_day, is_last_bar_of_day
                    )
                    
                    if is_engine_failure:
                        raise RuntimeError(f"ENGINE FAILURE at bar index {i}, {bar_time_str}")
                    
                    last_day = bar_date_str
                    bar_index = i
                    
                except RuntimeError as e:
                    if "ENGINE FAILURE" in str(e):
                        print(f"\nFATAL ENGINE FAILURE: {e}", file=sys.stderr)
                        print(f"Last good state: {self.last_good_state}", file=sys.stderr)
                        raise
                    raise
                except Exception as e:
                    print(f"\nFATAL ENGINE FAILURE at bar index {i}, {bar_time_str}: {e}", file=sys.stderr)
                    import traceback
                    traceback.print_exc(file=sys.stderr)
                    raise RuntimeError(f"ENGINE FAILURE: Unexpected exception: {e}")
        else:
            # FALLBACK: Daily execution mode (for daily data)
            dates = pd.bdate_range(self.start_date, self.end_date)
            
            if len(dates) == 0:
                print("Error: No business days in date range", file=sys.stderr)
                return {}
            
            total_days = len(dates)
            print(f"Daily execution mode: {total_days} trading days\n")
            
            for i in range(total_days):
                date = dates[i]
                date_str = date.strftime("%Y-%m-%d")
                
                assert i == len(self.processed_dates), (
                    f"CONTRACT VIOLATION: Loop index {i} doesn't match processed count {len(self.processed_dates)}"
                )
                
                try:
                    is_engine_failure, agent_count = self._run_daily_decision(date_str, i)
                    
                    if is_engine_failure:
                        raise RuntimeError(f"ENGINE FAILURE at index {i}, date {date_str}")
                        
                except RuntimeError as e:
                    if "ENGINE FAILURE" in str(e):
                        print(f"\nFATAL ENGINE FAILURE: {e}", file=sys.stderr)
                        print(f"Last good state: {self.last_good_state}", file=sys.stderr)
                        raise
                    raise
                except Exception as e:
                    print(f"\nFATAL ENGINE FAILURE at index {i}, date {date_str}: {e}", file=sys.stderr)
                    import traceback
                    traceback.print_exc(file=sys.stderr)
                    raise RuntimeError(f"ENGINE FAILURE: Unexpected exception: {e}")

        # Calculate metrics (guaranteed to execute after loop)
        print("\nCalculating metrics...", flush=True, file=sys.stderr)
        metrics = self._calculate_metrics()
        
        # CONTRACT: Determinism must be verifiable
        # Every run must produce hashable output for comparison
        final_hash = hashlib.md5("".join(self.daily_output_hashes).encode()).hexdigest()
        
        # CONTRACT: Iteration log must match processed dates/bars
        # For intraday: daily_values is one per day, not one per bar
        # For daily: all counts should match
        assert len(self.iteration_log) == len(self.processed_dates), (
            f"CONTRACT VIOLATION: Iteration log doesn't match processed dates/bars - "
            f"iterations={len(self.iteration_log)}, "
            f"dates/bars={len(self.processed_dates)}"
        )
        # Daily values should be <= processed dates (one per day for intraday, one per date for daily)
        assert len(self.daily_values) <= len(self.processed_dates), (
            f"CONTRACT VIOLATION: Daily values exceed processed dates - "
            f"values={len(self.daily_values)}, "
            f"dates/bars={len(self.processed_dates)}"
        )
        
        metrics["determinism"] = {
            "seed": DETERMINISTIC_SEED,
            "output_hash": final_hash,
            "total_iterations": len(self.iteration_log),
        }

        return metrics

    def _calculate_metrics(self) -> Dict:
        """Calculate performance metrics."""
        if not self.daily_values:
            return {}

        df = pd.DataFrame(self.daily_values)
        df.set_index("Date", inplace=True)
        df.sort_index(inplace=True)

        # Cumulative PnL
        initial_value = self.initial_capital
        final_value = df["Portfolio Value"].iloc[-1]
        cumulative_pnl = final_value - initial_value
        total_return = (final_value / initial_value - 1) * 100

        # Daily returns
        df["Daily Return"] = df["Portfolio Value"].pct_change()
        daily_returns = df["Daily Return"].dropna()

        # Max drawdown
        df["Cumulative"] = df["Portfolio Value"]
        df["Running Max"] = df["Cumulative"].expanding().max()
        df["Drawdown"] = (df["Cumulative"] - df["Running Max"]) / df["Running Max"]
        max_drawdown = df["Drawdown"].min() * 100
        if not df["Drawdown"].empty:
            max_dd_idx = df["Drawdown"].idxmin()
            # Handle both datetime index and string index
            if isinstance(max_dd_idx, str):
                max_drawdown_date = max_dd_idx
            else:
                max_drawdown_date = max_dd_idx.strftime("%Y-%m-%d")
        else:
            max_drawdown_date = None

        # Win rate (from realized gains)
        # Calculate win rate based on profitable vs unprofitable positions closed
        if self.trades:
            # Count trades that resulted in realized gains
            profitable_trades = 0
            total_closing_trades = 0
            for ticker in self.tickers:
                long_gains = self.portfolio["realized_gains"][ticker]["long"]
                short_gains = self.portfolio["realized_gains"][ticker]["short"]
                if long_gains > 0 or short_gains > 0:
                    profitable_trades += 1
                if long_gains != 0 or short_gains != 0:
                    total_closing_trades += 1
            
            win_rate = (profitable_trades / total_closing_trades * 100) if total_closing_trades > 0 else 0.0
        else:
            win_rate = 0.0

        # Sharpe ratio
        if len(daily_returns) > 1 and daily_returns.std() > 0:
            sharpe_ratio = (daily_returns.mean() / daily_returns.std()) * (252 ** 0.5)
        else:
            sharpe_ratio = 0.0

        # Agent contributions (defensive: ensure all agents are represented)
        agent_contributions = {}
        total_pnl = sum(v["pnl"] for v in self.agent_contributions.values())
        # Use canonical agent names from CORE_AGENTS to ensure consistent output
        for agent_name in self.CORE_AGENTS.values():
            data = self.agent_contributions.get(agent_name, {"pnl": 0.0, "trades": 0})
            pnl_pct = (data["pnl"] / total_pnl * 100) if total_pnl != 0 else 0.0
            agent_contributions[agent_name] = {
                "PnL": f"${data['pnl']:,.2f}",
                "PnL %": f"{pnl_pct:.1f}%",
                "Trades": int(data["trades"]),
            }

        # Health summary
        health_summary = None
        if self.health_monitor:
            try:
                health_summary = self.health_monitor.get_health_summary()
            except Exception:
                pass
        
        return {
            "cumulative_pnl": cumulative_pnl,
            "total_return": total_return,
            "final_value": final_value,
            "max_drawdown": max_drawdown,
            "max_drawdown_date": max_drawdown_date,
            "win_rate": win_rate,
            "sharpe_ratio": sharpe_ratio,
            "agent_contributions": agent_contributions,
            "total_trades": len(self.trades),
            "daily_values": df,
            "health_summary": health_summary,
            "health_history": self.health_history,
        }

    def print_summary(self, metrics: Dict, include_edge_analysis: bool = True) -> None:
        """Print backtest summary table."""
        print("\n" + "=" * 80)
        print("DETERMINISTIC BACKTEST SUMMARY")
        print("=" * 80)

        print(f"\nPeriod: {self.start_date} to {self.end_date}")
        print(f"Tickers: {', '.join(self.tickers)}")
        print(f"Initial Capital: ${self.initial_capital:,.2f}")
        
        # Determinism verification
        if metrics.get("determinism"):
            det = metrics["determinism"]
            print(f"Determinism: Seed={det['seed']}, Output Hash={det['output_hash'][:16]}...")

        print("\n" + "-" * 80)
        print("PERFORMANCE METRICS")
        print("-" * 80)
        print(f"Final Portfolio Value: ${metrics['final_value']:,.2f}")
        print(f"Cumulative PnL: ${metrics['cumulative_pnl']:,.2f}")
        print(f"Total Return: {metrics['total_return']:.2f}%")
        print(f"Max Drawdown: {metrics['max_drawdown']:.2f}%")
        if metrics.get("max_drawdown_date"):
            print(f"Max Drawdown Date: {metrics['max_drawdown_date']}")
        print(f"Sharpe Ratio: {metrics['sharpe_ratio']:.2f}")
        print(f"Win Rate: {metrics['win_rate']:.1f}%")
        print(f"Total Trades: {metrics['total_trades']}")

        print("\n" + "-" * 80)
        print("AGENT CONTRIBUTIONS")
        print("-" * 80)
        if metrics.get("agent_contributions"):
            from tabulate import tabulate
            agent_data = []
            for agent, data in metrics["agent_contributions"].items():
                agent_data.append([agent, data["PnL"], data["PnL %"], data["Trades"]])
            print(tabulate(agent_data, headers=["Agent", "PnL", "PnL %", "Trades"], tablefmt="grid"))
        
        # Health Summary
        if metrics.get("health_summary"):
            health = metrics["health_summary"]
            print("\n" + "-" * 80)
            print("PORTFOLIO HEALTH SUMMARY")
            print("-" * 80)
            if health.get("status") != "no_data":
                print(f"Overall Health Score: {health.get('overall_score', 0):.2f}/1.00")
                print(f"Overall Status: {health.get('overall_status', 'unknown').upper()}")
                print(f"NAV: ${health.get('nav', 0):,.2f} ({health.get('nav_pct', 0):.1%} of initial)")
                print(f"Active Alerts: {health.get('active_alerts', 0)}")
                
                if health.get("checks"):
                    print("\nHealth Checks:")
                    for check in health["checks"]:
                        status_icon = {
                            "excellent": "✅",
                            "healthy": "✅",
                            "caution": "⚠️",
                            "warning": "⚠️",
                            "critical": "🔴",
                        }.get(check["status"], "❓")
                        print(f"  {status_icon} {check['name']}: {check['status'].upper()} (score: {check['score']:.2f})")
        print("=" * 80)
        
        # Edge Analysis
        if include_edge_analysis and metrics.get("daily_values") is not None:
            try:
                df = metrics["daily_values"]
                if "Daily Return" in df.columns and len(df) > 1:
                    daily_returns = df["Daily Return"]
                    
                    # Get benchmark returns if available (SPY)
                    benchmark_returns = None
                    # TODO: Fetch SPY returns for comparison
                    
                    edge_analyzer = EdgeAnalysis(
                        daily_returns=daily_returns,
                        benchmark_returns=benchmark_returns,
                        trades=self.trades,
                        initial_capital=self.initial_capital,
                    )
                    
                    analysis = edge_analyzer.comprehensive_analysis()
                    edge_analyzer.print_analysis(analysis)
            except Exception as e:
                print(f"\nWarning: Could not run edge analysis: {e}")
        
        # Regime Analysis: Where does system consistently behave differently from random?
        regime_analysis = None
        try:
            df = metrics["daily_values"]
            if len(df) > 1:
                regime_analyzer = RegimeAnalysis(
                    daily_values=df,
                    trades=self.trades,
                    analyst_signals_history=self.analyst_signals_history,
                    market_regime_history=self.market_regime_history,
                )
                
                regime_analysis = regime_analyzer.identify_consistent_edge()
                regime_analyzer.print_analysis(regime_analysis)
        except Exception as e:
            print(f"\nWarning: Could not run regime analysis: {e}")
        
        # Learning: Extract insights from backtest and store in knowledge base
        try:
            from src.knowledge.learning_engine import LearningEngine
            
            learning_engine = LearningEngine()
            
            # Prepare agent contributions in format expected by learning engine
            agent_contributions_for_learning = {}
            for agent_name, contrib_data in self.agent_contributions.items():
                agent_contributions_for_learning[agent_name] = {
                    "pnl": contrib_data.get("pnl", 0.0),
                    "trades": contrib_data.get("trades", 0),
                }
            
            # Learn from this backtest
            learning_engine.learn_from_backtest(
                backtest_metrics=metrics,
                regime_analysis=regime_analysis,
                edge_analysis=None,  # Could be added if edge analysis results are available
                agent_contributions=agent_contributions_for_learning,
                analyst_signals_history=self.analyst_signals_history,
            )
            
            print("\n" + "=" * 80)
            print("KNOWLEDGE BASE UPDATED")
            print("=" * 80)
            print("Insights from this backtest have been stored in the knowledge base.")
            print("Agents will use this knowledge in future runs.")
        except Exception as e:
            print(f"\nWarning: Could not update knowledge base: {e}")
            import traceback
            traceback.print_exc()


def verify_determinism(run1_output_hash: str, run2_output_hash: str) -> bool:
    """Verify two runs produce identical outputs."""
    if run1_output_hash != run2_output_hash:
        raise RuntimeError(
            f"DETERMINISM VIOLATION: Output hashes differ\n"
            f"  Run 1: {run1_output_hash}\n"
            f"  Run 2: {run2_output_hash}\n"
            f"This indicates non-deterministic behavior."
        )
    return True


def main():
    """CLI entry point for deterministic backtest."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Run deterministic backtest for 5-core-agent system"
    )
    parser.add_argument(
        "--tickers",
        type=str,
        required=True,
        help="Comma-separated list of tickers (e.g., AAPL,MSFT,GOOGL)",
    )
    parser.add_argument(
        "--start-date",
        type=str,
        required=True,
        help="Start date YYYY-MM-DD",
    )
    parser.add_argument(
        "--end-date",
        type=str,
        required=True,
        help="End date YYYY-MM-DD",
    )
    parser.add_argument(
        "--initial-capital",
        type=float,
        default=100000.0,
        help="Initial capital (default: 100000)",
    )
    parser.add_argument(
        "--margin-requirement",
        type=float,
        default=0.0,
        help="Margin requirement for shorting (default: 0.0)",
    )
    parser.add_argument(
        "--no-edge-analysis",
        action="store_true",
        help="Skip edge detection analysis",
    )
    parser.add_argument(
        "--snapshot-dir",
        type=str,
        default=None,
        help="Directory to save state snapshots (default: None)",
    )
    parser.add_argument(
        "--enable-progress",
        action="store_true",
        help="Enable progress rendering (disabled by default in backtests)",
    )

    args = parser.parse_args()

    # Ensure deterministic mode
    os.environ["HEDGEFUND_NO_LLM"] = "1"
    
    # Disable progress rendering by default (can be enabled with flag)
    if args.enable_progress:
        # Temporarily disable progress updates if progress module exists
        try:
            from src.utils.progress import progress
            # Progress rendering is handled by individual agents
            # We just ensure it doesn't block
            pass
        except:
            pass

    tickers = [t.strip().upper() for t in args.tickers.split(",")]

    backtest = DeterministicBacktest(
        tickers=tickers,
        start_date=args.start_date,
        end_date=args.end_date,
        initial_capital=args.initial_capital,
        margin_requirement=args.margin_requirement,
        disable_progress=not args.enable_progress,
        snapshot_dir=args.snapshot_dir,
    )

    try:
        metrics = backtest.run()
    except RuntimeError as e:
        if "ENGINE FAILURE" in str(e):
            print(f"\nFATAL ENGINE FAILURE: {e}", file=sys.stderr)
            if backtest.last_good_state:
                print(f"Last good state: {backtest.last_good_state}", file=sys.stderr)
            import traceback
            traceback.print_exc(file=sys.stderr)
        # Still try to print summary with whatever data we have
        try:
            partial_metrics = backtest._calculate_metrics()
            if partial_metrics:
                print("\n" + "=" * 80)
                print("PARTIAL RESULTS (backtest failed before completion)")
                print("=" * 80)
                backtest.print_summary(partial_metrics, include_edge_analysis=False)
        except:
            pass
        return 1
    except Exception as e:
        print(f"\nFATAL ERROR in backtest execution: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        # Still try to print summary with whatever data we have
        try:
            partial_metrics = backtest._calculate_metrics()
            if partial_metrics:
                print("\n" + "=" * 80)
                print("PARTIAL RESULTS (backtest failed before completion)")
                print("=" * 80)
                backtest.print_summary(partial_metrics, include_edge_analysis=False)
        except:
            pass
        return 1
    
    # Guaranteed exit path: Always print summary
    try:
        backtest.print_summary(metrics, include_edge_analysis=not args.no_edge_analysis)
    except Exception as e:
        print(f"\nError printing summary: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        # At least show basic metrics
        if metrics:
            print(f"\nBasic Results:")
            print(f"  Final Value: ${metrics.get('final_value', 0):,.2f}")
            print(f"  Total Return: {metrics.get('total_return', 0):.2f}%")
            print(f"  Total Trades: {metrics.get('total_trades', 0)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
