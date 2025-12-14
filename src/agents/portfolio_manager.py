import json
import time
from langchain_core.messages import HumanMessage
from langchain_core.prompts import ChatPromptTemplate

from src.graph.state import AgentState, show_agent_reasoning
from pydantic import BaseModel, Field
from typing_extensions import Literal
from src.utils.progress import progress
from src.utils.llm import call_llm


class PortfolioDecision(BaseModel):
    action: Literal["buy", "sell", "short", "cover", "hold"]
    quantity: int = Field(description="Number of shares to trade")
    confidence: int = Field(description="Confidence 0-100")
    reasoning: str = Field(description="Reasoning for the decision")


class PortfolioManagerOutput(BaseModel):
    decisions: dict[str, PortfolioDecision] = Field(description="Dictionary of ticker to trading decisions")


##### Portfolio Management Agent #####
def portfolio_management_agent(state: AgentState, agent_id: str = "portfolio_manager"):
    """Makes final trading decisions and generates orders for multiple tickers"""

    portfolio = state["data"]["portfolio"]
    analyst_signals = state["data"]["analyst_signals"]
    tickers = state["data"]["tickers"]

    position_limits = {}
    current_prices = {}
    max_shares = {}
    signals_by_ticker = {}
    for ticker in tickers:
        progress.update_status(agent_id, ticker, "Processing analyst signals")

        # Find the corresponding risk manager for this portfolio manager
        if agent_id.startswith("portfolio_manager_"):
            suffix = agent_id.split('_')[-1]
            risk_manager_id = f"risk_management_agent_{suffix}"
        else:
            risk_manager_id = "risk_management_agent"  # Fallback for CLI

        risk_data = analyst_signals.get(risk_manager_id, {}).get(ticker, {})
        position_limits[ticker] = risk_data.get("remaining_position_limit", 0.0)
        current_prices[ticker] = float(risk_data.get("current_price", 0.0))

        # Calculate maximum shares allowed based on position limit and price
        if current_prices[ticker] > 0:
            max_shares[ticker] = int(position_limits[ticker] // current_prices[ticker])
        else:
            max_shares[ticker] = 0

        # Compress analyst signals to {sig, conf}
        # Filter to only use 5 core analysts (10-agent restructure)
        # Core analysts: warren_buffett, peter_lynch, aswath_damodaran, momentum, mean_reversion
        CORE_ANALYSTS = {
            "warren_buffett_agent",
            "peter_lynch_agent",
            "aswath_damodaran_agent",
            "momentum_agent",
            "mean_reversion_agent",
        }
        
        ticker_signals = {}
        for agent, signals in analyst_signals.items():
            # Only include core analysts (exclude system agents and advisory agents)
            if (agent in CORE_ANALYSTS
                and not agent.startswith("risk_management_agent")
                and not agent.startswith("portfolio_manager")
                and not agent.startswith("risk_budget_agent")
                and not agent.startswith("portfolio_allocator_agent")
                and ticker in signals):
                sig = signals[ticker].get("signal")
                conf = signals[ticker].get("confidence")
                if sig is not None and conf is not None:
                    ticker_signals[agent] = {"sig": sig, "conf": conf}
        signals_by_ticker[ticker] = ticker_signals

    state["data"]["current_prices"] = current_prices

    progress.update_status(agent_id, None, "Generating trading decisions")

    result = generate_trading_decision(
        tickers=tickers,
        signals_by_ticker=signals_by_ticker,
        current_prices=current_prices,
        max_shares=max_shares,
        portfolio=portfolio,
        agent_id=agent_id,
        state=state,
    )
    message = HumanMessage(
        content=json.dumps({ticker: decision.model_dump() for ticker, decision in result.decisions.items()}),
        name=agent_id,
    )

    if state["metadata"]["show_reasoning"]:
        show_agent_reasoning({ticker: decision.model_dump() for ticker, decision in result.decisions.items()},
                             "Portfolio Manager")

    # Store decisions in state for Risk Budget agent to read
    state["data"]["portfolio_decisions"] = {
        ticker: decision.model_dump() for ticker, decision in result.decisions.items()
    }

    progress.update_status(agent_id, None, "Done")

    return {
        "messages": state["messages"] + [message],
        "data": state["data"],
    }


def compute_allowed_actions(
        tickers: list[str],
        current_prices: dict[str, float],
        max_shares: dict[str, int],
        portfolio: dict[str, float],
) -> dict[str, dict[str, int]]:
    """Compute allowed actions and max quantities for each ticker deterministically."""
    allowed = {}
    cash = float(portfolio.get("cash", 0.0))
    positions = portfolio.get("positions", {}) or {}
    margin_requirement = float(portfolio.get("margin_requirement", 0.5))
    margin_used = float(portfolio.get("margin_used", 0.0))
    equity = float(portfolio.get("equity", cash))

    for ticker in tickers:
        price = float(current_prices.get(ticker, 0.0))
        pos = positions.get(
            ticker,
            {"long": 0, "long_cost_basis": 0.0, "short": 0, "short_cost_basis": 0.0},
        )
        long_shares = int(pos.get("long", 0) or 0)
        short_shares = int(pos.get("short", 0) or 0)
        max_qty = int(max_shares.get(ticker, 0) or 0)

        # Start with zeros
        actions = {"buy": 0, "sell": 0, "short": 0, "cover": 0, "hold": 0}

        # Long side
        if long_shares > 0:
            actions["sell"] = long_shares
        if cash > 0 and price > 0:
            max_buy_cash = int(cash // price)
            max_buy = max(0, min(max_qty, max_buy_cash))
            if max_buy > 0:
                actions["buy"] = max_buy

        # Short side
        if short_shares > 0:
            actions["cover"] = short_shares
        if price > 0 and max_qty > 0:
            if margin_requirement <= 0.0:
                # If margin requirement is zero or unset, only cap by max_qty
                max_short = max_qty
            else:
                available_margin = max(0.0, (equity / margin_requirement) - margin_used)
                max_short_margin = int(available_margin // price)
                max_short = max(0, min(max_qty, max_short_margin))
            if max_short > 0:
                actions["short"] = max_short

        # Hold always valid
        actions["hold"] = 0

        # Prune zero-capacity actions to reduce tokens, keep hold
        pruned = {"hold": 0}
        for k, v in actions.items():
            if k != "hold" and v > 0:
                pruned[k] = v

        allowed[ticker] = pruned

    return allowed


def _compact_signals(signals_by_ticker: dict[str, dict]) -> dict[str, dict]:
    """Keep only {agent: {sig, conf}} and drop empty agents."""
    out = {}
    for t, agents in signals_by_ticker.items():
        if not agents:
            out[t] = {}
            continue
        compact = {}
        for agent, payload in agents.items():
            sig = payload.get("sig") or payload.get("signal")
            conf = payload.get("conf") if "conf" in payload else payload.get("confidence")
            if sig is not None and conf is not None:
                compact[agent] = {"sig": sig, "conf": conf}
        out[t] = compact
    return out


def generate_trading_decision_rule_based(
        tickers: list[str],
        signals_by_ticker: dict[str, dict],
        current_prices: dict[str, float],
        max_shares: dict[str, int],
        portfolio: dict[str, float],
        prefilled_decisions: dict[str, PortfolioDecision],
        tickers_for_llm: list[str],
        allowed_actions_full: dict[str, dict[str, int]],
        state: AgentState,
) -> PortfolioManagerOutput:
    """
    Generate deterministic trading decisions based on signal aggregation with explicit weights.
    
    10-Agent Restructure: Uses only 5 core analysts with explicit weights:
    - Value Composite (warren_buffett): 30%
    - Growth Composite (peter_lynch): 25%
    - Valuation (aswath_damodaran): 20%
    - Momentum: 15% (regime-adjusted)
    - Mean Reversion: 10% (regime-adjusted)
    """
    decisions = dict(prefilled_decisions)
    
    # Explicit weights for core analysts (10-agent restructure)
    ANALYST_WEIGHTS = {
        "warren_buffett_agent": 0.30,
        "peter_lynch_agent": 0.25,
        "aswath_damodaran_agent": 0.20,
        "momentum_agent": 0.15,
        "mean_reversion_agent": 0.10,
    }
    
    for ticker in tickers_for_llm:
        signals = signals_by_ticker.get(ticker, {})
        allowed = allowed_actions_full.get(ticker, {"hold": 0})
        
        # Get market regime weights if available (advisory from Market Regime Analyst)
        market_regime_data = state["data"].get("market_regime", {})
        ticker_regime = market_regime_data.get(ticker, {})
        regime_weights = ticker_regime.get("weights", {})
        
        # Aggregate signals with explicit weights and regime-based adjustments
        bullish_weighted_sum = 0.0
        bearish_weighted_sum = 0.0
        neutral_weighted_sum = 0.0
        total_weight = 0.0
        weighted_confidence_sum = 0.0
        
        bullish_count = 0
        bearish_count = 0
        neutral_count = 0
        
        for agent, signal_data in signals.items():
            sig = signal_data.get("sig") or signal_data.get("signal")
            conf = signal_data.get("conf") if "conf" in signal_data else signal_data.get("confidence", 50)
            
            # Get base weight for this agent
            base_weight = ANALYST_WEIGHTS.get(agent, 0.0)
            if base_weight == 0.0:
                continue  # Skip agents not in core 5
            
            # Apply regime weights to Momentum and Mean Reversion
            final_weight = base_weight
            if agent == "momentum_agent" and "momentum" in regime_weights:
                final_weight = base_weight * regime_weights["momentum"]
            elif agent == "mean_reversion_agent" and "mean_reversion" in regime_weights:
                final_weight = base_weight * regime_weights["mean_reversion"]
            
            # Weighted signal contribution (convert signal to numeric: bullish=1, bearish=-1, neutral=0)
            if sig == "bullish":
                bullish_weighted_sum += final_weight
                bullish_count += 1
            elif sig == "bearish":
                bearish_weighted_sum += final_weight
                bearish_count += 1
            elif sig == "neutral":
                neutral_weighted_sum += final_weight
                neutral_count += 1
            
            # Weighted confidence contribution
            weighted_conf = conf * final_weight
            weighted_confidence_sum += weighted_conf
            total_weight += final_weight
        
        # Calculate weighted average confidence
        if total_weight > 0:
            avg_confidence = int(weighted_confidence_sum / total_weight)
        else:
            avg_confidence = 50
        
        # Build regime info string
        regime_info = ""
        if regime_weights:
            regime_info = f" (regime-adjusted: Momentum×{regime_weights.get('momentum', 1.0):.1f}, MR×{regime_weights.get('mean_reversion', 1.0):.1f})"
        
        # Rule-based decision logic using weighted signals
        # Decision based on weighted signal strength, not just counts
        net_weighted_signal = bullish_weighted_sum - bearish_weighted_sum
        
        if net_weighted_signal > 0.1 and bullish_count > 0:  # Weighted bullish
            # More bullish signals - try to buy
            if "buy" in allowed and allowed["buy"] > 0:
                qty = min(allowed["buy"], max_shares.get(ticker, 0))
                decisions[ticker] = PortfolioDecision(
                    action="buy",
                    quantity=qty,
                    confidence=int(avg_confidence),
                    reasoning=f"Bullish weighted signal (net: {net_weighted_signal:.2f}, {bullish_count}B/{bearish_count}S){regime_info}"
                )
            else:
                decisions[ticker] = PortfolioDecision(
                    action="hold",
                    quantity=0,
                    confidence=int(avg_confidence),
                    reasoning=f"Bullish but no buy capacity{regime_info}"
                )
        elif net_weighted_signal < -0.1 and bearish_count > 0:  # Weighted bearish
            # More bearish signals - try to sell or short
            if "sell" in allowed and allowed["sell"] > 0:
                qty = allowed["sell"]
                decisions[ticker] = PortfolioDecision(
                    action="sell",
                    quantity=qty,
                    confidence=int(avg_confidence),
                    reasoning=f"Bearish consensus ({bearish_count} bearish, {bullish_count} bullish){regime_info}"
                )
            elif "short" in allowed and allowed["short"] > 0:
                qty = min(allowed["short"], max_shares.get(ticker, 0))
                decisions[ticker] = PortfolioDecision(
                    action="short",
                    quantity=qty,
                    confidence=int(avg_confidence),
                    reasoning=f"Bearish consensus ({bearish_count} bearish, {bullish_count} bullish){regime_info}"
                )
            else:
                decisions[ticker] = PortfolioDecision(
                    action="hold",
                    quantity=0,
                    confidence=int(avg_confidence),
                    reasoning=f"Bearish weighted signal but no sell/short capacity (net: {net_weighted_signal:.2f}){regime_info}"
                )
        else:
            # Neutral or mixed signals - hold
            decisions[ticker] = PortfolioDecision(
                action="hold",
                quantity=0,
                confidence=int(avg_confidence) if signal_count > 0 else 50,
                reasoning=f"Mixed/neutral signals (net: {net_weighted_signal:.2f}, {bullish_count}B/{bearish_count}S/{neutral_count}N){regime_info}"
            )
    
    return PortfolioManagerOutput(decisions=decisions)


def generate_trading_decision(
        tickers: list[str],
        signals_by_ticker: dict[str, dict],
        current_prices: dict[str, float],
        max_shares: dict[str, int],
        portfolio: dict[str, float],
        agent_id: str,
        state: AgentState,
) -> PortfolioManagerOutput:
    """Get decisions from the LLM with deterministic constraints and a minimal prompt."""

    # Deterministic constraints
    allowed_actions_full = compute_allowed_actions(tickers, current_prices, max_shares, portfolio)

    # Pre-fill pure holds to avoid sending them to the LLM at all
    prefilled_decisions: dict[str, PortfolioDecision] = {}
    tickers_for_llm: list[str] = []
    for t in tickers:
        aa = allowed_actions_full.get(t, {"hold": 0})
        # If only 'hold' key exists, there is no trade possible
        if set(aa.keys()) == {"hold"}:
            prefilled_decisions[t] = PortfolioDecision(
                action="hold", quantity=0, confidence=100.0, reasoning="No valid trade available"
            )
        else:
            tickers_for_llm.append(t)

    if not tickers_for_llm:
        return PortfolioManagerOutput(decisions=prefilled_decisions)

    # Build compact payloads only for tickers sent to LLM
    compact_signals = _compact_signals({t: signals_by_ticker.get(t, {}) for t in tickers_for_llm})
    compact_allowed = {t: allowed_actions_full[t] for t in tickers_for_llm}

    # Minimal prompt template
    template = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You are a portfolio manager.\n"
                "Inputs per ticker: analyst signals and allowed actions with max qty (already validated).\n"
                "Pick one allowed action per ticker and a quantity ≤ the max. "
                "Keep reasoning very concise (max 100 chars). No cash or margin math. Return JSON only."
            ),
            (
                "human",
                "Signals:\n{signals}\n\n"
                "Allowed:\n{allowed}\n\n"
                "Format:\n"
                "{{\n"
                '  "decisions": {{\n'
                '    "TICKER": {{"action":"...","quantity":int,"confidence":int,"reasoning":"..."}}\n'
                "  }}\n"
                "}}"
            ),
        ]
    )

    prompt_data = {
        "signals": json.dumps(compact_signals, separators=(",", ":"), ensure_ascii=False),
        "allowed": json.dumps(compact_allowed, separators=(",", ":"), ensure_ascii=False),
    }
    prompt = template.invoke(prompt_data)

    # Default factory fills remaining tickers as hold if the LLM fails
    def create_default_portfolio_output():
        # start from prefilled
        decisions = dict(prefilled_decisions)
        for t in tickers_for_llm:
            decisions[t] = PortfolioDecision(
                action="hold", quantity=0, confidence=0.0, reasoning="Default decision: hold"
            )
        return PortfolioManagerOutput(decisions=decisions)

    # Rule-based factory for deterministic mode
    def create_rule_based_portfolio_output():
        return generate_trading_decision_rule_based(
            tickers=tickers,
            signals_by_ticker=signals_by_ticker,
            current_prices=current_prices,
            max_shares=max_shares,
            portfolio=portfolio,
            prefilled_decisions=prefilled_decisions,
            tickers_for_llm=tickers_for_llm,
            allowed_actions_full=allowed_actions_full,
            state=state,
        )

    llm_out = call_llm(
        prompt=prompt,
        pydantic_model=PortfolioManagerOutput,
        agent_name=agent_id,
        state=state,
        default_factory=create_default_portfolio_output,
        rule_based_factory=create_rule_based_portfolio_output,
    )

    # Merge prefilled holds with LLM results
    merged = dict(prefilled_decisions)
    merged.update(llm_out.decisions)
    return PortfolioManagerOutput(decisions=merged)
