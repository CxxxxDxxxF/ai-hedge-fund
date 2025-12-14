"""
Minimal Reference Loop: Canary Implementation

Purpose:
- Demonstrate the loop, invariants, and failure behavior
- Serve as the "canary" implementation
- Make future bugs obvious by comparison

This is the minimal, dependency-free reference that shows:
1. How the loop should work
2. How invariants should be logged
3. How failures should be handled
4. How determinism should be enforced

If the main DeterministicBacktest diverges from this pattern, it's a bug.
"""

from __future__ import annotations

import os
import sys
import hashlib
import random
import numpy as np
from datetime import datetime
from typing import Dict, List, Tuple


# Determinism: Seed all RNGs in one place
REFERENCE_SEED = 42
random.seed(REFERENCE_SEED)
np.random.seed(REFERENCE_SEED)


class ReferenceBacktestLoop:
    """
    Minimal reference implementation of deterministic backtest loop.
    
    This demonstrates the essential pattern:
    - Explicit loop index
    - Duplicate date guard
    - Invariant logging
    - Engine vs strategy failure separation
    - Determinism enforcement
    - Guaranteed summary
    """
    
    def __init__(self, dates: List[str], initial_value: float = 100000.0):
        self.dates = dates
        self.initial_value = initial_value
        self.processed_dates: set = set()
        self.daily_values: List[Dict] = []
        self.daily_hashes: List[str] = []
        self.iteration_log: List[Dict] = []
        self.last_good_state: Dict = {}
    
    def _log_invariant(self, index: int, date: str, value: float, delta: float) -> None:
        """One line per iteration - never skip."""
        log_entry = {
            "index": index,
            "date": date,
            "value": value,
            "delta": delta,
        }
        self.iteration_log.append(log_entry)
        print(f"[{index:4d}] {date} | V=${value:,.0f} | Δt={delta:.2f}s", file=sys.stderr, flush=True)
    
    def _hash_daily_output(self, date: str, value: float) -> str:
        """Hash daily output for determinism verification."""
        state_str = f"{date}:{value:.2f}:{len(self.daily_values)}"
        return hashlib.md5(state_str.encode()).hexdigest()
    
    def _process_day(self, date: str, index: int) -> Tuple[bool, float]:
        """
        Process one day.
        
        Returns:
            (is_engine_failure, portfolio_value)
        """
        # Contract: Duplicate date must never happen
        if date in self.processed_dates:
            raise RuntimeError(f"ENGINE FAILURE: Date {date} already processed at index {index}")
        self.processed_dates.add(date)
        
        start_time = datetime.now()
        
        # Simulate day processing (replace with actual logic)
        # For reference: just increment value slightly
        current_value = self.initial_value + (index * 100.0)
        
        # Hash output for determinism
        daily_hash = self._hash_daily_output(date, current_value)
        self.daily_hashes.append(daily_hash)
        
        # Record daily value
        self.daily_values.append({
            "date": date,
            "value": current_value,
            "index": index,
        })
        
        # Log invariant (contract: must happen every iteration)
        delta = (datetime.now() - start_time).total_seconds()
        self._log_invariant(index, date, current_value, delta)
        
        # Save last good state
        self.last_good_state = {
            "date": date,
            "index": index,
            "value": current_value,
        }
        
        return (False, current_value)  # No engine failure
    
    def run(self) -> Dict:
        """
        Run the reference loop.
        
        Contract: Loop must advance exactly once per iteration.
        Contract: Every iteration must log.
        Contract: Summary must always print.
        """
        total_days = len(self.dates)
        
        # Contract: Explicit index ensures advancement
        for i in range(total_days):
            date = self.dates[i]
            
            try:
                is_engine_failure, value = self._process_day(date, i)
                
                if is_engine_failure:
                    raise RuntimeError(f"ENGINE FAILURE at index {i}, date {date}")
                    
            except RuntimeError as e:
                # Engine failures: abort
                if "ENGINE FAILURE" in str(e):
                    print(f"\nFATAL: {e}", file=sys.stderr)
                    print(f"Last good state: {self.last_good_state}", file=sys.stderr)
                    raise
                raise
            except Exception as e:
                # Unexpected: treat as engine failure
                print(f"\nFATAL at index {i}, date {date}: {e}", file=sys.stderr)
                import traceback
                traceback.print_exc(file=sys.stderr)
                raise RuntimeError(f"ENGINE FAILURE: {e}")
        
        # Calculate final hash for determinism verification
        final_hash = hashlib.md5("".join(self.daily_hashes).encode()).hexdigest()
        
        return {
            "final_value": self.daily_values[-1]["value"] if self.daily_values else self.initial_value,
            "total_days": len(self.daily_values),
            "determinism": {
                "seed": REFERENCE_SEED,
                "output_hash": final_hash,
            },
        }
    
    def print_summary(self, metrics: Dict) -> None:
        """Print summary - contract: must always execute."""
        print("\n" + "=" * 80)
        print("REFERENCE BACKTEST SUMMARY")
        print("=" * 80)
        print(f"Final Value: ${metrics['final_value']:,.2f}")
        print(f"Total Days: {metrics['total_days']}")
        print(f"Determinism Hash: {metrics['determinism']['output_hash'][:16]}...")
        print("=" * 80)


def main():
    """Reference implementation entry point."""
    # Example dates
    dates = ["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"]
    
    loop = ReferenceBacktestLoop(dates, initial_value=100000.0)
    
    try:
        metrics = loop.run()
    except RuntimeError as e:
        print(f"\nFATAL: {e}", file=sys.stderr)
        # Still try to print partial results
        if loop.daily_values:
            partial = {
                "final_value": loop.daily_values[-1]["value"],
                "total_days": len(loop.daily_values),
                "determinism": {"seed": REFERENCE_SEED, "output_hash": "partial"},
            }
            loop.print_summary(partial)
        return 1
    
    # Guaranteed: Summary always prints
    loop.print_summary(metrics)
    return 0


if __name__ == "__main__":
    sys.exit(main())
