"""
Portfolio-Level Allocator Agent

A deterministic agent that enforces portfolio-level constraints:
- Gross/Net exposure limits
- Sector concentration caps
- Correlation limits across positions

Execution flow: Portfolio Manager (direction) → Risk Budget (size) → Portfolio Allocator (constraints) → Execution
"""

from src.graph.state import AgentState, show_agent_reasoning
from langchain_core.messages import HumanMessage
from src.tools.api import get_prices, prices_to_df
from src.utils.progress import progress
from src.utils.api_key import get_api_key_from_state
from src.data.models import CompanyFactsResponse
import pandas as pd
import numpy as np
import json
import os


# Portfolio constraint parameters
MAX_GROSS_EXPOSURE_PCT = 2.0  # Maximum gross exposure: 200% of portfolio value
MAX_NET_EXPOSURE_PCT = 0.5  # Maximum net exposure: ±50% of portfolio value
MAX_SECTOR_EXPOSURE_PCT = 0.30  # Maximum exposure per sector: 30% of portfolio value
MAX_CORRELATION = 0.70  # Maximum correlation between any two positions


def get_company_facts(ticker: str, api_key: str) -> dict | None:
    """
    Fetch company facts (including sector) for a ticker.
    Returns dict with sector, industry, or None if unavailable.
    """
    import requests
    
    headers = {}
    if api_key:
        headers["X-API-KEY"] = api_key
    
    url = f"https://api.financialdatasets.ai/company/facts/?ticker={ticker}"
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            response_model = CompanyFactsResponse(**data)
            facts = response_model.company_facts
            return {
                "sector": facts.sector,
                "industry": facts.industry,
                "name": facts.name,
            }
    except Exception:
        pass
    
    return None


def calculate_projected_exposures(
    portfolio: dict,
    pm_decisions: dict,
    risk_budgets: dict,
    current_prices: dict,
    portfolio_value: float,
) -> dict:
    """
    Calculate projected gross/net exposures after executing PM decisions.
    
    Returns:
        {
            "gross_exposure": float,
            "net_exposure": float,
            "long_exposure": float,
            "short_exposure": float,
            "by_ticker": {ticker: {"long": float, "short": float, "net": float}}
        }
    """
    projected_long = 0.0
    projected_short = 0.0
    by_ticker = {}
    
    # Start with current positions
    current_positions = portfolio.get("positions", {})
    for ticker, position in current_positions.items():
        if ticker not in current_prices or current_prices[ticker] <= 0:
            continue
        
        price = current_prices[ticker]
        current_long = position.get("long", 0)
        current_short = position.get("short", 0)
        
        # Apply PM decision to get new position
        pm_decision = pm_decisions.get(ticker, {})
        action = pm_decision.get("action", "hold")
        quantity = pm_decision.get("quantity", 0)
        
        new_long = current_long
        new_short = current_short
        
        if action == "buy":
            new_long = current_long + quantity
        elif action == "sell":
            new_long = max(0, current_long - quantity)
        elif action == "short":
            new_short = current_short + quantity
        elif action == "cover":
            new_short = max(0, current_short - quantity)
        
        # Calculate exposures
        long_exposure = new_long * price
        short_exposure = new_short * price
        net_exposure = long_exposure - short_exposure
        
        projected_long += long_exposure
        projected_short += short_exposure
        
        by_ticker[ticker] = {
            "long": long_exposure,
            "short": short_exposure,
            "net": net_exposure,
        }
    
    gross_exposure = projected_long + projected_short
    net_exposure = projected_long - projected_short
    
    return {
        "gross_exposure": gross_exposure,
        "net_exposure": net_exposure,
        "long_exposure": projected_long,
        "short_exposure": projected_short,
        "by_ticker": by_ticker,
    }


def calculate_sector_exposures(
    tickers: list[str],
    sector_map: dict[str, str],
    exposures_by_ticker: dict,
    portfolio_value: float,
) -> dict:
    """
    Calculate exposure by sector.
    
    Returns:
        {
            "sector_name": {
                "exposure": float,
                "exposure_pct": float,
                "tickers": [ticker, ...]
            }
        }
    """
    sector_exposures = {}
    
    for ticker in tickers:
        if ticker not in exposures_by_ticker:
            continue
        
        sector = sector_map.get(ticker, "Unknown")
        if sector not in sector_exposures:
            sector_exposures[sector] = {
                "exposure": 0.0,
                "exposure_pct": 0.0,
                "tickers": [],
            }
        
        # Use absolute net exposure for sector calculation
        ticker_exposure = abs(exposures_by_ticker[ticker].get("net", 0.0))
        sector_exposures[sector]["exposure"] += ticker_exposure
        sector_exposures[sector]["tickers"].append(ticker)
    
    # Calculate percentages
    for sector, data in sector_exposures.items():
        if portfolio_value > 0:
            data["exposure_pct"] = data["exposure"] / portfolio_value
        else:
            data["exposure_pct"] = 0.0
    
    return sector_exposures


def calculate_correlation_matrix(
    tickers: list[str],
    start_date: str,
    end_date: str,
    api_key: str,
) -> pd.DataFrame | None:
    """
    Calculate correlation matrix for tickers based on price returns.
    """
    returns_by_ticker = {}
    
    for ticker in tickers:
        prices = get_prices(
            ticker=ticker,
            start_date=start_date,
            end_date=end_date,
            api_key=api_key,
        )
        
        if not prices:
            continue
        
        prices_df = prices_to_df(prices)
        if len(prices_df) > 1:
            daily_returns = prices_df["close"].pct_change().dropna()
            if len(daily_returns) > 0:
                returns_by_ticker[ticker] = daily_returns
    
    if len(returns_by_ticker) < 2:
        return None
    
    try:
        returns_df = pd.DataFrame(returns_by_ticker).dropna(how="any")
        if returns_df.shape[1] >= 2 and returns_df.shape[0] >= 5:
            return returns_df.corr()
    except Exception:
        pass
    
    return None


def enforce_exposure_limits(
    pm_decisions: dict,
    risk_budgets: dict,
    projected_exposures: dict,
    portfolio_value: float,
) -> dict:
    """
    Adjust allocations to enforce gross/net exposure limits.
    
    Returns adjusted decisions dict.
    """
    adjusted_decisions = {}
    
    gross_exposure = projected_exposures["gross_exposure"]
    net_exposure = projected_exposures["net_exposure"]
    
    max_gross = portfolio_value * MAX_GROSS_EXPOSURE_PCT
    max_net = portfolio_value * MAX_NET_EXPOSURE_PCT
    
    # Check gross exposure limit
    if gross_exposure > max_gross:
        # Scale down all positions proportionally
        scale_factor = max_gross / gross_exposure
        for ticker, decision in pm_decisions.items():
            if decision.get("action", "hold") != "hold":
                adjusted = decision.copy()
                adjusted["quantity"] = int(decision.get("quantity", 0) * scale_factor)
                adjusted["reasoning"] = (
                    f"{decision.get('reasoning', '')} "
                    f"[Adjusted: gross exposure limit {gross_exposure:.0f} > {max_gross:.0f}]"
                )
                adjusted_decisions[ticker] = adjusted
            else:
                adjusted_decisions[ticker] = decision
    else:
        adjusted_decisions = pm_decisions.copy()
    
    # Check net exposure limit (after gross adjustment)
    # Recalculate net exposure with adjusted decisions
    # For simplicity, apply additional scaling if needed
    if abs(net_exposure) > max_net:
        net_scale = max_net / abs(net_exposure) if net_exposure != 0 else 1.0
        for ticker, decision in adjusted_decisions.items():
            action = decision.get("action", "hold")
            if action in ["buy", "short"]:
                adjusted = decision.copy()
                adjusted["quantity"] = int(decision.get("quantity", 0) * net_scale)
                adjusted["reasoning"] = (
                    f"{decision.get('reasoning', '')} "
                    f"[Adjusted: net exposure limit {net_exposure:.0f} > {max_net:.0f}]"
                )
                adjusted_decisions[ticker] = adjusted
    
    return adjusted_decisions


def enforce_sector_limits(
    pm_decisions: dict,
    sector_exposures: dict,
    exposures_by_ticker: dict,
    portfolio_value: float,
) -> dict:
    """
    Adjust allocations to enforce sector concentration limits.
    
    Returns adjusted decisions dict.
    """
    adjusted_decisions = pm_decisions.copy()
    max_sector_exposure = portfolio_value * MAX_SECTOR_EXPOSURE_PCT
    
    for sector, sector_data in sector_exposures.items():
        if sector_data["exposure_pct"] > MAX_SECTOR_EXPOSURE_PCT:
            # Sector over limit - scale down positions in this sector
            excess = sector_data["exposure"] - max_sector_exposure
            scale_factor = max_sector_exposure / sector_data["exposure"] if sector_data["exposure"] > 0 else 1.0
            
            for ticker in sector_data["tickers"]:
                if ticker in adjusted_decisions:
                    decision = adjusted_decisions[ticker]
                    action = decision.get("action", "hold")
                    if action != "hold":
                        adjusted = decision.copy()
                        adjusted["quantity"] = int(decision.get("quantity", 0) * scale_factor)
                        adjusted["reasoning"] = (
                            f"{decision.get('reasoning', '')} "
                            f"[Adjusted: sector {sector} limit {sector_data['exposure_pct']:.1%} > {MAX_SECTOR_EXPOSURE_PCT:.1%}]"
                        )
                        adjusted_decisions[ticker] = adjusted
    
    return adjusted_decisions


def enforce_correlation_limits(
    pm_decisions: dict,
    correlation_matrix: pd.DataFrame | None,
    exposures_by_ticker: dict,
    portfolio_value: float,
) -> dict:
    """
    Adjust allocations to reduce high correlations between positions.
    
    Returns adjusted decisions dict.
    """
    if correlation_matrix is None:
        return pm_decisions
    
    adjusted_decisions = pm_decisions.copy()
    
    # Find pairs with high correlation
    high_corr_pairs = []
    for i, ticker1 in enumerate(correlation_matrix.columns):
        for j, ticker2 in enumerate(correlation_matrix.columns):
            if i >= j:
                continue
            if ticker1 not in exposures_by_ticker or ticker2 not in exposures_by_ticker:
                continue
            
            corr = correlation_matrix.loc[ticker1, ticker2]
            if abs(corr) > MAX_CORRELATION:
                # Both have exposure - reduce the smaller one
                exp1 = abs(exposures_by_ticker[ticker1].get("net", 0))
                exp2 = abs(exposures_by_ticker[ticker2].get("net", 0))
                
                if exp1 > 0 and exp2 > 0:
                    high_corr_pairs.append((ticker1, ticker2, corr, exp1, exp2))
    
    # Adjust positions to reduce correlation
    for ticker1, ticker2, corr, exp1, exp2 in high_corr_pairs:
        # Reduce the smaller position by 50%
        if exp1 < exp2 and ticker1 in adjusted_decisions:
            decision = adjusted_decisions[ticker1]
            if decision.get("action", "hold") != "hold":
                adjusted = decision.copy()
                adjusted["quantity"] = int(decision.get("quantity", 0) * 0.5)
                adjusted["reasoning"] = (
                    f"{decision.get('reasoning', '')} "
                    f"[Adjusted: high correlation {corr:.2f} with {ticker2}]"
                )
                adjusted_decisions[ticker1] = adjusted
        elif exp2 < exp1 and ticker2 in adjusted_decisions:
            decision = adjusted_decisions[ticker2]
            if decision.get("action", "hold") != "hold":
                adjusted = decision.copy()
                adjusted["quantity"] = int(decision.get("quantity", 0) * 0.5)
                adjusted["reasoning"] = (
                    f"{decision.get('reasoning', '')} "
                    f"[Adjusted: high correlation {corr:.2f} with {ticker1}]"
                )
                adjusted_decisions[ticker2] = adjusted
    
    return adjusted_decisions


def portfolio_allocator_agent(state: AgentState, agent_id: str = "portfolio_allocator_agent"):
    """
    Enforces portfolio-level constraints: gross/net exposure, sector caps, correlation limits.
    
    Reads Portfolio Manager decisions and Risk Budget allocations, applies constraints,
    and outputs final adjusted allocations.
    """
    data = state["data"]
    tickers = data["tickers"]
    portfolio = data["portfolio"]
    start_date = data["start_date"]
    end_date = data["end_date"]
    api_key = get_api_key_from_state(state, "FINANCIAL_DATASETS_API_KEY")
    
    # Get Portfolio Manager decisions
    pm_decisions = data.get("portfolio_decisions", {})
    if not pm_decisions:
        # Try to get from messages
        for message in state["messages"]:
            if message.name == "portfolio_manager":
                try:
                    pm_decisions = json.loads(message.content)
                    break
                except (json.JSONDecodeError, TypeError):
                    continue
    
    # Get Risk Budget allocations
    risk_budgets = data.get("risk_budget", {})
    
    # Get current prices
    current_prices = data.get("current_prices", {})
    
    # Calculate portfolio value
    portfolio_value = portfolio.get("cash", 0.0)
    for ticker, positions in portfolio.get("positions", {}).items():
        if ticker in current_prices:
            price = current_prices[ticker]
            long_shares = positions.get("long", 0)
            short_shares = positions.get("short", 0)
            portfolio_value += (long_shares - short_shares) * price
    
    if portfolio_value <= 0:
        portfolio_value = portfolio.get("cash", 100000.0)
    
    # Fetch prices for all tickers if not already available
    for ticker in tickers:
        if ticker not in current_prices:
            progress.update_status(agent_id, ticker, "Fetching current price")
            prices = get_prices(
                ticker=ticker,
                start_date=start_date,
                end_date=end_date,
                api_key=api_key,
            )
            if prices:
                prices_df = prices_to_df(prices)
                if not prices_df.empty:
                    current_prices[ticker] = float(prices_df["close"].iloc[-1])
    
    # Calculate projected exposures
    progress.update_status(agent_id, None, "Calculating projected exposures")
    projected_exposures = calculate_projected_exposures(
        portfolio=portfolio,
        pm_decisions=pm_decisions,
        risk_budgets=risk_budgets,
        current_prices=current_prices,
        portfolio_value=portfolio_value,
    )
    
    # Get sector data for all tickers
    progress.update_status(agent_id, None, "Fetching sector classifications")
    sector_map = {}
    for ticker in tickers:
        facts = get_company_facts(ticker, api_key)
        if facts and facts.get("sector"):
            sector_map[ticker] = facts["sector"]
        else:
            sector_map[ticker] = "Unknown"
    
    # Calculate sector exposures
    sector_exposures = calculate_sector_exposures(
        tickers=tickers,
        sector_map=sector_map,
        exposures_by_ticker=projected_exposures["by_ticker"],
        portfolio_value=portfolio_value,
    )
    
    # Calculate correlation matrix
    progress.update_status(agent_id, None, "Calculating correlations")
    correlation_matrix = calculate_correlation_matrix(
        tickers=tickers,
        start_date=start_date,
        end_date=end_date,
        api_key=api_key,
    )
    
    # Apply constraints in order: exposure → sector → correlation
    adjusted_decisions = pm_decisions.copy()
    
    # 1. Enforce gross/net exposure limits
    progress.update_status(agent_id, None, "Enforcing exposure limits")
    adjusted_decisions = enforce_exposure_limits(
        pm_decisions=adjusted_decisions,
        risk_budgets=risk_budgets,
        projected_exposures=projected_exposures,
        portfolio_value=portfolio_value,
    )
    
    # 2. Enforce sector limits
    progress.update_status(agent_id, None, "Enforcing sector limits")
    # Recalculate exposures with adjusted decisions
    projected_exposures_adj = calculate_projected_exposures(
        portfolio=portfolio,
        pm_decisions=adjusted_decisions,
        risk_budgets=risk_budgets,
        current_prices=current_prices,
        portfolio_value=portfolio_value,
    )
    sector_exposures_adj = calculate_sector_exposures(
        tickers=tickers,
        sector_map=sector_map,
        exposures_by_ticker=projected_exposures_adj["by_ticker"],
        portfolio_value=portfolio_value,
    )
    adjusted_decisions = enforce_sector_limits(
        pm_decisions=adjusted_decisions,
        sector_exposures=sector_exposures_adj,
        exposures_by_ticker=projected_exposures_adj["by_ticker"],
        portfolio_value=portfolio_value,
    )
    
    # 3. Enforce correlation limits
    progress.update_status(agent_id, None, "Enforcing correlation limits")
    # Recalculate exposures again
    projected_exposures_final = calculate_projected_exposures(
        portfolio=portfolio,
        pm_decisions=adjusted_decisions,
        risk_budgets=risk_budgets,
        current_prices=current_prices,
        portfolio_value=portfolio_value,
    )
    adjusted_decisions = enforce_correlation_limits(
        pm_decisions=adjusted_decisions,
        correlation_matrix=correlation_matrix,
        exposures_by_ticker=projected_exposures_final["by_ticker"],
        portfolio_value=portfolio_value,
    )
    
    # Store final allocations and constraint analysis
    allocation_data = {
        "adjusted_decisions": adjusted_decisions,
        "constraints": {
            "gross_exposure": {
                "current": projected_exposures["gross_exposure"],
                "limit": portfolio_value * MAX_GROSS_EXPOSURE_PCT,
                "limit_pct": MAX_GROSS_EXPOSURE_PCT,
            },
            "net_exposure": {
                "current": projected_exposures["net_exposure"],
                "limit": portfolio_value * MAX_NET_EXPOSURE_PCT,
                "limit_pct": MAX_NET_EXPOSURE_PCT,
            },
            "sector_limits": {
                "max_sector_pct": MAX_SECTOR_EXPOSURE_PCT,
                "sector_exposures": sector_exposures_adj,
            },
            "correlation_limit": {
                "max_correlation": MAX_CORRELATION,
                "high_correlations": [],
            },
        },
    }
    
    # Identify high correlations
    if correlation_matrix is not None:
        high_corrs = []
        for i, ticker1 in enumerate(correlation_matrix.columns):
            for j, ticker2 in enumerate(correlation_matrix.columns):
                if i >= j:
                    continue
                corr = correlation_matrix.loc[ticker1, ticker2]
                if abs(corr) > MAX_CORRELATION:
                    high_corrs.append({
                        "ticker1": ticker1,
                        "ticker2": ticker2,
                        "correlation": float(corr),
                    })
        allocation_data["constraints"]["correlation_limit"]["high_correlations"] = high_corrs
    
    # Store in state
    if "portfolio_allocation" not in data:
        data["portfolio_allocation"] = {}
    data["portfolio_allocation"] = allocation_data
    
    # Store adjusted decisions for execution
    data["portfolio_decisions"] = adjusted_decisions
    
    # Create message
    message_content = json.dumps({
        "advisory": "Portfolio-level constraint enforcement",
        "allocation": allocation_data,
    })
    message = HumanMessage(content=message_content, name=agent_id)
    
    # Show reasoning if requested
    if state["metadata"]["show_reasoning"]:
        show_agent_reasoning(allocation_data, agent_id)
    
    progress.update_status(agent_id, None, "Done")
    
    return {"messages": [message], "data": state["data"]}
