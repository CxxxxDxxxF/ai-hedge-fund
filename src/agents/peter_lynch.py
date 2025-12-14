from src.graph.state import AgentState, show_agent_reasoning
from src.tools.api import (
    get_market_cap,
    search_line_items,
    get_insider_trades,
    get_company_news,
    get_financial_metrics,
    get_prices,
    prices_to_df,
)
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage
from pydantic import BaseModel
import json
from typing_extensions import Literal
from src.utils.progress import progress
from src.utils.llm import call_llm
from src.utils.api_key import get_api_key_from_state
from src.utils.deterministic_guard import is_deterministic_mode, require_deterministic_data


class PeterLynchSignal(BaseModel):
    """
    Container for the Peter Lynch-style output signal.
    """
    signal: Literal["bullish", "bearish", "neutral"]
    confidence: float
    reasoning: str


def peter_lynch_agent(state: AgentState, agent_id: str = "peter_lynch_agent"):
    """
    Growth Composite Analyst - Combines multiple growth investing principles:
    - Lynch: GARP (PEG), revenue/EPS growth, understandable business, manageable debt
    - Wood: Disruption focus (R&D intensity, accelerating growth, operating leverage)
    - Fisher: Scuttlebutt research (management quality, competitive position, growth consistency)
    - Growth Analyst: Growth trends, margin expansion, financial health
    
    Outputs ONE signal with confidence based on composite scoring.
    """

    data = state["data"]
    end_date = data["end_date"]
    tickers = data["tickers"]
    api_key = get_api_key_from_state(state, "FINANCIAL_DATASETS_API_KEY")
    analysis_data = {}
    lynch_analysis = {}

    for ticker in tickers:
        # Check if deterministic mode - use price-based fallback
        # Note: API-level guard in _make_api_request also blocks external calls,
        # but we can still use price data for technical growth signals
        if is_deterministic_mode():
            # Use price-based growth proxy when external data unavailable
            progress.update_status(agent_id, ticker, "Using price-based growth proxy (deterministic mode)")
            
            # Get price data for growth momentum analysis
            prices = get_prices(
                ticker=ticker,
                start_date=data.get("start_date", end_date),
                end_date=end_date,
                api_key=api_key,
            )
            
            if prices:
                prices_df = prices_to_df(prices)
                if len(prices_df) >= 60:  # Need enough data for growth trend
                    # Calculate price-based growth proxy
                    # Use 60-day momentum as proxy for business growth
                    current_price = float(prices_df["close"].iloc[-1])
                    price_60_days_ago = float(prices_df["close"].iloc[-60])
                    price_growth = (current_price - price_60_days_ago) / price_60_days_ago if price_60_days_ago > 0 else 0.0
                    
                    # Calculate volatility-adjusted growth (lower vol = higher confidence)
                    returns = prices_df["close"].pct_change().dropna()
                    volatility = returns.std() * (252 ** 0.5)  # Annualized
                    
                    # Map price growth to signal
                    if price_growth > 0.15 and volatility < 0.40:  # Strong growth, low volatility
                        signal = "bullish"
                        confidence = min(75, 50 + int(price_growth * 200))
                        reasoning = f"Price-based growth proxy: {price_growth:.1%} over 60 days, low volatility ({volatility:.0%})"
                    elif price_growth > 0.05 and volatility < 0.50:
                        signal = "bullish"
                        confidence = min(65, 50 + int(price_growth * 150))
                        reasoning = f"Price-based growth proxy: {price_growth:.1%} over 60 days, moderate volatility"
                    elif price_growth < -0.15 or volatility > 0.60:  # Poor growth or high volatility
                        signal = "bearish"
                        confidence = min(70, 50 + int(abs(price_growth) * 150))
                        reasoning = f"Price-based growth proxy: {price_growth:.1%} over 60 days, high volatility ({volatility:.0%})"
                    else:
                        signal = "neutral"
                        confidence = 50
                        reasoning = f"Price-based growth proxy: {price_growth:.1%} over 60 days, mixed signals"
                    
                    lynch_analysis[ticker] = {
                        "signal": signal,
                        "confidence": float(confidence),
                        "reasoning": reasoning,
                    }
                    progress.update_status(agent_id, ticker, f"Done (price-based: {signal})")
                    continue
            
            # If no price data or insufficient data, return neutral
            lynch_analysis[ticker] = {
                "signal": "neutral",
                "confidence": 50.0,
                "reasoning": "Insufficient price data for growth proxy in deterministic mode",
            }
            progress.update_status(agent_id, ticker, "Done (deterministic mode - insufficient data)")
            continue
        
        progress.update_status(agent_id, ticker, "Gathering financial line items")
        # Relevant line items for Peter Lynch's approach
        financial_line_items = search_line_items(
            ticker,
            [
                "revenue",
                "earnings_per_share",
                "net_income",
                "operating_income",
                "gross_margin",
                "operating_margin",
                "free_cash_flow",
                "capital_expenditure",
                "cash_and_equivalents",
                "total_debt",
                "shareholders_equity",
                "outstanding_shares",
            ],
            end_date,
            period="annual",
            limit=5,
            api_key=api_key,
        )

        progress.update_status(agent_id, ticker, "Getting market cap")
        market_cap = get_market_cap(ticker, end_date, api_key=api_key)
        
        progress.update_status(agent_id, ticker, "Fetching financial metrics")
        metrics = get_financial_metrics(ticker, end_date, period="annual", limit=5, api_key=api_key)

        # Skip insider trades and news in deterministic mode (already handled above, but defensive)
        allowed, fallback = require_deterministic_data(agent_id, "insider_trades", [])
        if allowed:
            progress.update_status(agent_id, ticker, "Fetching insider trades")
            insider_trades = get_insider_trades(ticker, end_date, limit=50, api_key=api_key)
        else:
            insider_trades = fallback

        allowed, fallback = require_deterministic_data(agent_id, "company_news", [])
        if allowed:
            progress.update_status(agent_id, ticker, "Fetching company news")
            company_news = get_company_news(ticker, end_date, limit=50, api_key=api_key)
        else:
            company_news = fallback

        # GROWTH COMPOSITE FACTOR ANALYSIS
        progress.update_status(agent_id, ticker, "Analyzing growth composite factors")
        
        # Factor 1: Revenue Growth (Lynch + Wood + Growth Analyst)
        revenue_growth = analyze_revenue_growth_composite(financial_line_items)
        
        # Factor 2: Earnings Growth (Lynch + Fisher + Growth Analyst)
        earnings_growth = analyze_earnings_growth_composite(financial_line_items)
        
        # Factor 3: PEG-Style Valuation Sanity Check (Lynch)
        valuation_sanity = analyze_valuation_sanity_check(financial_line_items, market_cap)
        
        # Factor 4: Business Simplicity Proxy (Lynch + Fisher)
        business_simplicity = analyze_business_simplicity(financial_line_items, metrics)
        
        # Composite scoring with explicit weights
        # Weights: Revenue Growth (30%), Earnings Growth (25%), Valuation (25%), Simplicity (20%)
        COMPOSITE_WEIGHTS = {
            "revenue_growth": 0.30,
            "earnings_growth": 0.25,
            "valuation_sanity": 0.25,
            "business_simplicity": 0.20,
        }
        
        # Calculate weighted composite score
        total_score = (
            revenue_growth["score"] * COMPOSITE_WEIGHTS["revenue_growth"] +
            earnings_growth["score"] * COMPOSITE_WEIGHTS["earnings_growth"] +
            valuation_sanity["score"] * COMPOSITE_WEIGHTS["valuation_sanity"] +
            business_simplicity["score"] * COMPOSITE_WEIGHTS["business_simplicity"]
        )
        
        # Max possible score (all factors at max)
        max_possible_score = (
            revenue_growth["max_score"] * COMPOSITE_WEIGHTS["revenue_growth"] +
            earnings_growth["max_score"] * COMPOSITE_WEIGHTS["earnings_growth"] +
            valuation_sanity["max_score"] * COMPOSITE_WEIGHTS["valuation_sanity"] +
            business_simplicity["max_score"] * COMPOSITE_WEIGHTS["business_simplicity"]
        )
        
        # Map final score to signal
        score_ratio = total_score / max_possible_score if max_possible_score > 0 else 0.5
        if score_ratio >= 0.7:
            signal = "bullish"
        elif score_ratio <= 0.4:
            signal = "bearish"
        else:
            signal = "neutral"
        
        # Legacy analysis (for backward compatibility and LLM reasoning)
        growth_analysis = analyze_lynch_growth(financial_line_items)
        fundamentals_analysis = analyze_lynch_fundamentals(financial_line_items)
        valuation_analysis = analyze_lynch_valuation(financial_line_items, market_cap)
        sentiment_analysis = analyze_sentiment(company_news)
        insider_activity = analyze_insider_activity(insider_trades)

        analysis_data[ticker] = {
            "signal": signal,
            "score": total_score,
            "max_score": max_possible_score,
            # Composite factors (primary)
            "revenue_growth": revenue_growth,
            "earnings_growth": earnings_growth,
            "valuation_sanity": valuation_sanity,
            "business_simplicity": business_simplicity,
            # Legacy analysis (for LLM context)
            "growth_analysis": growth_analysis,
            "valuation_analysis": valuation_analysis,
            "fundamentals_analysis": fundamentals_analysis,
            "sentiment_analysis": sentiment_analysis,
            "insider_activity": insider_activity,
        }

        progress.update_status(agent_id, ticker, "Generating Peter Lynch analysis")
        lynch_output = generate_lynch_output(
            ticker=ticker,
            analysis_data=analysis_data[ticker],
            state=state,
            agent_id=agent_id,
        )

        lynch_analysis[ticker] = {
            "signal": lynch_output.signal,
            "confidence": lynch_output.confidence,
            "reasoning": lynch_output.reasoning,
        }

        progress.update_status(agent_id, ticker, "Done", analysis=lynch_output.reasoning)

    # Wrap up results
    message = HumanMessage(content=json.dumps(lynch_analysis), name=agent_id)

    if state["metadata"].get("show_reasoning"):
        show_agent_reasoning(lynch_analysis, "Peter Lynch Agent")

    # Save signals to state
    state["data"]["analyst_signals"][agent_id] = lynch_analysis

    progress.update_status(agent_id, None, "Done")

    return {"messages": [message], "data": state["data"]}


def analyze_lynch_growth(financial_line_items: list) -> dict:
    """
    Evaluate growth based on revenue and EPS trends:
      - Consistent revenue growth
      - Consistent EPS growth
    Peter Lynch liked companies with steady, understandable growth,
    often searching for potential 'ten-baggers' with a long runway.
    """
    if not financial_line_items or len(financial_line_items) < 2:
        return {"score": 0, "details": "Insufficient financial data for growth analysis"}

    details = []
    raw_score = 0  # We'll sum up points, then scale to 0–10 eventually

    # 1) Revenue Growth
    revenues = [fi.revenue for fi in financial_line_items if fi.revenue is not None]
    if len(revenues) >= 2:
        latest_rev = revenues[0]
        older_rev = revenues[-1]
        if older_rev > 0:
            rev_growth = (latest_rev - older_rev) / abs(older_rev)
            if rev_growth > 0.25:
                raw_score += 3
                details.append(f"Strong revenue growth: {rev_growth:.1%}")
            elif rev_growth > 0.10:
                raw_score += 2
                details.append(f"Moderate revenue growth: {rev_growth:.1%}")
            elif rev_growth > 0.02:
                raw_score += 1
                details.append(f"Slight revenue growth: {rev_growth:.1%}")
            else:
                details.append(f"Flat or negative revenue growth: {rev_growth:.1%}")
        else:
            details.append("Older revenue is zero/negative; can't compute revenue growth.")
    else:
        details.append("Not enough revenue data to assess growth.")

    # 2) EPS Growth
    eps_values = [fi.earnings_per_share for fi in financial_line_items if fi.earnings_per_share is not None]
    if len(eps_values) >= 2:
        latest_eps = eps_values[0]
        older_eps = eps_values[-1]
        if abs(older_eps) > 1e-9:
            eps_growth = (latest_eps - older_eps) / abs(older_eps)
            if eps_growth > 0.25:
                raw_score += 3
                details.append(f"Strong EPS growth: {eps_growth:.1%}")
            elif eps_growth > 0.10:
                raw_score += 2
                details.append(f"Moderate EPS growth: {eps_growth:.1%}")
            elif eps_growth > 0.02:
                raw_score += 1
                details.append(f"Slight EPS growth: {eps_growth:.1%}")
            else:
                details.append(f"Minimal or negative EPS growth: {eps_growth:.1%}")
        else:
            details.append("Older EPS is near zero; skipping EPS growth calculation.")
    else:
        details.append("Not enough EPS data for growth calculation.")

    # raw_score can be up to 6 => scale to 0–10
    final_score = min(10, (raw_score / 6) * 10)
    return {"score": final_score, "details": "; ".join(details)}


def analyze_lynch_fundamentals(financial_line_items: list) -> dict:
    """
    Evaluate basic fundamentals:
      - Debt/Equity
      - Operating margin (or gross margin)
      - Positive Free Cash Flow
    Lynch avoided heavily indebted or complicated businesses.
    """
    if not financial_line_items:
        return {"score": 0, "details": "Insufficient fundamentals data"}

    details = []
    raw_score = 0  # We'll accumulate up to 6 points, then scale to 0–10

    # 1) Debt-to-Equity
    debt_values = [fi.total_debt for fi in financial_line_items if fi.total_debt is not None]
    eq_values = [fi.shareholders_equity for fi in financial_line_items if fi.shareholders_equity is not None]
    if debt_values and eq_values and len(debt_values) == len(eq_values) and len(debt_values) > 0:
        recent_debt = debt_values[0]
        recent_equity = eq_values[0] if eq_values[0] else 1e-9
        de_ratio = recent_debt / recent_equity
        if de_ratio < 0.5:
            raw_score += 2
            details.append(f"Low debt-to-equity: {de_ratio:.2f}")
        elif de_ratio < 1.0:
            raw_score += 1
            details.append(f"Moderate debt-to-equity: {de_ratio:.2f}")
        else:
            details.append(f"High debt-to-equity: {de_ratio:.2f}")
    else:
        details.append("No consistent debt/equity data available.")

    # 2) Operating Margin
    om_values = [fi.operating_margin for fi in financial_line_items if fi.operating_margin is not None]
    if om_values:
        om_recent = om_values[0]
        if om_recent > 0.20:
            raw_score += 2
            details.append(f"Strong operating margin: {om_recent:.1%}")
        elif om_recent > 0.10:
            raw_score += 1
            details.append(f"Moderate operating margin: {om_recent:.1%}")
        else:
            details.append(f"Low operating margin: {om_recent:.1%}")
    else:
        details.append("No operating margin data available.")

    # 3) Positive Free Cash Flow
    fcf_values = [fi.free_cash_flow for fi in financial_line_items if fi.free_cash_flow is not None]
    if fcf_values and fcf_values[0] is not None:
        if fcf_values[0] > 0:
            raw_score += 2
            details.append(f"Positive free cash flow: {fcf_values[0]:,.0f}")
        else:
            details.append(f"Recent FCF is negative: {fcf_values[0]:,.0f}")
    else:
        details.append("No free cash flow data available.")

    # raw_score up to 6 => scale to 0–10
    final_score = min(10, (raw_score / 6) * 10)
    return {"score": final_score, "details": "; ".join(details)}


def analyze_lynch_valuation(financial_line_items: list, market_cap: float | None) -> dict:
    """
    Peter Lynch's approach to 'Growth at a Reasonable Price' (GARP):
      - Emphasize the PEG ratio: (P/E) / Growth Rate
      - Also consider a basic P/E if PEG is unavailable
    A PEG < 1 is very attractive; 1-2 is fair; >2 is expensive.
    """
    if not financial_line_items or market_cap is None:
        return {"score": 0, "details": "Insufficient data for valuation"}

    details = []
    raw_score = 0

    # Gather data for P/E
    net_incomes = [fi.net_income for fi in financial_line_items if fi.net_income is not None]
    eps_values = [fi.earnings_per_share for fi in financial_line_items if fi.earnings_per_share is not None]

    # Approximate P/E via (market cap / net income) if net income is positive
    pe_ratio = None
    if net_incomes and net_incomes[0] and net_incomes[0] > 0:
        pe_ratio = market_cap / net_incomes[0]
        details.append(f"Estimated P/E: {pe_ratio:.2f}")
    else:
        details.append("No positive net income => can't compute approximate P/E")

    # If we have at least 2 EPS data points, let's estimate growth
    eps_growth_rate = None
    if len(eps_values) >= 2:
        latest_eps = eps_values[0]
        older_eps = eps_values[-1]
        if older_eps > 0:
            # Calculate annualized growth rate (CAGR) for PEG ratio
            num_years = len(eps_values) - 1
            if latest_eps > 0:
                # CAGR formula: (ending_value/beginning_value)^(1/years) - 1
                eps_growth_rate = (latest_eps / older_eps) ** (1 / num_years) - 1
            else:
                # If latest EPS is negative, use simple average growth
                eps_growth_rate = (latest_eps - older_eps) / (older_eps * num_years)
            details.append(f"Annualized EPS growth rate: {eps_growth_rate:.1%}")
        else:
            details.append("Cannot compute EPS growth rate (older EPS <= 0)")
    else:
        details.append("Not enough EPS data to compute growth rate")

    # Compute PEG if possible
    peg_ratio = None
    if pe_ratio and eps_growth_rate and eps_growth_rate > 0:
        # PEG ratio formula: P/E divided by growth rate (as percentage)
        # Since eps_growth_rate is stored as decimal (0.25 for 25%),
        # we multiply by 100 to convert to percentage for the PEG calculation
        # Example: P/E=20, growth=0.25 (25%) => PEG = 20/25 = 0.8
        peg_ratio = pe_ratio / (eps_growth_rate * 100)
        details.append(f"PEG ratio: {peg_ratio:.2f}")

    # Scoring logic:
    #   - P/E < 15 => +2, < 25 => +1
    #   - PEG < 1 => +3, < 2 => +2, < 3 => +1
    if pe_ratio is not None:
        if pe_ratio < 15:
            raw_score += 2
        elif pe_ratio < 25:
            raw_score += 1

    if peg_ratio is not None:
        if peg_ratio < 1:
            raw_score += 3
        elif peg_ratio < 2:
            raw_score += 2
        elif peg_ratio < 3:
            raw_score += 1

    final_score = min(10, (raw_score / 5) * 10)
    return {"score": final_score, "details": "; ".join(details)}


def analyze_sentiment(news_items: list) -> dict:
    """
    Basic news sentiment check. Negative headlines weigh on the final score.
    """
    if not news_items:
        return {"score": 5, "details": "No news data; default to neutral sentiment"}

    negative_keywords = ["lawsuit", "fraud", "negative", "downturn", "decline", "investigation", "recall"]
    negative_count = 0
    for news in news_items:
        title_lower = (news.title or "").lower()
        if any(word in title_lower for word in negative_keywords):
            negative_count += 1

    details = []
    if negative_count > len(news_items) * 0.3:
        # More than 30% negative => somewhat bearish => 3/10
        score = 3
        details.append(f"High proportion of negative headlines: {negative_count}/{len(news_items)}")
    elif negative_count > 0:
        # Some negativity => 6/10
        score = 6
        details.append(f"Some negative headlines: {negative_count}/{len(news_items)}")
    else:
        # Mostly positive => 8/10
        score = 8
        details.append("Mostly positive or neutral headlines")

    return {"score": score, "details": "; ".join(details)}


def analyze_insider_activity(insider_trades: list) -> dict:
    """
    Simple insider-trade analysis:
      - If there's heavy insider buying, it's a positive sign.
      - If there's mostly selling, it's a negative sign.
      - Otherwise, neutral.
    """
    # Default 5 (neutral)
    score = 5
    details = []

    if not insider_trades:
        details.append("No insider trades data; defaulting to neutral")
        return {"score": score, "details": "; ".join(details)}

    buys, sells = 0, 0
    for trade in insider_trades:
        if trade.transaction_shares is not None:
            if trade.transaction_shares > 0:
                buys += 1
            elif trade.transaction_shares < 0:
                sells += 1

    total = buys + sells
    if total == 0:
        details.append("No significant buy/sell transactions found; neutral stance")
        return {"score": score, "details": "; ".join(details)}

    buy_ratio = buys / total
    if buy_ratio > 0.7:
        # Heavy buying => +3 => total 8
        score = 8
        details.append(f"Heavy insider buying: {buys} buys vs. {sells} sells")
    elif buy_ratio > 0.4:
        # Some buying => +1 => total 6
        score = 6
        details.append(f"Moderate insider buying: {buys} buys vs. {sells} sells")
    else:
        # Mostly selling => -1 => total 4
        score = 4
        details.append(f"Mostly insider selling: {buys} buys vs. {sells} sells")

    return {"score": score, "details": "; ".join(details)}


def analyze_revenue_growth_composite(financial_line_items: list) -> dict:
    """
    Factor 1: Revenue Growth (30% weight)
    Combines Lynch (consistent growth) + Wood (accelerating growth) + Growth Analyst (CAGR trends).
    """
    if not financial_line_items or len(financial_line_items) < 2:
        return {"score": 0, "max_score": 10, "details": "Insufficient data for revenue growth"}
    
    score = 0
    details = []
    revenues = [fi.revenue for fi in financial_line_items if fi.revenue is not None]
    
    if len(revenues) >= 2:
        # Calculate CAGR (Lynch + Growth Analyst)
        latest_rev = revenues[0]
        oldest_rev = revenues[-1]
        years = len(revenues) - 1
        if oldest_rev > 0 and latest_rev > 0:
            cagr = ((latest_rev / oldest_rev) ** (1 / years)) - 1
            if cagr > 0.25:
                score += 4
                details.append(f"Revenue CAGR: {cagr:.1%} (exceptional)")
            elif cagr > 0.15:
                score += 3
                details.append(f"Revenue CAGR: {cagr:.1%} (strong)")
            elif cagr > 0.08:
                score += 2
                details.append(f"Revenue CAGR: {cagr:.1%} (moderate)")
            elif cagr > 0.03:
                score += 1
                details.append(f"Revenue CAGR: {cagr:.1%} (slow)")
            else:
                details.append(f"Revenue CAGR: {cagr:.1%} (stagnant)")
    
    # Check for acceleration (Wood: disruptive growth)
    if len(revenues) >= 3:
        growth_rates = []
        for i in range(len(revenues) - 1):
            if revenues[i+1] > 0:
                growth = (revenues[i] - revenues[i+1]) / abs(revenues[i+1])
                growth_rates.append(growth)
        if len(growth_rates) >= 2:
            recent_growth = growth_rates[0]
            older_growth = growth_rates[-1]
            if recent_growth > older_growth * 1.2:  # 20%+ acceleration
                score += 3
                details.append(f"Accelerating growth: {recent_growth:.1%} vs {older_growth:.1%} (Wood disruptive)")
            elif recent_growth > older_growth:
                score += 2
                details.append(f"Improving growth: {recent_growth:.1%} vs {older_growth:.1%}")
    
    # Consistency check (Lynch: steady growth preferred)
    if len(revenues) >= 3:
        positive_growth_periods = 0
        for i in range(len(revenues) - 1):
            if revenues[i] > revenues[i+1]:
                positive_growth_periods += 1
        consistency = positive_growth_periods / (len(revenues) - 1)
        if consistency >= 0.8:
            score += 3
            details.append(f"Growth consistency: {consistency:.0%} (Lynch steady)")
        elif consistency >= 0.6:
            score += 2
            details.append(f"Growth consistency: {consistency:.0%} (mostly steady)")
        elif consistency >= 0.4:
            score += 1
            details.append(f"Growth consistency: {consistency:.0%} (inconsistent)")
    
    return {"score": min(score, 10), "max_score": 10, "details": "; ".join(details) if details else "Limited revenue data"}


def generate_lynch_output(
    ticker: str,
    analysis_data: dict[str, any],
    state: AgentState,
    agent_id: str,
) -> PeterLynchSignal:
    """
    Generates a final JSON signal in Peter Lynch's voice & style.
    """
    template = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """You are a Peter Lynch AI agent. You make investment decisions based on Peter Lynch's well-known principles:
                
                1. Invest in What You Know: Emphasize understandable businesses, possibly discovered in everyday life.
                2. Growth at a Reasonable Price (GARP): Rely on the PEG ratio as a prime metric.
                3. Look for 'Ten-Baggers': Companies capable of growing earnings and share price substantially.
                4. Steady Growth: Prefer consistent revenue/earnings expansion, less concern about short-term noise.
                5. Avoid High Debt: Watch for dangerous leverage.
                6. Management & Story: A good 'story' behind the stock, but not overhyped or too complex.
                
                When you provide your reasoning, do it in Peter Lynch's voice:
                - Cite the PEG ratio
                - Mention 'ten-bagger' potential if applicable
                - Refer to personal or anecdotal observations (e.g., "If my kids love the product...")
                - Use practical, folksy language
                - Provide key positives and negatives
                - Conclude with a clear stance (bullish, bearish, or neutral)
                
                Return your final output strictly in JSON with the fields:
                {{
                  "signal": "bullish" | "bearish" | "neutral",
                  "confidence": 0 to 100,
                  "reasoning": "string"
                }}
                """,
            ),
            (
                "human",
                """Based on the following analysis data for {ticker}, produce your Peter Lynch–style investment signal.

                Analysis Data:
                {analysis_data}

                Return only valid JSON with "signal", "confidence", and "reasoning".
                """,
            ),
        ]
    )

    prompt = template.invoke({"analysis_data": json.dumps(analysis_data, indent=2), "ticker": ticker})

    def create_default_signal():
        return PeterLynchSignal(
            signal="neutral",
            confidence=0.0,
            reasoning="Error in analysis; defaulting to neutral"
        )

    def create_rule_based_peter_lynch_signal():
        """
        Deterministic Growth Composite signal based on composite factor scores.
        """
        signal = analysis_data.get("signal", "neutral")
        score = analysis_data.get("score", 0)
        max_score = analysis_data.get("max_score", 1)
        
        if max_score == 0:
            return PeterLynchSignal(
                signal="neutral",
                confidence=50.0,
                reasoning="Insufficient data for Growth Composite analysis"
            )
        
        score_ratio = score / max_score
        
        # Get composite factor scores for detailed reasoning
        revenue_growth = analysis_data.get("revenue_growth", {})
        earnings_growth = analysis_data.get("earnings_growth", {})
        valuation_sanity = analysis_data.get("valuation_sanity", {})
        business_simplicity = analysis_data.get("business_simplicity", {})
        
        # Calculate confidence based on score ratio and factor consistency
        base_confidence = 50.0 + (score_ratio - 0.5) * 60.0  # 20-80 base range
        base_confidence = max(20.0, min(85.0, base_confidence))  # Clamp to 20-85
        
        # Adjust confidence based on factor consistency
        factor_scores = [
            revenue_growth.get("score", 0) / max(1, revenue_growth.get("max_score", 1)),
            earnings_growth.get("score", 0) / max(1, earnings_growth.get("max_score", 1)),
            valuation_sanity.get("score", 0) / max(1, valuation_sanity.get("max_score", 1)),
            business_simplicity.get("score", 0) / max(1, business_simplicity.get("max_score", 1)),
        ]
        
        # If factors are consistent (all high or all low), increase confidence
        factor_std = (sum((f - score_ratio)**2 for f in factor_scores) / len(factor_scores))**0.5
        consistency_boost = max(0, 10 - int(factor_std * 20))  # Up to +10 points for consistency
        final_confidence = min(90.0, base_confidence + consistency_boost)
        
        # Get PEG for reasoning
        peg = valuation_sanity.get("peg_ratio", "N/A")
        if isinstance(peg, (int, float)):
            peg_str = f"{peg:.2f}"
        else:
            peg_str = str(peg)
        
        reasoning = (
            f"Growth Composite: Score {score:.1f}/{max_score:.1f} ({score_ratio:.0%}). "
            f"PEG: {peg_str}, Rev Growth: {revenue_growth.get('score', 0):.1f}, "
            f"Earnings Growth: {earnings_growth.get('score', 0):.1f}, "
            f"Simplicity: {business_simplicity.get('score', 0):.1f}. "
            f"{signal.capitalize()} ({int(final_confidence)}%)"
        )
        
        return PeterLynchSignal(
            signal=signal,
            confidence=final_confidence,
            reasoning=reasoning
        )

    return call_llm(
        prompt=prompt,
        pydantic_model=PeterLynchSignal,
        agent_name=agent_id,
        state=state,
        default_factory=create_default_signal,
        rule_based_factory=create_rule_based_peter_lynch_signal,
    )


def analyze_earnings_growth_composite(financial_line_items: list) -> dict:
    """
    Factor 2: Earnings Growth (25% weight)
    Combines Lynch (EPS growth) + Fisher (consistency) + Growth Analyst (trends).
    """
    if not financial_line_items or len(financial_line_items) < 2:
        return {"score": 0, "max_score": 10, "details": "Insufficient data for earnings growth"}
    
    score = 0
    details = []
    eps_values = [fi.earnings_per_share for fi in financial_line_items if hasattr(fi, 'earnings_per_share') and fi.earnings_per_share is not None]
    
    if len(eps_values) >= 2:
        # Calculate CAGR (Lynch + Growth Analyst)
        latest_eps = eps_values[0]
        oldest_eps = eps_values[-1]
        years = len(eps_values) - 1
        if oldest_eps > 0 and latest_eps > 0:
            cagr = ((latest_eps / oldest_eps) ** (1 / years)) - 1
            if cagr > 0.25:
                score += 4
                details.append(f"EPS CAGR: {cagr:.1%} (exceptional)")
            elif cagr > 0.15:
                score += 3
                details.append(f"EPS CAGR: {cagr:.1%} (strong)")
            elif cagr > 0.08:
                score += 2
                details.append(f"EPS CAGR: {cagr:.1%} (moderate)")
            elif cagr > 0.03:
                score += 1
                details.append(f"EPS CAGR: {cagr:.1%} (slow)")
            else:
                details.append(f"EPS CAGR: {cagr:.1%} (stagnant)")
    
    # Consistency check (Fisher: scuttlebutt research values consistency)
    if len(eps_values) >= 3:
        positive_periods = sum(1 for i in range(len(eps_values) - 1) if eps_values[i] > eps_values[i+1])
        consistency = positive_periods / (len(eps_values) - 1)
        if consistency >= 0.8:
            score += 3
            details.append(f"EPS consistency: {consistency:.0%} (Fisher quality)")
        elif consistency >= 0.6:
            score += 2
            details.append(f"EPS consistency: {consistency:.0%} (mostly consistent)")
        elif consistency >= 0.4:
            score += 1
            details.append(f"EPS consistency: {consistency:.0%} (inconsistent)")
    
    # Growth quality (Fisher: growth should outpace inflation)
    if len(eps_values) >= 3:
        avg_growth = sum((eps_values[i] - eps_values[i+1]) / abs(eps_values[i+1]) for i in range(len(eps_values) - 1) if eps_values[i+1] > 0) / (len(eps_values) - 1)
        if avg_growth > 0.10:
            score += 3
            details.append(f"EPS growth quality: {avg_growth:.1%} avg (Fisher strong)")
        elif avg_growth > 0.05:
            score += 2
            details.append(f"EPS growth quality: {avg_growth:.1%} avg (moderate)")
    
    return {"score": min(score, 10), "max_score": 10, "details": "; ".join(details) if details else "Limited earnings data"}


def analyze_valuation_sanity_check(financial_line_items: list, market_cap: float | None) -> dict:
    """
    Factor 3: PEG-Style Valuation Sanity Check (25% weight)
    Lynch's GARP approach: PEG ratio and P/E reasonableness.
    """
    if not financial_line_items or market_cap is None or market_cap <= 0:
        return {"score": 5, "max_score": 10, "details": "Insufficient data, neutral score"}
    
    score = 5  # Start neutral
    details = []
    latest = financial_line_items[0]
    
    # Calculate P/E
    net_income = latest.net_income if hasattr(latest, 'net_income') else None
    eps = latest.earnings_per_share if hasattr(latest, 'earnings_per_share') else None
    
    pe_ratio = None
    if net_income and net_income > 0:
        pe_ratio = market_cap / net_income
        details.append(f"P/E: {pe_ratio:.2f}")
    elif eps and eps > 0 and latest.outstanding_shares and latest.outstanding_shares > 0:
        price_per_share = market_cap / latest.outstanding_shares
        pe_ratio = price_per_share / eps
        details.append(f"P/E: {pe_ratio:.2f}")
    
    # P/E reasonableness (Lynch: < 15 very attractive, < 25 reasonable)
    if pe_ratio:
        if pe_ratio < 15:
            score += 3
            details.append("P/E < 15 (Lynch very attractive)")
        elif pe_ratio < 25:
            score += 2
            details.append("P/E < 25 (Lynch reasonable)")
        elif pe_ratio < 35:
            score += 1
            details.append("P/E < 35 (moderate)")
        else:
            score -= 1
            details.append("P/E > 35 (expensive)")
    
    # Calculate PEG ratio (Lynch's favorite metric)
    peg_ratio = None
    eps_values = [fi.earnings_per_share for fi in financial_line_items if hasattr(fi, 'earnings_per_share') and fi.earnings_per_share is not None]
    if pe_ratio and len(eps_values) >= 2 and eps_values[-1] > 0:
        years = len(eps_values) - 1
        if eps_values[0] > 0:
            eps_growth = ((eps_values[0] / eps_values[-1]) ** (1 / years)) - 1
            if eps_growth > 0:
                # PEG = P/E / (growth rate * 100) - Lynch formula
                peg_ratio = pe_ratio / (eps_growth * 100)
                details.append(f"PEG: {peg_ratio:.2f} (growth: {eps_growth:.1%})")
                
                # PEG scoring (Lynch: < 1 very attractive, < 2 fair, > 2 expensive)
                if peg_ratio < 1.0:
                    score += 4
                    details.append("PEG < 1.0 (Lynch very attractive)")
                elif peg_ratio < 2.0:
                    score += 3
                    details.append("PEG < 2.0 (Lynch fair)")
                elif peg_ratio < 3.0:
                    score += 1
                    details.append("PEG < 3.0 (moderate)")
                else:
                    score -= 2
                    details.append("PEG > 3.0 (expensive)")
    
    return {
        "score": max(0, min(score, 10)),
        "max_score": 10,
        "details": "; ".join(details) if details else "Limited valuation data",
        "peg_ratio": peg_ratio,
        "pe_ratio": pe_ratio,
    }


def analyze_business_simplicity(financial_line_items: list, metrics: list = None) -> dict:
    """
    Factor 4: Business Simplicity Proxy (20% weight)
    Combines Lynch (manageable debt, understandable) + Fisher (operating leverage, FCF) + Wood (operating leverage).
    """
    if not financial_line_items:
        return {"score": 5, "max_score": 10, "details": "Insufficient data, neutral score"}
    
    score = 5  # Start neutral
    details = []
    latest = financial_line_items[0]
    
    # Debt levels (Lynch: avoid high debt)
    debt = latest.total_debt if hasattr(latest, 'total_debt') else 0
    equity = latest.shareholders_equity if hasattr(latest, 'shareholders_equity') else 0
    if equity > 0:
        de_ratio = debt / equity
        if de_ratio < 0.3:
            score += 3
            details.append(f"Debt/Equity: {de_ratio:.2f} (Lynch manageable)")
        elif de_ratio < 0.5:
            score += 2
            details.append(f"Debt/Equity: {de_ratio:.2f} (moderate)")
        elif de_ratio < 1.0:
            score += 1
            details.append(f"Debt/Equity: {de_ratio:.2f} (high)")
        else:
            score -= 2
            details.append(f"Debt/Equity: {de_ratio:.2f} (very high)")
    
    # Free Cash Flow (Lynch + Fisher: positive FCF indicates simplicity)
    fcf = latest.free_cash_flow if hasattr(latest, 'free_cash_flow') else None
    if fcf:
        if fcf > 0:
            score += 2
            details.append(f"FCF: ${fcf:,.0f} (positive, simple)")
        else:
            score -= 1
            details.append(f"FCF: ${fcf:,.0f} (negative, complex)")
    
    # Operating Leverage (Wood: revenue grows faster than expenses)
    revenues = [fi.revenue for fi in financial_line_items if hasattr(fi, 'revenue') and fi.revenue is not None]
    if len(revenues) >= 2:
        rev_growth = (revenues[0] - revenues[-1]) / abs(revenues[-1]) if revenues[-1] > 0 else 0
        # Check if operating expenses are growing slower (proxy via operating income)
        op_incomes = [fi.operating_income for fi in financial_line_items if hasattr(fi, 'operating_income') and fi.operating_income is not None]
        if len(op_incomes) >= 2 and op_incomes[-1] > 0:
            op_income_growth = (op_incomes[0] - op_incomes[-1]) / abs(op_incomes[-1])
            if op_income_growth > rev_growth * 1.1:  # Operating income growing faster than revenue
                score += 3
                details.append(f"Operating leverage: {op_income_growth:.1%} > {rev_growth:.1%} (Wood positive)")
            elif op_income_growth > rev_growth:
                score += 2
                details.append(f"Operating leverage: {op_income_growth:.1%} > {rev_growth:.1%} (good)")
    
    # R&D Intensity (Wood: innovation indicator, but not too high = complexity)
    rd = latest.research_and_development if hasattr(latest, 'research_and_development') else None
    revenue = latest.revenue if hasattr(latest, 'revenue') else None
    if rd and revenue and revenue > 0:
        rd_intensity = rd / revenue
        if 0.05 < rd_intensity < 0.15:  # Moderate R&D (Wood: innovation without complexity)
            score += 2
            details.append(f"R&D Intensity: {rd_intensity:.1%} (Wood balanced)")
        elif rd_intensity > 0.15:
            score += 1
            details.append(f"R&D Intensity: {rd_intensity:.1%} (high, may be complex)")
        elif rd_intensity > 0:
            score += 1
            details.append(f"R&D Intensity: {rd_intensity:.1%} (low)")
    
    return {"score": max(0, min(score, 10)), "max_score": 10, "details": "; ".join(details) if details else "Limited simplicity data"}


