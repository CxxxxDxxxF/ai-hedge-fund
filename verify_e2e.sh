#!/bin/bash
# End-to-End Verification Script
# Run this in Poetry environment: poetry shell, then ./verify_e2e.sh

set -e  # Exit on error

echo "=========================================="
echo "Hedge Fund E2E Verification"
echo "=========================================="
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if HEDGEFUND_NO_LLM is set
if [ -z "$HEDGEFUND_NO_LLM" ]; then
    export HEDGEFUND_NO_LLM=1
    echo -e "${YELLOW}Setting HEDGEFUND_NO_LLM=1${NC}"
fi

ERRORS=0

# 1. Compile Check
echo "1. Running compileall..."
if poetry run python -m compileall src > /dev/null 2>&1; then
    echo -e "${GREEN}✓ compileall: Zero errors${NC}"
else
    echo -e "${RED}✗ compileall: Errors found${NC}"
    poetry run python -m compileall src 2>&1 | grep -E "(Error|Sorry)" || true
    ERRORS=$((ERRORS + 1))
fi
echo ""

# 2. Regression Tests
echo "2. Running regression tests..."
if poetry run python tests/test_peter_lynch_functions.py > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Peter Lynch functions test: PASSED${NC}"
else
    echo -e "${RED}✗ Peter Lynch functions test: FAILED${NC}"
    poetry run python tests/test_peter_lynch_functions.py
    ERRORS=$((ERRORS + 1))
fi

if poetry run python tests/test_deterministic_backtest_agent_keys.py > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Backtest agent keys test: PASSED${NC}"
else
    echo -e "${RED}✗ Backtest agent keys test: FAILED${NC}"
    poetry run python tests/test_deterministic_backtest_agent_keys.py
    ERRORS=$((ERRORS + 1))
fi
echo ""

# 3. Main Pipeline Test
echo "3. Running main pipeline test..."
echo "   Command: poetry run python src/main.py --ticker AAPL --analysts warren_buffett,peter_lynch,aswath_damodaran,momentum,mean_reversion,market_regime"
if poetry run python src/main.py \
    --ticker AAPL \
    --analysts warren_buffett,peter_lynch,aswath_damodaran,momentum,mean_reversion,market_regime \
    > /tmp/main_pipeline_output.txt 2>&1; then
    echo -e "${GREEN}✓ Main pipeline: Completed successfully${NC}"
    # Check for errors in output
    if grep -i "indentationerror\|noneType\|TypeError.*format" /tmp/main_pipeline_output.txt > /dev/null; then
        echo -e "${RED}✗ Main pipeline: Errors detected in output${NC}"
        grep -i "indentationerror\|noneType\|TypeError.*format" /tmp/main_pipeline_output.txt
        ERRORS=$((ERRORS + 1))
    else
        echo -e "${GREEN}✓ Main pipeline: No IndentationError or NoneType errors${NC}"
    fi
else
    echo -e "${RED}✗ Main pipeline: FAILED${NC}"
    cat /tmp/main_pipeline_output.txt
    ERRORS=$((ERRORS + 1))
fi
echo ""

# 4. Deterministic Backtest Test
echo "4. Running deterministic backtest..."
echo "   Command: poetry run python src/backtesting/deterministic_backtest.py --tickers AAPL,MSFT --start-date 2024-01-02 --end-date 2024-02-29 --initial-capital 100000"
if poetry run python src/backtesting/deterministic_backtest.py \
    --tickers AAPL,MSFT \
    --start-date 2024-01-02 \
    --end-date 2024-02-29 \
    --initial-capital 100000 \
    > /tmp/backtest_output.txt 2>&1; then
    echo -e "${GREEN}✓ Backtest: Completed successfully${NC}"
    
    # Check for agent key warnings
    if grep -i "warren_buffett_agent\|peter_lynch_agent\|aswath_damodaran_agent" /tmp/backtest_output.txt > /dev/null; then
        echo -e "${RED}✗ Backtest: Warnings about *_agent keys detected${NC}"
        grep -i "warren_buffett_agent\|peter_lynch_agent\|aswath_damodaran_agent" /tmp/backtest_output.txt
        ERRORS=$((ERRORS + 1))
    else
        echo -e "${GREEN}✓ Backtest: No *_agent key warnings${NC}"
    fi
    
    # Check for agent attribution
    if grep -E "Value|Growth|Valuation|Momentum|Mean Reversion" /tmp/backtest_output.txt > /dev/null; then
        echo -e "${GREEN}✓ Backtest: Agent attribution present${NC}"
        echo "   Agent attribution found:"
        grep -E "Value|Growth|Valuation|Momentum|Mean Reversion" /tmp/backtest_output.txt | head -5
    else
        echo -e "${YELLOW}⚠ Backtest: Agent attribution not found in output${NC}"
    fi
    
    # Check for errors
    if grep -i "indentationerror\|noneType\|TypeError.*format\|traceback" /tmp/backtest_output.txt > /dev/null; then
        echo -e "${RED}✗ Backtest: Errors detected${NC}"
        grep -i "indentationerror\|noneType\|TypeError.*format\|traceback" /tmp/backtest_output.txt
        ERRORS=$((ERRORS + 1))
    else
        echo -e "${GREEN}✓ Backtest: No errors detected${NC}"
    fi
else
    echo -e "${RED}✗ Backtest: FAILED${NC}"
    cat /tmp/backtest_output.txt
    ERRORS=$((ERRORS + 1))
fi
echo ""

# Summary
echo "=========================================="
if [ $ERRORS -eq 0 ]; then
    echo -e "${GREEN}✓ All checks passed!${NC}"
    echo ""
    echo "Ready to tag:"
    echo "  git tag v0.1-deterministic-core"
    exit 0
else
    echo -e "${RED}✗ $ERRORS error(s) found${NC}"
    echo ""
    echo "Fix errors before tagging."
    exit 1
fi
