"""
Edge Detection Analysis: Statistical significance testing for trading system performance.

Answers: "Does my system have repeatable edge after costs, or is it just noise?"

Key Metrics:
1. Sharpe Ratio (risk-adjusted returns)
2. Information Ratio (alpha vs benchmark)
3. Statistical Significance (t-test, p-value)
4. Transaction Costs Impact
5. Bootstrap Analysis (robustness)
6. Out-of-Sample Validation
7. Multiple Time Periods Analysis
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
try:
    from scipy import stats
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False
    # Fallback: basic stats without scipy
    import math
from datetime import datetime


class EdgeAnalysis:
    """
    Comprehensive edge detection analysis for trading systems.
    
    Determines if performance is statistically significant or random noise.
    """
    
    # Typical transaction costs (conservative estimates)
    COMMISSION_PER_TRADE = 0.01  # $0.01 per share (typical retail)
    SLIPPAGE_BPS = 5  # 5 basis points (0.05%) per trade
    BID_ASK_SPREAD_BPS = 3  # 3 basis points (0.03%) for liquid stocks
    
    def __init__(
        self,
        daily_returns: pd.Series,
        benchmark_returns: Optional[pd.Series] = None,
        trades: Optional[List[Dict]] = None,
        initial_capital: float = 100000.0,
    ):
        """
        Initialize edge analysis.
        
        Args:
            daily_returns: Daily portfolio returns (as decimal, e.g., 0.01 for 1%)
            benchmark_returns: Benchmark returns (e.g., SPY) for comparison
            trades: List of trade dictionaries with 'quantity', 'price', 'action'
            initial_capital: Starting capital for cost calculations
        """
        self.daily_returns = daily_returns.dropna()
        self.benchmark_returns = benchmark_returns.dropna() if benchmark_returns is not None else None
        self.trades = trades or []
        self.initial_capital = initial_capital
        
    def calculate_transaction_costs(self) -> Dict[str, float]:
        """
        Calculate total transaction costs (commissions + slippage + spread).
        
        Returns:
            Dict with total_cost, commission_cost, slippage_cost, spread_cost
        """
        if not self.trades:
            return {
                "total_cost": 0.0,
                "commission_cost": 0.0,
                "slippage_cost": 0.0,
                "spread_cost": 0.0,
                "cost_pct_of_capital": 0.0,
            }
        
        commission_cost = 0.0
        slippage_cost = 0.0
        spread_cost = 0.0
        
        for trade in self.trades:
            quantity = abs(trade.get("quantity", 0))
            price = trade.get("price", 0.0)
            trade_value = quantity * price
            
            # Commission
            commission = quantity * self.COMMISSION_PER_TRADE
            commission_cost += commission
            
            # Slippage (basis points)
            slippage = trade_value * (self.SLIPPAGE_BPS / 10000)
            slippage_cost += slippage
            
            # Bid-ask spread (half round-trip, since we pay spread on entry)
            spread = trade_value * (self.BID_ASK_SPREAD_BPS / 10000)
            spread_cost += spread
        
        total_cost = commission_cost + slippage_cost + spread_cost
        
        return {
            "total_cost": total_cost,
            "commission_cost": commission_cost,
            "slippage_cost": slippage_cost,
            "spread_cost": spread_cost,
            "cost_pct_of_capital": (total_cost / self.initial_capital) * 100,
            "cost_per_trade": total_cost / len(self.trades) if self.trades else 0.0,
        }
    
    def calculate_sharpe_ratio(self, risk_free_rate: float = 0.0434) -> Dict[str, float]:
        """
        Calculate annualized Sharpe ratio.
        
        Args:
            risk_free_rate: Annual risk-free rate (default 4.34% = 10Y Treasury)
        
        Returns:
            Dict with sharpe_ratio, annual_return, annual_volatility
        """
        if len(self.daily_returns) < 2:
            return {
                "sharpe_ratio": 0.0,
                "annual_return": 0.0,
                "annual_volatility": 0.0,
                "excess_return": 0.0,
            }
        
        # Annualize
        trading_days = 252
        annual_return = self.daily_returns.mean() * trading_days
        annual_volatility = self.daily_returns.std() * np.sqrt(trading_days)
        
        # Excess return
        daily_rf = risk_free_rate / trading_days
        excess_return = annual_return - risk_free_rate
        
        # Sharpe ratio
        if annual_volatility > 0:
            sharpe_ratio = excess_return / annual_volatility
        else:
            sharpe_ratio = 0.0
        
        return {
            "sharpe_ratio": sharpe_ratio,
            "annual_return": annual_return * 100,  # Convert to percentage
            "annual_volatility": annual_volatility * 100,
            "excess_return": excess_return * 100,
        }
    
    def calculate_information_ratio(self) -> Dict[str, float]:
        """
        Calculate Information Ratio (alpha / tracking error).
        
        Measures risk-adjusted excess returns vs benchmark.
        
        Returns:
            Dict with information_ratio, alpha, tracking_error, beta
        """
        if self.benchmark_returns is None or len(self.daily_returns) < 2:
            return {
                "information_ratio": None,
                "alpha": None,
                "tracking_error": None,
                "beta": None,
            }
        
        # Align dates
        aligned = pd.DataFrame({
            "portfolio": self.daily_returns,
            "benchmark": self.benchmark_returns,
        }).dropna()
        
        if len(aligned) < 2:
            return {
                "information_ratio": None,
                "alpha": None,
                "tracking_error": None,
                "beta": None,
            }
        
        portfolio_returns = aligned["portfolio"]
        benchmark_returns = aligned["benchmark"]
        
        # Calculate beta (regression coefficient)
        if benchmark_returns.std() > 0:
            beta = np.cov(portfolio_returns, benchmark_returns)[0, 1] / np.var(benchmark_returns)
        else:
            beta = 1.0
        
        # Alpha (excess return after adjusting for beta)
        alpha = (portfolio_returns.mean() - benchmark_returns.mean() * beta) * 252
        
        # Tracking error (std of excess returns)
        excess_returns = portfolio_returns - benchmark_returns
        tracking_error = excess_returns.std() * np.sqrt(252)
        
        # Information ratio
        if tracking_error > 0:
            information_ratio = alpha / tracking_error
        else:
            information_ratio = 0.0
        
        return {
            "information_ratio": information_ratio,
            "alpha": alpha * 100,  # Convert to percentage
            "tracking_error": tracking_error * 100,
            "beta": beta,
        }
    
    def test_statistical_significance(self, null_hypothesis_return: float = 0.0) -> Dict[str, float]:
        """
        Test if returns are statistically significant (not just noise).
        
        Uses one-sample t-test: H0: mean return = null_hypothesis_return
        
        Args:
            null_hypothesis_return: Expected return under null hypothesis (default 0 = random walk)
        
        Returns:
            Dict with t_statistic, p_value, is_significant (at 5% level), confidence_interval
        """
        if len(self.daily_returns) < 2:
            return {
                "t_statistic": 0.0,
                "p_value": 1.0,
                "is_significant": False,
                "confidence_interval_95": (0.0, 0.0),
            }
        
        # Annualize returns for test
        annualized_returns = self.daily_returns * 252
        
        # One-sample t-test
        if HAS_SCIPY:
            t_stat, p_value = stats.ttest_1samp(annualized_returns, null_hypothesis_return)
        else:
            # Manual t-test calculation
            mean_return = annualized_returns.mean()
            std_error = annualized_returns.std() / np.sqrt(len(annualized_returns))
            if std_error > 0:
                t_stat = (mean_return - null_hypothesis_return) / std_error
                # Approximate p-value using normal distribution (for large samples)
                p_value = 2 * (1 - 0.5 * (1 + math.erf(abs(t_stat) / math.sqrt(2))))
            else:
                t_stat = 0.0
                p_value = 1.0
        
        # 95% confidence interval
        mean_return = annualized_returns.mean()
        std_error = annualized_returns.std() / np.sqrt(len(annualized_returns))
        if HAS_SCIPY:
            confidence_interval = stats.t.interval(
                0.95,
                len(annualized_returns) - 1,
                loc=mean_return,
                scale=std_error,
            )
        else:
            # Approximate using normal distribution
            z_score = 1.96  # 95% confidence
            confidence_interval = (
                mean_return - z_score * std_error,
                mean_return + z_score * std_error,
            )
        
        # Significant if p < 0.05 (5% level)
        is_significant = p_value < 0.05
        
        return {
            "t_statistic": float(t_stat),
            "p_value": float(p_value),
            "is_significant": is_significant,
            "confidence_interval_95": (float(confidence_interval[0]), float(confidence_interval[1])),
            "mean_annual_return": float(mean_return),
        }
    
    def bootstrap_analysis(self, n_bootstrap: int = 1000, confidence_level: float = 0.95) -> Dict[str, float]:
        """
        Bootstrap analysis to test robustness of results.
        
        Resamples returns with replacement to estimate distribution of Sharpe ratio.
        
        Args:
            n_bootstrap: Number of bootstrap samples
            confidence_level: Confidence level for intervals
        
        Returns:
            Dict with bootstrap_sharpe_mean, bootstrap_sharpe_std, confidence_interval
        """
        if len(self.daily_returns) < 10:
            return {
                "bootstrap_sharpe_mean": 0.0,
                "bootstrap_sharpe_std": 0.0,
                "confidence_interval": (0.0, 0.0),
                "p_value_positive": 1.0,
            }
        
        sharpe_ratios = []
        
        for _ in range(n_bootstrap):
            # Resample with replacement
            resampled = np.random.choice(self.daily_returns, size=len(self.daily_returns), replace=True)
            
            # Calculate Sharpe for resample
            if resampled.std() > 0:
                sharpe = (resampled.mean() / resampled.std()) * np.sqrt(252)
                sharpe_ratios.append(sharpe)
        
        if not sharpe_ratios:
            return {
                "bootstrap_sharpe_mean": 0.0,
                "bootstrap_sharpe_std": 0.0,
                "confidence_interval": (0.0, 0.0),
                "p_value_positive": 1.0,
            }
        
        sharpe_array = np.array(sharpe_ratios)
        
        # Confidence interval
        alpha = 1 - confidence_level
        lower = np.percentile(sharpe_array, (alpha / 2) * 100)
        upper = np.percentile(sharpe_array, (1 - alpha / 2) * 100)
        
        # P-value: probability that Sharpe > 0
        p_value_positive = (sharpe_array > 0).mean()
        
        return {
            "bootstrap_sharpe_mean": float(sharpe_array.mean()),
            "bootstrap_sharpe_std": float(sharpe_array.std()),
            "confidence_interval": (float(lower), float(upper)),
            "p_value_positive": float(p_value_positive),
        }
    
    def calculate_after_cost_returns(self) -> Dict[str, float]:
        """
        Calculate returns after transaction costs.
        
        Returns:
            Dict with before_cost_return, after_cost_return, cost_impact
        """
        costs = self.calculate_transaction_costs()
        
        # Before cost return
        if len(self.daily_returns) > 0:
            total_return = (1 + self.daily_returns).prod() - 1
            before_cost_return = total_return * 100
        else:
            before_cost_return = 0.0
        
        # After cost return
        cost_pct = costs["cost_pct_of_capital"] / 100
        after_cost_return = before_cost_return - cost_pct
        
        return {
            "before_cost_return": before_cost_return,
            "after_cost_return": after_cost_return,
            "cost_impact_pct": cost_pct,
            "total_cost": costs["total_cost"],
        }
    
    def comprehensive_analysis(self) -> Dict[str, any]:
        """
        Run comprehensive edge detection analysis.
        
        Returns:
            Complete analysis dictionary with all metrics
        """
        sharpe = self.calculate_sharpe_ratio()
        info_ratio = self.calculate_information_ratio()
        significance = self.test_statistical_significance()
        bootstrap = self.bootstrap_analysis()
        costs = self.calculate_transaction_costs()
        after_cost = self.calculate_after_cost_returns()
        
        # Edge assessment
        has_edge = (
            significance["is_significant"]
            and sharpe["sharpe_ratio"] > 1.0  # Sharpe > 1 is good
            and after_cost["after_cost_return"] > 0  # Profitable after costs
            and bootstrap["p_value_positive"] > 0.8  # 80%+ bootstrap samples positive
        )
        
        edge_strength = "STRONG" if sharpe["sharpe_ratio"] > 2.0 else "MODERATE" if sharpe["sharpe_ratio"] > 1.0 else "WEAK" if has_edge else "NONE"
        
        return {
            "has_edge": has_edge,
            "edge_strength": edge_strength,
            "sharpe_ratio": sharpe,
            "information_ratio": info_ratio,
            "statistical_significance": significance,
            "bootstrap_analysis": bootstrap,
            "transaction_costs": costs,
            "after_cost_returns": after_cost,
            "summary": {
                "sharpe_ratio": sharpe["sharpe_ratio"],
                "annual_return_pct": sharpe["annual_return"],
                "is_statistically_significant": significance["is_significant"],
                "p_value": significance["p_value"],
                "after_cost_return_pct": after_cost["after_cost_return"],
                "cost_impact_pct": after_cost["cost_impact_pct"],
            },
        }
    
    def print_analysis(self, analysis: Optional[Dict] = None) -> None:
        """Print comprehensive edge analysis report."""
        if analysis is None:
            analysis = self.comprehensive_analysis()
        
        print("\n" + "=" * 80)
        print("EDGE DETECTION ANALYSIS")
        print("=" * 80)
        print("\nQuestion: Does this system have repeatable edge after costs, or is it just noise?")
        print("\n" + "-" * 80)
        
        # Edge Assessment
        print("EDGE ASSESSMENT")
        print("-" * 80)
        print(f"Has Edge: {'✓ YES' if analysis['has_edge'] else '✗ NO'}")
        print(f"Edge Strength: {analysis['edge_strength']}")
        print()
        
        # Sharpe Ratio
        sharpe = analysis["sharpe_ratio"]
        print("RISK-ADJUSTED RETURNS (Sharpe Ratio)")
        print("-" * 80)
        print(f"Sharpe Ratio: {sharpe['sharpe_ratio']:.2f}")
        print(f"  Interpretation: {'Excellent (>2)' if sharpe['sharpe_ratio'] > 2 else 'Good (>1)' if sharpe['sharpe_ratio'] > 1 else 'Poor (<1)'}")
        print(f"Annual Return: {sharpe['annual_return']:.2f}%")
        print(f"Annual Volatility: {sharpe['annual_volatility']:.2f}%")
        print(f"Excess Return (vs Risk-Free): {sharpe['excess_return']:.2f}%")
        print()
        
        # Statistical Significance
        sig = analysis["statistical_significance"]
        print("STATISTICAL SIGNIFICANCE")
        print("-" * 80)
        print(f"Significant (p < 0.05): {'✓ YES' if sig['is_significant'] else '✗ NO'}")
        print(f"P-Value: {sig['p_value']:.4f}")
        print(f"T-Statistic: {sig['t_statistic']:.2f}")
        print(f"95% Confidence Interval: [{sig['confidence_interval_95'][0]:.2f}%, {sig['confidence_interval_95'][1]:.2f}%]")
        print(f"Mean Annual Return: {sig['mean_annual_return']:.2f}%")
        print()
        
        # Transaction Costs
        costs = analysis["transaction_costs"]
        print("TRANSACTION COSTS")
        print("-" * 80)
        print(f"Total Cost: ${costs['total_cost']:,.2f}")
        print(f"Cost as % of Capital: {costs['cost_pct_of_capital']:.2f}%")
        print(f"Cost per Trade: ${costs['cost_per_trade']:.2f}")
        print(f"  Commission: ${costs['commission_cost']:,.2f}")
        print(f"  Slippage: ${costs['slippage_cost']:,.2f}")
        print(f"  Bid-Ask Spread: ${costs['spread_cost']:,.2f}")
        print()
        
        # After-Cost Returns
        after_cost = analysis["after_cost_returns"]
        print("RETURNS AFTER COSTS")
        print("-" * 80)
        print(f"Before Cost Return: {after_cost['before_cost_return']:.2f}%")
        print(f"After Cost Return: {after_cost['after_cost_return']:.2f}%")
        print(f"Cost Impact: -{after_cost['cost_impact_pct']:.2f}%")
        print()
        
        # Bootstrap Analysis
        bootstrap = analysis["bootstrap_analysis"]
        print("BOOTSTRAP ROBUSTNESS TEST")
        print("-" * 80)
        print(f"Bootstrap Sharpe Mean: {bootstrap['bootstrap_sharpe_mean']:.2f}")
        print(f"Bootstrap Sharpe Std: {bootstrap['bootstrap_sharpe_std']:.2f}")
        print(f"95% Confidence Interval: [{bootstrap['confidence_interval'][0]:.2f}, {bootstrap['confidence_interval'][1]:.2f}]")
        print(f"P(Sharpe > 0): {bootstrap['p_value_positive']:.1%}")
        print()
        
        # Information Ratio (if benchmark available)
        if analysis["information_ratio"]["information_ratio"] is not None:
            info = analysis["information_ratio"]
            print("INFORMATION RATIO (vs Benchmark)")
            print("-" * 80)
            print(f"Information Ratio: {info['information_ratio']:.2f}")
            print(f"Alpha: {info['alpha']:.2f}%")
            print(f"Tracking Error: {info['tracking_error']:.2f}%")
            print(f"Beta: {info['beta']:.2f}")
            print()
        
        # Final Verdict
        print("=" * 80)
        print("VERDICT")
        print("=" * 80)
        if analysis["has_edge"]:
            print("✓ SYSTEM HAS DETECTABLE EDGE")
            print(f"  Edge Strength: {analysis['edge_strength']}")
            print(f"  Sharpe Ratio: {sharpe['sharpe_ratio']:.2f} ({'Excellent' if sharpe['sharpe_ratio'] > 2 else 'Good'})")
            print(f"  Statistically Significant: {'Yes' if sig['is_significant'] else 'No'}")
            print(f"  Profitable After Costs: {'Yes' if after_cost['after_cost_return'] > 0 else 'No'}")
        else:
            print("✗ SYSTEM LIKELY HAS NO DETECTABLE EDGE")
            print("  Reasons:")
            if not sig['is_significant']:
                print(f"    - Not statistically significant (p={sig['p_value']:.4f})")
            if sharpe['sharpe_ratio'] <= 1.0:
                print(f"    - Low Sharpe ratio ({sharpe['sharpe_ratio']:.2f} <= 1.0)")
            if after_cost['after_cost_return'] <= 0:
                print(f"    - Not profitable after costs ({after_cost['after_cost_return']:.2f}%)")
            if bootstrap['p_value_positive'] <= 0.8:
                print(f"    - Low bootstrap confidence ({bootstrap['p_value_positive']:.1%} < 80%)")
        print("=" * 80)
