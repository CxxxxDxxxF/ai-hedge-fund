from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import pandas as pd
import numpy as np
from typing import Callable, Dict, List, Optional, Any
import asyncio

from src.tools.api import (
    get_company_news,
    get_price_data,
    get_prices,
    get_financial_metrics,
    get_insider_trades,
)
from app.backend.services.graph import run_graph_async, parse_hedge_fund_response
from app.backend.services.portfolio import create_portfolio

class BacktestService:
    """
    Core backtesting service that focuses purely on backtesting logic.
    Uses a pre-compiled graph and portfolio for trading decisions.
    """

    def __init__(
        self,
        graph,
        portfolio: dict,
        tickers: List[str],
        start_date: str,
        end_date: str,
        initial_capital: float,
        model_name: str = "gpt-4.1",
        model_provider: str = "OpenAI",
        request: dict = {},
    ):
        """
        Initialize the backtest service.
        
        :param graph: Pre-compiled LangGraph graph for trading decisions.
        :param portfolio: Initial portfolio state.
        :param tickers: List of tickers to backtest.
        :param start_date: Start date string (YYYY-MM-DD).
        :param end_date: End date string (YYYY-MM-DD).
        :param initial_capital: Starting portfolio cash.
        :param model_name: Which LLM model name to use.
        :param model_provider: Which LLM provider.
        :param request: Request object containing API keys and other metadata.
        """
        self.graph = graph
        self.portfolio = portfolio
        self.tickers = tickers
        self.start_date = start_date
        self.end_date = end_date
        self.initial_capital = initial_capital
        self.model_name = model_name
        self.model_provider = model_provider
        self.request = request
        self.portfolio_values = []
        # Trade tracking for metrics calculation
        self.trades = []  # List of all executed trades
        self.daily_pnl = []  # List of daily PnL records
        self.previous_portfolio_value = initial_capital

    def execute_trade(self, ticker: str, action: str, quantity: float, current_price: float) -> int:
        """
        Execute trades with support for both long and short positions.
        Returns the actual quantity traded.
        """
        if quantity <= 0:
            return 0

        quantity = int(quantity)  # force integer shares
        position = self.portfolio["positions"][ticker]

        if action == "buy":
            cost = quantity * current_price
            if cost <= self.portfolio["cash"]:
                # Weighted average cost basis for the new total
                old_shares = position["long"]
                old_cost_basis = position["long_cost_basis"]
                new_shares = quantity
                total_shares = old_shares + new_shares

                if total_shares > 0:
                    total_old_cost = old_cost_basis * old_shares
                    total_new_cost = cost
                    position["long_cost_basis"] = (total_old_cost + total_new_cost) / total_shares

                position["long"] += quantity
                self.portfolio["cash"] -= cost
                return quantity
            else:
                # Calculate maximum affordable quantity
                max_quantity = int(self.portfolio["cash"] / current_price)
                if max_quantity > 0:
                    cost = max_quantity * current_price
                    old_shares = position["long"]
                    old_cost_basis = position["long_cost_basis"]
                    total_shares = old_shares + max_quantity

                    if total_shares > 0:
                        total_old_cost = old_cost_basis * old_shares
                        total_new_cost = cost
                        position["long_cost_basis"] = (total_old_cost + total_new_cost) / total_shares

                    position["long"] += max_quantity
                    self.portfolio["cash"] -= cost
                    return max_quantity
                return 0

        elif action == "sell":
            quantity = min(quantity, position["long"])
            if quantity > 0:
                avg_cost_per_share = position["long_cost_basis"] if position["long"] > 0 else 0
                realized_gain = (current_price - avg_cost_per_share) * quantity
                self.portfolio["realized_gains"][ticker]["long"] += realized_gain

                position["long"] -= quantity
                self.portfolio["cash"] += quantity * current_price

                if position["long"] == 0:
                    position["long_cost_basis"] = 0.0

                return quantity

        elif action == "short":
            proceeds = current_price * quantity
            margin_required = proceeds * self.portfolio["margin_requirement"]
            if margin_required <= self.portfolio["cash"]:
                # Weighted average short cost basis
                old_short_shares = position["short"]
                old_cost_basis = position["short_cost_basis"]
                new_shares = quantity
                total_shares = old_short_shares + new_shares

                if total_shares > 0:
                    total_old_cost = old_cost_basis * old_short_shares
                    total_new_cost = current_price * new_shares
                    position["short_cost_basis"] = (total_old_cost + total_new_cost) / total_shares

                position["short"] += quantity
                position["short_margin_used"] += margin_required
                self.portfolio["margin_used"] += margin_required

                self.portfolio["cash"] += proceeds
                self.portfolio["cash"] -= margin_required
                return quantity
            else:
                margin_ratio = self.portfolio["margin_requirement"]
                if margin_ratio > 0:
                    max_quantity = int(self.portfolio["cash"] / (current_price * margin_ratio))
                else:
                    max_quantity = 0

                if max_quantity > 0:
                    proceeds = current_price * max_quantity
                    margin_required = proceeds * margin_ratio

                    old_short_shares = position["short"]
                    old_cost_basis = position["short_cost_basis"]
                    total_shares = old_short_shares + max_quantity

                    if total_shares > 0:
                        total_old_cost = old_cost_basis * old_short_shares
                        total_new_cost = current_price * max_quantity
                        position["short_cost_basis"] = (total_old_cost + total_new_cost) / total_shares

                    position["short"] += max_quantity
                    position["short_margin_used"] += margin_required
                    self.portfolio["margin_used"] += margin_required

                    self.portfolio["cash"] += proceeds
                    self.portfolio["cash"] -= margin_required
                    return max_quantity
                return 0

        elif action == "cover":
            quantity = min(quantity, position["short"])
            if quantity > 0:
                cover_cost = quantity * current_price
                avg_short_price = position["short_cost_basis"] if position["short"] > 0 else 0
                realized_gain = (avg_short_price - current_price) * quantity

                if position["short"] > 0:
                    portion = quantity / position["short"]
                else:
                    portion = 1.0

                margin_to_release = portion * position["short_margin_used"]

                position["short"] -= quantity
                position["short_margin_used"] -= margin_to_release
                self.portfolio["margin_used"] -= margin_to_release

                self.portfolio["cash"] += margin_to_release
                self.portfolio["cash"] -= cover_cost

                self.portfolio["realized_gains"][ticker]["short"] += realized_gain

                if position["short"] == 0:
                    position["short_cost_basis"] = 0.0
                    position["short_margin_used"] = 0.0

                return quantity

        return 0

    def _record_trade_entry(self, ticker: str, action: str, date: str, price: float, quantity: int):
        """Record a trade entry (opening a position)."""
        trade = {
            "ticker": ticker,
            "action": action,
            "entry_date": date,
            "entry_price": price,
            "quantity": quantity,
            "exit_date": None,
            "exit_price": None,
            "pnl": None
        }
        self.trades.append(trade)

    def _record_trade(self, ticker: str, position_type: str, date: str, price: float, quantity: int, pnl: float):
        """Record a completed trade with realized PnL."""
        # Find the most recent open trade for this ticker and position type
        for trade in reversed(self.trades):
            if (trade["ticker"] == ticker and 
                trade["exit_date"] is None and
                ((position_type == "long" and trade["action"] == "buy") or
                 (position_type == "short" and trade["action"] == "short"))):
                trade["exit_date"] = date
                trade["exit_price"] = price
                trade["pnl"] = pnl
                break

    def calculate_portfolio_value(self, current_prices: Dict[str, float]) -> float:
        """Calculate total portfolio value."""
        total_value = self.portfolio["cash"]

        for ticker in self.tickers:
            position = self.portfolio["positions"][ticker]
            price = current_prices[ticker]

            # Long position value
            long_value = position["long"] * price
            total_value += long_value

            # Short position unrealized PnL
            if position["short"] > 0:
                total_value -= position["short"] * price

        return total_value

    def prefetch_data(self):
        """Pre-fetch all data needed for the backtest period."""
        end_date_dt = datetime.strptime(self.end_date, "%Y-%m-%d")
        start_date_dt = end_date_dt - relativedelta(years=1)
        start_date_str = start_date_dt.strftime("%Y-%m-%d")
        api_key = self.request.api_keys.get("FINANCIAL_DATASETS_API_KEY")

        for ticker in self.tickers:
            get_prices(ticker, start_date_str, self.end_date, api_key=api_key)
            get_financial_metrics(ticker, self.end_date, limit=10, api_key=api_key)
            get_insider_trades(ticker, self.end_date, start_date=self.start_date, limit=1000, api_key=api_key)
            get_company_news(ticker, self.end_date, start_date=self.start_date, limit=1000, api_key=api_key)

    def _calculate_trade_metrics(self, performance_metrics: Dict[str, Any]):
        """Calculate trade-based metrics (win rate, profit factor, etc.)."""
        if not self.trades:
            performance_metrics["total_trades"] = 0
            performance_metrics["win_rate"] = 0.0
            performance_metrics["profit_factor"] = 0.0
            performance_metrics["expectancy"] = 0.0
            performance_metrics["average_win"] = 0.0
            performance_metrics["average_loss"] = 0.0
            return

        # Filter completed trades (have both entry and exit)
        completed_trades = [t for t in self.trades if t.get("exit_date") is not None]
        performance_metrics["total_trades"] = len(completed_trades)

        if len(completed_trades) == 0:
            performance_metrics["win_rate"] = 0.0
            performance_metrics["profit_factor"] = 0.0
            performance_metrics["expectancy"] = 0.0
            performance_metrics["average_win"] = 0.0
            performance_metrics["average_loss"] = 0.0
            return

        # Calculate win rate
        winning_trades = [t for t in completed_trades if t.get("pnl", 0) > 0]
        losing_trades = [t for t in completed_trades if t.get("pnl", 0) < 0]
        performance_metrics["win_rate"] = (len(winning_trades) / len(completed_trades)) * 100 if completed_trades else 0.0

        # Calculate average win/loss
        if winning_trades:
            performance_metrics["average_win"] = np.mean([t.get("pnl", 0) for t in winning_trades])
        else:
            performance_metrics["average_win"] = 0.0

        if losing_trades:
            performance_metrics["average_loss"] = abs(np.mean([t.get("pnl", 0) for t in losing_trades]))
        else:
            performance_metrics["average_loss"] = 0.0

        # Calculate profit factor
        total_profit = sum([t.get("pnl", 0) for t in winning_trades]) if winning_trades else 0.0
        total_loss = abs(sum([t.get("pnl", 0) for t in losing_trades])) if losing_trades else 0.0
        if total_loss > 1e-9:
            performance_metrics["profit_factor"] = total_profit / total_loss
        else:
            performance_metrics["profit_factor"] = float('inf') if total_profit > 0 else 0.0

        # Calculate expectancy
        if completed_trades:
            total_pnl = sum([t.get("pnl", 0) for t in completed_trades])
            performance_metrics["expectancy"] = total_pnl / len(completed_trades)
        else:
            performance_metrics["expectancy"] = 0.0

    def _calculate_daily_metrics(self, performance_metrics: Dict[str, Any]):
        """Calculate daily PnL based metrics."""
        if not self.daily_pnl:
            performance_metrics["largest_winning_day"] = 0.0
            performance_metrics["largest_losing_day"] = 0.0
            performance_metrics["profitable_days_pct"] = 0.0
            performance_metrics["losing_streaks"] = []
            performance_metrics["time_to_recovery"] = None
            return

        daily_pnl_values = [d.get("pnl", 0) for d in self.daily_pnl]
        
        # Largest winning/losing days
        if daily_pnl_values:
            performance_metrics["largest_winning_day"] = max(daily_pnl_values) if max(daily_pnl_values) > 0 else 0.0
            performance_metrics["largest_losing_day"] = min(daily_pnl_values) if min(daily_pnl_values) < 0 else 0.0
        else:
            performance_metrics["largest_winning_day"] = 0.0
            performance_metrics["largest_losing_day"] = 0.0

        # % Profitable days
        profitable_days = len([d for d in daily_pnl_values if d > 0])
        performance_metrics["profitable_days_pct"] = (profitable_days / len(daily_pnl_values)) * 100 if daily_pnl_values else 0.0

        # Losing streaks (track all streaks, not just max)
        streaks = []
        current_streak = 0
        for pnl in daily_pnl_values:
            if pnl < 0:
                current_streak += 1
            else:
                if current_streak > 0:
                    streaks.append(current_streak)
                current_streak = 0
        if current_streak > 0:
            streaks.append(current_streak)
        performance_metrics["losing_streaks"] = streaks if streaks else []

        # Time to recovery (days to recover from max drawdown)
        if len(self.portfolio_values) > 1:
            values_df = pd.DataFrame(self.portfolio_values).set_index("Date")
            rolling_max = values_df["Portfolio Value"].cummax()
            drawdown = (values_df["Portfolio Value"] - rolling_max) / rolling_max
            
            if len(drawdown) > 0 and drawdown.min() < 0:
                max_dd_date = drawdown.idxmin()
                max_dd_value = rolling_max.loc[max_dd_date]
                
                # Find when portfolio value recovered to max_dd_value
                recovery_idx = None
                for idx, (date, value) in enumerate(values_df.iterrows()):
                    if idx > values_df.index.get_loc(max_dd_date) and value["Portfolio Value"] >= max_dd_value:
                        recovery_idx = idx
                        break
                
                if recovery_idx is not None:
                    dd_date_idx = values_df.index.get_loc(max_dd_date)
                    performance_metrics["time_to_recovery"] = recovery_idx - dd_date_idx
                else:
                    performance_metrics["time_to_recovery"] = None
            else:
                performance_metrics["time_to_recovery"] = None
        else:
            performance_metrics["time_to_recovery"] = None

    def _calculate_topstep_metrics(self, performance_metrics: Dict[str, Any]):
        """Calculate Topstep strategy specific metrics."""
        # Check if we're trading Topstep instruments (ES, NQ, MES, MNQ)
        topstep_tickers = {"ES", "NQ", "MES", "MNQ"}
        is_topstep = any(ticker.upper() in topstep_tickers for ticker in self.tickers)
        
        if not is_topstep:
            # Not a Topstep strategy, set metrics to None/0
            performance_metrics["opening_range_breaks"] = 0
            performance_metrics["pullback_entries"] = 0
            performance_metrics["regime_filter_passes"] = 0
            performance_metrics["daily_trade_limit_hits"] = 0
            return
        
        # For now, we'll track basic stats from trades
        # In the future, this can be enhanced to parse strategy-specific signals
        # from analyst_signals or decisions metadata
        
        # Count trades (as a proxy for strategy activity)
        # This is a placeholder - ideally we'd track:
        # - Opening range breaks from strategy signals
        # - Pullback entries from strategy signals
        # - Regime filter passes from strategy signals
        # - Daily limit hits from strategy signals
        
        # For now, set to 0 and note that this requires strategy-specific signal tracking
        performance_metrics["opening_range_breaks"] = 0  # TODO: Track from strategy signals
        performance_metrics["pullback_entries"] = 0  # TODO: Track from strategy signals
        performance_metrics["regime_filter_passes"] = 0  # TODO: Track from strategy signals
        performance_metrics["daily_trade_limit_hits"] = 0  # TODO: Track from strategy signals

    def _update_performance_metrics(self, performance_metrics: Dict[str, Any]):
        """Update performance metrics using daily returns."""
        values_df = pd.DataFrame(self.portfolio_values).set_index("Date")
        values_df["Daily Return"] = values_df["Portfolio Value"].pct_change()
        clean_returns = values_df["Daily Return"].dropna()

        if len(clean_returns) < 2:
            return

        # Total return
        if len(values_df) > 0:
            final_value = values_df["Portfolio Value"].iloc[-1]
            performance_metrics["total_return"] = ((final_value / self.initial_capital) - 1) * 100
        else:
            performance_metrics["total_return"] = 0.0

        daily_risk_free_rate = 0.0434 / 252
        excess_returns = clean_returns - daily_risk_free_rate
        mean_excess_return = excess_returns.mean()
        std_excess_return = excess_returns.std()

        # Sharpe ratio
        if std_excess_return > 1e-12:
            performance_metrics["sharpe_ratio"] = np.sqrt(252) * (mean_excess_return / std_excess_return)
        else:
            performance_metrics["sharpe_ratio"] = 0.0

        # Sortino ratio
        negative_returns = excess_returns[excess_returns < 0]
        if len(negative_returns) > 0:
            downside_std = negative_returns.std()
            if downside_std > 1e-12:
                performance_metrics["sortino_ratio"] = np.sqrt(252) * (mean_excess_return / downside_std)
            else:
                performance_metrics["sortino_ratio"] = None if mean_excess_return > 0 else 0
        else:
            performance_metrics["sortino_ratio"] = None if mean_excess_return > 0 else 0

        # Maximum drawdown
        rolling_max = values_df["Portfolio Value"].cummax()
        drawdown = (values_df["Portfolio Value"] - rolling_max) / rolling_max

        if len(drawdown) > 0:
            min_drawdown = drawdown.min()
            performance_metrics["max_drawdown"] = min_drawdown * 100

            if min_drawdown < 0:
                performance_metrics["max_drawdown_date"] = drawdown.idxmin().strftime("%Y-%m-%d")
            else:
                performance_metrics["max_drawdown_date"] = None
        else:
            performance_metrics["max_drawdown"] = 0.0
            performance_metrics["max_drawdown_date"] = None

        # Calculate trade-based metrics
        self._calculate_trade_metrics(performance_metrics)
        
        # Calculate daily PnL metrics
        self._calculate_daily_metrics(performance_metrics)
        
        # Calculate Topstep strategy metrics (if applicable)
        self._calculate_topstep_metrics(performance_metrics)

    async def run_backtest_async(self, progress_callback: Optional[Callable] = None) -> Dict[str, Any]:
        """
        Run the backtest asynchronously with optional progress callbacks.
        Uses the pre-compiled graph for trading decisions.
        """
        # Pre-fetch all data at the start
        self.prefetch_data()

        dates = pd.date_range(self.start_date, self.end_date, freq="B")
        performance_metrics = {
            "sharpe_ratio": 0.0,
            "sortino_ratio": 0.0,
            "max_drawdown": 0.0,
            "total_return": 0.0,
            "long_short_ratio": 0.0,
            "gross_exposure": 0.0,
            "net_exposure": 0.0,
            "total_trades": 0,
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "expectancy": 0.0,
            "average_win": 0.0,
            "average_loss": 0.0,
            "time_to_recovery": None,
            "losing_streaks": [],
            "profitable_days_pct": 0.0,
            "largest_winning_day": 0.0,
            "largest_losing_day": 0.0,
            "opening_range_breaks": 0,
            "pullback_entries": 0,
            "regime_filter_passes": 0,
            "daily_trade_limit_hits": 0,
        }

        # Initialize portfolio values
        if len(dates) > 0:
            self.portfolio_values = [{"Date": dates[0], "Portfolio Value": self.initial_capital}]
        else:
            self.portfolio_values = []

        backtest_results = []

        for i, current_date in enumerate(dates):
            # Allow other async operations to run
            await asyncio.sleep(0)

            lookback_start = (current_date - timedelta(days=30)).strftime("%Y-%m-%d")
            current_date_str = current_date.strftime("%Y-%m-%d")
            previous_date_str = (current_date - timedelta(days=1)).strftime("%Y-%m-%d")

            if lookback_start == current_date_str:
                continue

            # Send progress update if callback provided
            if progress_callback:
                progress_callback({
                    "type": "progress",
                    "current_date": current_date_str,
                    "progress": (i + 1) / len(dates),
                    "total_dates": len(dates),
                    "current_step": i + 1,
                })

            # Get current prices
            try:
                current_prices = {}
                missing_data = False

                for ticker in self.tickers:
                    try:
                        price_data = get_price_data(ticker, previous_date_str, current_date_str)
                        if price_data.empty:
                            missing_data = True
                            break
                        current_prices[ticker] = price_data.iloc[-1]["close"]
                    except Exception as e:
                        missing_data = True
                        break

                if missing_data:
                    continue

            except Exception:
                continue

            # Create portfolio for this iteration
            portfolio_for_graph = create_portfolio(
                initial_cash=self.portfolio["cash"],
                margin_requirement=self.portfolio["margin_requirement"],
                tickers=self.tickers,
                portfolio_positions=[]  # We'll handle positions manually
            )
            
            # Copy current portfolio state to the graph portfolio
            portfolio_for_graph.update(self.portfolio)

            # Execute graph-based agent decisions
            try:
                result = await run_graph_async(
                    graph=self.graph,
                    portfolio=portfolio_for_graph,
                    tickers=self.tickers,
                    start_date=lookback_start,
                    end_date=current_date_str,
                    model_name=self.model_name,
                    model_provider=self.model_provider,
                    request=self.request,
                )
                
                # Parse the decisions from the graph result
                if result and result.get("messages"):
                    decisions = parse_hedge_fund_response(result["messages"][-1].content)
                    analyst_signals = result.get("data", {}).get("analyst_signals", {})
                else:
                    decisions = {}
                    analyst_signals = {}
                    
            except Exception as e:
                print(f"Error running graph for {current_date_str}: {e}")
                decisions = {}
                analyst_signals = {}

            # Execute trades based on decisions
            executed_trades = {}
            # Store previous realized gains to track new realized PnL
            prev_realized_gains = {}
            for ticker in self.tickers:
                prev_realized_gains[ticker] = {
                    "long": self.portfolio["realized_gains"][ticker]["long"],
                    "short": self.portfolio["realized_gains"][ticker]["short"]
                }
            
            for ticker in self.tickers:
                decision = decisions.get(ticker, {"action": "hold", "quantity": 0})
                action, quantity = decision.get("action", "hold"), decision.get("quantity", 0)
                executed_quantity = self.execute_trade(ticker, action, quantity, current_prices[ticker])
                executed_trades[ticker] = executed_quantity
                
                # Track realized PnL from this trade
                if executed_quantity > 0:
                    new_long_pnl = self.portfolio["realized_gains"][ticker]["long"] - prev_realized_gains[ticker]["long"]
                    new_short_pnl = self.portfolio["realized_gains"][ticker]["short"] - prev_realized_gains[ticker]["short"]
                    
                    if new_long_pnl != 0:
                        # Long position was closed
                        self._record_trade(ticker, "long", current_date_str, current_prices[ticker], executed_quantity, new_long_pnl)
                    elif new_short_pnl != 0:
                        # Short position was closed
                        self._record_trade(ticker, "short", current_date_str, current_prices[ticker], executed_quantity, new_short_pnl)
                    elif action in ["buy", "short"]:
                        # Opening a new position
                        self._record_trade_entry(ticker, action, current_date_str, current_prices[ticker], executed_quantity)

            # Calculate portfolio value
            total_value = self.calculate_portfolio_value(current_prices)
            
            # Track daily PnL
            daily_pnl_value = total_value - self.previous_portfolio_value
            self.daily_pnl.append({
                "date": current_date_str,
                "pnl": daily_pnl_value,
                "portfolio_value": total_value
            })
            self.previous_portfolio_value = total_value

            # Calculate exposures
            long_exposure = sum(self.portfolio["positions"][t]["long"] * current_prices[t] for t in self.tickers)
            short_exposure = sum(self.portfolio["positions"][t]["short"] * current_prices[t] for t in self.tickers)
            gross_exposure = long_exposure + short_exposure
            net_exposure = long_exposure - short_exposure
            long_short_ratio = long_exposure / short_exposure if short_exposure > 1e-9 else None

            # Track portfolio value
            self.portfolio_values.append({
                "Date": current_date,
                "Portfolio Value": total_value,
                "Long Exposure": long_exposure,
                "Short Exposure": short_exposure,
                "Gross Exposure": gross_exposure,
                "Net Exposure": net_exposure,
                "Long/Short Ratio": long_short_ratio,
            })

            # Calculate performance metrics for this day
            portfolio_return = (total_value / self.initial_capital - 1) * 100
            
            # Update performance metrics if we have enough data
            if len(self.portfolio_values) > 2:
                self._update_performance_metrics(performance_metrics)

            # Build detailed result for this date (similar to CLI format)
            date_result = {
                "date": current_date_str,
                "portfolio_value": total_value,
                "cash": self.portfolio["cash"],
                "decisions": decisions,
                "executed_trades": executed_trades,
                "analyst_signals": analyst_signals,
                "current_prices": current_prices,
                "long_exposure": long_exposure,
                "short_exposure": short_exposure,
                "gross_exposure": gross_exposure,
                "net_exposure": net_exposure,
                "long_short_ratio": long_short_ratio,
                "portfolio_return": portfolio_return,
                "performance_metrics": performance_metrics.copy(),
                # Add detailed trading information for each ticker
                "ticker_details": []
            }

            # Build ticker details (similar to CLI format_backtest_row)
            for ticker in self.tickers:
                ticker_signals = {}
                for agent_name, signals in analyst_signals.items():
                    if ticker in signals:
                        ticker_signals[agent_name] = signals[ticker]

                bullish_count = len([s for s in ticker_signals.values() if s.get("signal", "").lower() == "bullish"])
                bearish_count = len([s for s in ticker_signals.values() if s.get("signal", "").lower() == "bearish"])
                neutral_count = len([s for s in ticker_signals.values() if s.get("signal", "").lower() == "neutral"])

                # Calculate net position value
                pos = self.portfolio["positions"][ticker]
                long_val = pos["long"] * current_prices[ticker]
                short_val = pos["short"] * current_prices[ticker]
                net_position_value = long_val - short_val

                # Get the action and quantity from the decisions
                action = decisions.get(ticker, {}).get("action", "hold")
                quantity = executed_trades.get(ticker, 0)

                ticker_detail = {
                    "ticker": ticker,
                    "action": action,
                    "quantity": quantity,
                    "price": current_prices[ticker],
                    "shares_owned": pos["long"] - pos["short"],  # net shares
                    "long_shares": pos["long"],
                    "short_shares": pos["short"],
                    "position_value": net_position_value,
                    "bullish_count": bullish_count,
                    "bearish_count": bearish_count,
                    "neutral_count": neutral_count,
                }
                
                date_result["ticker_details"].append(ticker_detail)

            backtest_results.append(date_result)

            # Send intermediate result if callback provided
            if progress_callback:
                progress_callback({
                    "type": "backtest_result",
                    "data": date_result,
                })

        # Ensure final performance metrics are calculated
        if len(self.portfolio_values) > 1:
            self._update_performance_metrics(performance_metrics)

        # Calculate final exposures if we have results
        if backtest_results:
            final_result = backtest_results[-1]
            performance_metrics["gross_exposure"] = final_result["gross_exposure"]
            performance_metrics["net_exposure"] = final_result["net_exposure"]
            performance_metrics["long_short_ratio"] = final_result["long_short_ratio"]

        # Store final performance metrics
        self.performance_metrics = performance_metrics

        return {
            "results": backtest_results,
            "performance_metrics": performance_metrics,
            "portfolio_values": self.portfolio_values,
            "final_portfolio": self.portfolio,
        }

    def run_backtest_sync(self) -> Dict[str, Any]:
        """
        Run the backtest synchronously.
        This version can be used by the CLI.
        """
        # Use asyncio to run the async version
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(self.run_backtest_async())
        finally:
            loop.close()

    def analyze_performance(self) -> pd.DataFrame:
        """Analyze performance and return DataFrame with metrics."""
        if not self.portfolio_values:
            return pd.DataFrame()

        performance_df = pd.DataFrame(self.portfolio_values).set_index("Date")
        if performance_df.empty:
            return performance_df

        # Calculate additional metrics
        performance_df["Daily Return"] = performance_df["Portfolio Value"].pct_change().fillna(0)
        
        return performance_df 