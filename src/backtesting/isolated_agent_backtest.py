"""
Isolated Agent Backtest - Honest Testing Framework

Tests a SINGLE agent in complete isolation:
- No aggregation
- No portfolio manager
- No other agents
- Direct signal execution
- No parameter tuning
- No optimization

This is Step 1 of rigorous testing: Can the agent survive alone?

Usage:
    HEDGEFUND_NO_LLM=1 poetry run python src/backtesting/isolated_agent_backtest.py \
        --agent warren_buffett \
        --tickers AAPL,MSFT,GOOGL,TSLA,NVDA \
        --start-date 2019-01-01 \
        --end-date 2024-12-31 \
        --initial-capital 100000
"""

from __future__ import annotations

import os
import sys
import json
import random
import numpy as np
from datetime import datetime
from typing import Dict, List, Optional
from collections import defaultdict

import pandas as pd
from dateutil.relativedelta import relativedelta

from src.main import run_hedge_fund
from src.tools.api import get_price_data, get_prices
from src.utils.analysts import ANALYST_CONFIG
from src.data.price_cache import get_price_cache

# Force deterministic mode
os.environ["HEDGEFUND_NO_LLM"] = "1"

# Determinism: Seed all RNGs
DETERMINISTIC_SEED = 42
random.seed(DETERMINISTIC_SEED)
np.random.seed(DETERMINISTIC_SEED)


class IsolatedAgentBacktest:
    """
    Tests a SINGLE agent in complete isolation.
    No aggregation, no portfolio manager, no other agents.
    Direct signal execution only.
    """

    def __init__(
        self,
        agent_name: str,  # e.g., "warren_buffett", "peter_lynch", etc.
        tickers: List[str],
        start_date: str,
        end_date: str,
        initial_capital: float = 100000.0,
        margin_requirement: float = 0.0,
    ):
        self.agent_name = agent_name
        self.tickers = tickers
        self.start_date = start_date
        self.end_date = end_date
        self.initial_capital = initial_capital
        self.margin_requirement = margin_requirement

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

        # Track daily values
        self.daily_values = []
        self.trades = []

        # Transaction costs (conservative)
        self.COMMISSION_PER_SHARE = 0.01
        self.SLIPPAGE_BPS = 5  # 0.05%
        self.SPREAD_BPS = 3    # 0.03%

        # Performance optimization: Pre-load all price data into memory
        self.price_data = {}  # {ticker: DataFrame indexed by date}
        self._preload_price_data()
        
        # Performance optimization: Cache agent signals in deterministic mode
        # In deterministic mode, same inputs = same outputs, so we can cache
        self.signal_cache = {}  # {(date, agent_name, tickers_tuple): signals}
        self.is_deterministic = os.getenv("HEDGEFUND_NO_LLM") == "1"

    def _preload_price_data(self) -> None:
        """Pre-load all price data for the backtest period into memory."""
        cache = get_price_cache()
        for ticker in self.tickers:
            try:
                df = cache.get_prices_for_range(ticker, self.start_date, self.end_date)
                if df is not None and not df.empty:
                    # Set date as index for fast lookups
                    if 'date' in df.columns:
                        df = df.set_index('date')
                    elif df.index.name == 'date' or isinstance(df.index, pd.DatetimeIndex):
                        pass  # Already indexed by date
                    else:
                        # Try to infer date column
                        df.index = pd.to_datetime(df.index)
                    self.price_data[ticker] = df
                else:
                    self.price_data[ticker] = pd.DataFrame()
            except Exception as e:
                print(f"  WARNING: Failed to pre-load price data for {ticker}: {e}", file=sys.stderr, flush=True)
                self.price_data[ticker] = pd.DataFrame()

    def _get_current_prices(self, date: str) -> Dict[str, float]:
        """
        Get current prices for all tickers.
        Uses pre-loaded price data for fast lookups.
        """
        prices = {}
        date_obj = pd.to_datetime(date)
        
        for ticker in self.tickers:
            try:
                if ticker in self.price_data and not self.price_data[ticker].empty:
                    df = self.price_data[ticker]
                    # Try to find the date in the index
                    if date_obj in df.index:
                        prices[ticker] = float(df.loc[date_obj, 'close'])
                    else:
                        # Fallback: use PriceCache directly
                        cache = get_price_cache()
                        cached = cache.get(ticker, date)
                        if cached:
                            prices[ticker] = float(cached["close"])
                        else:
                            prices[ticker] = 0.0
                else:
                    # Fallback: use PriceCache directly
                    cache = get_price_cache()
                    cached = cache.get(ticker, date)
                    if cached:
                        prices[ticker] = float(cached["close"])
                    else:
                        prices[ticker] = 0.0
            except Exception as e:
                # If all methods fail, set to 0.0 (will be logged)
                prices[ticker] = 0.0
                
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
            # This P&L is already reflected in cash (proceeds received), but we need to account for
            # the current liability (what we owe) vs what we received
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
        # If NAV ≤ 0, trades are blocked and liquidation should occur
        if current_nav <= 0:
            return (False, "NAV is zero or negative - liquidation required")
        
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
        commission = quantity * self.COMMISSION_PER_SHARE
        slippage = trade_value * (self.SLIPPAGE_BPS / 10000)
        spread = trade_value * (self.SPREAD_BPS / 10000)
        total_cost = commission + slippage + spread
        
        # Estimate post-trade NAV (simplified - actual NAV depends on price changes)
        # For constraint checking, we use current prices and assume no price change
        post_trade_nav = current_nav
        
        if action == "buy":
            # Buying: cash decreases by trade value + costs, position value increases
            # Net: NAV decreases by costs only (assuming no price change)
            post_trade_nav -= total_cost
        elif action == "sell":
            # Selling: cash increases by trade value - costs, position value decreases
            # Net: NAV decreases by costs only
            post_trade_nav -= total_cost
        elif action == "short":
            # Shorting: receive proceeds, pay margin + costs
            # Net cash change: trade_value - margin - costs
            # Short position created (liability)
            # Net NAV change: -costs only (proceeds received, margin is collateral)
            margin_needed = trade_value * self.margin_requirement
            post_trade_nav -= total_cost
        elif action == "cover":
            # Covering: cash decreases by trade value + costs, short position closed
            # Net: NAV decreases by costs only
            post_trade_nav -= total_cost
        
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
        date: str,
        prices: Dict[str, float] = None,
    ) -> bool:
        """
        Execute a trade and apply transaction costs.
        Enforces strict capital and leverage constraints.
        """
        if quantity <= 0 or price <= 0:
            return False

        # Get current prices for constraint checking
        if prices is None:
            prices = self._get_current_prices(date)
        
        # Check capital and leverage constraints BEFORE executing
        allowed, reason = self._check_capital_constraints(ticker, action, quantity, price, prices)
        if not allowed:
            # Trade rejected due to constraints - this is expected behavior
            return False

        pos = self.portfolio["positions"][ticker]
        trade_value = quantity * price

        # Calculate transaction costs
        commission = quantity * self.COMMISSION_PER_SHARE
        slippage = trade_value * (self.SLIPPAGE_BPS / 10000)
        spread = trade_value * (self.SPREAD_BPS / 10000)
        total_cost = commission + slippage + spread

        if action == "buy":
            total_needed = trade_value + total_cost
            if total_needed > self.portfolio["cash"]:
                return False  # Insufficient cash

            self.portfolio["cash"] -= total_needed
            old_cost = pos["long_cost_basis"]
            old_qty = pos["long"]
            pos["long"] += quantity
            pos["long_cost_basis"] = (
                (old_cost * old_qty + trade_value) / pos["long"] if pos["long"] > 0 else 0
            )

            self.trades.append({
                "date": date,
                "ticker": ticker,
                "action": "buy",
                "quantity": quantity,
                "price": price,
                "cost": total_cost,
            })

        elif action == "sell":
            if pos["long"] < quantity:
                return False

            proceeds = trade_value - total_cost
            self.portfolio["cash"] += proceeds
            pnl = (price - pos["long_cost_basis"]) * quantity
            self.portfolio["realized_gains"][ticker]["long"] += pnl
            pos["long"] -= quantity
            if pos["long"] == 0:
                pos["long_cost_basis"] = 0.0

            self.trades.append({
                "date": date,
                "ticker": ticker,
                "action": "sell",
                "quantity": quantity,
                "price": price,
                "cost": total_cost,
            })

        elif action == "short":
            # Shorting: sell shares you don't own
            # 1. Receive proceeds from sale (cash increases)
            # 2. Put up margin as collateral (cash decreases)
            # 3. Pay transaction costs (cash decreases)
            # Net: cash increases by (proceeds - margin - costs)
            margin_needed = trade_value * self.margin_requirement
            total_needed = margin_needed + total_cost
            
            # Check if we have enough cash for margin + costs
            # Note: We'll receive proceeds, but need margin upfront
            if total_needed > self.portfolio["cash"]:
                return False

            # Receive proceeds from short sale, pay margin and costs
            self.portfolio["cash"] += trade_value  # Receive proceeds
            self.portfolio["cash"] -= total_needed   # Pay margin + costs
            # Net cash change: trade_value - margin_needed - total_cost
            
            self.portfolio["margin_used"] += margin_needed
            old_cost = pos["short_cost_basis"]
            old_qty = pos["short"]
            pos["short"] += quantity
            pos["short_cost_basis"] = (
                (old_cost * old_qty + trade_value) / pos["short"] if pos["short"] > 0 else 0
            )
            pos["short_margin_used"] += margin_needed

            self.trades.append({
                "date": date,
                "ticker": ticker,
                "action": "short",
                "quantity": quantity,
                "price": price,
                "cost": total_cost,
            })

        elif action == "cover":
            if pos["short"] < quantity:
                return False

            # Covering: buy back shares to close short position
            # Pay: trade_value + costs
            # Receive: margin back
            cost_to_cover = trade_value + total_cost
            if cost_to_cover > self.portfolio["cash"]:
                return False

            self.portfolio["cash"] -= cost_to_cover
            # Calculate P&L: you sold at short_cost_basis, buying back at current price
            avg_short_price = pos["short_cost_basis"] if pos["short"] > 0 else price
            # P&L = (sale_price - buy_price) * quantity - costs
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

            self.trades.append({
                "date": date,
                "ticker": ticker,
                "action": "cover",
                "quantity": quantity,
                "price": price,
                "cost": total_cost,
            })

        # Post-trade validation: NAV must never go below zero
        post_trade_nav = self._calculate_portfolio_value(prices)
        if post_trade_nav < 0:
            raise RuntimeError(
                f"ENGINE FAILURE: Trade execution resulted in negative NAV: ${post_trade_nav:.2f}\n"
                f"Trade: {action} {quantity} {ticker} @ ${price:.2f}"
            )

        return True

    def _get_agent_signal(self, date: str) -> Dict[str, Dict]:
        """
        Get signal from the isolated agent ONLY.
        No aggregation, no portfolio manager, just the raw agent signal.
        
        Performance: Caches signals in deterministic mode (same inputs = same outputs).
        """
        # Use a lookback period for analysis
        lookback_date = (datetime.strptime(date, "%Y-%m-%d") - relativedelta(days=30)).strftime("%Y-%m-%d")

        # Performance optimization: Cache signals in deterministic mode
        if self.is_deterministic:
            cache_key = (date, self.agent_name, tuple(sorted(self.tickers)), lookback_date)
            if cache_key in self.signal_cache:
                return self.signal_cache[cache_key]

        try:
            result = run_hedge_fund(
                tickers=self.tickers,
                start_date=lookback_date,
                end_date=date,
                portfolio=self.portfolio.copy(),
                show_reasoning=False,
                selected_analysts=[self.agent_name],  # ONLY this agent
                model_name="deterministic",
                model_provider="deterministic",
            )
        except Exception as e:
            print(f"  ERROR in run_hedge_fund for {date}: {e}", file=sys.stderr, flush=True)
            return {}

        if not isinstance(result, dict):
            return {}

        analyst_signals = result.get("analyst_signals", {})
        agent_node_name = f"{self.agent_name}_agent"

        # Get signal from this agent only
        agent_signals = {}
        if agent_node_name in analyst_signals:
            agent_signals = analyst_signals[agent_node_name]

        # Cache the result in deterministic mode
        if self.is_deterministic:
            cache_key = (date, self.agent_name, tuple(sorted(self.tickers)), lookback_date)
            self.signal_cache[cache_key] = agent_signals

        return agent_signals

    def _force_liquidation(self, date: str, prices: Dict[str, float]) -> None:
        """
        Force liquidation of all positions when NAV ≤ 0.
        Closes all long and short positions, then stops the backtest.
        This bypasses normal constraint checks to ensure positions are closed.
        """
        print(f"\n{'='*80}", flush=True)
        print(f"FORCED LIQUIDATION: NAV ≤ 0", flush=True)
        print(f"{'='*80}", flush=True)
        print(f"Date: {date}", flush=True)
        print(f"Liquidating all positions...", flush=True)
        
        liquidation_trades = 0
        
        for ticker in self.tickers:
            pos = self.portfolio["positions"][ticker]
            price = prices.get(ticker, 0.0)
            
            if price <= 0:
                continue
            
            # Close long positions (bypass constraint checks for liquidation)
            if pos["long"] > 0:
                quantity = pos["long"]
                try:
                    # Direct execution without constraint checks for liquidation
                    pos = self.portfolio["positions"][ticker]
                    trade_value = quantity * price
                    commission = quantity * self.COMMISSION_PER_SHARE
                    slippage = trade_value * (self.SLIPPAGE_BPS / 10000)
                    spread = trade_value * (self.SPREAD_BPS / 10000)
                    total_cost = commission + slippage + spread
                    
                    proceeds = trade_value - total_cost
                    self.portfolio["cash"] += proceeds
                    pnl = (price - pos["long_cost_basis"]) * quantity
                    self.portfolio["realized_gains"][ticker]["long"] += pnl
                    pos["long"] = 0
                    pos["long_cost_basis"] = 0.0
                    
                    liquidation_trades += 1
                    print(f"  Closed {quantity} shares of {ticker} long @ ${price:.2f}", flush=True)
                except Exception as e:
                    print(f"  WARNING: Failed to close {ticker} long: {e}", flush=True)
            
            # Close short positions (bypass constraint checks for liquidation)
            if pos["short"] > 0:
                quantity = pos["short"]
                try:
                    # Direct execution without constraint checks for liquidation
                    pos = self.portfolio["positions"][ticker]
                    trade_value = quantity * price
                    commission = quantity * self.COMMISSION_PER_SHARE
                    slippage = trade_value * (self.SLIPPAGE_BPS / 10000)
                    spread = trade_value * (self.SPREAD_BPS / 10000)
                    total_cost = commission + slippage + spread
                    
                    cost_to_cover = trade_value + total_cost
                    self.portfolio["cash"] -= cost_to_cover
                    avg_short_price = pos["short_cost_basis"] if pos["short"] > 0 else price
                    pnl = (avg_short_price * quantity) - cost_to_cover
                    self.portfolio["realized_gains"][ticker]["short"] += pnl
                    margin_returned = (pos["short_margin_used"] / pos["short"]) * quantity if pos["short"] > 0 else 0
                    self.portfolio["cash"] += margin_returned
                    self.portfolio["margin_used"] -= margin_returned
                    pos["short"] = 0
                    pos["short_cost_basis"] = 0.0
                    pos["short_margin_used"] = 0.0
                    
                    liquidation_trades += 1
                    print(f"  Closed {quantity} shares of {ticker} short @ ${price:.2f}", flush=True)
                except Exception as e:
                    print(f"  WARNING: Failed to close {ticker} short: {e}", flush=True)
        
        final_nav = self._calculate_portfolio_value(prices)
        print(f"\nLiquidation complete: {liquidation_trades} positions closed", flush=True)
        print(f"Final NAV after liquidation: ${final_nav:,.2f}", flush=True)
        print(f"{'='*80}\n", flush=True)
        
        # Record the liquidation event
        self.daily_values.append({
            "Date": date,
            "Portfolio Value": final_nav,
            "Liquidation": True,
        })
    
    def _execute_agent_signal(self, date: str, prices: Dict[str, float]):
        """
        Execute trades based on agent signal ONLY.
        No aggregation, no portfolio manager logic.
        Direct signal-to-trade execution.
        Enforces capital and leverage constraints.
        
        STRICT CONSTRAINTS:
        - NAV must never go below zero (checked before and after trades)
        - Max gross exposure ≤ 100% of NAV
        - Max position size ≤ 20% of NAV per ticker
        - No new positions if NAV ≤ 50% of initial capital
        """
        # Pre-check: If NAV ≤ 0, block all trades
        current_nav = self._calculate_portfolio_value(prices)
        if current_nav <= 0:
            # This should have been caught by the daily NAV check, but double-check
            return  # Block all trades if NAV ≤ 0
        
        agent_signals = self._get_agent_signal(date)

        for ticker in self.tickers:
            signal_data = agent_signals.get(ticker, {})
            signal = signal_data.get("signal", "neutral")
            confidence = signal_data.get("confidence", 50)

            if signal == "neutral":
                continue  # No trade on neutral

            price = prices.get(ticker, 0.0)
            if price <= 0:
                continue

            pos = self.portfolio["positions"][ticker]

            # DIRECT SIGNAL EXECUTION - No aggregation, no portfolio manager
            # Simple rule: signal = action, confidence = position size
            # Position sizing respects 20% max per ticker constraint
            if signal == "bullish":
                # Buy: Use confidence to scale position, but cap at 20% of NAV
                if pos["long"] == 0:  # Only enter if not already long
                    # Calculate max position size (20% of NAV)
                    max_position_value = current_nav * 0.20
                    # Scale by confidence
                    target_position_value = (confidence / 100.0) * max_position_value
                    quantity = int(target_position_value / price)
                    if quantity > 0:
                        self._execute_trade(ticker, "buy", quantity, price, date, prices)

            elif signal == "bearish":
                # Sell if long, or short if not long
                if pos["long"] > 0:
                    # Sell existing position
                    self._execute_trade(ticker, "sell", pos["long"], price, date, prices)
                elif pos["short"] == 0:  # Only enter if not already short
                    # Short: Use confidence to scale position, but cap at 20% of NAV
                    max_position_value = current_nav * 0.20
                    target_position_value = (confidence / 100.0) * max_position_value
                    quantity = int(target_position_value / price)
                    if quantity > 0:
                        self._execute_trade(ticker, "short", quantity, price, date, prices)

    def _calculate_metrics(self) -> Dict:
        """Calculate performance metrics vs buy-and-hold."""
        if not self.daily_values:
            return {}

        df = pd.DataFrame(self.daily_values)
        df.set_index("Date", inplace=True)
        df.sort_index(inplace=True)

        initial_value = self.initial_capital
        final_value = df["Portfolio Value"].iloc[-1]
        total_return = ((final_value - initial_value) / initial_value) * 100

        # Calculate returns
        df["Returns"] = df["Portfolio Value"].pct_change()
        returns = df["Returns"].dropna()

        # Max drawdown
        cumulative = (1 + returns).cumprod()
        running_max = cumulative.expanding().max()
        drawdown = (cumulative - running_max) / running_max
        max_drawdown = drawdown.min() * 100
        max_drawdown_date = drawdown.idxmin()

        # Sharpe ratio (annualized)
        if len(returns) > 1 and returns.std() > 0:
            sharpe = (returns.mean() / returns.std()) * (252 ** 0.5)
        else:
            sharpe = 0.0

        # Calculate buy-and-hold returns (equal-weighted portfolio) - VECTORIZED
        # Much faster than looping through dates
        price_cols = [f"{ticker}_Price" for ticker in self.tickers]
        available_cols = [col for col in price_cols if col in df.columns]
        
        if available_cols:
            # Get initial prices (first row)
            initial_prices = df.loc[df.index[0], available_cols]
            # Get all current prices
            current_prices = df[available_cols]
            # Calculate returns: (current / initial) for each ticker
            returns = current_prices.div(initial_prices, axis='columns')
            # Replace inf/NaN with 0 (for missing initial prices)
            returns = returns.replace([np.inf, -np.inf], 0).fillna(0)
            # Equal-weighted: each ticker gets equal allocation
            ticker_allocation = initial_value / len(available_cols)
            # Sum returns across tickers and multiply by allocation
            df["BuyHold"] = returns.sum(axis=1) * ticker_allocation
        else:
            # Fallback: no price data available
            df["BuyHold"] = initial_value
        bh_final = df["BuyHold"].iloc[-1]
        bh_return = ((bh_final - initial_value) / initial_value) * 100

        # Transaction costs
        total_costs = sum(t["cost"] for t in self.trades)
        cost_pct = (total_costs / initial_value) * 100

        return {
            "agent": self.agent_name,
            "period": f"{self.start_date} to {self.end_date}",
            "tickers": self.tickers,
            "initial_capital": initial_value,
            "final_value": final_value,
            "total_return": total_return,
            "buy_hold_return": bh_return,
            "excess_return": total_return - bh_return,
            "max_drawdown": max_drawdown,
            "max_drawdown_date": max_drawdown_date,
            "sharpe_ratio": sharpe,
            "total_trades": len(self.trades),
            "total_costs": total_costs,
            "cost_pct": cost_pct,
            "win_rate": self._calculate_win_rate(),
        }

    def _calculate_win_rate(self) -> float:
        """Calculate win rate from realized gains."""
        winning_trades = 0
        total_trades = 0

        for ticker in self.tickers:
            long_pnl = self.portfolio["realized_gains"][ticker]["long"]
            short_pnl = self.portfolio["realized_gains"][ticker]["short"]
            total_pnl = long_pnl + short_pnl

            if total_pnl != 0:
                total_trades += 1
                if total_pnl > 0:
                    winning_trades += 1

        return (winning_trades / total_trades * 100) if total_trades > 0 else 0.0

    def run(self) -> Dict:
        """Run the isolated agent backtest."""
        print(f"\n{'='*80}")
        print(f"ISOLATED AGENT BACKTEST - {self.agent_name.upper()}")
        print(f"{'='*80}")
        print(f"Agent: {self.agent_name} (ONLY - no aggregation, no other agents)")
        print(f"Period: {self.start_date} to {self.end_date}")
        print(f"Tickers: {', '.join(self.tickers)}")
        print(f"Initial Capital: ${self.initial_capital:,.2f}")
        print(f"Deterministic Seed: {DETERMINISTIC_SEED}")
        print(f"{'='*80}\n")

        dates = pd.bdate_range(self.start_date, self.end_date)

        if len(dates) == 0:
            print("Error: No business days in date range", file=sys.stderr)
            return {}

        total_days = len(dates)
        print(f"Total trading days: {total_days}\n")
        
        # Performance: Pre-load price data status
        loaded_tickers = sum(1 for t in self.tickers if t in self.price_data and not self.price_data[t].empty)
        if loaded_tickers > 0:
            print(f"Price data pre-loaded for {loaded_tickers}/{len(self.tickers)} tickers", flush=True)
        if self.is_deterministic:
            print(f"Signal caching enabled (deterministic mode)", flush=True)
        print("", flush=True)

        for i, date in enumerate(dates):
            date_str = date.strftime("%Y-%m-%d")

            if i % 50 == 0 or i == 0:
                print(f"Processing {date_str} ({i+1}/{total_days})...", flush=True)

            try:
                # Get current prices
                prices = self._get_current_prices(date_str)
                
                # Count tickers with valid prices
                valid_prices = [p for p in prices.values() if p > 0]
                if i == 0:
                    print(f"  Got prices for {len(valid_prices)}/{len(self.tickers)} tickers", flush=True)
                    if len(valid_prices) == 0:
                        print(f"  WARNING: No price data available for any ticker on {date_str}", flush=True)
                        print(f"  Check that CSV files exist in src/data/prices/ for: {', '.join(self.tickers)}", flush=True)
                
                # Skip day if no prices available (data not loaded yet)
                if len(valid_prices) == 0:
                    if i == 0:
                        print(f"  Skipping day {i+1} - no price data available", flush=True)
                    continue

                # Execute agent signal directly (no aggregation)
                if i == 0:
                    print(f"  Getting agent signal...", flush=True)
                self._execute_agent_signal(date_str, prices)
                
                if i == 0:
                    print(f"  Signal executed", flush=True)

                # Record daily value
                portfolio_value = self._calculate_portfolio_value(prices)
                
                # STRICT CONSTRAINT: If NAV ≤ 0, force liquidation and stop backtest
                if portfolio_value <= 0:
                    print(f"\n{'!'*80}", flush=True)
                    print(f"CRITICAL: NAV ≤ 0 detected on {date_str}", flush=True)
                    print(f"NAV: ${portfolio_value:.2f}", flush=True)
                    print(f"{'!'*80}", flush=True)
                    
                    # Force liquidation of all positions
                    self._force_liquidation(date_str, prices)
                    
                    # Stop the backtest
                    print(f"\nBacktest stopped due to NAV ≤ 0 constraint violation.", flush=True)
                    print(f"Remaining trading days skipped: {total_days - i - 1}", flush=True)
                    break
                
                # Constraint validation: NAV must never go below zero (sanity check)
                if portfolio_value < 0:
                    raise RuntimeError(
                        f"ENGINE FAILURE: Portfolio value went negative: ${portfolio_value:.2f} on {date_str}\n"
                        f"This should have been caught by the NAV ≤ 0 check above."
                    )
                
                daily_record = {
                    "Date": date_str,
                    "Portfolio Value": portfolio_value,
                }
                for ticker in self.tickers:
                    daily_record[f"{ticker}_Price"] = prices.get(ticker, 0.0)
                self.daily_values.append(daily_record)
                
                if i == 0:
                    print(f"  Day 1 complete. Portfolio value: ${portfolio_value:,.2f}", flush=True)
                    
            except Exception as e:
                print(f"\nERROR on day {i+1} ({date_str}): {e}", file=sys.stderr, flush=True)
                import traceback
                traceback.print_exc(file=sys.stderr)
                raise

        print("\nCalculating metrics...\n")
        metrics = self._calculate_metrics()

        # Print results
        self._print_results(metrics)

        return metrics

    def _print_results(self, metrics: Dict):
        """Print honest results - no sugar coating."""
        print(f"\n{'='*80}")
        print("RESULTS")
        print(f"{'='*80}\n")

        print(f"Agent: {metrics['agent']}")
        print(f"Period: {metrics['period']}")
        print(f"Tickers: {len(metrics['tickers'])}")
        print(f"\nPerformance:")
        print(f"  Initial Capital: ${metrics['initial_capital']:,.2f}")
        print(f"  Final Value: ${metrics['final_value']:,.2f}")
        print(f"  Total Return: {metrics['total_return']:+.2f}%")
        print(f"\nBuy-and-Hold:")
        print(f"  Buy-Hold Return: {metrics['buy_hold_return']:+.2f}%")
        print(f"  Excess Return: {metrics['excess_return']:+.2f}%")
        print(f"\nRisk:")
        print(f"  Max Drawdown: {metrics['max_drawdown']:.2f}%")
        print(f"  Max Drawdown Date: {metrics['max_drawdown_date']}")
        print(f"  Sharpe Ratio: {metrics['sharpe_ratio']:.2f}")
        print(f"\nTrading:")
        print(f"  Total Trades: {metrics['total_trades']}")
        print(f"  Transaction Costs: ${metrics['total_costs']:,.2f} ({metrics['cost_pct']:.2f}%)")
        print(f"  Win Rate: {metrics['win_rate']:.1f}%")
        print(f"\n{'='*80}")
        print("VERDICT:")
        print(f"{'='*80}")
        
        # Calculate buy-and-hold drawdown for comparison
        df_bh = pd.DataFrame(self.daily_values)
        if "BuyHold" in df_bh.columns and len(df_bh) > 1:
            df_bh["BH_Returns"] = df_bh["BuyHold"].pct_change()
            bh_returns = df_bh["BH_Returns"].dropna()
            if len(bh_returns) > 0:
                bh_cumulative = (1 + bh_returns).cumprod()
                bh_running_max = bh_cumulative.expanding().max()
                bh_drawdown = (bh_cumulative - bh_running_max) / bh_running_max
                bh_max_drawdown = bh_drawdown.min() * 100
            else:
                bh_max_drawdown = 0.0
        else:
            bh_max_drawdown = 0.0
        
        # Honest assessment
        if metrics['excess_return'] > 0 and abs(metrics['max_drawdown']) < abs(bh_max_drawdown):
            print("✓ PASSES: Beats buy-and-hold with lower drawdown")
        else:
            print("✗ FAILS: Does not beat buy-and-hold or has higher drawdown")
            if metrics['excess_return'] <= 0:
                print(f"  Reason: Excess return is {metrics['excess_return']:.2f}% (must be > 0%)")
            if abs(metrics['max_drawdown']) >= abs(bh_max_drawdown):
                print(f"  Reason: Max drawdown is {metrics['max_drawdown']:.2f}% vs buy-hold {bh_max_drawdown:.2f}%")
        
        print(f"{'='*80}\n")


def main():
    """CLI entry point."""
    import argparse
    from src.utils.analysts import ANALYST_CONFIG

    # Get all available agents from ANALYST_CONFIG (excluding advisory-only and system agents)
    available_agents = [
        key for key, config in ANALYST_CONFIG.items()
        if not config.get("advisory_only", False)
    ]

    parser = argparse.ArgumentParser(
        description="Isolated Agent Backtest - Test a single agent in complete isolation"
    )
    parser.add_argument(
        "--agent",
        type=str,
        required=True,
        choices=available_agents,
        help=f"Agent to test in isolation. Available: {', '.join(available_agents)}",
    )
    parser.add_argument(
        "--tickers",
        type=str,
        required=True,
        help="Comma-separated list of tickers",
    )
    parser.add_argument(
        "--start-date",
        type=str,
        required=True,
        help="Start date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--end-date",
        type=str,
        required=True,
        help="End date (YYYY-MM-DD)",
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

    args = parser.parse_args()

    tickers = [t.strip().upper() for t in args.tickers.split(",")]

    backtest = IsolatedAgentBacktest(
        agent_name=args.agent,
        tickers=tickers,
        start_date=args.start_date,
        end_date=args.end_date,
        initial_capital=args.initial_capital,
        margin_requirement=args.margin_requirement,
    )

    metrics = backtest.run()
    return metrics


if __name__ == "__main__":
    main()
