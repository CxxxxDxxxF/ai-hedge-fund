"""Constants and utilities related to analysts configuration.

10-Agent Structure (CTO Restructure):
- Core Analysts (5): Value Composite, Growth Composite, Valuation, Momentum, Mean Reversion
- Advisory (2): Market Regime, Performance Auditor
- System (3): Portfolio Manager, Risk Budget, Portfolio Allocator
"""

from src.agents import portfolio_manager
from src.agents.aswath_damodaran import aswath_damodaran_agent
from src.agents.peter_lynch import peter_lynch_agent
from src.agents.warren_buffett import warren_buffett_agent
from src.agents.momentum import momentum_agent
from src.agents.mean_reversion import mean_reversion_agent
from src.agents.performance_auditor import performance_auditor_agent
from src.agents.market_regime import market_regime_agent

# Define analyst configuration - single source of truth
# 10-Agent Structure: 5 Core Analysts + 2 Advisory + 3 System
ANALYST_CONFIG = {
    # CORE ANALYSTS (5) - Direct capital allocation influence
    "warren_buffett": {
        "display_name": "Value Composite",
        "description": "Value Composite Analyst (Buffett/Graham/Munger/Burry/Pabrai)",
        "investing_style": "Composite value investing incorporating Buffett's quality focus, Graham's margin of safety, Munger's rational thinking, Burry's deep value, and Pabrai's Dhandho principles. Seeks companies with strong fundamentals, competitive advantages, and adequate margin of safety.",
        "agent_func": warren_buffett_agent,
        "type": "analyst",
        "order": 1,
        "weight": 0.30,  # 30% weight in Portfolio Manager
    },
    "peter_lynch": {
        "display_name": "Growth Composite",
        "description": "Growth Composite Analyst (Lynch/Wood/Fisher)",
        "investing_style": "Composite growth investing incorporating Lynch's GARP and 'buy what you know', Wood's disruption focus, and Fisher's scuttlebutt research. Focuses on understandable businesses with strong growth potential at reasonable prices.",
        "agent_func": peter_lynch_agent,
        "type": "analyst",
        "order": 2,
        "weight": 0.25,  # 25% weight in Portfolio Manager
    },
    "aswath_damodaran": {
        "display_name": "Aswath Damodaran",
        "description": "The Dean of Valuation",
        "investing_style": "Focuses on intrinsic value and financial metrics to assess investment opportunities through rigorous valuation analysis.",
        "agent_func": aswath_damodaran_agent,
        "type": "analyst",
        "order": 3,
        "weight": 0.20,  # 20% weight in Portfolio Manager
    },
    "momentum": {
        "display_name": "Momentum",
        "description": "20-Day Price Momentum Specialist",
        "investing_style": "Uses 20-day price momentum to identify trending stocks. Bullish when price has risen significantly, bearish when price has declined significantly. Weight adjusted by Market Regime.",
        "agent_func": momentum_agent,
        "type": "analyst",
        "order": 4,
        "weight": 0.15,  # 15% weight in Portfolio Manager (regime-adjusted)
    },
    "mean_reversion": {
        "display_name": "Mean Reversion",
        "description": "Statistical Mean Reversion Specialist",
        "investing_style": "Identifies oversold (bullish) and overbought (bearish) conditions using RSI, price deviations from moving averages. Contrarian to momentum - buys dips, sells rallies. Weight adjusted by Market Regime.",
        "agent_func": mean_reversion_agent,
        "type": "analyst",
        "order": 5,
        "weight": 0.10,  # 10% weight in Portfolio Manager (regime-adjusted)
    },
    # ADVISORY AGENTS (2) - Context only, no direct trading influence
    "market_regime": {
        "display_name": "Market Regime Analyst",
        "description": "Market Condition Classifier (Advisory Only)",
        "investing_style": "Advisory agent that classifies market conditions (trending/mean-reverting/volatile/calm) and publishes recommended strategy weights. Does NOT emit trade signals. Portfolio Manager applies these weights when aggregating Momentum and Mean Reversion signals.",
        "agent_func": market_regime_agent,
        "type": "analyst",
        "order": 6,
        "advisory_only": True,  # Does NOT write to analyst_signals
    },
    "performance_auditor": {
        "display_name": "Performance Auditor",
        "description": "Performance Tracking Specialist (Advisory Only)",
        "investing_style": "Tracks analyst performance metrics (signal correctness, PnL contribution, drawdowns) and produces credibility scores (0.0-1.0) per agent. Scores update gradually based on historical performance. Does NOT emit trade signals.",
        "agent_func": performance_auditor_agent,
        "type": "analyst",
        "order": 7,
        "advisory_only": True,  # Does NOT write to analyst_signals
    },
}

# Derive ANALYST_ORDER from ANALYST_CONFIG for backwards compatibility
ANALYST_ORDER = [(config["display_name"], key) for key, config in sorted(ANALYST_CONFIG.items(), key=lambda x: x[1]["order"])]


def get_analyst_nodes():
    """Get the mapping of analyst keys to their (node_name, agent_func) tuples."""
    return {key: (f"{key}_agent", config["agent_func"]) for key, config in ANALYST_CONFIG.items()}


def get_agents_list():
    """Get the list of agents for API responses."""
    return [
        {
            "key": key,
            "display_name": config["display_name"],
            "description": config["description"],
            "investing_style": config["investing_style"],
            "order": config["order"]
        }
        for key, config in sorted(ANALYST_CONFIG.items(), key=lambda x: x[1]["order"])
    ]
