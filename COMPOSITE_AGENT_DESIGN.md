# Composite Agent Design Documentation

**Research Engineer Implementation**  
**Date:** 2025-01-XX  
**Goal:** Make each composite internally diversified but externally singular

---

## Value Composite Analyst (`warren_buffett.py`)

### Factor List

**5 Composite Factors (Weighted):**

1. **Valuation Margin of Safety (30% weight)**
   - Graham Number: `sqrt(22.5 * EPS * BVPS)` vs current price
   - Net-Net Current Asset Value: `(Current Assets - Total Liabilities) / Shares` vs price
   - Intrinsic Value Discount: DCF-based intrinsic value vs market cap
   - Sources: Graham (margin of safety), Buffett (intrinsic value)

2. **Business Quality (25% weight)**
   - ROE: > 20% excellent, > 15% good, > 10% moderate
   - ROE Consistency: % of periods with ROE > 15% (Munger predictability)
   - Operating Margin: > 20% strong, > 15% good
   - Competitive Moat: Historical ROE/margin stability, pricing power
   - Sources: Buffett (quality businesses), Munger (predictability)

3. **Balance Sheet Strength (20% weight)**
   - Current Ratio: >= 2.0 (Graham strong), >= 1.5 (moderate)
   - Debt-to-Equity: < 0.3 (very conservative), < 0.5 (Graham conservative)
   - Cash/Debt Ratio: > 1.5 (Burry strong), > 1.0 (adequate)
   - FCF Yield: > 10% (Burry attractive), > 5% (moderate)
   - Sources: Graham (liquidity, debt ratios), Burry (cash/debt, FCF yield)

4. **Earnings Quality (15% weight)**
   - Earnings Stability: % of periods with positive EPS (Graham: 5+ years)
   - Earnings Consistency: Growing trend (Buffett consistency)
   - FCF Conversion: FCF / Net Income ratio (> 80% excellent, > 50% good)
   - Earnings Growth Consistency: All periods positive growth (Pabrai low risk)
   - Sources: Graham (stability), Buffett (consistency), Pabrai (low risk)

5. **Conservative Growth (10% weight)**
   - Historical Revenue Growth: CAGR with 30% haircut (Buffett/Munger conservatism)
   - Historical Earnings Growth: CAGR with 30% haircut
   - Growth Rate Assessment: > 15% strong, > 8% moderate, > 3% slow
   - Sources: Buffett (conservative assumptions), Munger (rational thinking)

### Scoring Logic

**Composite Score Calculation:**
```python
total_score = (
    valuation_margin["score"] * 0.30 +
    business_quality["score"] * 0.25 +
    balance_sheet_strength["score"] * 0.20 +
    earnings_quality["score"] * 0.15 +
    conservative_growth["score"] * 0.10
)

max_possible_score = (
    valuation_margin["max_score"] * 0.30 +
    business_quality["max_score"] * 0.25 +
    balance_sheet_strength["max_score"] * 0.20 +
    earnings_quality["max_score"] * 0.15 +
    conservative_growth["max_score"] * 0.10
)

score_ratio = total_score / max_possible_score
```

**Signal Decision:**
- **Bullish:** `score_ratio > 0.7` AND `margin_of_safety > 0.2` (strong business + significant discount)
- **Bullish:** `score_ratio > 0.6` AND `margin_of_safety > 0` (good business + positive discount)
- **Bearish:** `score_ratio < 0.4` OR `margin_of_safety < -0.2` (weak fundamentals OR overvalued)
- **Neutral:** Otherwise (mixed signals)

### Confidence Calculation

**Base Confidence:**
```python
base_confidence = 50 + (score_ratio - 0.5) * 60  # Range: 20-80
base_confidence = clamp(20, 85, base_confidence)
```

**Consistency Adjustment:**
```python
# Calculate factor score standard deviation
factor_scores = [
    valuation_margin_score_ratio,
    business_quality_score_ratio,
    balance_sheet_score_ratio,
    earnings_quality_score_ratio,
    conservative_growth_score_ratio,
]
factor_std = std(factor_scores)
consistency_boost = max(0, 10 - int(factor_std * 20))  # Up to +10 for consistency

final_confidence = min(90, base_confidence + consistency_boost)
```

**Confidence Ranges:**
- **85-90%:** Exceptional composite score with high factor consistency
- **70-84%:** Strong composite score with good consistency
- **50-69%:** Moderate composite score or mixed factors
- **30-49%:** Weak composite score or inconsistent factors
- **20-29%:** Very weak composite score

### Before/After Example

**Before (Single Agent - Buffett only):**
```
Input: AAPL financial data
Analysis:
  - ROE: 150% (excellent)
  - Moat: Strong
  - Margin of Safety: 15%
Output:
  Signal: bullish
  Confidence: 75%
  Reasoning: "Strong business with 15% margin of safety"
```

**After (Value Composite):**
```
Input: AAPL financial data
Composite Factors:
  - Valuation Margin: 8.5/10 (Graham Number: 30% discount, IV: 20% discount)
  - Business Quality: 9.0/10 (ROE: 150%, consistency: 90%, moat: strong)
  - Balance Sheet: 7.0/10 (Current ratio: 1.8, D/E: 0.2, Cash/Debt: 2.5)
  - Earnings Quality: 8.5/10 (Stability: 100%, FCF conversion: 85%)
  - Conservative Growth: 6.0/10 (Revenue CAGR: 8% after haircut)

Composite Score: 7.9/10 (79%)
Factor Consistency: High (std: 0.12)
Margin of Safety: 20%

Output:
  Signal: bullish
  Confidence: 87% (base 77% + 10% consistency boost)
  Reasoning: "Value Composite: Strong (score 79%, margin 20%). 
              Factors: Val 8.5, Quality 9.0, BS 7.0, Earnings 8.5, Growth 6.0"
```

**Key Differences:**
- ✅ **More factors:** 5 composite factors vs 6 legacy factors (but weighted)
- ✅ **Explicit weights:** Clear importance hierarchy
- ✅ **Factor transparency:** Reasoning shows all factor scores
- ✅ **Consistency boost:** Higher confidence when factors agree
- ✅ **Single signal:** One composite signal, not multiple overlapping signals

---

## Growth Composite Analyst (`peter_lynch.py`)

### Factor List

**4 Composite Factors (Weighted):**

1. **Revenue Growth (30% weight)**
   - Revenue CAGR: Annualized growth rate over historical periods
   - Growth Acceleration: Recent growth > older growth by 20%+ (Wood: disruptive)
   - Growth Consistency: % of periods with positive growth (Lynch: steady)
   - Sources: Lynch (consistent growth), Wood (accelerating growth), Growth Analyst (CAGR trends)

2. **Earnings Growth (25% weight)**
   - EPS CAGR: Annualized EPS growth rate
   - Growth Consistency: % of periods with positive EPS growth (Fisher: quality)
   - Growth Quality: Average growth rate (Fisher: should outpace inflation)
   - Sources: Lynch (EPS growth), Fisher (consistency), Growth Analyst (trends)

3. **PEG-Style Valuation Sanity Check (25% weight)**
   - P/E Ratio: Market cap / Net Income or Price / EPS
   - PEG Ratio: P/E / (EPS Growth Rate * 100)
   - P/E Reasonableness: < 15 very attractive, < 25 reasonable, < 35 moderate
   - PEG Attractiveness: < 1.0 very attractive, < 2.0 fair, < 3.0 moderate
   - Sources: Lynch (GARP, PEG focus)

4. **Business Simplicity Proxy (20% weight)**
   - Debt-to-Equity: < 0.3 manageable (Lynch), < 0.5 moderate
   - Free Cash Flow: Positive FCF indicates simplicity
   - Operating Leverage: Operating income growth > revenue growth (Wood: positive leverage)
   - R&D Intensity: 5-15% balanced (Wood: innovation without complexity)
   - Sources: Lynch (manageable debt), Fisher (operating leverage), Wood (R&D balance)

### Scoring Logic

**Composite Score Calculation:**
```python
total_score = (
    revenue_growth["score"] * 0.30 +
    earnings_growth["score"] * 0.25 +
    valuation_sanity["score"] * 0.25 +
    business_simplicity["score"] * 0.20
)

max_possible_score = (
    revenue_growth["max_score"] * 0.30 +
    earnings_growth["max_score"] * 0.25 +
    valuation_sanity["max_score"] * 0.25 +
    business_simplicity["max_score"] * 0.20
)

score_ratio = total_score / max_possible_score
```

**Signal Decision:**
- **Bullish:** `score_ratio >= 0.7` (strong growth + reasonable valuation + simple business)
- **Bearish:** `score_ratio <= 0.4` (weak growth OR expensive valuation OR complex business)
- **Neutral:** `0.4 < score_ratio < 0.7` (mixed signals)

### Confidence Calculation

**Base Confidence:**
```python
base_confidence = 50.0 + (score_ratio - 0.5) * 60.0  # Range: 20-80
base_confidence = clamp(20.0, 85.0, base_confidence)
```

**Consistency Adjustment:**
```python
# Calculate factor score standard deviation
factor_scores = [
    revenue_growth_score_ratio,
    earnings_growth_score_ratio,
    valuation_sanity_score_ratio,
    business_simplicity_score_ratio,
]
factor_std = std(factor_scores)
consistency_boost = max(0, 10 - int(factor_std * 20))  # Up to +10 for consistency

final_confidence = min(90.0, base_confidence + consistency_boost)
```

**Confidence Ranges:**
- **85-90%:** Exceptional growth composite with high factor consistency
- **70-84%:** Strong growth composite with good consistency
- **50-69%:** Moderate growth composite or mixed factors
- **30-49%:** Weak growth composite or inconsistent factors
- **20-29%:** Very weak growth composite

### Before/After Example

**Before (Single Agent - Lynch only):**
```
Input: TSLA financial data
Analysis:
  - Revenue Growth: 25% (strong)
  - PEG: 1.2 (fair)
  - Debt/Equity: 0.4 (moderate)
Output:
  Signal: bullish
  Confidence: 70%
  Reasoning: "Lynch GARP: Score 7.5/10. PEG: 1.2, Growth: 8.0, Fundamentals: 7.0"
```

**After (Growth Composite):**
```
Input: TSLA financial data
Composite Factors:
  - Revenue Growth: 9.0/10 (CAGR: 28%, accelerating: 35% vs 20%, consistency: 90%)
  - Earnings Growth: 7.5/10 (EPS CAGR: 22%, consistency: 80%, quality: 18% avg)
  - Valuation Sanity: 6.5/10 (P/E: 28, PEG: 1.2 fair)
  - Business Simplicity: 7.0/10 (D/E: 0.4, FCF: positive, Op leverage: positive, R&D: 8%)

Composite Score: 7.6/10 (76%)
Factor Consistency: Moderate (std: 0.15)

Output:
  Signal: bullish
  Confidence: 81% (base 75% + 6% consistency boost)
  Reasoning: "Growth Composite: Score 7.6/10.0 (76%). 
              PEG: 1.2, Rev Growth: 9.0, Earnings Growth: 7.5, Simplicity: 7.0. 
              Bullish (81%)"
```

**Key Differences:**
- ✅ **More factors:** 4 composite factors vs 5 legacy factors (but weighted)
- ✅ **Explicit weights:** Clear importance hierarchy
- ✅ **Factor transparency:** Reasoning shows all factor scores
- ✅ **Consistency boost:** Higher confidence when factors agree
- ✅ **Single signal:** One composite signal, not multiple overlapping signals
- ✅ **PEG prominence:** PEG ratio explicitly calculated and displayed

---

## Implementation Details

### Deterministic Logic First

Both composite agents:
1. **Calculate all factors deterministically** (no LLM calls for factor analysis)
2. **Combine factors with explicit weights** (transparent scoring)
3. **Generate signal deterministically** (rule-based decision logic)
4. **Calculate confidence deterministically** (score ratio + consistency adjustment)
5. **LLM is optional** (only used for enhanced reasoning in non-deterministic mode)

### Factor Traceability

Each factor clearly documents:
- **Source principles:** Which investor's approach it incorporates
- **Scoring thresholds:** Explicit cutoffs (e.g., ROE > 15%, PEG < 1.0)
- **Weight in composite:** Percentage contribution to final score
- **Reasoning inclusion:** Factor scores appear in output reasoning

### Internal Diversification

**Value Composite:**
- Diversified across: Valuation (30%), Quality (25%), Balance Sheet (20%), Earnings (15%), Growth (10%)
- Each factor uses different metrics (Graham Number, ROE, Current Ratio, FCF, CAGR)
- Factors are relatively independent (low correlation between factors)

**Growth Composite:**
- Diversified across: Revenue Growth (30%), Earnings Growth (25%), Valuation (25%), Simplicity (20%)
- Each factor uses different metrics (CAGR, PEG, Debt/Equity, Operating Leverage)
- Factors are relatively independent (low correlation between factors)

### External Singularity

**Single Signal Output:**
- Both composites output ONE signal (bullish/bearish/neutral)
- ONE confidence score (0-100)
- ONE reasoning string (includes all factor scores for transparency)

**No Signal Overlap:**
- Value Composite focuses on margin of safety and quality
- Growth Composite focuses on growth and reasonable valuation
- Different philosophies, different signals (can both be bullish for different reasons)

---

## Verification

### Test Commands

```bash
# Test Value Composite
cd ai-hedge-fund
HEDGEFUND_NO_LLM=1 poetry run python src/main.py \
  --ticker AAPL \
  --analysts warren_buffett

# Test Growth Composite
HEDGEFUND_NO_LLM=1 poetry run python src/main.py \
  --ticker TSLA \
  --analysts peter_lynch

# Test Both Composites
HEDGEFUND_NO_LLM=1 poetry run python src/main.py \
  --ticker AAPL,TSLA \
  --analysts warren_buffett,peter_lynch,aswath_damodaran,momentum,mean_reversion
```

### Expected Output Format

**Value Composite:**
```json
{
  "AAPL": {
    "signal": "bullish",
    "confidence": 87,
    "reasoning": "Value Composite: Strong (score 79%, margin 20%). Factors: Val 8.5, Quality 9.0, BS 7.0, Earnings 8.5, Growth 6.0"
  }
}
```

**Growth Composite:**
```json
{
  "TSLA": {
    "signal": "bullish",
    "confidence": 81,
    "reasoning": "Growth Composite: Score 7.6/10.0 (76%). PEG: 1.2, Rev Growth: 9.0, Earnings Growth: 7.5, Simplicity: 7.0. Bullish (81%)"
  }
}
```

---

## Summary

### Value Composite
- **5 factors** internally diversified (Valuation, Quality, Balance Sheet, Earnings, Growth)
- **30/25/20/15/10 weights** reflect importance
- **Single signal** externally (bullish/bearish/neutral)
- **Deterministic first** (rule-based, LLM optional)

### Growth Composite
- **4 factors** internally diversified (Revenue Growth, Earnings Growth, Valuation, Simplicity)
- **30/25/25/20 weights** reflect importance
- **Single signal** externally (bullish/bearish/neutral)
- **Deterministic first** (rule-based, LLM optional)

Both composites are **internally diversified** (multiple factors from different sources) but **externally singular** (one signal, one confidence, one reasoning).
