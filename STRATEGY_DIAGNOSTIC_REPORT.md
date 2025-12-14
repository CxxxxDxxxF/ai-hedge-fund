# TOPSTEPSTRATEGY DIAGNOSTIC REPORT
**Date:** 2025-01-XX  
**Mode:** INTRADAY STRATEGY DIAGNOSTIC  
**Role:** Quant Engineer (Behavioral Attribution)  
**Instrument:** ES proxy (^GSPC 5-minute data)

---

## 1. STRATEGY EVALUATIONS

**Total Evaluations:** 780

Strategy was called on 780 bars during the trading window (9:30-10:30) across the full dataset (2025-09-19 to 2025-12-12).

---

## 2. TRADES ATTEMPTED

**Trades Attempted:** 0  
**Trades Executed:** 0

No trades were attempted or executed during the evaluation period.

---

## 3. FILTER FAILURE FREQUENCY TABLE

| Filter | Count | Percentage |
|--------|-------|------------|
| **No OR Break (either direction)** | 492 | 63.1% |
| **No Pullback (Long)** | 145 | 18.6% |
| **No Pullback (Short)** | 98 | 12.6% |
| **ATR Filter** | 44 | 5.6% |
| **Insufficient Data** | 1 | 0.1% |
| **Opening Range ID** | 0 | 0.0% |
| **Daily Limits** | 0 | 0.0% |
| **Position Size** | 0 | 0.0% |

**Total Evaluations:** 780

---

## 4. REPRESENTATIVE FAILED DAYS PER FILTER

### Filter: INSUFFICIENT_DATA
- **Date/Time:** 2025-09-19
- **Bars Available:** 1
- **Reasoning:** Insufficient price data
- **Context:** First day of dataset, only 1 bar available

---

### Filter: ATR_FILTER
- **Date/Time:** 2025-09-19
- **Bars Available:** 2
- **Reasoning:** Market regime filter: Insufficient data for regime filter
- **Context:** Requires 20 days of ATR history, only 2 bars available

---

### Filter: NO_OR_BREAK
- **Date/Time:** 2025-09-22
- **Bars Available:** 79
- **Reasoning:** No OR break in either direction
- **OR High:** $6656.61
- **OR Low:** $6648.85
- **OR Range:** $7.76
- **Last Bar High:** $6698.63
- **Last Bar Low:** $6693.76
- **Last Bar Close:** $6693.76
- **Context:** Price moved significantly above OR High but never broke OR Low. Strategy requires price to break AND close outside OR range. Last bar closed at $6693.76, which is above OR High ($6656.61) but the break was not confirmed by a close above OR High in the same bar.

---

### Filter: NO_PULLBACK_LONG
- **Date/Time:** 2025-09-22
- **Bars Available:** 83
- **Reasoning:** OR break long but no pullback entry
- **OR High:** $6657.17
- **OR Low:** $6648.07
- **OR Range:** $9.10
- **Last Bar Close:** $6693.76
- **Prev Bar Close:** $6696.99
- **Context:** OR break occurred (price broke above OR High), but pullback condition not met. Strategy requires 50-70% retrace of breakout candle plus bullish engulfing pattern or strong close. Pullback did not occur or did not meet entry criteria.

---

### Filter: NO_PULLBACK_SHORT
- **Date/Time:** 2025-09-23
- **Bars Available:** 167
- **Reasoning:** OR break short but no pullback entry
- **OR High:** $6699.05
- **OR Low:** $6691.47
- **OR Range:** $7.58
- **Last Bar Close:** $6658.09
- **Prev Bar Close:** $6660.48
- **Context:** OR break occurred (price broke below OR Low), but pullback condition not met. Strategy requires 50-70% retrace of breakout candle plus bearish engulfing pattern or strong close. Pullback did not occur or did not meet entry criteria.

---

## SUMMARY

**Primary Failure Mode:** No Opening Range Break (63.1% of evaluations)

The strategy's most common failure is the absence of an OR break in either direction. When OR breaks do occur, the strategy fails to find valid pullback entries (31.2% combined: 18.6% long, 12.6% short).

**Secondary Failure Mode:** Pullback Entry Conditions (31.2% of evaluations)

When OR breaks occur, the strategy frequently fails to find pullback entries that meet the strict criteria (50-70% retrace + engulfing/strong close pattern).

**Tertiary Failure Mode:** ATR Filter (5.6% of evaluations)

A small percentage of evaluations fail the ATR regime filter, typically due to insufficient historical data early in the dataset.

---

**END OF REPORT**
