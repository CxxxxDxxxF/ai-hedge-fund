#!/usr/bin/env python3
"""
CLI entry point for deterministic backtest runner.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.backtesting.deterministic_backtest import main

if __name__ == "__main__":
    sys.exit(main())
