"""
Regime Analysis: Identify where the system consistently behaves differently from random.

Answers: "Where does this system consistently behave differently from random?"

Key Questions:
1. Which market regimes show edge?
2. Which agent combinations work best?
3. Which ticker characteristics matter?
4. What time periods show consistent performance?
5. What signal patterns predict success?
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from collections import defaultdict
from datetime import datetime


class RegimeAnalysis:
    """
    Analyze where the system shows consistent, non-random behavior.
    
    Identifies:
    - Market regimes with edge
    - Agent combinations that work
    - Ticker characteristics that matter
    - Time periods with consistent performance
    - Signal patterns that predict success
    """
    
    def __init__(
        self,
        daily_values: pd.DataFrame,
        trades: List[Dict],
        analyst_signals_history: Optional[List[Dict]] = None,
        market_regime_history: Optional[List[Dict]] = None,
    ):
        """
        Initialize regime analysis.
        
        Args:
            daily_values: DataFrame with Date, Portfolio Value, Daily Return
            trades: List of trade dictionaries
            analyst_signals_history: Historical analyst signals per day
            market_regime_history: Historical market regime classifications
        """
        self.daily_values = daily_values.copy()
        self.trades = trades
        self.analyst_signals_history = analyst_signals_history or []
        self.market_regime_history = market_regime_history or []
        
        # Ensure Date is index
        if "Date" in self.daily_values.columns:
            self.daily_values.set_index("Date", inplace=True)
        
        # Calculate daily returns if not present
        if "Daily Return" not in self.daily_values.columns and "Portfolio Value" in self.daily_values.columns:
            self.daily_values["Daily Return"] = self.daily_values["Portfolio Value"].pct_change()
    
    def analyze_by_market_regime(self) -> Dict[str, Dict]:
        """
        Analyze performance by market regime.
        
        Returns:
            Dict mapping regime -> performance metrics
        """
        if not self.market_regime_history:
            return {}
        
        regime_performance = defaultdict(lambda: {"returns": [], "trades": [], "dates": []})
        
        # Map dates to regimes
        date_to_regime = {}
        for regime_data in self.market_regime_history:
            for ticker, regime_info in regime_data.items():
                if isinstance(regime_info, dict):
                    regime = regime_info.get("regime", "unknown")
                    date = regime_info.get("date")
                    if date:
                        date_to_regime[date] = regime
        
        # Group returns by regime
        for date, row in self.daily_values.iterrows():
            regime = date_to_regime.get(str(date), "unknown")
            if "Daily Return" in row and pd.notna(row["Daily Return"]):
                regime_performance[regime]["returns"].append(row["Daily Return"])
                regime_performance[regime]["dates"].append(date)
        
        # Group trades by regime
        for trade in self.trades:
            trade_date = trade.get("date")
            if trade_date:
                regime = date_to_regime.get(str(trade_date), "unknown")
                regime_performance[regime]["trades"].append(trade)
        
        # Calculate metrics per regime
        regime_metrics = {}
        for regime, data in regime_performance.items():
            if not data["returns"]:
                continue
            
            returns = pd.Series(data["returns"])
            
            # Annualized metrics
            mean_return = returns.mean() * 252
            volatility = returns.std() * np.sqrt(252)
            sharpe = (mean_return / volatility) if volatility > 0 else 0.0
            
            # Win rate
            positive_days = (returns > 0).sum()
            win_rate = (positive_days / len(returns)) * 100 if len(returns) > 0 else 0.0
            
            # Trade count
            trade_count = len(data["trades"])
            
            regime_metrics[regime] = {
                "mean_annual_return": mean_return * 100,
                "volatility": volatility * 100,
                "sharpe_ratio": sharpe,
                "win_rate": win_rate,
                "trade_count": trade_count,
                "days": len(data["returns"]),
            }
        
        return regime_metrics
    
    def analyze_by_agent_combination(self) -> Dict[str, Dict]:
        """
        Analyze performance by agent signal combinations.
        
        Identifies which agent combinations predict success.
        
        Returns:
            Dict mapping agent combination -> performance metrics
        """
        if not self.analyst_signals_history:
            return {}
        
        agent_combos = defaultdict(lambda: {"returns": [], "trades": [], "count": 0})
        
        # Map dates to agent signals
        for day_data in self.analyst_signals_history:
            date = day_data.get("date")
            signals = day_data.get("signals", {})
            
            if not date or not signals:
                continue
            
            # Create agent combination signature
            combo_parts = []
            for agent, ticker_signals in signals.items():
                for ticker, signal_data in ticker_signals.items():
                    signal = signal_data.get("signal", "neutral")
                    confidence = signal_data.get("confidence", 50)
                    # Only count strong signals
                    if signal in ["bullish", "bearish"] and confidence >= 60:
                        combo_parts.append(f"{agent}:{signal}")
            
            if combo_parts:
                combo_key = "|".join(sorted(combo_parts))
                
                # Get return for this day
                if date in self.daily_values.index:
                    daily_return = self.daily_values.loc[date, "Daily Return"]
                    if pd.notna(daily_return):
                        agent_combos[combo_key]["returns"].append(daily_return)
                        agent_combos[combo_key]["count"] += 1
        
        # Calculate metrics per combination
        combo_metrics = {}
        for combo, data in agent_combos.items():
            if len(data["returns"]) < 3:  # Need at least 3 occurrences
                continue
            
            returns = pd.Series(data["returns"])
            
            mean_return = returns.mean() * 252
            volatility = returns.std() * np.sqrt(252)
            sharpe = (mean_return / volatility) if volatility > 0 else 0.0
            
            positive_days = (returns > 0).sum()
            win_rate = (positive_days / len(returns)) * 100
            
            combo_metrics[combo] = {
                "mean_annual_return": mean_return * 100,
                "sharpe_ratio": sharpe,
                "win_rate": win_rate,
                "occurrences": data["count"],
                "avg_return": returns.mean() * 100,
            }
        
        # Sort by Sharpe ratio
        combo_metrics = dict(sorted(combo_metrics.items(), key=lambda x: x[1]["sharpe_ratio"], reverse=True))
        
        return combo_metrics
    
    def analyze_by_ticker_characteristics(self) -> Dict[str, Dict]:
        """
        Analyze performance by ticker characteristics.
        
        Identifies which tickers show consistent edge.
        
        Returns:
            Dict mapping ticker -> performance metrics
        """
        ticker_performance = defaultdict(lambda: {"returns": [], "trades": [], "pnl": 0.0})
        
        # Group trades by ticker
        for trade in self.trades:
            ticker = trade.get("ticker")
            if not ticker:
                continue
            
            # Calculate PnL for this trade (simplified)
            action = trade.get("action", "hold")
            quantity = trade.get("quantity", 0)
            price = trade.get("price", 0.0)
            
            # Track trade
            ticker_performance[ticker]["trades"].append(trade)
        
        # Calculate daily returns per ticker (from portfolio value changes)
        # This is simplified - in reality would need position-level tracking
        ticker_metrics = {}
        for ticker, data in ticker_performance.items():
            trade_count = len(data["trades"])
            
            # Estimate performance (simplified)
            # In full implementation, would track position-level PnL
            
            ticker_metrics[ticker] = {
                "trade_count": trade_count,
                "total_trades": trade_count,
            }
        
        return ticker_metrics
    
    def analyze_by_time_period(self, period_days: int = 30) -> Dict[str, Dict]:
        """
        Analyze performance by time periods.
        
        Identifies periods with consistent edge vs random periods.
        
        Args:
            period_days: Number of days per period
        
        Returns:
            Dict mapping period -> performance metrics
        """
        if len(self.daily_values) < period_days:
            return {}
        
        period_metrics = {}
        period_num = 0
        
        for i in range(0, len(self.daily_values), period_days):
            period_data = self.daily_values.iloc[i:i+period_days]
            
            if len(period_data) < 5:  # Need at least 5 days
                continue
            
            returns = period_data["Daily Return"].dropna()
            
            if len(returns) < 3:
                continue
            
            # Calculate period metrics
            period_return = (1 + returns).prod() - 1
            period_volatility = returns.std() * np.sqrt(252)
            period_sharpe = (period_return * (252 / len(returns)) / period_volatility) if period_volatility > 0 else 0.0
            
            positive_days = (returns > 0).sum()
            win_rate = (positive_days / len(returns)) * 100
            
            start_date = period_data.index[0]
            end_date = period_data.index[-1]
            
            period_metrics[f"Period_{period_num}"] = {
                "start_date": str(start_date),
                "end_date": str(end_date),
                "return": period_return * 100,
                "volatility": period_volatility * 100,
                "sharpe_ratio": period_sharpe,
                "win_rate": win_rate,
                "days": len(returns),
            }
            
            period_num += 1
        
        return period_metrics
    
    def analyze_signal_quality_patterns(self) -> Dict[str, Dict]:
        """
        Analyze which signal patterns predict success.
        
        Identifies:
        - Signal strength vs outcome
        - Confidence levels that work
        - Signal agreement patterns
        """
        if not self.analyst_signals_history:
            return {}
        
        signal_patterns = defaultdict(lambda: {"returns": [], "count": 0})
        
        for day_data in self.analyst_signals_history:
            date = day_data.get("date")
            signals = day_data.get("signals", {})
            
            if not date or date not in self.daily_values.index:
                continue
            
            daily_return = self.daily_values.loc[date, "Daily Return"]
            if pd.isna(daily_return):
                continue
            
            # Analyze signal patterns
            for agent, ticker_signals in signals.items():
                for ticker, signal_data in ticker_signals.items():
                    signal = signal_data.get("signal", "neutral")
                    confidence = signal_data.get("confidence", 50)
                    
                    # Pattern: Signal strength
                    if confidence >= 80:
                        pattern = "high_confidence"
                    elif confidence >= 60:
                        pattern = "medium_confidence"
                    else:
                        pattern = "low_confidence"
                    
                    signal_patterns[f"{pattern}_{signal}"]["returns"].append(daily_return)
                    signal_patterns[f"{pattern}_{signal}"]["count"] += 1
            
            # Pattern: Agent agreement
            all_signals = []
            for agent, ticker_signals in signals.items():
                for ticker, signal_data in ticker_signals.items():
                    signal = signal_data.get("signal", "neutral")
                    if signal != "neutral":
                        all_signals.append(signal)
            
            if len(all_signals) >= 3:
                bullish_count = all_signals.count("bullish")
                bearish_count = all_signals.count("bearish")
                
                if bullish_count >= 3:
                    signal_patterns["strong_bullish_consensus"]["returns"].append(daily_return)
                    signal_patterns["strong_bullish_consensus"]["count"] += 1
                elif bearish_count >= 3:
                    signal_patterns["strong_bearish_consensus"]["returns"].append(daily_return)
                    signal_patterns["strong_bearish_consensus"]["count"] += 1
                elif abs(bullish_count - bearish_count) <= 1:
                    signal_patterns["mixed_signals"]["returns"].append(daily_return)
                    signal_patterns["mixed_signals"]["count"] += 1
        
        # Calculate metrics per pattern
        pattern_metrics = {}
        for pattern, data in signal_patterns.items():
            if len(data["returns"]) < 5:  # Need at least 5 occurrences
                continue
            
            returns = pd.Series(data["returns"])
            
            mean_return = returns.mean() * 252
            volatility = returns.std() * np.sqrt(252)
            sharpe = (mean_return / volatility) if volatility > 0 else 0.0
            
            positive_days = (returns > 0).sum()
            win_rate = (positive_days / len(returns)) * 100
            
            pattern_metrics[pattern] = {
                "mean_annual_return": mean_return * 100,
                "sharpe_ratio": sharpe,
                "win_rate": win_rate,
                "occurrences": data["count"],
                "avg_daily_return": returns.mean() * 100,
            }
        
        # Sort by Sharpe ratio
        pattern_metrics = dict(sorted(pattern_metrics.items(), key=lambda x: x[1]["sharpe_ratio"], reverse=True))
        
        return pattern_metrics
    
    def identify_consistent_edge(self) -> Dict[str, any]:
        """
        Comprehensive analysis to identify where system shows consistent edge.
        
        Returns:
            Dict with all analyses and summary
        """
        results = {
            "by_market_regime": self.analyze_by_market_regime(),
            "by_agent_combination": self.analyze_by_agent_combination(),
            "by_ticker": self.analyze_by_ticker_characteristics(),
            "by_time_period": self.analyze_by_time_period(),
            "by_signal_patterns": self.analyze_signal_quality_patterns(),
        }
        
        # Summary: Identify consistent patterns
        consistent_patterns = []
        
        # Regimes with edge
        for regime, metrics in results["by_market_regime"].items():
            if metrics["sharpe_ratio"] > 1.0 and metrics["win_rate"] > 55:
                consistent_patterns.append({
                    "type": "market_regime",
                    "pattern": regime,
                    "sharpe": metrics["sharpe_ratio"],
                    "win_rate": metrics["win_rate"],
                })
        
        # Agent combinations with edge
        top_combos = list(results["by_agent_combination"].items())[:5]
        for combo, metrics in top_combos:
            if metrics["sharpe_ratio"] > 1.0:
                consistent_patterns.append({
                    "type": "agent_combination",
                    "pattern": combo,
                    "sharpe": metrics["sharpe_ratio"],
                    "win_rate": metrics["win_rate"],
                })
        
        # Signal patterns with edge
        top_patterns = list(results["by_signal_patterns"].items())[:5]
        for pattern, metrics in top_patterns:
            if metrics["sharpe_ratio"] > 0.5:
                consistent_patterns.append({
                    "type": "signal_pattern",
                    "pattern": pattern,
                    "sharpe": metrics["sharpe_ratio"],
                    "win_rate": metrics["win_rate"],
                })
        
        results["consistent_patterns"] = consistent_patterns
        
        return results
    
    def print_analysis(self, analysis: Optional[Dict] = None) -> None:
        """Print comprehensive regime analysis report."""
        if analysis is None:
            analysis = self.identify_consistent_edge()
        
        print("\n" + "=" * 80)
        print("REGIME ANALYSIS: Where does the system consistently behave differently from random?")
        print("=" * 80)
        
        # Market Regime Analysis
        if analysis["by_market_regime"]:
            print("\n" + "-" * 80)
            print("PERFORMANCE BY MARKET REGIME")
            print("-" * 80)
            from tabulate import tabulate
            regime_data = []
            for regime, metrics in analysis["by_market_regime"].items():
                regime_data.append([
                    regime,
                    f"{metrics['mean_annual_return']:.2f}%",
                    f"{metrics['sharpe_ratio']:.2f}",
                    f"{metrics['win_rate']:.1f}%",
                    metrics['trade_count'],
                    metrics['days'],
                ])
            print(tabulate(
                regime_data,
                headers=["Regime", "Annual Return", "Sharpe", "Win Rate", "Trades", "Days"],
                tablefmt="grid"
            ))
        
        # Agent Combinations
        if analysis["by_agent_combination"]:
            print("\n" + "-" * 80)
            print("TOP AGENT COMBINATIONS (by Sharpe Ratio)")
            print("-" * 80)
            combo_data = []
            for combo, metrics in list(analysis["by_agent_combination"].items())[:10]:
                combo_short = combo[:50] + "..." if len(combo) > 50 else combo
                combo_data.append([
                    combo_short,
                    f"{metrics['sharpe_ratio']:.2f}",
                    f"{metrics['win_rate']:.1f}%",
                    metrics['occurrences'],
                ])
            if combo_data:
                print(tabulate(
                    combo_data,
                    headers=["Agent Combination", "Sharpe", "Win Rate", "Occurrences"],
                    tablefmt="grid"
                ))
        
        # Signal Patterns
        if analysis["by_signal_patterns"]:
            print("\n" + "-" * 80)
            print("SIGNAL PATTERNS THAT PREDICT SUCCESS")
            print("-" * 80)
            pattern_data = []
            for pattern, metrics in list(analysis["by_signal_patterns"].items())[:10]:
                pattern_data.append([
                    pattern,
                    f"{metrics['sharpe_ratio']:.2f}",
                    f"{metrics['win_rate']:.1f}%",
                    f"{metrics['avg_daily_return']:.3f}%",
                    metrics['occurrences'],
                ])
            if pattern_data:
                print(tabulate(
                    pattern_data,
                    headers=["Pattern", "Sharpe", "Win Rate", "Avg Daily Return", "Occurrences"],
                    tablefmt="grid"
                ))
        
        # Time Periods
        if analysis["by_time_period"]:
            print("\n" + "-" * 80)
            print("PERFORMANCE BY TIME PERIOD (30-day windows)")
            print("-" * 80)
            period_data = []
            for period, metrics in analysis["by_time_period"].items():
                period_data.append([
                    metrics['start_date'],
                    metrics['end_date'],
                    f"{metrics['return']:.2f}%",
                    f"{metrics['sharpe_ratio']:.2f}",
                    f"{metrics['win_rate']:.1f}%",
                ])
            if period_data:
                print(tabulate(
                    period_data,
                    headers=["Start", "End", "Return", "Sharpe", "Win Rate"],
                    tablefmt="grid"
                ))
        
        # Consistent Patterns Summary
        if analysis["consistent_patterns"]:
            print("\n" + "=" * 80)
            print("CONSISTENT PATTERNS (Where system shows edge)")
            print("=" * 80)
            for pattern in analysis["consistent_patterns"]:
                print(f"\n{pattern['type'].upper()}: {pattern['pattern']}")
                print(f"  Sharpe: {pattern['sharpe']:.2f}")
                print(f"  Win Rate: {pattern['win_rate']:.1f}%")
        else:
            print("\n" + "=" * 80)
            print("NO CONSISTENT PATTERNS DETECTED")
            print("=" * 80)
            print("System performance appears random across all analyzed dimensions.")
        
        print("=" * 80)
