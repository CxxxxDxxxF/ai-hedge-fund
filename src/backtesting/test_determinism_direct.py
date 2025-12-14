"""
Direct Determinism Test - No subprocess, direct verification.
"""

import os
import sys

os.environ['HEDGEFUND_NO_LLM'] = '1'

from src.backtesting.deterministic_backtest import DeterministicBacktest

print("=" * 80)
print("DIRECT DETERMINISM VERIFICATION")
print("=" * 80)

# Run 1
print("\nRun 1...")
backtest1 = DeterministicBacktest(
    tickers=['AAPL'],
    start_date='2024-01-02',
    end_date='2024-01-05',
    initial_capital=100000.0,
    disable_progress=True,
)
metrics1 = backtest1.run()
hash1 = metrics1['determinism']['output_hash']
value1 = backtest1.daily_values[-1]['portfolio_value'] if backtest1.daily_values else 0
dates1 = len(backtest1.processed_dates)

print(f"  Hash: {hash1}")
print(f"  Final Value: ${value1:,.2f}")
print(f"  Dates Processed: {dates1}")

# Run 2 (identical)
print("\nRun 2 (identical inputs)...")
backtest2 = DeterministicBacktest(
    tickers=['AAPL'],
    start_date='2024-01-02',
    end_date='2024-01-05',
    initial_capital=100000.0,
    disable_progress=True,
)
metrics2 = backtest2.run()
hash2 = metrics2['determinism']['output_hash']
value2 = backtest2.daily_values[-1]['portfolio_value'] if backtest2.daily_values else 0
dates2 = len(backtest2.processed_dates)

print(f"  Hash: {hash2}")
print(f"  Final Value: ${value2:,.2f}")
print(f"  Dates Processed: {dates2}")

# Verify
print("\n" + "=" * 80)
print("VERIFICATION")
print("=" * 80)

hash_match = hash1 == hash2
value_match = abs(value1 - value2) < 0.01  # Allow tiny floating point differences
dates_match = dates1 == dates2

print(f"Hashes Match: {hash_match} {'✅' if hash_match else '❌'}")
print(f"Values Match: {value_match} {'✅' if value_match else '❌'} (diff: ${abs(value1 - value2):.2f})")
print(f"Dates Match: {dates_match} {'✅' if dates_match else '❌'}")

if hash_match and value_match and dates_match:
    print("\n✅ PASS: Determinism verified - identical inputs produce identical outputs")
    sys.exit(0)
else:
    print("\n❌ FAIL: Determinism violation detected")
    sys.exit(1)
