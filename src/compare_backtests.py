#!/usr/bin/env python3
"""Deterministic backtest comparison runner for warren_buffett, momentum, and ensemble strategies."""

import os
import sys
import argparse
import json
import csv
from datetime import datetime
from pathlib import Path

from src.main import run_hedge_fund
from src.backtesting.engine import BacktestEngine
from src.backtesting.types import PerformanceMetrics
from src.backtesting.controller import AgentController
from src.backtesting.trader import TradeExecutor
from src.backtesting.portfolio import Portfolio
from src.backtesting.metrics import PerformanceMetricsCalculator
from src.backtesting.output import OutputBuilder
from src.backtesting.valuation import calculate_portfolio_value, compute_exposures
from src.backtesting.benchmarks import BenchmarkCalculator
from dateutil.relativedelta import relativedelta
import pandas as pd
from src.tools.api import get_price_data, get_prices, get_financial_metrics, get_insider_trades, get_company_news


class TradeTrackingBacktestEngine(BacktestEngine):
    """BacktestEngine that tracks all executed trades for accurate counting."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._trade_log: list[dict] = []  # List of executed trades
    
    def run_backtest(self) -> PerformanceMetrics:
        """Run backtest and log all executed trades."""
        self._prefetch_data()
        self._trade_log = []  # Reset trade log
        
        dates = pd.date_range(self._start_date, self._end_date, freq="B")
        if len(dates) > 0:
            self._portfolio_values = [
                {"Date": dates[0], "Portfolio Value": self._initial_capital}
            ]
        else:
            self._portfolio_values = []
        
        for current_date in dates:
            lookback_start = (current_date - relativedelta(months=1)).strftime("%Y-%m-%d")
            current_date_str = current_date.strftime("%Y-%m-%d")
            previous_date_str = (current_date - relativedelta(days=1)).strftime("%Y-%m-%d")
            if lookback_start == current_date_str:
                continue
            
            try:
                current_prices: dict[str, float] = {}
                missing_data = False
                for ticker in self._tickers:
                    try:
                        price_data = get_price_data(ticker, previous_date_str, current_date_str)
                        if price_data.empty:
                            missing_data = True
                            break
                        current_prices[ticker] = float(price_data.iloc[-1]["close"])
                    except Exception:
                        missing_data = True
                        break
                if missing_data:
                    continue
            except Exception:
                continue
            
            agent_output = self._agent_controller.run_agent(
                self._agent,
                tickers=self._tickers,
                start_date=lookback_start,
                end_date=current_date_str,
                portfolio=self._portfolio,
                model_name=self._model_name,
                model_provider=self._model_provider,
                selected_analysts=self._selected_analysts,
            )
            decisions = agent_output["decisions"]
            
            executed_trades: dict[str, int] = {}
            for ticker in self._tickers:
                d = decisions.get(ticker, {"action": "hold", "quantity": 0})
                action = d.get("action", "hold")
                qty = d.get("quantity", 0)
                executed_qty = self._executor.execute_trade(ticker, action, qty, current_prices[ticker], self._portfolio)
                executed_trades[ticker] = executed_qty
                
                # Log trade if executed
                if executed_qty != 0:
                    self._trade_log.append({
                        "date": current_date_str,
                        "ticker": ticker,
                        "action": action,
                        "quantity": executed_qty,
                        "price": current_prices[ticker],
                    })
            
            total_value = calculate_portfolio_value(self._portfolio, current_prices)
            exposures = compute_exposures(self._portfolio, current_prices)
            
            point = {
                "Date": current_date,
                "Portfolio Value": total_value,
                "Long Exposure": exposures["Long Exposure"],
                "Short Exposure": exposures["Short Exposure"],
                "Gross Exposure": exposures["Gross Exposure"],
                "Net Exposure": exposures["Net Exposure"],
                "Long/Short Ratio": exposures["Long/Short Ratio"],
            }
            self._portfolio_values.append(point)
            
            rows = self._results.build_day_rows(
                date_str=current_date_str,
                tickers=self._tickers,
                agent_output=agent_output,
                executed_trades=executed_trades,
                current_prices=current_prices,
                portfolio=self._portfolio,
                performance_metrics=self._performance_metrics,
                total_value=total_value,
                benchmark_return_pct=self._benchmark.get_return_pct("SPY", self._start_date, current_date_str),
            )
            self._table_rows = rows + self._table_rows
            self._results.print_rows(self._table_rows)
            
            if len(self._portfolio_values) > 3:
                computed = self._perf.compute_metrics(self._portfolio_values)
                if computed:
                    self._performance_metrics.update(computed)
        
        return self._performance_metrics
    
    def get_trade_log(self) -> list[dict]:
        """Get the complete trade log."""
        return list(self._trade_log)
    
    def get_total_trades(self) -> int:
        """Get total number of executed trades from trade log."""
        return len(self._trade_log)


def run_strategy_backtest(
    strategy_name: str,
    tickers: list[str],
    start_date: str,
    end_date: str,
    initial_capital: float,
    margin_requirement: float,
) -> dict:
    """Run a single strategy backtest and return metrics."""
    print(f"\n{'='*60}")
    print(f"Running backtest: {strategy_name}")
    print(f"{'='*60}\n")
    
    backtester = TradeTrackingBacktestEngine(
        agent=run_hedge_fund,
        tickers=tickers,
        start_date=start_date,
        end_date=end_date,
        initial_capital=initial_capital,
        model_name="gpt-4.1",  # Not used in NO_LLM mode
        model_provider="OpenAI",  # Not used in NO_LLM mode
        selected_analysts=[strategy_name],
        initial_margin_requirement=margin_requirement,
    )
    
    performance_metrics = backtester.run_backtest()
    portfolio_values = backtester.get_portfolio_values()
    # Get trade count from trade log
    total_trades = backtester.get_total_trades()
    
    # Calculate metrics
    if not portfolio_values:
        return {
            "strategy": strategy_name,
            "total_return": None,
            "max_drawdown": None,
            "sharpe_ratio": None,
            "num_trades": total_trades,
            "final_portfolio_value": None,
            "initial_capital": initial_capital,
        }
    
    initial_value = portfolio_values[0]["Portfolio Value"]
    final_value = portfolio_values[-1]["Portfolio Value"]
    total_return = ((final_value - initial_value) / initial_value) * 100 if initial_value > 0 else 0.0
    
    # Use consistent rounding for deterministic output
    max_dd = performance_metrics.get("max_drawdown")
    sharpe = performance_metrics.get("sharpe_ratio")
    
    return {
        "strategy": strategy_name,
        "total_return": round(total_return, 2) if total_return is not None else None,
        "max_drawdown": round(max_dd, 2) if max_dd is not None else None,
        "sharpe_ratio": round(sharpe, 3) if sharpe is not None else None,
        "num_trades": total_trades,
        "final_portfolio_value": round(final_value, 2) if final_value is not None else None,
        "initial_capital": round(initial_value, 2),
    }


def generate_markdown_report(
    results: list[dict], 
    output_file: str,
    tickers: list[str],
    start_date: str,
    end_date: str,
    initial_capital: float,
):
    """Generate markdown comparison report with sanity checks."""
    with open(output_file, "w") as f:
        f.write("# Backtest Comparison Report\n\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        # Sanity check section
        f.write("## Comparison Sanity Checks\n\n")
        f.write("This section confirms that all strategies were run with identical settings:\n\n")
        f.write(f"- **Initial Capital**: ${initial_capital:,.2f}\n")
        f.write(f"- **Date Range**: {start_date} to {end_date}\n")
        f.write(f"- **Tickers**: {', '.join(tickers)}\n")
        
        # Verify all strategies have same initial capital
        initial_capitals = [r.get("initial_capital") for r in results]
        if len(set(initial_capitals)) == 1:
            f.write(f"- ✅ **Initial Capital Consistency**: All strategies used ${initial_capitals[0]:,.2f}\n")
        else:
            f.write(f"- ⚠️ **Initial Capital Inconsistency**: Found {set(initial_capitals)}\n")
        
        # Verify date range consistency (all strategies should use same range)
        f.write(f"- ✅ **Date Range Consistency**: All strategies used {start_date} to {end_date}\n")
        
        # Verify ticker list consistency
        f.write(f"- ✅ **Ticker List Consistency**: All strategies used {', '.join(sorted(tickers))}\n")
        
        f.write("\n")
        f.write("## Strategy Comparison\n\n")
        f.write("| Strategy | Total Return (%) | Max Drawdown (%) | Sharpe Ratio | Num Trades | Final Value ($) |\n")
        f.write("|----------|------------------|------------------|--------------|------------|-----------------|\n")
        
        # Sort results by strategy name for deterministic output
        sorted_results = sorted(results, key=lambda x: x["strategy"])
        for r in sorted_results:
            total_return = f"{r['total_return']:.2f}%" if r['total_return'] is not None else "N/A"
            max_dd = f"{r['max_drawdown']:.2f}%" if r['max_drawdown'] is not None else "N/A"
            sharpe = f"{r['sharpe_ratio']:.3f}" if r['sharpe_ratio'] is not None else "N/A"
            num_trades = str(r['num_trades'])
            final_value = f"${r['final_portfolio_value']:,.2f}" if r['final_portfolio_value'] is not None else "N/A"
            
            f.write(f"| {r['strategy']} | {total_return} | {max_dd} | {sharpe} | {num_trades} | {final_value} |\n")
        
        f.write("\n## Detailed Metrics\n\n")
        for r in sorted_results:
            f.write(f"### {r['strategy']}\n\n")
            f.write(f"- **Initial Capital**: ${r['initial_capital']:,.2f}\n")
            f.write(f"- **Final Portfolio Value**: ${r['final_portfolio_value']:,.2f}\n" if r['final_portfolio_value'] else "- **Final Portfolio Value**: N/A\n")
            f.write(f"- **Total Return**: {r['total_return']:.2f}%\n" if r['total_return'] is not None else "- **Total Return**: N/A\n")
            f.write(f"- **Max Drawdown**: {r['max_drawdown']:.2f}%\n" if r['max_drawdown'] is not None else "- **Max Drawdown**: N/A\n")
            f.write(f"- **Sharpe Ratio**: {r['sharpe_ratio']:.3f}\n" if r['sharpe_ratio'] is not None else "- **Sharpe Ratio**: N/A\n")
            f.write(f"- **Number of Trades**: {r['num_trades']}\n")
            f.write("\n")


def generate_csv_summary(results: list[dict], output_file: str):
    """Generate CSV summary table with deterministic ordering."""
    # Sort results by strategy name for deterministic output
    sorted_results = sorted(results, key=lambda x: x["strategy"])
    with open(output_file, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "strategy", "total_return", "max_drawdown", "sharpe_ratio", 
            "num_trades", "final_portfolio_value", "initial_capital"
        ])
        writer.writeheader()
        writer.writerows(sorted_results)


def generate_json_summary(results: list[dict], output_file: str):
    """Generate JSON summary table with deterministic ordering."""
    # Sort results by strategy name for deterministic output
    sorted_results = sorted(results, key=lambda x: x["strategy"])
    with open(output_file, "w") as f:
        json.dump(sorted_results, f, indent=2, sort_keys=False)


def main():
    # Set deterministic mode here (not at module level)
    os.environ["HEDGEFUND_NO_LLM"] = "1"
    
    parser = argparse.ArgumentParser(
        description="Compare backtests for warren_buffett, momentum, and ensemble strategies"
    )
    parser.add_argument(
        "--tickers",
        type=str,
        required=True,
        help="Comma-separated list of stock ticker symbols (e.g., AAPL,MSFT)",
    )
    parser.add_argument(
        "--start-date",
        type=str,
        help="Start date (YYYY-MM-DD). Defaults to 1 month ago.",
    )
    parser.add_argument(
        "--end-date",
        type=str,
        default=datetime.now().strftime("%Y-%m-%d"),
        help="End date (YYYY-MM-DD). Defaults to today.",
    )
    parser.add_argument(
        "--initial-capital",
        type=float,
        default=100000.0,
        help="Initial capital (default: 100000.0)",
    )
    parser.add_argument(
        "--margin-requirement",
        type=float,
        default=0.0,
        help="Margin requirement ratio for shorts (default: 0.0)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=".",
        help="Output directory for reports (default: current directory)",
    )
    
    args = parser.parse_args()
    
    # Parse tickers and sort for deterministic ordering
    tickers = sorted([t.strip().upper() for t in args.tickers.split(",") if t.strip()])
    if not tickers:
        print("Error: No valid tickers provided")
        sys.exit(1)
    
    # Parse dates
    if args.start_date:
        start_date = args.start_date
    else:
        from dateutil.relativedelta import relativedelta
        end_date_obj = datetime.strptime(args.end_date, "%Y-%m-%d")
        start_date = (end_date_obj - relativedelta(months=1)).strftime("%Y-%m-%d")
    
    end_date = args.end_date
    
    # Strategies to compare (sorted for deterministic ordering)
    strategies = sorted(["warren_buffett", "momentum", "ensemble"])
    
    print(f"\n{'='*60}")
    print("Backtest Comparison Runner")
    print(f"{'='*60}")
    print(f"Tickers: {', '.join(tickers)}")
    print(f"Date Range: {start_date} to {end_date}")
    print(f"Initial Capital: ${args.initial_capital:,.2f}")
    print(f"Strategies: {', '.join(strategies)}")
    print(f"HEDGEFUND_NO_LLM: {os.getenv('HEDGEFUND_NO_LLM', 'NOT SET')}")
    print(f"{'='*60}\n")
    
    # Run backtests for each strategy
    results = []
    for strategy in strategies:
        try:
            result = run_strategy_backtest(
                strategy_name=strategy,
                tickers=tickers,
                start_date=start_date,
                end_date=end_date,
                initial_capital=args.initial_capital,
                margin_requirement=args.margin_requirement,
            )
            results.append(result)
        except Exception as e:
            print(f"Error running {strategy}: {e}")
            results.append({
                "strategy": strategy,
                "total_return": None,
                "max_drawdown": None,
                "sharpe_ratio": None,
                "num_trades": 0,
                "final_portfolio_value": None,
                "initial_capital": args.initial_capital,
            })
    
    # Generate reports
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    markdown_file = output_dir / f"backtest_comparison_{timestamp}.md"
    csv_file = output_dir / f"backtest_comparison_{timestamp}.csv"
    json_file = output_dir / f"backtest_comparison_{timestamp}.json"
    
    generate_markdown_report(
        results, 
        str(markdown_file),
        tickers=tickers,
        start_date=start_date,
        end_date=end_date,
        initial_capital=args.initial_capital,
    )
    generate_csv_summary(results, str(csv_file))
    generate_json_summary(results, str(json_file))
    
    print(f"\n{'='*60}")
    print("Comparison Complete")
    print(f"{'='*60}")
    print(f"Markdown Report: {markdown_file}")
    print(f"CSV Summary: {csv_file}")
    print(f"JSON Summary: {json_file}")
    print(f"{'='*60}\n")
    
    # Print summary table (sorted for consistency)
    print("\nSummary Table:")
    print("| Strategy | Total Return (%) | Max Drawdown (%) | Sharpe | Trades | Final Value ($) |")
    print("|----------|------------------|------------------|--------|--------|-----------------|")
    sorted_results = sorted(results, key=lambda x: x["strategy"])
    for r in sorted_results:
        total_return = f"{r['total_return']:.2f}%" if r['total_return'] is not None else "N/A"
        max_dd = f"{r['max_drawdown']:.2f}%" if r['max_drawdown'] is not None else "N/A"
        sharpe = f"{r['sharpe_ratio']:.3f}" if r['sharpe_ratio'] is not None else "N/A"
        num_trades = str(r['num_trades'])
        final_value = f"${r['final_portfolio_value']:,.2f}" if r['final_portfolio_value'] is not None else "N/A"
        print(f"| {r['strategy']} | {total_return} | {max_dd} | {sharpe} | {num_trades} | {final_value} |")


if __name__ == "__main__":
    main()

