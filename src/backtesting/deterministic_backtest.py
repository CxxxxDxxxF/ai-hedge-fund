"""
Deterministic Backtest Runner for 5-Core-Agent System

Runs backtests using only rule-based logic (no LLMs).
Tracks performance metrics and agent contributions.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from collections import defaultdict

import pandas as pd
from dateutil.relativedelta import relativedelta

from src.main import run_hedge_fund
from src.tools.api import get_price_data, get_prices
from src.utils.analysts import ANALYST_CONFIG


# Force deterministic mode
os.environ["HEDGEFUND_NO_LLM"] = "1"


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
    ):
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

        # Performance tracking
        self.daily_values: List[Dict] = []
        self.trades: List[Dict] = []
        # Initialize agent contributions with canonical agent names (defensive)
        self.agent_contributions: Dict[str, Dict[str, float]] = {
            agent_name: {"pnl": 0.0, "trades": 0}
            for agent_name in self.CORE_AGENTS.values()
        }

    def _get_current_prices(self, date: str) -> Dict[str, float]:
        """Get current prices for all tickers on a given date."""
        prices = {}
        for ticker in self.tickers:
            try:
                # Get price data for the date (use a small window to ensure we have data)
                lookback_date = (datetime.strptime(date, "%Y-%m-%d") - timedelta(days=5)).strftime("%Y-%m-%d")
                price_df = get_price_data(ticker, lookback_date, date)
                if not price_df.empty:
                    # Get the price closest to the target date
                    price_df = price_df[price_df.index <= pd.Timestamp(date)]
                    if not price_df.empty:
                        prices[ticker] = float(price_df["close"].iloc[-1])
                    else:
                        prices[ticker] = 0.0
                else:
                    prices[ticker] = 0.0
            except Exception as e:
                # Silently use 0.0 if price unavailable (non-trading day, etc.)
                prices[ticker] = 0.0
        return prices

    def _calculate_portfolio_value(self, prices: Dict[str, float]) -> float:
        """Calculate total portfolio value."""
        total_value = self.portfolio["cash"]

        for ticker in self.tickers:
            pos = self.portfolio["positions"][ticker]
            price = prices.get(ticker, 0.0)

            # Long positions
            if pos["long"] > 0:
                total_value += pos["long"] * price

            # Short positions (value is negative)
            if pos["short"] > 0:
                # Short value = cost basis - current value (profit if price goes down)
                short_value = (pos["short_cost_basis"] - (pos["short"] * price))
                total_value += short_value

        return total_value

    def _execute_trade(
        self,
        ticker: str,
        action: str,
        quantity: int,
        price: float,
        agent_signals: Dict,
    ) -> bool:
        """Execute a trade and track agent contributions."""
        if quantity <= 0 or price <= 0:
            return False

        pos = self.portfolio["positions"][ticker]
        cost = quantity * price

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
            proceeds = quantity * price
            self.portfolio["cash"] += proceeds
            pnl = (price - pos["long_cost_basis"]) * quantity
            self.portfolio["realized_gains"][ticker]["long"] += pnl
            pos["long"] -= quantity
            if pos["long"] == 0:
                pos["long_cost_basis"] = 0.0

            # Track agent contribution (defensive: ensure agent exists in dict)
            for agent in contributing_agents:
                if agent in self.agent_contributions:
                    self.agent_contributions[agent]["pnl"] += pnl

        elif action == "short":
            margin_needed = cost * self.margin_requirement
            if margin_needed > self.portfolio["cash"]:
                return False  # Insufficient margin
            self.portfolio["cash"] -= margin_needed
            self.portfolio["margin_used"] += margin_needed
            old_cost = pos["short_cost_basis"]
            old_qty = pos["short"]
            pos["short"] += quantity
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
            cost_to_cover = quantity * price
            if cost_to_cover > self.portfolio["cash"]:
                return False  # Insufficient cash
            self.portfolio["cash"] -= cost_to_cover
            # Short PnL: profit when price goes down (cost basis > current price)
            # pnl = proceeds from short sale - cost to cover
            avg_short_price = pos["short_cost_basis"] if pos["short"] > 0 else price
            pnl = (avg_short_price * quantity) - cost_to_cover
            self.portfolio["realized_gains"][ticker]["short"] += pnl
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

        # Record trade
        self.trades.append(
            {
                "date": datetime.strptime(self.current_date, "%Y-%m-%d"),
                "ticker": ticker,
                "action": action,
                "quantity": quantity,
                "price": price,
                "agents": ", ".join(contributing_agents) if contributing_agents else "None",
            }
        )

        return True

    def _run_daily_decision(self, date: str) -> None:
        """Run trading decision for a single day."""
        self.current_date = date

        # Get current prices
        prices = self._get_current_prices(date)

        # Run hedge fund system for this date
        # Use a lookback period for analysis (agents need historical data)
        lookback_date = (datetime.strptime(date, "%Y-%m-%d") - relativedelta(days=30)).strftime("%Y-%m-%d")
        
        try:
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

            # Execute trades from portfolio decisions
            portfolio_decisions = result.get("portfolio_decisions", {})
            analyst_signals = result.get("analyst_signals", {})

            for ticker, decision in portfolio_decisions.items():
                action = decision.get("action", "hold").lower()
                quantity = int(decision.get("quantity", 0))
                price = prices.get(ticker, 0.0)

                if action != "hold" and quantity > 0:
                    self._execute_trade(ticker, action, quantity, price, analyst_signals)

        except Exception as e:
            print(f"Warning: Error running decision for {date}: {e}")

        # Calculate portfolio value
        portfolio_value = self._calculate_portfolio_value(prices)

        # Calculate exposures
        long_exposure = sum(
            self.portfolio["positions"][t]["long"] * prices.get(t, 0.0)
            for t in self.tickers
        )
        short_exposure = sum(
            self.portfolio["positions"][t]["short"] * prices.get(t, 0.0)
            for t in self.tickers
        )

        # Record daily value
        self.daily_values.append(
            {
                "Date": datetime.strptime(date, "%Y-%m-%d"),
                "Portfolio Value": portfolio_value,
                "Cash": self.portfolio["cash"],
                "Long Exposure": long_exposure,
                "Short Exposure": short_exposure,
            }
        )

    def run(self) -> Dict:
        """Run the backtest."""
        print(f"Running deterministic backtest from {self.start_date} to {self.end_date}...")
        print(f"Tickers: {', '.join(self.tickers)}")
        print(f"Initial Capital: ${self.initial_capital:,.2f}\n")

        # Generate business days
        dates = pd.bdate_range(self.start_date, self.end_date)
        
        if len(dates) == 0:
            print("Error: No business days in date range")
            return {}
        
        total_days = len(dates)
        print(f"Total trading days: {total_days}\n")
        
        for i, date in enumerate(dates):
            date_str = date.strftime("%Y-%m-%d")
            if (i + 1) % 20 == 0 or i == 0 or i == total_days - 1:
                print(f"Processing {date_str} ({i+1}/{total_days})...")
            self._run_daily_decision(date_str)

        # Calculate metrics
        metrics = self._calculate_metrics()

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
        max_drawdown_date = df["Drawdown"].idxmin().strftime("%Y-%m-%d") if not df["Drawdown"].empty else None

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
        }

    def print_summary(self, metrics: Dict) -> None:
        """Print backtest summary table."""
        print("\n" + "=" * 80)
        print("DETERMINISTIC BACKTEST SUMMARY")
        print("=" * 80)

        print(f"\nPeriod: {self.start_date} to {self.end_date}")
        print(f"Tickers: {', '.join(self.tickers)}")
        print(f"Initial Capital: ${self.initial_capital:,.2f}")

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
        print(f"{'Agent':<20} {'PnL':<15} {'PnL %':<10} {'Trades':<10}")
        print("-" * 80)
        for agent, data in metrics["agent_contributions"].items():
            print(
                f"{agent:<20} {data['PnL']:<15} {data['PnL %']:<10} {data['Trades']:<10}"
            )

        print("\n" + "=" * 80)


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

    args = parser.parse_args()

    # Ensure deterministic mode
    os.environ["HEDGEFUND_NO_LLM"] = "1"

    tickers = [t.strip().upper() for t in args.tickers.split(",")]

    backtest = DeterministicBacktest(
        tickers=tickers,
        start_date=args.start_date,
        end_date=args.end_date,
        initial_capital=args.initial_capital,
        margin_requirement=args.margin_requirement,
    )

    metrics = backtest.run()
    backtest.print_summary(metrics)

    return 0


if __name__ == "__main__":
    sys.exit(main())
