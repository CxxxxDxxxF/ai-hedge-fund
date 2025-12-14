from colorama import Fore, Style
from tabulate import tabulate
from .analysts import ANALYST_ORDER
import os
import json


def sort_agent_signals(signals):
    """Sort agent signals in a consistent order."""
    # Create order mapping from ANALYST_ORDER
    analyst_order = {display: idx for idx, (display, _) in enumerate(ANALYST_ORDER)}
    analyst_order["Risk Management"] = len(ANALYST_ORDER)  # Add Risk Management at the end

    return sorted(signals, key=lambda x: analyst_order.get(x[0], 999))


def print_trading_output(result: dict) -> None:
    """
    Print formatted trading results with colored tables for multiple tickers.
    Supports three run types:
    1. Advisory-only (regime, risk, no trades)
    2. Trade decision only
    3. Full pipeline (signals + allocation + risk)

    Args:
        result (dict): Dictionary containing decisions, analyst signals, market_regime, and risk_budget
    """
    decisions = result.get("decisions")
    market_regime = result.get("market_regime", {})
    risk_budget = result.get("risk_budget", {})
    portfolio_decisions = result.get("portfolio_decisions", {})
    
    # Handle None or empty decisions
    if not decisions:
        decisions = {}
    
    # Defensive: ensure decisions is a dict and values are dicts
    if isinstance(decisions, dict):
        # Filter out non-dict values (defensive)
        decisions = {k: v for k, v in decisions.items() if isinstance(v, dict)}
    else:
        decisions = {}
    
    # Check if this is an advisory-only run (no tradable decisions)
    has_tradable_decisions = bool(decisions) and any(
        d.get("action", "hold").lower() != "hold" or d.get("quantity", 0) > 0
        for d in decisions.values() if isinstance(d, dict)
    )
    
    # If no tradable decisions, check for advisory data
    if not has_tradable_decisions:
        has_advisory_data = bool(market_regime or risk_budget or portfolio_decisions)
        
        if not has_advisory_data:
            print(f"{Fore.YELLOW}No executable trades generated (advisory/context-only run).{Style.RESET_ALL}")
            return
        
        # Advisory-only run: display context information
        print(f"\n{Fore.WHITE}{Style.BRIGHT}ADVISORY-ONLY RUN{Style.RESET_ALL}")
        print(f"{Fore.WHITE}{Style.BRIGHT}{'=' * 50}{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}No executable trades generated (advisory/context-only run).{Style.RESET_ALL}\n")
        
        # Get tickers from available data
        tickers = set()
        if market_regime:
            tickers.update(market_regime.keys())
        if risk_budget:
            tickers.update(risk_budget.keys())
        if portfolio_decisions:
            tickers.update(portfolio_decisions.keys())
        
        if not tickers:
            return
        
        # Display advisory information for each ticker
        for ticker in sorted(tickers):
            print(f"\n{Fore.WHITE}{Style.BRIGHT}Advisory Information for {Fore.CYAN}{ticker}{Style.RESET_ALL}")
            print(f"{Fore.WHITE}{Style.BRIGHT}{'=' * 50}{Style.RESET_ALL}")
            
            # Display Market Regime info
            if ticker in market_regime:
                regime_data = market_regime[ticker]
                regime = regime_data.get("regime", "unknown")
                weights = regime_data.get("weights", {})
                risk_mult = regime_data.get("risk_multiplier", 1.0)
                reasoning = regime_data.get("reasoning", "")
                
                regime_color = {
                    "trending": Fore.GREEN,
                    "mean_reverting": Fore.YELLOW,
                    "volatile": Fore.RED,
                    "calm": Fore.CYAN,
                }.get(regime, Fore.WHITE)
                
                regime_table = [
                    ["Regime", f"{regime_color}{regime.upper()}{Style.RESET_ALL}"],
                    ["Risk Multiplier", f"{Fore.WHITE}{risk_mult:.2f}{Style.RESET_ALL}"],
                ]
                
                if weights:
                    momentum_w = weights.get("momentum", 1.0)
                    mean_rev_w = weights.get("mean_reversion", 1.0)
                    regime_table.append(["Momentum Weight", f"{Fore.WHITE}{momentum_w:.2f}{Style.RESET_ALL}"])
                    regime_table.append(["Mean Reversion Weight", f"{Fore.WHITE}{mean_rev_w:.2f}{Style.RESET_ALL}"])
                
                if reasoning:
                    regime_table.append(["Reasoning", f"{Fore.CYAN}{reasoning}{Style.RESET_ALL}"])
                
                print(f"\n{Fore.WHITE}{Style.BRIGHT}MARKET REGIME:{Style.RESET_ALL}")
                print(tabulate(regime_table, tablefmt="grid", colalign=("left", "left")))
            
            # Display Risk Budget info
            if ticker in risk_budget:
                budget_data = risk_budget[ticker]
                base_risk = budget_data.get("base_risk_pct", 0.0)
                vol_adj = budget_data.get("volatility_adjustment", 1.0)
                regime_mult = budget_data.get("regime_multiplier", 1.0)
                final_risk = budget_data.get("final_risk_pct", 0.0)
                reasoning = budget_data.get("reasoning", "")
                
                budget_table = [
                    ["Base Risk %", f"{Fore.WHITE}{base_risk:.2%}{Style.RESET_ALL}"],
                    ["Volatility Adjustment", f"{Fore.WHITE}{vol_adj:.2f}{Style.RESET_ALL}"],
                    ["Regime Multiplier", f"{Fore.WHITE}{regime_mult:.2f}{Style.RESET_ALL}"],
                    ["Final Risk %", f"{Fore.CYAN}{Style.BRIGHT}{final_risk:.2%}{Style.RESET_ALL}"],
                ]
                
                if reasoning:
                    budget_table.append(["Reasoning", f"{Fore.CYAN}{reasoning}{Style.RESET_ALL}"])
                
                print(f"\n{Fore.WHITE}{Style.BRIGHT}RISK BUDGET:{Style.RESET_ALL}")
                print(tabulate(budget_table, tablefmt="grid", colalign=("left", "left")))
        
        return
    
    # Normal trading run: display decisions and signals
    # Print decisions for each ticker
    for ticker, decision in decisions.items():
        print(f"\n{Fore.WHITE}{Style.BRIGHT}Analysis for {Fore.CYAN}{ticker}{Style.RESET_ALL}")
        print(f"{Fore.WHITE}{Style.BRIGHT}{'=' * 50}{Style.RESET_ALL}")

        # Prepare analyst signals table for this ticker
        table_data = []
        analyst_signals = result.get("analyst_signals", {})
        for agent, signals in analyst_signals.items():
            if ticker not in signals:
                continue
                
            # Skip Risk Management agent in the signals section
            if agent == "risk_management_agent":
                continue

            signal = signals[ticker]
            agent_name = agent.replace("_agent", "").replace("_", " ").title()
            signal_type = signal.get("signal", "").upper()
            confidence = signal.get("confidence", 0)

            signal_color = {
                "BULLISH": Fore.GREEN,
                "BEARISH": Fore.RED,
                "NEUTRAL": Fore.YELLOW,
            }.get(signal_type, Fore.WHITE)
            
            # Get reasoning if available
            reasoning_str = ""
            if "reasoning" in signal and signal["reasoning"]:
                reasoning = signal["reasoning"]
                
                # Handle different types of reasoning (string, dict, etc.)
                if isinstance(reasoning, str):
                    reasoning_str = reasoning
                elif isinstance(reasoning, dict):
                    # Convert dict to string representation
                    reasoning_str = json.dumps(reasoning, indent=2)
                else:
                    # Convert any other type to string
                    reasoning_str = str(reasoning)
                
                # Wrap long reasoning text to make it more readable
                wrapped_reasoning = ""
                current_line = ""
                # Use a fixed width of 60 characters to match the table column width
                max_line_length = 60
                for word in reasoning_str.split():
                    if len(current_line) + len(word) + 1 > max_line_length:
                        wrapped_reasoning += current_line + "\n"
                        current_line = word
                    else:
                        if current_line:
                            current_line += " " + word
                        else:
                            current_line = word
                if current_line:
                    wrapped_reasoning += current_line
                
                reasoning_str = wrapped_reasoning

            table_data.append(
                [
                    f"{Fore.CYAN}{agent_name}{Style.RESET_ALL}",
                    f"{signal_color}{signal_type}{Style.RESET_ALL}",
                    f"{Fore.WHITE}{confidence}%{Style.RESET_ALL}",
                    f"{Fore.WHITE}{reasoning_str}{Style.RESET_ALL}",
                ]
            )

        # Only print analyst signals table if we have data
        if table_data:
            # Sort the signals according to the predefined order
            table_data = sort_agent_signals(table_data)

            print(f"\n{Fore.WHITE}{Style.BRIGHT}AGENT ANALYSIS:{Style.RESET_ALL} [{Fore.CYAN}{ticker}{Style.RESET_ALL}]")
            print(
                tabulate(
                    table_data,
                    headers=[f"{Fore.WHITE}Agent", "Signal", "Confidence", "Reasoning"],
                    tablefmt="grid",
                    colalign=("left", "center", "right", "left"),
                )
            )

        # Print Trading Decision Table
        action = decision.get("action", "").upper()
        action_color = {
            "BUY": Fore.GREEN,
            "SELL": Fore.RED,
            "HOLD": Fore.YELLOW,
            "COVER": Fore.GREEN,
            "SHORT": Fore.RED,
        }.get(action, Fore.WHITE)

        # Get reasoning and format it
        reasoning = decision.get("reasoning", "")
        # Wrap long reasoning text to make it more readable
        wrapped_reasoning = ""
        if reasoning:
            current_line = ""
            # Use a fixed width of 60 characters to match the table column width
            max_line_length = 60
            for word in reasoning.split():
                if len(current_line) + len(word) + 1 > max_line_length:
                    wrapped_reasoning += current_line + "\n"
                    current_line = word
                else:
                    if current_line:
                        current_line += " " + word
                    else:
                        current_line = word
            if current_line:
                wrapped_reasoning += current_line

        decision_data = [
            ["Action", f"{action_color}{action}{Style.RESET_ALL}"],
            ["Quantity", f"{action_color}{decision.get('quantity')}{Style.RESET_ALL}"],
            [
                "Confidence",
                f"{Fore.WHITE}{decision.get('confidence'):.1f}%{Style.RESET_ALL}",
            ],
            ["Reasoning", f"{Fore.WHITE}{wrapped_reasoning}{Style.RESET_ALL}"],
        ]
        
        print(f"\n{Fore.WHITE}{Style.BRIGHT}TRADING DECISION:{Style.RESET_ALL} [{Fore.CYAN}{ticker}{Style.RESET_ALL}]")
        print(tabulate(decision_data, tablefmt="grid", colalign=("left", "left")))
        
        # Display Market Regime info if available
        if ticker in market_regime:
            regime_data = market_regime[ticker]
            regime = regime_data.get("regime", "unknown")
            weights = regime_data.get("weights", {})
            risk_mult = regime_data.get("risk_multiplier", 1.0)
            reasoning = regime_data.get("reasoning", "")
            
            regime_color = {
                "trending": Fore.GREEN,
                "mean_reverting": Fore.YELLOW,
                "volatile": Fore.RED,
                "calm": Fore.CYAN,
            }.get(regime, Fore.WHITE)
            
            regime_table = [
                ["Regime", f"{regime_color}{regime.upper()}{Style.RESET_ALL}"],
                ["Risk Multiplier", f"{Fore.WHITE}{risk_mult:.2f}{Style.RESET_ALL}"],
            ]
            
            if weights:
                momentum_w = weights.get("momentum", 1.0)
                mean_rev_w = weights.get("mean_reversion", 1.0)
                regime_table.append(["Momentum Weight", f"{Fore.WHITE}{momentum_w:.2f}{Style.RESET_ALL}"])
                regime_table.append(["Mean Reversion Weight", f"{Fore.WHITE}{mean_rev_w:.2f}{Style.RESET_ALL}"])
            
            if reasoning:
                regime_table.append(["Reasoning", f"{Fore.CYAN}{reasoning}{Style.RESET_ALL}"])
            
            print(f"\n{Fore.WHITE}{Style.BRIGHT}MARKET REGIME:{Style.RESET_ALL} [{Fore.CYAN}{ticker}{Style.RESET_ALL}]")
            print(tabulate(regime_table, tablefmt="grid", colalign=("left", "left")))
        
        # Display Risk Budget info if available
        if ticker in risk_budget:
            budget_data = risk_budget[ticker]
            base_risk = budget_data.get("base_risk_pct", 0.0)
            vol_adj = budget_data.get("volatility_adjustment", 1.0)
            regime_mult = budget_data.get("regime_multiplier", 1.0)
            final_risk = budget_data.get("final_risk_pct", 0.0)
            reasoning = budget_data.get("reasoning", "")
            
            budget_table = [
                ["Base Risk %", f"{Fore.WHITE}{base_risk:.2%}{Style.RESET_ALL}"],
                ["Volatility Adjustment", f"{Fore.WHITE}{vol_adj:.2f}{Style.RESET_ALL}"],
                ["Regime Multiplier", f"{Fore.WHITE}{regime_mult:.2f}{Style.RESET_ALL}"],
                ["Final Risk %", f"{Fore.CYAN}{Style.BRIGHT}{final_risk:.2%}{Style.RESET_ALL}"],
            ]
            
            if reasoning:
                budget_table.append(["Reasoning", f"{Fore.CYAN}{reasoning}{Style.RESET_ALL}"])
            
            print(f"\n{Fore.WHITE}{Style.BRIGHT}RISK BUDGET:{Style.RESET_ALL} [{Fore.CYAN}{ticker}{Style.RESET_ALL}]")
            print(tabulate(budget_table, tablefmt="grid", colalign=("left", "left")))
    
    # Display Portfolio-Level Allocation Constraints (once, after all tickers)
    portfolio_allocation = result.get("portfolio_allocation", {})
    if portfolio_allocation and portfolio_allocation.get("constraints"):
        constraints = portfolio_allocation["constraints"]
        print(f"\n{Fore.WHITE}{Style.BRIGHT}PORTFOLIO-LEVEL CONSTRAINTS:{Style.RESET_ALL}")
        print(f"{Fore.WHITE}{Style.BRIGHT}{'=' * 50}{Style.RESET_ALL}")
        
        # Gross/Net Exposure
        gross_data = constraints.get("gross_exposure", {})
        net_data = constraints.get("net_exposure", {})
        if gross_data and net_data:
            gross_current = gross_data.get("current", 0)
            gross_limit = gross_data.get("limit", 0)
            gross_pct = (gross_current / gross_limit * 100) if gross_limit > 0 else 0
            gross_color = Fore.RED if gross_pct > 100 else Fore.GREEN
            
            net_current = net_data.get("current", 0)
            net_limit = abs(net_data.get("limit", 0))
            net_pct = (abs(net_current) / net_limit * 100) if net_limit > 0 else 0
            net_color = Fore.RED if net_pct > 100 else Fore.GREEN
            
            exposure_table = [
                ["Gross Exposure", f"{Fore.WHITE}${gross_current:,.0f}{Style.RESET_ALL}", f"{Fore.WHITE}${gross_limit:,.0f}{Style.RESET_ALL}", f"{gross_color}{gross_pct:.1f}%{Style.RESET_ALL}"],
                ["Net Exposure", f"{Fore.WHITE}${net_current:,.0f}{Style.RESET_ALL}", f"{Fore.WHITE}±${net_limit:,.0f}{Style.RESET_ALL}", f"{net_color}{net_pct:.1f}%{Style.RESET_ALL}"],
            ]
            print(f"\n{Fore.WHITE}{Style.BRIGHT}Exposure Limits:{Style.RESET_ALL}")
            print(tabulate(exposure_table, headers=[f"{Fore.WHITE}Metric", "Current", "Limit", "Usage%{Style.RESET_ALL}"], tablefmt="grid", colalign=("left", "right", "right", "right")))
        
        # Sector Limits
        sector_limits = constraints.get("sector_limits", {})
        if sector_limits and sector_limits.get("sector_exposures"):
            sector_exposures = sector_limits["sector_exposures"]
            max_sector_pct = sector_limits.get("max_sector_pct", 0.30)
            
            sector_table = []
            for sector, sector_data in sorted(sector_exposures.items(), key=lambda x: x[1]["exposure_pct"], reverse=True):
                exposure_pct = sector_data.get("exposure_pct", 0.0)
                exposure = sector_data.get("exposure", 0.0)
                ticker_count = len(sector_data.get("tickers", []))
                sector_color = Fore.RED if exposure_pct > max_sector_pct else Fore.GREEN
                
                sector_table.append([
                    f"{Fore.CYAN}{sector}{Style.RESET_ALL}",
                    f"{Fore.WHITE}${exposure:,.0f}{Style.RESET_ALL}",
                    f"{sector_color}{exposure_pct:.1%}{Style.RESET_ALL}",
                    f"{Fore.WHITE}{ticker_count}{Style.RESET_ALL}",
                ])
            
            if sector_table:
                print(f"\n{Fore.WHITE}{Style.BRIGHT}Sector Concentration (Max: {max_sector_pct:.0%}):{Style.RESET_ALL}")
                print(tabulate(sector_table, headers=[f"{Fore.WHITE}Sector", "Exposure", "Pct", "Tickers{Style.RESET_ALL}"], tablefmt="grid", colalign=("left", "right", "right", "right")))
        
        # Correlation Limits
        corr_limit = constraints.get("correlation_limit", {})
        if corr_limit and corr_limit.get("high_correlations"):
            high_corrs = corr_limit["high_correlations"]
            max_corr = corr_limit.get("max_correlation", 0.70)
            
            if high_corrs:
                corr_table = []
                for corr_pair in high_corrs[:10]:  # Show top 10
                    ticker1 = corr_pair.get("ticker1", "")
                    ticker2 = corr_pair.get("ticker2", "")
                    corr = corr_pair.get("correlation", 0.0)
                    corr_color = Fore.RED if abs(corr) > max_corr else Fore.YELLOW
                    
                    corr_table.append([
                        f"{Fore.CYAN}{ticker1}{Style.RESET_ALL}",
                        f"{Fore.CYAN}{ticker2}{Style.RESET_ALL}",
                        f"{corr_color}{corr:.2f}{Style.RESET_ALL}",
                    ])
                
                if corr_table:
                    print(f"\n{Fore.WHITE}{Style.BRIGHT}High Correlations (Max: {max_corr:.2f}):{Style.RESET_ALL}")
                    print(tabulate(corr_table, headers=[f"{Fore.WHITE}Ticker 1", "Ticker 2", "Correlation{Style.RESET_ALL}"], tablefmt="grid", colalign=("left", "left", "right")))

    # Print Portfolio Summary
    print(f"\n{Fore.WHITE}{Style.BRIGHT}PORTFOLIO SUMMARY:{Style.RESET_ALL}")
    portfolio_data = []
    
    # Extract portfolio manager reasoning (common for all tickers)
    portfolio_manager_reasoning = None
    for ticker, decision in decisions.items():
        if decision.get("reasoning"):
            portfolio_manager_reasoning = decision.get("reasoning")
            break
            
    analyst_signals = result.get("analyst_signals", {})
    for ticker, decision in decisions.items():
        action = decision.get("action", "").upper()
        action_color = {
            "BUY": Fore.GREEN,
            "SELL": Fore.RED,
            "HOLD": Fore.YELLOW,
            "COVER": Fore.GREEN,
            "SHORT": Fore.RED,
        }.get(action, Fore.WHITE)

        # Calculate analyst signal counts
        bullish_count = 0
        bearish_count = 0
        neutral_count = 0
        if analyst_signals:
            for agent, signals in analyst_signals.items():
                if ticker in signals:
                    signal = signals[ticker].get("signal", "").upper()
                    if signal == "BULLISH":
                        bullish_count += 1
                    elif signal == "BEARISH":
                        bearish_count += 1
                    elif signal == "NEUTRAL":
                        neutral_count += 1

        portfolio_data.append(
            [
                f"{Fore.CYAN}{ticker}{Style.RESET_ALL}",
                f"{action_color}{action}{Style.RESET_ALL}",
                f"{action_color}{decision.get('quantity')}{Style.RESET_ALL}",
                f"{Fore.WHITE}{decision.get('confidence'):.1f}%{Style.RESET_ALL}",
                f"{Fore.GREEN}{bullish_count}{Style.RESET_ALL}",
                f"{Fore.RED}{bearish_count}{Style.RESET_ALL}",
                f"{Fore.YELLOW}{neutral_count}{Style.RESET_ALL}",
            ]
        )

    # Only print portfolio summary table if we have data
    if portfolio_data:
        headers = [
            f"{Fore.WHITE}Ticker",
            f"{Fore.WHITE}Action",
            f"{Fore.WHITE}Quantity",
            f"{Fore.WHITE}Confidence",
            f"{Fore.WHITE}Bullish",
            f"{Fore.WHITE}Bearish",
            f"{Fore.WHITE}Neutral",
        ]
        
        # Print the portfolio summary table
        print(
            tabulate(
                portfolio_data,
                headers=headers,
                tablefmt="grid",
                colalign=("left", "center", "right", "right", "center", "center", "center"),
            )
        )
    
    # Print Portfolio Manager's reasoning if available
    if portfolio_manager_reasoning:
        # Handle different types of reasoning (string, dict, etc.)
        reasoning_str = ""
        if isinstance(portfolio_manager_reasoning, str):
            reasoning_str = portfolio_manager_reasoning
        elif isinstance(portfolio_manager_reasoning, dict):
            # Convert dict to string representation
            reasoning_str = json.dumps(portfolio_manager_reasoning, indent=2)
        else:
            # Convert any other type to string
            reasoning_str = str(portfolio_manager_reasoning)
            
        # Wrap long reasoning text to make it more readable
        wrapped_reasoning = ""
        current_line = ""
        # Use a fixed width of 60 characters to match the table column width
        max_line_length = 60
        for word in reasoning_str.split():
            if len(current_line) + len(word) + 1 > max_line_length:
                wrapped_reasoning += current_line + "\n"
                current_line = word
            else:
                if current_line:
                    current_line += " " + word
                else:
                    current_line = word
        if current_line:
            wrapped_reasoning += current_line
            
        print(f"\n{Fore.WHITE}{Style.BRIGHT}Portfolio Strategy:{Style.RESET_ALL}")
        print(f"{Fore.CYAN}{wrapped_reasoning}{Style.RESET_ALL}")


def print_backtest_results(table_rows: list) -> None:
    """Print the backtest results in a nicely formatted table"""
    # Clear the screen
    os.system("cls" if os.name == "nt" else "clear")

    # Split rows into ticker rows and summary rows
    ticker_rows = []
    summary_rows = []

    for row in table_rows:
        if isinstance(row[1], str) and "PORTFOLIO SUMMARY" in row[1]:
            summary_rows.append(row)
        else:
            ticker_rows.append(row)

    # Display latest portfolio summary
    if summary_rows:
        # Pick the most recent summary by date (YYYY-MM-DD)
        latest_summary = max(summary_rows, key=lambda r: r[0])
        print(f"\n{Fore.WHITE}{Style.BRIGHT}PORTFOLIO SUMMARY:{Style.RESET_ALL}")

        # Adjusted indexes after adding Long/Short Shares
        position_str = latest_summary[7].split("$")[1].split(Style.RESET_ALL)[0].replace(",", "")
        cash_str     = latest_summary[8].split("$")[1].split(Style.RESET_ALL)[0].replace(",", "")
        total_str    = latest_summary[9].split("$")[1].split(Style.RESET_ALL)[0].replace(",", "")

        print(f"Cash Balance: {Fore.CYAN}${float(cash_str):,.2f}{Style.RESET_ALL}")
        print(f"Total Position Value: {Fore.YELLOW}${float(position_str):,.2f}{Style.RESET_ALL}")
        print(f"Total Value: {Fore.WHITE}${float(total_str):,.2f}{Style.RESET_ALL}")
        print(f"Portfolio Return: {latest_summary[10]}")
        if len(latest_summary) > 14 and latest_summary[14]:
            print(f"Benchmark Return: {latest_summary[14]}")

        # Display performance metrics if available
        if latest_summary[11]:  # Sharpe ratio
            print(f"Sharpe Ratio: {latest_summary[11]}")
        if latest_summary[12]:  # Sortino ratio
            print(f"Sortino Ratio: {latest_summary[12]}")
        if latest_summary[13]:  # Max drawdown
            print(f"Max Drawdown: {latest_summary[13]}")

    # Add vertical spacing
    print("\n" * 2)

    # Print the table with just ticker rows
    print(
        tabulate(
            ticker_rows,
            headers=[
                "Date",
                "Ticker",
                "Action",
                "Quantity",
                "Price",
                "Long Shares",
                "Short Shares",
                "Position Value",
            ],
            tablefmt="grid",
            colalign=(
                "left",    # Date
                "left",    # Ticker
                "center",  # Action
                "right",   # Quantity
                "right",   # Price
                "right",   # Long Shares
                "right",   # Short Shares
                "right",   # Position Value
            ),
        )
    )

    # Add vertical spacing
    print("\n" * 4)


def format_backtest_row(
    date: str,
    ticker: str,
    action: str,
    quantity: float,
    price: float,
    long_shares: float = 0,
    short_shares: float = 0,
    position_value: float = 0,
    is_summary: bool = False,
    total_value: float = None,
    return_pct: float = None,
    cash_balance: float = None,
    total_position_value: float = None,
    sharpe_ratio: float = None,
    sortino_ratio: float = None,
    max_drawdown: float = None,
    benchmark_return_pct: float | None = None,
) -> list[any]:
    """Format a row for the backtest results table"""
    # Color the action
    action_color = {
        "BUY": Fore.GREEN,
        "COVER": Fore.GREEN,
        "SELL": Fore.RED,
        "SHORT": Fore.RED,
        "HOLD": Fore.WHITE,
    }.get(action.upper(), Fore.WHITE)

    if is_summary:
        return_color = Fore.GREEN if return_pct >= 0 else Fore.RED
        benchmark_str = ""
        if benchmark_return_pct is not None:
            bench_color = Fore.GREEN if benchmark_return_pct >= 0 else Fore.RED
            benchmark_str = f"{bench_color}{benchmark_return_pct:+.2f}%{Style.RESET_ALL}"
        return [
            date,
            f"{Fore.WHITE}{Style.BRIGHT}PORTFOLIO SUMMARY{Style.RESET_ALL}",
            "",  # Action
            "",  # Quantity
            "",  # Price
            "",  # Long Shares
            "",  # Short Shares
            f"{Fore.YELLOW}${total_position_value:,.2f}{Style.RESET_ALL}",  # Total Position Value
            f"{Fore.CYAN}${cash_balance:,.2f}{Style.RESET_ALL}",  # Cash Balance
            f"{Fore.WHITE}${total_value:,.2f}{Style.RESET_ALL}",  # Total Value
            f"{return_color}{return_pct:+.2f}%{Style.RESET_ALL}",  # Return
            f"{Fore.YELLOW}{sharpe_ratio:.2f}{Style.RESET_ALL}" if sharpe_ratio is not None else "",  # Sharpe Ratio
            f"{Fore.YELLOW}{sortino_ratio:.2f}{Style.RESET_ALL}" if sortino_ratio is not None else "",  # Sortino Ratio
            f"{Fore.RED}{max_drawdown:.2f}%{Style.RESET_ALL}" if max_drawdown is not None else "",  # Max Drawdown (signed)
            benchmark_str,  # Benchmark (S&P 500)
        ]
    else:
        return [
            date,
            f"{Fore.CYAN}{ticker}{Style.RESET_ALL}",
            f"{action_color}{action.upper()}{Style.RESET_ALL}",
            f"{action_color}{quantity:,.0f}{Style.RESET_ALL}",
            f"{Fore.WHITE}{price:,.2f}{Style.RESET_ALL}",
            f"{Fore.GREEN}{long_shares:,.0f}{Style.RESET_ALL}",   # Long Shares
            f"{Fore.RED}{short_shares:,.0f}{Style.RESET_ALL}",    # Short Shares
            f"{Fore.YELLOW}{position_value:,.2f}{Style.RESET_ALL}",
        ]
