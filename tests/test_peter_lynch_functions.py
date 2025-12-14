"""
Regression test: Ensure all functions in peter_lynch.py have executable code.

This test fails if any function body contains only a docstring.
"""

import ast
import pytest
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def test_peter_lynch_functions_have_executable_code():
    """Test that all functions in peter_lynch.py have executable code (not just docstrings)."""
    peter_lynch_file = Path(__file__).parent.parent / "src" / "agents" / "peter_lynch.py"
    
    with open(peter_lynch_file, 'r') as f:
        content = f.read()
    
    tree = ast.parse(content, peter_lynch_file)
    issues = []
    
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            body = node.body
            # Check if function has only docstring
            if len(body) == 0:
                issues.append(f"Empty function: {node.name} at line {node.lineno}")
            elif len(body) == 1:
                first = body[0]
                # Check if only docstring (Expr with Constant string or Str)
                if isinstance(first, ast.Expr):
                    if isinstance(first.value, ast.Constant):
                        if isinstance(first.value.value, str):
                            issues.append(
                                f"Function with only docstring: {node.name} at line {node.lineno}"
                            )
                    elif isinstance(first.value, ast.Str):
                        issues.append(
                            f"Function with only docstring: {node.name} at line {node.lineno}"
                        )
    
    if issues:
        pytest.fail(
            f"Found {len(issues)} function(s) with only docstrings in peter_lynch.py:\n"
            + "\n".join(f"  - {issue}" for issue in issues)
        )


if __name__ == "__main__":
    test_peter_lynch_functions_have_executable_code()
    print("✓ All functions in peter_lynch.py have executable code")
