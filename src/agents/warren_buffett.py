from src.graph.state import AgentState, show_agent_reasoning
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field
import json
import math
from typing_extensions import Literal
from src.tools.api import get_financial_metrics, get_market_cap, search_line_items
from src.utils.llm import call_llm
from src.utils.progress import progress
from src.utils.api_key import get_api_key_from_state


class WarrenBuffettSignal(BaseModel):
    signal: Literal["bullish", "bearish", "neutral"]
    confidence: int = Field(description="Confidence 0-100")
    reasoning: str = Field(description="Reasoning for the decision")


def warren_buffett_agent(state: AgentState, agent_id: str = "warren_buffett_agent"):
    """
    Value Composite Analyst - Combines multiple value investing principles:
    - Buffett: Quality businesses, moat, management, pricing power
    - Graham: Margin of safety, balance sheet strength, earnings stability
    - Munger: Quality focus, predictability, rational thinking
    - Burry: Deep value metrics, cash/debt ratios, FCF yield
    - Pabrai: Dhandho principles (low risk, high reward)
    
    Outputs ONE signal with confidence based on composite scoring.
    
    STATUS: INVALID FOR DIRECT TRADE EXECUTION
    - Falsified in 5-year deterministic backtest
    - Does not beat buy-and-hold after costs
    - Requires external financial data (not price-only)
    - Do not tune or repair - agent has no standalone edge
    """
    data = state["data"]
    end_date = data["end_date"]
    tickers = data["tickers"]
    api_key = get_api_key_from_state(state, "FINANCIAL_DATASETS_API_KEY")
    # Collect all analysis for LLM reasoning
    analysis_data = {}
    buffett_analysis = {}

    for ticker in tickers:
        progress.update_status(agent_id, ticker, "Fetching financial metrics")
        # Fetch required data - request more periods for better trend analysis
        metrics = get_financial_metrics(ticker, end_date, period="ttm", limit=10, api_key=api_key)

        progress.update_status(agent_id, ticker, "Gathering financial line items")
        financial_line_items = search_line_items(
            ticker,
            [
                "capital_expenditure",
                "depreciation_and_amortization",
                "net_income",
                "outstanding_shares",
                "total_assets",
                "total_liabilities",
                "shareholders_equity",
                "dividends_and_other_cash_distributions",
                "issuance_or_purchase_of_equity_shares",
                "gross_profit",
                "revenue",
                "free_cash_flow",
            ],
            end_date,
            period="ttm",
            limit=10,
            api_key=api_key,
        )

        progress.update_status(agent_id, ticker, "Getting market cap")
        # Get current market cap
        market_cap = get_market_cap(ticker, end_date, api_key=api_key)

        progress.update_status(agent_id, ticker, "Analyzing value composite factors")
        
        # VALUE COMPOSITE FACTOR ANALYSIS
        # Factor 1: Valuation Margin of Safety (Graham + Buffett)
        valuation_margin = analyze_valuation_margin_of_safety(financial_line_items, market_cap, metrics, ticker)
        
        # Factor 2: Balance Sheet Strength (Graham + Burry)
        balance_sheet_strength = analyze_balance_sheet_strength(financial_line_items, metrics)
        
        # Factor 3: Earnings Quality (Graham + Buffett)
        earnings_quality = analyze_earnings_quality(financial_line_items, metrics)
        
        # Factor 4: Conservative Growth (Buffett + Munger)
        conservative_growth = analyze_conservative_growth(financial_line_items)
        
        # Factor 5: Business Quality (Buffett + Munger)
        business_quality = analyze_business_quality(metrics, financial_line_items)
        
        # Composite scoring with explicit weights
        # Weights reflect importance: Valuation (30%), Quality (25%), Balance Sheet (20%), Earnings (15%), Growth (10%)
        COMPOSITE_WEIGHTS = {
            "valuation_margin": 0.30,
            "business_quality": 0.25,
            "balance_sheet_strength": 0.20,
            "earnings_quality": 0.15,
            "conservative_growth": 0.10,
        }
        
        # Calculate weighted composite score
        total_score = (
            valuation_margin["score"] * COMPOSITE_WEIGHTS["valuation_margin"] +
            business_quality["score"] * COMPOSITE_WEIGHTS["business_quality"] +
            balance_sheet_strength["score"] * COMPOSITE_WEIGHTS["balance_sheet_strength"] +
            earnings_quality["score"] * COMPOSITE_WEIGHTS["earnings_quality"] +
            conservative_growth["score"] * COMPOSITE_WEIGHTS["conservative_growth"]
        )
        
        # Max possible score (all factors at max)
        max_possible_score = (
            valuation_margin["max_score"] * COMPOSITE_WEIGHTS["valuation_margin"] +
            business_quality["max_score"] * COMPOSITE_WEIGHTS["business_quality"] +
            balance_sheet_strength["max_score"] * COMPOSITE_WEIGHTS["balance_sheet_strength"] +
            earnings_quality["max_score"] * COMPOSITE_WEIGHTS["earnings_quality"] +
            conservative_growth["max_score"] * COMPOSITE_WEIGHTS["conservative_growth"]
        )
        
        # Legacy analysis (for backward compatibility and LLM reasoning)
        fundamental_analysis = analyze_fundamentals(metrics)
        consistency_analysis = analyze_consistency(financial_line_items)
        moat_analysis = analyze_moat(metrics)
        pricing_power_analysis = analyze_pricing_power(financial_line_items, metrics)
        book_value_analysis = analyze_book_value_growth(financial_line_items)
        mgmt_analysis = analyze_management_quality(financial_line_items)
        intrinsic_value_analysis = calculate_intrinsic_value(financial_line_items)

        # Add margin of safety analysis if we have both intrinsic value and current price
        margin_of_safety = None
        intrinsic_value = intrinsic_value_analysis.get("intrinsic_value")
        if intrinsic_value and market_cap:
            margin_of_safety = (intrinsic_value - market_cap) / market_cap

        # Combine all analysis results for LLM evaluation
        analysis_data[ticker] = {
            "ticker": ticker,
            "score": total_score,
            "max_score": max_possible_score,
            # Composite factors (primary)
            "valuation_margin": valuation_margin,
            "balance_sheet_strength": balance_sheet_strength,
            "earnings_quality": earnings_quality,
            "conservative_growth": conservative_growth,
            "business_quality": business_quality,
            # Legacy analysis (for LLM context)
            "fundamental_analysis": fundamental_analysis,
            "consistency_analysis": consistency_analysis,
            "moat_analysis": moat_analysis,
            "pricing_power_analysis": pricing_power_analysis,
            "book_value_analysis": book_value_analysis,
            "management_analysis": mgmt_analysis,
            "intrinsic_value_analysis": intrinsic_value_analysis,
            "market_cap": market_cap,
            "margin_of_safety": margin_of_safety,
        }

        progress.update_status(agent_id, ticker, "Generating Warren Buffett analysis")
        buffett_output = generate_buffett_output(
            ticker=ticker,
            analysis_data=analysis_data[ticker],
            state=state,
            agent_id=agent_id,
        )

        # Store analysis in consistent format with other agents
        buffett_analysis[ticker] = {
            "signal": buffett_output.signal,
            "confidence": buffett_output.confidence,
            "reasoning": buffett_output.reasoning,
        }

        progress.update_status(agent_id, ticker, "Done", analysis=buffett_output.reasoning)

    # Create the message
    message = HumanMessage(content=json.dumps(buffett_analysis), name=agent_id)

    # Show reasoning if requested
    if state["metadata"]["show_reasoning"]:
        show_agent_reasoning(buffett_analysis, agent_id)

    # Add the signal to the analyst_signals list
    state["data"]["analyst_signals"][agent_id] = buffett_analysis

    progress.update_status(agent_id, None, "Done")

    return {"messages": [message], "data": state["data"]}


def analyze_fundamentals(metrics: list) -> dict[str, any]:
    """Analyze company fundamentals based on Buffett's criteria."""
    if not metrics:
        return {"score": 0, "details": "Insufficient fundamental data"}

    latest_metrics = metrics[0]

    score = 0
    reasoning = []

    # Check ROE (Return on Equity)
    if latest_metrics.return_on_equity and latest_metrics.return_on_equity > 0.15:  # 15% ROE threshold
        score += 2
        reasoning.append(f"Strong ROE of {latest_metrics.return_on_equity:.1%}")
    elif latest_metrics.return_on_equity:
        reasoning.append(f"Weak ROE of {latest_metrics.return_on_equity:.1%}")
    else:
        reasoning.append("ROE data not available")

    # Check Debt to Equity
    if latest_metrics.debt_to_equity and latest_metrics.debt_to_equity < 0.5:
        score += 2
        reasoning.append("Conservative debt levels")
    elif latest_metrics.debt_to_equity:
        reasoning.append(f"High debt to equity ratio of {latest_metrics.debt_to_equity:.1f}")
    else:
        reasoning.append("Debt to equity data not available")

    # Check Operating Margin
    if latest_metrics.operating_margin and latest_metrics.operating_margin > 0.15:
        score += 2
        reasoning.append("Strong operating margins")
    elif latest_metrics.operating_margin:
        reasoning.append(f"Weak operating margin of {latest_metrics.operating_margin:.1%}")
    else:
        reasoning.append("Operating margin data not available")

    # Check Current Ratio
    if latest_metrics.current_ratio and latest_metrics.current_ratio > 1.5:
        score += 1
        reasoning.append("Good liquidity position")
    elif latest_metrics.current_ratio:
        reasoning.append(f"Weak liquidity with current ratio of {latest_metrics.current_ratio:.1f}")
    else:
        reasoning.append("Current ratio data not available")

    return {"score": score, "details": "; ".join(reasoning), "metrics": latest_metrics.model_dump()}


def analyze_consistency(financial_line_items: list) -> dict[str, any]:
    """Analyze earnings consistency and growth."""
    if len(financial_line_items) < 4:  # Need at least 4 periods for trend analysis
        return {"score": 0, "details": "Insufficient historical data"}

    score = 0
    reasoning = []

    # Check earnings growth trend
    earnings_values = [item.net_income for item in financial_line_items if item.net_income]
    if len(earnings_values) >= 4:
        # Simple check: is each period's earnings bigger than the next?
        earnings_growth = all(earnings_values[i] > earnings_values[i + 1] for i in range(len(earnings_values) - 1))

        if earnings_growth:
            score += 3
            reasoning.append("Consistent earnings growth over past periods")
        else:
            reasoning.append("Inconsistent earnings growth pattern")

        # Calculate total growth rate from oldest to latest
        if len(earnings_values) >= 2 and earnings_values[-1] != 0:
            growth_rate = (earnings_values[0] - earnings_values[-1]) / abs(earnings_values[-1])
            reasoning.append(f"Total earnings growth of {growth_rate:.1%} over past {len(earnings_values)} periods")
    else:
        reasoning.append("Insufficient earnings data for trend analysis")

    return {
        "score": score,
        "details": "; ".join(reasoning),
    }


def analyze_moat(metrics: list) -> dict[str, any]:
    """
    Evaluate whether the company likely has a durable competitive advantage (moat).
    Enhanced to include multiple moat indicators that Buffett actually looks for:
    1. Consistent high returns on capital
    2. Pricing power (stable/growing margins)
    3. Scale advantages (improving metrics with size)
    4. Brand strength (inferred from margins and consistency)
    5. Switching costs (inferred from customer retention)
    """
    if not metrics or len(metrics) < 5:  # Need more data for proper moat analysis
        return {"score": 0, "max_score": 5, "details": "Insufficient data for comprehensive moat analysis"}

    reasoning = []
    moat_score = 0
    max_score = 5

    # 1. Return on Capital Consistency (Buffett's favorite moat indicator)
    historical_roes = [m.return_on_equity for m in metrics if m.return_on_equity is not None]
    historical_roics = [m.return_on_invested_capital for m in metrics if
                        hasattr(m, 'return_on_invested_capital') and m.return_on_invested_capital is not None]

    if len(historical_roes) >= 5:
        # Check for consistently high ROE (>15% for most periods)
        high_roe_periods = sum(1 for roe in historical_roes if roe > 0.15)
        roe_consistency = high_roe_periods / len(historical_roes)

        if roe_consistency >= 0.8:  # 80%+ of periods with ROE > 15%
            moat_score += 2
            avg_roe = sum(historical_roes) / len(historical_roes)
            reasoning.append(
                f"Excellent ROE consistency: {high_roe_periods}/{len(historical_roes)} periods >15% (avg: {avg_roe:.1%}) - indicates durable competitive advantage")
        elif roe_consistency >= 0.6:
            moat_score += 1
            reasoning.append(f"Good ROE performance: {high_roe_periods}/{len(historical_roes)} periods >15%")
        else:
            reasoning.append(f"Inconsistent ROE: only {high_roe_periods}/{len(historical_roes)} periods >15%")
    else:
        reasoning.append("Insufficient ROE history for moat analysis")

    # 2. Operating Margin Stability (Pricing Power Indicator)
    historical_margins = [m.operating_margin for m in metrics if m.operating_margin is not None]
    if len(historical_margins) >= 5:
        # Check for stable or improving margins (sign of pricing power)
        avg_margin = sum(historical_margins) / len(historical_margins)
        recent_margins = historical_margins[:3]  # Last 3 periods
        older_margins = historical_margins[-3:]  # First 3 periods

        recent_avg = sum(recent_margins) / len(recent_margins)
        older_avg = sum(older_margins) / len(older_margins)

        if avg_margin > 0.2 and recent_avg >= older_avg:  # 20%+ margins and stable/improving
            moat_score += 1
            reasoning.append(f"Strong and stable operating margins (avg: {avg_margin:.1%}) indicate pricing power moat")
        elif avg_margin > 0.15:  # At least decent margins
            reasoning.append(f"Decent operating margins (avg: {avg_margin:.1%}) suggest some competitive advantage")
        else:
            reasoning.append(f"Low operating margins (avg: {avg_margin:.1%}) suggest limited pricing power")

    # 3. Asset Efficiency and Scale Advantages
    if len(metrics) >= 5:
        # Check asset turnover trends (revenue efficiency)
        asset_turnovers = []
        for m in metrics:
            if hasattr(m, 'asset_turnover') and m.asset_turnover is not None:
                asset_turnovers.append(m.asset_turnover)

        if len(asset_turnovers) >= 3:
            if any(turnover > 1.0 for turnover in asset_turnovers):  # Efficient asset use
                moat_score += 1
                reasoning.append("Efficient asset utilization suggests operational moat")

    # 4. Competitive Position Strength (inferred from trend stability)
    if len(historical_roes) >= 5 and len(historical_margins) >= 5:
        # Calculate coefficient of variation (stability measure)
        roe_avg = sum(historical_roes) / len(historical_roes)
        roe_variance = sum((roe - roe_avg) ** 2 for roe in historical_roes) / len(historical_roes)
        roe_stability = 1 - (roe_variance ** 0.5) / roe_avg if roe_avg > 0 else 0

        margin_avg = sum(historical_margins) / len(historical_margins)
        margin_variance = sum((margin - margin_avg) ** 2 for margin in historical_margins) / len(historical_margins)
        margin_stability = 1 - (margin_variance ** 0.5) / margin_avg if margin_avg > 0 else 0

        overall_stability = (roe_stability + margin_stability) / 2

        if overall_stability > 0.7:  # High stability indicates strong competitive position
            moat_score += 1
            reasoning.append(f"High performance stability ({overall_stability:.1%}) suggests strong competitive moat")

    # Cap the score at max_score
    moat_score = min(moat_score, max_score)

    return {
        "score": moat_score,
        "max_score": max_score,
        "details": "; ".join(reasoning) if reasoning else "Limited moat analysis available",
    }


def analyze_management_quality(financial_line_items: list) -> dict[str, any]:
    """
    Checks for share dilution or consistent buybacks, and some dividend track record.
    A simplified approach:
      - if there's net share repurchase or stable share count, it suggests management
        might be shareholder-friendly.
      - if there's a big new issuance, it might be a negative sign (dilution).
    """
    if not financial_line_items:
        return {"score": 0, "max_score": 2, "details": "Insufficient data for management analysis"}

    reasoning = []
    mgmt_score = 0

    latest = financial_line_items[0]
    if hasattr(latest,
               "issuance_or_purchase_of_equity_shares") and latest.issuance_or_purchase_of_equity_shares and latest.issuance_or_purchase_of_equity_shares < 0:
        # Negative means the company spent money on buybacks
        mgmt_score += 1
        reasoning.append("Company has been repurchasing shares (shareholder-friendly)")

    if hasattr(latest,
               "issuance_or_purchase_of_equity_shares") and latest.issuance_or_purchase_of_equity_shares and latest.issuance_or_purchase_of_equity_shares > 0:
        # Positive issuance means new shares => possible dilution
        reasoning.append("Recent common stock issuance (potential dilution)")
    else:
        reasoning.append("No significant new stock issuance detected")

    # Check for any dividends
    if hasattr(latest,
               "dividends_and_other_cash_distributions") and latest.dividends_and_other_cash_distributions and latest.dividends_and_other_cash_distributions < 0:
        mgmt_score += 1
        reasoning.append("Company has a track record of paying dividends")
    else:
        reasoning.append("No or minimal dividends paid")

    return {
        "score": mgmt_score,
        "max_score": 2,
        "details": "; ".join(reasoning),
    }


def calculate_owner_earnings(financial_line_items: list) -> dict[str, any]:
    """
    Calculate owner earnings (Buffett's preferred measure of true earnings power).
    Enhanced methodology: Net Income + Depreciation/Amortization - Maintenance CapEx - Working Capital Changes
    Uses multi-period analysis for better maintenance capex estimation.
    """
    if not financial_line_items or len(financial_line_items) < 2:
        return {"owner_earnings": None, "details": ["Insufficient data for owner earnings calculation"]}

    latest = financial_line_items[0]
    details = []

    # Core components
    net_income = latest.net_income
    depreciation = latest.depreciation_and_amortization
    capex = latest.capital_expenditure

    if not all([net_income is not None, depreciation is not None, capex is not None]):
        missing = []
        if net_income is None: missing.append("net income")
        if depreciation is None: missing.append("depreciation")
        if capex is None: missing.append("capital expenditure")
        return {"owner_earnings": None, "details": [f"Missing components: {', '.join(missing)}"]}

    # Enhanced maintenance capex estimation using historical analysis
    maintenance_capex = estimate_maintenance_capex(financial_line_items)

    # Working capital change analysis (if data available)
    working_capital_change = 0
    if len(financial_line_items) >= 2:
        try:
            current_assets_current = getattr(latest, 'current_assets', None)
            current_liab_current = getattr(latest, 'current_liabilities', None)

            previous = financial_line_items[1]
            current_assets_previous = getattr(previous, 'current_assets', None)
            current_liab_previous = getattr(previous, 'current_liabilities', None)

            if all([current_assets_current, current_liab_current, current_assets_previous, current_liab_previous]):
                wc_current = current_assets_current - current_liab_current
                wc_previous = current_assets_previous - current_liab_previous
                working_capital_change = wc_current - wc_previous
                details.append(f"Working capital change: ${working_capital_change:,.0f}")
        except:
            pass  # Skip working capital adjustment if data unavailable

    # Calculate owner earnings
    owner_earnings = net_income + depreciation - maintenance_capex - working_capital_change

    # Sanity checks
    if owner_earnings < net_income * 0.3:  # Owner earnings shouldn't be less than 30% of net income typically
        details.append("Warning: Owner earnings significantly below net income - high capex intensity")

    if maintenance_capex > depreciation * 2:  # Maintenance capex shouldn't typically exceed 2x depreciation
        details.append("Warning: Estimated maintenance capex seems high relative to depreciation")

    details.extend([
        f"Net income: ${net_income:,.0f}",
        f"Depreciation: ${depreciation:,.0f}",
        f"Estimated maintenance capex: ${maintenance_capex:,.0f}",
        f"Owner earnings: ${owner_earnings:,.0f}"
    ])

    return {
        "owner_earnings": owner_earnings,
        "components": {
            "net_income": net_income,
            "depreciation": depreciation,
            "maintenance_capex": maintenance_capex,
            "working_capital_change": working_capital_change,
            "total_capex": abs(capex) if capex else 0
        },
        "details": details,
    }


def estimate_maintenance_capex(financial_line_items: list) -> float:
    """
    Estimate maintenance capital expenditure using multiple approaches.
    Buffett considers this crucial for understanding true owner earnings.
    """
    if not financial_line_items:
        return 0

    # Approach 1: Historical average as % of revenue
    capex_ratios = []
    depreciation_values = []

    for item in financial_line_items[:5]:  # Last 5 periods
        if hasattr(item, 'capital_expenditure') and hasattr(item, 'revenue'):
            if item.capital_expenditure and item.revenue and item.revenue > 0:
                capex_ratio = abs(item.capital_expenditure) / item.revenue
                capex_ratios.append(capex_ratio)

        if hasattr(item, 'depreciation_and_amortization') and item.depreciation_and_amortization:
            depreciation_values.append(item.depreciation_and_amortization)

    # Approach 2: Percentage of depreciation (typically 80-120% for maintenance)
    latest_depreciation = financial_line_items[0].depreciation_and_amortization if financial_line_items[
        0].depreciation_and_amortization else 0

    # Approach 3: Industry-specific heuristics
    latest_capex = abs(financial_line_items[0].capital_expenditure) if financial_line_items[
        0].capital_expenditure else 0

    # Conservative estimate: Use the higher of:
    # 1. 85% of total capex (assuming 15% is growth capex)
    # 2. 100% of depreciation (replacement of worn-out assets)
    # 3. Historical average if stable

    method_1 = latest_capex * 0.85  # 85% of total capex
    method_2 = latest_depreciation  # 100% of depreciation

    # If we have historical data, use average capex ratio
    if len(capex_ratios) >= 3:
        avg_capex_ratio = sum(capex_ratios) / len(capex_ratios)
        latest_revenue = financial_line_items[0].revenue if hasattr(financial_line_items[0], 'revenue') and \
                                                            financial_line_items[0].revenue else 0
        method_3 = avg_capex_ratio * latest_revenue if latest_revenue else 0

        # Use the median of the three approaches for conservatism
        estimates = sorted([method_1, method_2, method_3])
        return estimates[1]  # Median
    else:
        # Use the higher of method 1 and 2
        return max(method_1, method_2)


def calculate_intrinsic_value(financial_line_items: list) -> dict[str, any]:
    """
    Calculate intrinsic value using enhanced DCF with owner earnings.
    Uses more sophisticated assumptions and conservative approach like Buffett.
    """
    if not financial_line_items or len(financial_line_items) < 3:
        return {"intrinsic_value": None, "details": ["Insufficient data for reliable valuation"]}

    # Calculate owner earnings with better methodology
    earnings_data = calculate_owner_earnings(financial_line_items)
    if not earnings_data["owner_earnings"]:
        return {"intrinsic_value": None, "details": earnings_data["details"]}

    owner_earnings = earnings_data["owner_earnings"]
    latest_financial_line_items = financial_line_items[0]
    shares_outstanding = latest_financial_line_items.outstanding_shares

    if not shares_outstanding or shares_outstanding <= 0:
        return {"intrinsic_value": None, "details": ["Missing or invalid shares outstanding data"]}

    # Enhanced DCF with more realistic assumptions
    details = []

    # Estimate growth rate based on historical performance (more conservative)
    historical_earnings = []
    for item in financial_line_items[:5]:  # Last 5 years
        if hasattr(item, 'net_income') and item.net_income:
            historical_earnings.append(item.net_income)

    # Calculate historical growth rate
    if len(historical_earnings) >= 3:
        oldest_earnings = historical_earnings[-1]
        latest_earnings = historical_earnings[0]
        years = len(historical_earnings) - 1

        if oldest_earnings > 0:
            historical_growth = ((latest_earnings / oldest_earnings) ** (1 / years)) - 1
            # Conservative adjustment - cap growth and apply haircut
            historical_growth = max(-0.05, min(historical_growth, 0.15))  # Cap between -5% and 15%
            conservative_growth = historical_growth * 0.7  # Apply 30% haircut for conservatism
        else:
            conservative_growth = 0.03  # Default 3% if negative base
    else:
        conservative_growth = 0.03  # Default conservative growth

    # Buffett's conservative assumptions
    stage1_growth = min(conservative_growth, 0.08)  # Stage 1: cap at 8%
    stage2_growth = min(conservative_growth * 0.5, 0.04)  # Stage 2: half of stage 1, cap at 4%
    terminal_growth = 0.025  # Long-term GDP growth rate

    # Risk-adjusted discount rate based on business quality
    base_discount_rate = 0.09  # Base 9%

    # Adjust based on analysis scores (if available in calling context)
    # For now, use conservative 10%
    discount_rate = 0.10

    # Three-stage DCF model
    stage1_years = 5  # High growth phase
    stage2_years = 5  # Transition phase

    present_value = 0
    details.append(
        f"Using three-stage DCF: Stage 1 ({stage1_growth:.1%}, {stage1_years}y), Stage 2 ({stage2_growth:.1%}, {stage2_years}y), Terminal ({terminal_growth:.1%})")

    # Stage 1: Higher growth
    stage1_pv = 0
    for year in range(1, stage1_years + 1):
        future_earnings = owner_earnings * (1 + stage1_growth) ** year
        pv = future_earnings / (1 + discount_rate) ** year
        stage1_pv += pv

    # Stage 2: Transition growth
    stage2_pv = 0
    stage1_final_earnings = owner_earnings * (1 + stage1_growth) ** stage1_years
    for year in range(1, stage2_years + 1):
        future_earnings = stage1_final_earnings * (1 + stage2_growth) ** year
        pv = future_earnings / (1 + discount_rate) ** (stage1_years + year)
        stage2_pv += pv

    # Terminal value using Gordon Growth Model
    final_earnings = stage1_final_earnings * (1 + stage2_growth) ** stage2_years
    terminal_earnings = final_earnings * (1 + terminal_growth)
    terminal_value = terminal_earnings / (discount_rate - terminal_growth)
    terminal_pv = terminal_value / (1 + discount_rate) ** (stage1_years + stage2_years)

    # Total intrinsic value
    intrinsic_value = stage1_pv + stage2_pv + terminal_pv

    # Apply additional margin of safety (Buffett's conservatism)
    conservative_intrinsic_value = intrinsic_value * 0.85  # 15% additional haircut

    details.extend([
        f"Stage 1 PV: ${stage1_pv:,.0f}",
        f"Stage 2 PV: ${stage2_pv:,.0f}",
        f"Terminal PV: ${terminal_pv:,.0f}",
        f"Total IV: ${intrinsic_value:,.0f}",
        f"Conservative IV (15% haircut): ${conservative_intrinsic_value:,.0f}",
        f"Owner earnings: ${owner_earnings:,.0f}",
        f"Discount rate: {discount_rate:.1%}"
    ])

    return {
        "intrinsic_value": conservative_intrinsic_value,
        "raw_intrinsic_value": intrinsic_value,
        "owner_earnings": owner_earnings,
        "assumptions": {
            "stage1_growth": stage1_growth,
            "stage2_growth": stage2_growth,
            "terminal_growth": terminal_growth,
            "discount_rate": discount_rate,
            "stage1_years": stage1_years,
            "stage2_years": stage2_years,
            "historical_growth": conservative_growth if 'conservative_growth' in locals() else None,
        },
        "details": details,
    }


def analyze_book_value_growth(financial_line_items: list) -> dict[str, any]:
    """Analyze book value per share growth - a key Buffett metric."""
    if len(financial_line_items) < 3:
        return {"score": 0, "details": "Insufficient data for book value analysis"}

    # Extract book values per share
    book_values = [
        item.shareholders_equity / item.outstanding_shares
        for item in financial_line_items
        if hasattr(item, 'shareholders_equity') and hasattr(item, 'outstanding_shares')
        and item.shareholders_equity and item.outstanding_shares
    ]

    if len(book_values) < 3:
        return {"score": 0, "details": "Insufficient book value data for growth analysis"}

    score = 0
    reasoning = []

    # Analyze growth consistency
    growth_periods = sum(1 for i in range(len(book_values) - 1) if book_values[i] > book_values[i + 1])
    growth_rate = growth_periods / (len(book_values) - 1)

    # Score based on consistency
    if growth_rate >= 0.8:
        score += 3
        reasoning.append("Consistent book value per share growth (Buffett's favorite metric)")
    elif growth_rate >= 0.6:
        score += 2
        reasoning.append("Good book value per share growth pattern")
    elif growth_rate >= 0.4:
        score += 1
        reasoning.append("Moderate book value per share growth")
    else:
        reasoning.append("Inconsistent book value per share growth")

    # Calculate and score CAGR
    cagr_score, cagr_reason = _calculate_book_value_cagr(book_values)
    score += cagr_score
    reasoning.append(cagr_reason)

    return {"score": score, "details": "; ".join(reasoning)}


def _calculate_book_value_cagr(book_values: list) -> tuple[int, str]:
    """Helper function to safely calculate book value CAGR and return score + reasoning."""
    if len(book_values) < 2:
        return 0, "Insufficient data for CAGR calculation"

    oldest_bv, latest_bv = book_values[-1], book_values[0]
    years = len(book_values) - 1

    # Handle different scenarios
    if oldest_bv > 0 and latest_bv > 0:
        cagr = ((latest_bv / oldest_bv) ** (1 / years)) - 1
        if cagr > 0.15:
            return 2, f"Excellent book value CAGR: {cagr:.1%}"
        elif cagr > 0.1:
            return 1, f"Good book value CAGR: {cagr:.1%}"
        else:
            return 0, f"Book value CAGR: {cagr:.1%}"
    elif oldest_bv < 0 < latest_bv:
        return 3, "Excellent: Company improved from negative to positive book value"
    elif oldest_bv > 0 > latest_bv:
        return 0, "Warning: Company declined from positive to negative book value"
    else:
        return 0, "Unable to calculate meaningful book value CAGR due to negative values"


def analyze_pricing_power(financial_line_items: list, metrics: list) -> dict[str, any]:
    """
    Analyze pricing power - Buffett's key indicator of a business moat.
    Looks at ability to raise prices without losing customers (margin expansion during inflation).
    """
    if not financial_line_items or not metrics:
        return {"score": 0, "details": "Insufficient data for pricing power analysis"}

    score = 0
    reasoning = []

    # Check gross margin trends (ability to maintain/expand margins)
    gross_margins = []
    for item in financial_line_items:
        if hasattr(item, 'gross_margin') and item.gross_margin is not None:
            gross_margins.append(item.gross_margin)

    if len(gross_margins) >= 3:
        # Check margin stability/improvement
        recent_avg = sum(gross_margins[:2]) / 2 if len(gross_margins) >= 2 else gross_margins[0]
        older_avg = sum(gross_margins[-2:]) / 2 if len(gross_margins) >= 2 else gross_margins[-1]

        if recent_avg > older_avg + 0.02:  # 2%+ improvement
            score += 3
            reasoning.append("Expanding gross margins indicate strong pricing power")
        elif recent_avg > older_avg:
            score += 2
            reasoning.append("Improving gross margins suggest good pricing power")
        elif abs(recent_avg - older_avg) < 0.01:  # Stable within 1%
            score += 1
            reasoning.append("Stable gross margins during economic uncertainty")
        else:
            reasoning.append("Declining gross margins may indicate pricing pressure")

    # Check if company has been able to maintain high margins consistently
    if gross_margins:
        avg_margin = sum(gross_margins) / len(gross_margins)
        if avg_margin > 0.5:  # 50%+ gross margins
            score += 2
            reasoning.append(f"Consistently high gross margins ({avg_margin:.1%}) indicate strong pricing power")
        elif avg_margin > 0.3:  # 30%+ gross margins
            score += 1
            reasoning.append(f"Good gross margins ({avg_margin:.1%}) suggest decent pricing power")

    return {
        "score": score,
        "details": "; ".join(reasoning) if reasoning else "Limited pricing power analysis available"
    }


def analyze_valuation_margin_of_safety(
    financial_line_items: list,
    market_cap: float | None,
    metrics: list,
    ticker: str = "",
) -> dict[str, any]:
    """
    Factor 1: Valuation Margin of Safety (30% weight)
    Combines Graham (Graham Number, net-net) + Buffett (intrinsic value discount).
    """
    if not financial_line_items or not market_cap or market_cap <= 0:
        return {"score": 0, "max_score": 10, "details": "Insufficient data for valuation margin"}
    
    score = 0
    details = []
    latest = financial_line_items[0]
    
    # Graham Number: sqrt(22.5 * EPS * BVPS)
    eps = latest.earnings_per_share if hasattr(latest, 'earnings_per_share') else None
    bvps = (latest.shareholders_equity / latest.outstanding_shares) if (hasattr(latest, 'shareholders_equity') and hasattr(latest, 'outstanding_shares') and latest.outstanding_shares > 0) else None
    
    graham_number = None
    if eps and eps > 0 and bvps and bvps > 0:
        graham_number = math.sqrt(22.5 * eps * bvps)
        price_per_share = market_cap / latest.outstanding_shares
        if price_per_share > 0:
            graham_margin = (graham_number - price_per_share) / price_per_share
            if graham_margin > 0.5:
                score += 4
                details.append(f"Graham Number: {graham_margin:.0%} margin (excellent)")
            elif graham_margin > 0.2:
                score += 2
                details.append(f"Graham Number: {graham_margin:.0%} margin (good)")
            elif graham_margin > 0:
                score += 1
                details.append(f"Graham Number: {graham_margin:.0%} margin (moderate)")
            else:
                details.append(f"Graham Number: Overvalued by {abs(graham_margin):.0%}")
    
    # Net-Net Current Asset Value (Graham)
    current_assets = latest.current_assets if hasattr(latest, 'current_assets') else 0
    total_liabilities = latest.total_liabilities if hasattr(latest, 'total_liabilities') else 0
    if current_assets > 0 and latest.outstanding_shares > 0:
        ncav = current_assets - total_liabilities
        ncav_per_share = ncav / latest.outstanding_shares
        price_per_share = market_cap / latest.outstanding_shares
        if ncav > market_cap:
            score += 3
            details.append("Net-Net: NCAV > Market Cap (deep value)")
        elif ncav_per_share >= price_per_share * 0.67:
            score += 2
            details.append("Net-Net: NCAV >= 67% of price (moderate discount)")
    
    # Intrinsic Value Discount (Buffett)
    intrinsic_value_analysis = calculate_intrinsic_value(financial_line_items)
    intrinsic_value = intrinsic_value_analysis.get("intrinsic_value")
    if intrinsic_value and market_cap > 0:
        iv_discount = (intrinsic_value - market_cap) / market_cap
        if iv_discount > 0.3:
            score += 3
            details.append(f"Intrinsic Value: {iv_discount:.0%} discount (excellent)")
        elif iv_discount > 0.1:
            score += 2
            details.append(f"Intrinsic Value: {iv_discount:.0%} discount (good)")
        elif iv_discount > 0:
            score += 1
            details.append(f"Intrinsic Value: {iv_discount:.0%} discount (moderate)")
        else:
            details.append(f"Intrinsic Value: Overvalued by {abs(iv_discount):.0%}")
    
    return {"score": min(score, 10), "max_score": 10, "details": "; ".join(details) if details else "Limited valuation data"}


def analyze_balance_sheet_strength(
    financial_line_items: list,
    metrics: list,
) -> dict[str, any]:
    """
    Factor 2: Balance Sheet Strength (20% weight)
    Combines Graham (current ratio, debt ratio) + Burry (cash/debt, FCF yield).
    """
    if not financial_line_items:
        return {"score": 0, "max_score": 10, "details": "Insufficient data for balance sheet analysis"}
    
    score = 0
    details = []
    latest = financial_line_items[0]
    latest_metrics = metrics[0] if metrics else None
    
    # Current Ratio (Graham: >= 2.0 is strong)
    current_assets = latest.current_assets if hasattr(latest, 'current_assets') else 0
    current_liabilities = latest.current_liabilities if hasattr(latest, 'current_liabilities') else 0
    if current_liabilities > 0:
        current_ratio = current_assets / current_liabilities
        if current_ratio >= 2.0:
            score += 3
            details.append(f"Current ratio: {current_ratio:.2f} (Graham strong)")
        elif current_ratio >= 1.5:
            score += 2
            details.append(f"Current ratio: {current_ratio:.2f} (moderate)")
        elif current_ratio >= 1.0:
            score += 1
            details.append(f"Current ratio: {current_ratio:.2f} (adequate)")
        else:
            details.append(f"Current ratio: {current_ratio:.2f} (weak)")
    
    # Debt-to-Equity (Graham: < 0.5 conservative, Burry: < 0.3 very strong)
    if latest_metrics and latest_metrics.debt_to_equity is not None:
        de_ratio = latest_metrics.debt_to_equity
        if de_ratio < 0.3:
            score += 3
            details.append(f"Debt/Equity: {de_ratio:.2f} (very conservative)")
        elif de_ratio < 0.5:
            score += 2
            details.append(f"Debt/Equity: {de_ratio:.2f} (Graham conservative)")
        elif de_ratio < 1.0:
            score += 1
            details.append(f"Debt/Equity: {de_ratio:.2f} (moderate)")
        else:
            details.append(f"Debt/Equity: {de_ratio:.2f} (high)")
    
    # Cash/Debt Ratio (Burry: > 1.5 is strong)
    cash = latest.cash_and_equivalents if hasattr(latest, 'cash_and_equivalents') else 0
    debt = latest.total_debt if hasattr(latest, 'total_debt') else 0
    if debt > 0:
        cash_debt_ratio = cash / debt
        if cash_debt_ratio > 1.5:
            score += 2
            details.append(f"Cash/Debt: {cash_debt_ratio:.2f} (Burry strong)")
        elif cash_debt_ratio > 1.0:
            score += 1
            details.append(f"Cash/Debt: {cash_debt_ratio:.2f} (adequate)")
        else:
            details.append(f"Cash/Debt: {cash_debt_ratio:.2f} (low)")
    elif debt == 0 and cash > 0:
        score += 2
        details.append("No debt, cash positive (excellent)")
    
    # FCF Yield (Burry: > 10% is attractive)
    # Note: market_cap not available in this function scope
    # FCF yield is a valuation metric, not balance sheet strength
    # (already covered in valuation_margin_of_safety factor via intrinsic value)
    
    return {"score": min(score, 10), "max_score": 10, "details": "; ".join(details) if details else "Limited balance sheet data"}


def analyze_earnings_quality(
    financial_line_items: list,
    metrics: list,
) -> dict[str, any]:
    """
    Factor 3: Earnings Quality (15% weight)
    Combines Graham (earnings stability) + Buffett (consistency, FCF conversion).
    """
    if not financial_line_items or len(financial_line_items) < 3:
        return {"score": 0, "max_score": 10, "details": "Insufficient data for earnings quality"}
    
    score = 0
    details = []
    
    # Earnings Stability (Graham: 5+ years positive)
    eps_values = [item.earnings_per_share for item in financial_line_items if hasattr(item, 'earnings_per_share') and item.earnings_per_share is not None]
    if len(eps_values) >= 3:
        positive_years = sum(1 for e in eps_values if e > 0)
        if positive_years == len(eps_values):
            score += 3
            details.append(f"EPS: {positive_years}/{len(eps_values)} positive (Graham stable)")
        elif positive_years >= len(eps_values) * 0.8:
            score += 2
            details.append(f"EPS: {positive_years}/{len(eps_values)} positive (mostly stable)")
        else:
            details.append(f"EPS: {positive_years}/{len(eps_values)} positive (unstable)")
    
    # Earnings Consistency (Buffett: growing trend)
    if len(eps_values) >= 3:
        if eps_values[0] > eps_values[-1]:
            score += 2
            details.append("EPS: Growing trend (Buffett consistent)")
        elif eps_values[0] == eps_values[-1]:
            score += 1
            details.append("EPS: Stable (no growth)")
        else:
            details.append("EPS: Declining trend")
    
    # FCF Conversion (Buffett: FCF should be substantial portion of earnings)
    net_incomes = [item.net_income for item in financial_line_items if hasattr(item, 'net_income') and item.net_income is not None]
    fcf_values = [item.free_cash_flow for item in financial_line_items if hasattr(item, 'free_cash_flow') and item.free_cash_flow is not None]
    if len(net_incomes) >= 2 and len(fcf_values) >= 2:
        latest_ni = net_incomes[0]
        latest_fcf = fcf_values[0]
        if latest_ni > 0:
            fcf_conversion = latest_fcf / latest_ni
            if fcf_conversion > 0.8:
                score += 3
                details.append(f"FCF Conversion: {fcf_conversion:.0%} (excellent quality)")
            elif fcf_conversion > 0.5:
                score += 2
                details.append(f"FCF Conversion: {fcf_conversion:.0%} (good quality)")
            elif fcf_conversion > 0.3:
                score += 1
                details.append(f"FCF Conversion: {fcf_conversion:.0%} (moderate)")
            else:
                details.append(f"FCF Conversion: {fcf_conversion:.0%} (poor quality)")
    
    # Earnings Growth Consistency (Pabrai: consistent growth is low risk)
    if len(eps_values) >= 4:
        growth_rates = []
        for i in range(len(eps_values) - 1):
            if eps_values[i+1] > 0:
                growth = (eps_values[i] - eps_values[i+1]) / abs(eps_values[i+1])
                growth_rates.append(growth)
        if len(growth_rates) >= 2:
            avg_growth = sum(growth_rates) / len(growth_rates)
            if avg_growth > 0.1 and all(g > 0 for g in growth_rates):
                score += 2
                details.append(f"EPS Growth: {avg_growth:.0%} avg, all positive (Pabrai low risk)")
    
    return {"score": min(score, 10), "max_score": 10, "details": "; ".join(details) if details else "Limited earnings data"}


def analyze_conservative_growth(
    financial_line_items: list,
) -> dict[str, any]:
    """
    Factor 4: Conservative Growth Assumptions (10% weight)
    Uses historical growth with haircuts (Buffett/Munger conservatism).
    """
    if not financial_line_items or len(financial_line_items) < 3:
        return {"score": 5, "max_score": 10, "details": "Insufficient data, neutral score"}
    
    score = 5  # Start neutral
    details = []
    
    # Calculate historical growth
    revenues = [item.revenue for item in financial_line_items if hasattr(item, 'revenue') and item.revenue is not None]
    earnings = [item.net_income for item in financial_line_items if hasattr(item, 'net_income') and item.net_income is not None]
    
    if len(revenues) >= 3:
        oldest_rev = revenues[-1]
        latest_rev = revenues[0]
        if oldest_rev > 0:
            years = len(revenues) - 1
            historical_growth = ((latest_rev / oldest_rev) ** (1 / years)) - 1
            # Apply 30% haircut for conservatism (Buffett/Munger)
            conservative_growth = max(0, historical_growth * 0.7)
            
            if conservative_growth > 0.15:
                score += 3
                details.append(f"Conservative growth: {conservative_growth:.1%} (strong)")
            elif conservative_growth > 0.08:
                score += 2
                details.append(f"Conservative growth: {conservative_growth:.1%} (moderate)")
            elif conservative_growth > 0.03:
                score += 1
                details.append(f"Conservative growth: {conservative_growth:.1%} (slow)")
            else:
                score -= 1
                details.append(f"Conservative growth: {conservative_growth:.1%} (stagnant)")
    
    if len(earnings) >= 3:
        oldest_earn = earnings[-1]
        latest_earn = earnings[0]
        if oldest_earn > 0:
            years = len(earnings) - 1
            earnings_growth = ((latest_earn / oldest_earn) ** (1 / years)) - 1
            conservative_earn_growth = max(0, earnings_growth * 0.7)
            
            if conservative_earn_growth > 0.15:
                score += 2
                details.append(f"Conservative earnings growth: {conservative_earn_growth:.1%}")
            elif conservative_earn_growth < 0:
                score -= 2
                details.append(f"Negative earnings growth: {conservative_earn_growth:.1%}")
    
    return {"score": max(0, min(score, 10)), "max_score": 10, "details": "; ".join(details) if details else "Limited growth data"}


def analyze_business_quality(
    metrics: list,
    financial_line_items: list,
) -> dict[str, any]:
    """
    Factor 5: Business Quality (25% weight)
    Combines Buffett (ROE, moat, pricing power) + Munger (quality, predictability).
    """
    if not metrics:
        return {"score": 0, "max_score": 10, "details": "Insufficient data for quality analysis"}
    
    score = 0
    details = []
    latest_metrics = metrics[0]
    
    # ROE (Buffett/Munger: > 15% is quality)
    if latest_metrics.return_on_equity is not None:
        roe = latest_metrics.return_on_equity
        if roe > 0.20:
            score += 3
            details.append(f"ROE: {roe:.1%} (excellent quality)")
        elif roe > 0.15:
            score += 2
            details.append(f"ROE: {roe:.1%} (good quality)")
        elif roe > 0.10:
            score += 1
            details.append(f"ROE: {roe:.1%} (moderate)")
        else:
            details.append(f"ROE: {roe:.1%} (weak)")
    
    # ROE Consistency (Munger: predictability)
    if len(metrics) >= 5:
        roes = [m.return_on_equity for m in metrics if m.return_on_equity is not None]
        if len(roes) >= 5:
            high_roe_periods = sum(1 for r in roes if r > 0.15)
            consistency = high_roe_periods / len(roes)
            if consistency >= 0.8:
                score += 2
                details.append(f"ROE Consistency: {consistency:.0%} periods >15% (Munger predictable)")
            elif consistency >= 0.6:
                score += 1
                details.append(f"ROE Consistency: {consistency:.0%} periods >15%")
    
    # Operating Margin (Buffett: pricing power indicator)
    if latest_metrics.operating_margin is not None:
        op_margin = latest_metrics.operating_margin
        if op_margin > 0.20:
            score += 2
            details.append(f"Operating Margin: {op_margin:.1%} (strong)")
        elif op_margin > 0.15:
            score += 1
            details.append(f"Operating Margin: {op_margin:.1%} (good)")
        else:
            details.append(f"Operating Margin: {op_margin:.1%} (weak)")
    
    # Moat Indicators (Buffett: competitive advantage)
    moat_analysis = analyze_moat(metrics)
    moat_score = moat_analysis.get("score", 0)
    moat_max = moat_analysis.get("max_score", 5)
    if moat_max > 0:
        moat_ratio = moat_score / moat_max
        if moat_ratio > 0.8:
            score += 3
            details.append(f"Moat: {moat_ratio:.0%} (strong competitive advantage)")
        elif moat_ratio > 0.6:
            score += 2
            details.append(f"Moat: {moat_ratio:.0%} (moderate advantage)")
        elif moat_ratio > 0.4:
            score += 1
            details.append(f"Moat: {moat_ratio:.0%} (some advantage)")
    
    return {"score": min(score, 10), "max_score": 10, "details": "; ".join(details) if details else "Limited quality data"}


def generate_buffett_output_rule_based(
        ticker: str,
        analysis_data: dict[str, any],
) -> WarrenBuffettSignal:
    """
    Generate deterministic Value Composite signal based on composite factor scores.
    
    Composite factors (weighted):
    - Valuation Margin of Safety (30%): Graham Number, net-net, intrinsic value discount
    - Business Quality (25%): ROE, moat, pricing power, consistency
    - Balance Sheet Strength (20%): Current ratio, debt-to-equity, cash/debt
    - Earnings Quality (15%): Stability, FCF yield, consistency
    - Conservative Growth (10%): Historical growth with haircuts
    """
    score = analysis_data.get("score", 0)
    max_score = analysis_data.get("max_score", 1)
    margin_of_safety = analysis_data.get("margin_of_safety")
    
    # Get composite factor scores for detailed reasoning
    valuation_margin = analysis_data.get("valuation_margin", {})
    balance_sheet = analysis_data.get("balance_sheet_strength", {})
    earnings = analysis_data.get("earnings_quality", {})
    growth = analysis_data.get("conservative_growth", {})
    quality = analysis_data.get("business_quality", {})
    
    # Calculate score ratio
    score_ratio = score / max_score if max_score > 0 else 0.0
    
    # Calculate confidence based on score ratio and factor consistency
    base_confidence = int(50 + (score_ratio - 0.5) * 60)  # 20-80 base range
    base_confidence = max(20, min(85, base_confidence))  # Clamp to 20-85
    
    # Adjust confidence based on factor consistency
    factor_scores = [
        valuation_margin.get("score", 0) / max(1, valuation_margin.get("max_score", 1)),
        balance_sheet.get("score", 0) / max(1, balance_sheet.get("max_score", 1)),
        earnings.get("score", 0) / max(1, earnings.get("max_score", 1)),
        growth.get("score", 0) / max(1, growth.get("max_score", 1)),
        quality.get("score", 0) / max(1, quality.get("max_score", 1)),
    ]
    
    # If factors are consistent (all high or all low), increase confidence
    factor_std = (sum((f - score_ratio)**2 for f in factor_scores) / len(factor_scores))**0.5
    consistency_boost = max(0, 10 - int(factor_std * 20))  # Up to +10 points for consistency
    final_confidence = min(90, base_confidence + consistency_boost)
    
    # Rule-based decision logic
    if margin_of_safety is not None:
        # Strong bullish: High composite score + significant margin of safety
        if score_ratio > 0.7 and margin_of_safety > 0.2:
            return WarrenBuffettSignal(
                signal="bullish",
                confidence=final_confidence,
                reasoning=f"Value Composite: Strong (score {score_ratio:.0%}, margin {margin_of_safety:.0%}). Factors: Val {valuation_margin.get('score', 0):.1f}, Quality {quality.get('score', 0):.1f}, BS {balance_sheet.get('score', 0):.1f}, Earnings {earnings.get('score', 0):.1f}, Growth {growth.get('score', 0):.1f}"
            )
        # Moderate bullish: Good score + positive margin of safety
        elif score_ratio > 0.6 and margin_of_safety > 0:
            return WarrenBuffettSignal(
                signal="bullish",
                confidence=final_confidence,
                reasoning=f"Value Composite: Good (score {score_ratio:.0%}, margin {margin_of_safety:.0%}). Factors: Val {valuation_margin.get('score', 0):.1f}, Quality {quality.get('score', 0):.1f}, BS {balance_sheet.get('score', 0):.1f}"
            )
        # Bearish: Poor score or negative margin of safety
        elif score_ratio < 0.4 or margin_of_safety < -0.2:
            return WarrenBuffettSignal(
                signal="bearish",
                confidence=final_confidence,
                reasoning=f"Value Composite: Weak (score {score_ratio:.0%}, margin {margin_of_safety:.0%}). Poor valuation/quality/balance sheet"
            )
        # Neutral: Mixed signals
        else:
            return WarrenBuffettSignal(
                signal="neutral",
                confidence=final_confidence,
                reasoning=f"Value Composite: Mixed (score {score_ratio:.0%}, margin {margin_of_safety:.0%}). Inconsistent factors"
            )
    else:
        # No margin of safety data - use score only
        if score_ratio > 0.7:
            return WarrenBuffettSignal(
                signal="bullish",
                confidence=final_confidence,
                reasoning=f"Value Composite: Strong fundamentals (score {score_ratio:.0%}), valuation unknown. Quality {quality.get('score', 0):.1f}, BS {balance_sheet.get('score', 0):.1f}"
            )
        elif score_ratio < 0.4:
            return WarrenBuffettSignal(
                signal="bearish",
                confidence=final_confidence,
                reasoning=f"Value Composite: Weak fundamentals (score {score_ratio:.0%}). Poor quality/balance sheet"
            )
        else:
            return WarrenBuffettSignal(
                signal="neutral",
                confidence=final_confidence,
                reasoning=f"Value Composite: Moderate (score {score_ratio:.0%}), insufficient valuation data"
            )


def generate_buffett_output(
        ticker: str,
        analysis_data: dict[str, any],
        state: AgentState,
        agent_id: str = "warren_buffett_agent",
) -> WarrenBuffettSignal:
    """Get investment decision from LLM with a compact prompt."""

    # --- Build compact facts here ---
    facts = {
        "score": analysis_data.get("score"),
        "max_score": analysis_data.get("max_score"),
        "fundamentals": analysis_data.get("fundamental_analysis", {}).get("details"),
        "consistency": analysis_data.get("consistency_analysis", {}).get("details"),
        "moat": analysis_data.get("moat_analysis", {}).get("details"),
        "pricing_power": analysis_data.get("pricing_power_analysis", {}).get("details"),
        "book_value": analysis_data.get("book_value_analysis", {}).get("details"),
        "management": analysis_data.get("management_analysis", {}).get("details"),
        "intrinsic_value": analysis_data.get("intrinsic_value_analysis", {}).get("intrinsic_value"),
        "market_cap": analysis_data.get("market_cap"),
        "margin_of_safety": analysis_data.get("margin_of_safety"),
    }

    template = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You are Warren Buffett. Decide bullish, bearish, or neutral using only the provided facts.\n"
                "\n"
                "Checklist for decision:\n"
                "- Circle of competence\n"
                "- Competitive moat\n"
                "- Management quality\n"
                "- Financial strength\n"
                "- Valuation vs intrinsic value\n"
                "- Long-term prospects\n"
                "\n"
                "Signal rules:\n"
                "- Bullish: strong business AND margin_of_safety > 0.\n"
                "- Bearish: poor business OR clearly overvalued.\n"
                "- Neutral: good business but margin_of_safety <= 0, or mixed evidence.\n"
                "\n"
                "Confidence scale:\n"
                "- 90-100%: Exceptional business within my circle, trading at attractive price\n"
                "- 70-89%: Good business with decent moat, fair valuation\n"
                "- 50-69%: Mixed signals, would need more information or better price\n"
                "- 30-49%: Outside my expertise or concerning fundamentals\n"
                "- 10-29%: Poor business or significantly overvalued\n"
                "\n"
                "Keep reasoning under 120 characters. Do not invent data. Return JSON only."
            ),
            (
                "human",
                "Ticker: {ticker}\n"
                "Facts:\n{facts}\n\n"
                "Return exactly:\n"
                "{{\n"
                '  "signal": "bullish" | "bearish" | "neutral",\n'
                '  "confidence": int,\n'
                '  "reasoning": "short justification"\n'
                "}}"
            ),
        ]
    )

    prompt = template.invoke({
        "facts": json.dumps(facts, separators=(",", ":"), ensure_ascii=False),
        "ticker": ticker,
    })

    # Default fallback uses int confidence to match schema and avoid parse retries
    def create_default_warren_buffett_signal():
        return WarrenBuffettSignal(signal="neutral", confidence=50, reasoning="Insufficient data")

    # Rule-based factory for deterministic mode
    def create_rule_based_warren_buffett_signal():
        return generate_buffett_output_rule_based(ticker, analysis_data)

    return call_llm(
        prompt=prompt,
        pydantic_model=WarrenBuffettSignal,
        agent_name=agent_id,
        state=state,
        default_factory=create_default_warren_buffett_signal,
        rule_based_factory=create_rule_based_warren_buffett_signal,
    )
