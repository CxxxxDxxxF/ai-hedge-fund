import sys

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langgraph.graph import END, StateGraph
from colorama import Fore, Style, init
import questionary
from src.agents.portfolio_manager import portfolio_management_agent
from src.agents.risk_budget import risk_budget_agent
from src.agents.portfolio_allocator import portfolio_allocator_agent
from src.graph.state import AgentState
from src.utils.display import print_trading_output
from src.utils.analysts import ANALYST_ORDER, get_analyst_nodes
from src.utils.progress import progress
from src.utils.visualize import save_graph_as_png
from src.cli.input import (
    parse_cli_inputs,
)

import argparse
from datetime import datetime
from dateutil.relativedelta import relativedelta
import json

# Load environment variables from .env file
load_dotenv()

init(autoreset=True)


def parse_hedge_fund_response(response):
    """Parses a JSON string and returns a dictionary."""
    try:
        return json.loads(response)
    except json.JSONDecodeError as e:
        print(f"JSON decoding error: {e}\nResponse: {repr(response)}")
        return None
    except TypeError as e:
        print(f"Invalid response type (expected string, got {type(response).__name__}): {e}")
        return None
    except Exception as e:
        print(f"Unexpected error while parsing response: {e}\nResponse: {repr(response)}")
        return None


##### Run the Hedge Fund #####
def run_hedge_fund(
    tickers: list[str],
    start_date: str,
    end_date: str,
    portfolio: dict,
    show_reasoning: bool = False,
    selected_analysts: list[str] = [],
    model_name: str = "gpt-4.1",
    model_provider: str = "OpenAI",
):
    # Start progress tracking
    progress.start()

    try:
        # Build workflow (default to all analysts when none provided)
        workflow = create_workflow(selected_analysts if selected_analysts else None)
        agent = workflow.compile()

        final_state = agent.invoke(
            {
                "messages": [
                    HumanMessage(
                        content="Make trading decisions based on the provided data.",
                    )
                ],
                "data": {
                    "tickers": tickers,
                    "portfolio": portfolio,
                    "start_date": start_date,
                    "end_date": end_date,
                    "analyst_signals": {},
                },
                "metadata": {
                    "show_reasoning": show_reasoning,
                    "model_name": model_name,
                    "model_provider": model_provider,
                },
            },
        )

        return {
            "decisions": parse_hedge_fund_response(final_state["messages"][-1].content),
            "analyst_signals": final_state["data"]["analyst_signals"],
            "market_regime": final_state["data"].get("market_regime", {}),
            "risk_budget": final_state["data"].get("risk_budget", {}),
            "portfolio_decisions": final_state["data"].get("portfolio_decisions", {}),
            "portfolio_allocation": final_state["data"].get("portfolio_allocation", {}),
        }
    finally:
        # Stop progress tracking
        progress.stop()


def start(state: AgentState):
    """Initialize the workflow with the input message."""
    return state


def create_workflow(selected_analysts=None):
    """Create the workflow with selected analysts."""
    workflow = StateGraph(AgentState)
    workflow.add_node("start_node", start)

    # Get analyst nodes from the configuration
    analyst_nodes = get_analyst_nodes()

    # Default to all analysts if none selected
    if selected_analysts is None:
        selected_analysts = list(analyst_nodes.keys())
    
    # Separate regular analysts from system analysts that need special ordering
    # 10-agent restructure: Only Market Regime and Performance Auditor are system analysts
    system_analysts = {"performance_auditor", "market_regime"}
    regular_analysts = [a for a in selected_analysts if a not in system_analysts]
    has_performance_auditor = "performance_auditor" in selected_analysts
    has_market_regime = "market_regime" in selected_analysts
    
    # Add all selected analyst nodes
    for analyst_key in selected_analysts:
        node_name, node_func = analyst_nodes[analyst_key]
        workflow.add_node(node_name, node_func)
        # Regular analysts connect from start_node
        if analyst_key not in system_analysts:
            workflow.add_edge("start_node", node_name)

    # Always add risk budget, portfolio management, and portfolio allocator
    # Note: Risk Manager merged into Portfolio Allocator (10-agent restructure)
    workflow.add_node("risk_budget_agent", risk_budget_agent)
    workflow.add_node("portfolio_manager", portfolio_management_agent)
    workflow.add_node("portfolio_allocator_agent", portfolio_allocator_agent)

    # Connect analysts in correct order (10-agent restructure):
    # Core Analysts → Market Regime (if selected) → Performance Auditor → Portfolio Manager → Risk Budget → Portfolio Allocator → END
    
    # Market Regime depends on momentum and mean_reversion agents
    if has_market_regime:
        market_regime_node = analyst_nodes["market_regime"][0]
        # Connect momentum and mean_reversion to market_regime if they exist
        if "momentum" in selected_analysts:
            momentum_node = analyst_nodes["momentum"][0]
            workflow.add_edge(momentum_node, market_regime_node)
        if "mean_reversion" in selected_analysts:
            mean_reversion_node = analyst_nodes["mean_reversion"][0]
            workflow.add_edge(mean_reversion_node, market_regime_node)
        # If neither exists, connect from start_node
        if "momentum" not in selected_analysts and "mean_reversion" not in selected_analysts:
            workflow.add_edge("start_node", market_regime_node)
    
    if has_performance_auditor:
        # Connect all regular analysts to performance auditor
        perf_auditor_node = analyst_nodes["performance_auditor"][0]
        for analyst_key in regular_analysts:
            node_name = analyst_nodes[analyst_key][0]
            workflow.add_edge(node_name, perf_auditor_node)
        
        # Market Regime → Performance Auditor (if both exist)
        if has_market_regime:
            workflow.add_edge(market_regime_node, perf_auditor_node)
        
        # Performance Auditor → Portfolio Manager (10-agent restructure: removed Conflict Arbiter and Risk Manager)
        workflow.add_edge(perf_auditor_node, "portfolio_manager")
    else:
        # No Performance Auditor: Regular analysts → Portfolio Manager
        for analyst_key in regular_analysts:
            node_name = analyst_nodes[analyst_key][0]
            workflow.add_edge(node_name, "portfolio_manager")
        # Market Regime → Portfolio Manager (if no Performance Auditor)
        if has_market_regime:
            workflow.add_edge(market_regime_node, "portfolio_manager")
    
    # Connect Portfolio Manager → Risk Budget → Portfolio Allocator → END
    workflow.add_edge("portfolio_manager", "risk_budget_agent")
    workflow.add_edge("risk_budget_agent", "portfolio_allocator_agent")
    workflow.add_edge("portfolio_allocator_agent", END)

    workflow.set_entry_point("start_node")
    return workflow


if __name__ == "__main__":
    inputs = parse_cli_inputs(
        description="Run the hedge fund trading system",
        require_tickers=True,
        default_months_back=None,
        include_graph_flag=True,
        include_reasoning_flag=True,
    )

    tickers = inputs.tickers
    selected_analysts = inputs.selected_analysts

    # Construct portfolio here
    portfolio = {
        "cash": inputs.initial_cash,
        "margin_requirement": inputs.margin_requirement,
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
            ticker: {
                "long": 0.0,
                "short": 0.0,
            }
            for ticker in tickers
        },
    }

    result = run_hedge_fund(
        tickers=tickers,
        start_date=inputs.start_date,
        end_date=inputs.end_date,
        portfolio=portfolio,
        show_reasoning=inputs.show_reasoning,
        selected_analysts=inputs.selected_analysts,
        model_name=inputs.model_name,
        model_provider=inputs.model_provider,
    )
    print_trading_output(result)
