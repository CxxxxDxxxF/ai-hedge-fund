"""
Regression test: Ensure deterministic backtest uses canonical agent registry keys.

This test fails if CORE_AGENTS contains non-canonical keys (e.g., with "_agent" suffix).
"""

import ast
import pytest
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def test_deterministic_backtest_uses_canonical_agent_keys():
    """Test that CORE_AGENTS in deterministic_backtest.py uses canonical registry keys."""
    backtest_file = (
        Path(__file__).parent.parent / "src" / "backtesting" / "deterministic_backtest.py"
    )
    
    with open(backtest_file, 'r') as f:
        content = f.read()
    
    tree = ast.parse(content, backtest_file)
    
    # Expected canonical keys (without "_agent" suffix)
    expected_keys = {
        "warren_buffett",
        "peter_lynch",
        "aswath_damodaran",
        "momentum",
        "mean_reversion",
    }
    
    # Find CORE_AGENTS dictionary definition
    core_agents_keys = None
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "CORE_AGENTS":
                    if isinstance(node.value, ast.Dict):
                        # Extract keys from dictionary
                        core_agents_keys = set()
                        for key_node in node.value.keys:
                            if isinstance(key_node, ast.Constant):
                                core_agents_keys.add(key_node.value)
                            elif isinstance(key_node, ast.Str):
                                core_agents_keys.add(key_node.s)
                        break
    
    if core_agents_keys is None:
        pytest.fail("Could not find CORE_AGENTS dictionary in deterministic_backtest.py")
    
    # Check for non-canonical keys (with "_agent" suffix)
    invalid_keys = {k for k in core_agents_keys if k.endswith("_agent")}
    if invalid_keys:
        pytest.fail(
            f"CORE_AGENTS contains non-canonical keys with '_agent' suffix: {invalid_keys}\n"
            f"Expected canonical keys: {expected_keys}\n"
            f"Found keys: {core_agents_keys}"
        )
    
    # Check that all expected keys are present
    missing_keys = expected_keys - core_agents_keys
    if missing_keys:
        pytest.fail(
            f"CORE_AGENTS missing expected canonical keys: {missing_keys}\n"
            f"Found keys: {core_agents_keys}"
        )
    
    # Check that no unexpected keys are present
    unexpected_keys = core_agents_keys - expected_keys
    if unexpected_keys:
        pytest.fail(
            f"CORE_AGENTS contains unexpected keys: {unexpected_keys}\n"
            f"Expected keys: {expected_keys}"
        )


if __name__ == "__main__":
    test_deterministic_backtest_uses_canonical_agent_keys()
    print("✓ CORE_AGENTS uses only canonical registry keys")
