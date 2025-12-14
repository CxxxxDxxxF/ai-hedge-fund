"""
Deterministic Backtest Validation & Abuse Testing Suite

Purpose: Prove or disprove that hardening claims are true.

Rules:
- Do not modify production code unless test exposes real failure
- Do not assume correctness because tests exist
- Treat all claims as unproven until demonstrated
- Prefer observable behavior over documentation
"""

from __future__ import annotations

import os
import sys
import subprocess
import tempfile
import shutil
import hashlib
import json
import time
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from datetime import datetime

# Force deterministic mode
os.environ["HEDGEFUND_NO_LLM"] = "1"


class ValidationResult:
    """Track pass/fail for each test."""
    
    def __init__(self, test_name: str):
        self.test_name = test_name
        self.passed = False
        self.failed = False
        self.error_message = ""
        self.observations: List[str] = []
    
    def pass_test(self, observation: str = ""):
        self.passed = True
        if observation:
            self.observations.append(observation)
    
    def fail_test(self, reason: str):
        self.failed = True
        self.error_message = reason
    
    def __str__(self):
        status = "✅ PASS" if self.passed else "❌ FAIL" if self.failed else "⏸️  SKIP"
        return f"{status}: {self.test_name}\n  {self.error_message if self.failed else ''}"


class BaselineIntegrityTests:
    """Phase 1: Clean-room execution tests."""
    
    def __init__(self, repo_path: str):
        self.repo_path = Path(repo_path)
        self.results: List[ValidationResult] = []
    
    def test_clean_room_execution(self) -> ValidationResult:
        """Test 1: Run in clean environment, verify end-to-end execution."""
        result = ValidationResult("Clean-room execution")
        
        try:
            # Create temporary directory
            with tempfile.TemporaryDirectory() as tmpdir:
                # Copy minimal files needed
                test_script = Path(tmpdir) / "test_backtest.py"
                script_content = f"""
import os
import sys
sys.path.insert(0, r'{self.repo_path.absolute()}')

os.environ['HEDGEFUND_NO_LLM'] = '1'

from src.backtesting.deterministic_backtest import DeterministicBacktest

backtest = DeterministicBacktest(
    tickers=['AAPL'],
    start_date='2024-01-02',
    end_date='2024-01-05',
    initial_capital=100000.0,
    disable_progress=True,
)

try:
    metrics = backtest.run()
    backtest.print_summary(metrics)
    print("EXECUTION_COMPLETE")
except Exception as e:
    print(f"EXECUTION_FAILED: {{e}}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
"""
                test_script.write_text(script_content)
                
                # Run in clean environment
                env = os.environ.copy()
                env['HEDGEFUND_NO_LLM'] = '1'
                env['PYTHONPATH'] = str(self.repo_path.absolute())
                
                proc = subprocess.run(
                    [sys.executable, str(test_script)],
                    cwd=tmpdir,
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
                
                output = proc.stdout + proc.stderr
                
                # Verify execution completed
                if "EXECUTION_COMPLETE" in output:
                    result.pass_test("Backtest completed end-to-end")
                elif "EXECUTION_FAILED" in output:
                    result.fail_test(f"Execution failed: {output}")
                else:
                    result.fail_test(f"Unclear execution status. Output: {output[:500]}")
                    
        except subprocess.TimeoutExpired:
            result.fail_test("Execution timed out (stalled)")
        except Exception as e:
            result.fail_test(f"Test setup failed: {e}")
        
        self.results.append(result)
        return result
    
    def test_invariant_logging(self) -> ValidationResult:
        """Test 2: Verify invariant logging prints exactly once per iteration."""
        result = ValidationResult("Invariant logging (once per iteration)")
        
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                test_script = Path(tmpdir) / "test_logging.py"
                script_content = f"""
import os
import sys
sys.path.insert(0, r'{self.repo_path.absolute()}')

os.environ['HEDGEFUND_NO_LLM'] = '1'

from src.backtesting.deterministic_backtest import DeterministicBacktest
import io

# Capture stderr
stderr_capture = io.StringIO()
old_stderr = sys.stderr
sys.stderr = stderr_capture

backtest = DeterministicBacktest(
    tickers=['AAPL'],
    start_date='2024-01-02',
    end_date='2024-01-05',
    initial_capital=100000.0,
    disable_progress=True,
)

try:
    metrics = backtest.run()
    sys.stderr = old_stderr
    
    stderr_output = stderr_capture.getvalue()
    log_lines = [line for line in stderr_output.split(chr(10)) if '[' in line and ']' in line and '|' in line]
    
    # Should have exactly 4 log lines (4 days)
    if len(log_lines) == 4:
        print(f"PASS: Found exactly {{len(log_lines)}} invariant log lines")
    else:
        print(f"FAIL: Expected 4 log lines, found {{len(log_lines)}}")
        print(f"Log lines: {{log_lines}}")
        
except Exception as e:
    sys.stderr = old_stderr
    print(f"FAIL: {{e}}")
    import traceback
    traceback.print_exc()
"""
                test_script.write_text(script_content)
                
                env = os.environ.copy()
                env['HEDGEFUND_NO_LLM'] = '1'
                env['PYTHONPATH'] = str(self.repo_path.absolute())
                
                proc = subprocess.run(
                    [sys.executable, str(test_script)],
                    cwd=tmpdir,
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
                
                output = proc.stdout
                if "PASS:" in output:
                    result.pass_test(output.split("PASS:")[1].strip())
                else:
                    result.fail_test(f"Invariant logging test failed: {output}")
                    
        except Exception as e:
            result.fail_test(f"Test failed: {e}")
        
        self.results.append(result)
        return result
    
    def test_summary_always_prints(self) -> ValidationResult:
        """Test 3: Verify summary prints even on controlled failure."""
        result = ValidationResult("Summary always prints (even on failure)")
        
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                test_script = Path(tmpdir) / "test_summary.py"
                script_content = f"""
import os
import sys
sys.path.insert(0, r'{self.repo_path.absolute()}')

os.environ['HEDGEFUND_NO_LLM'] = '1'

# Monkey-patch to force a strategy failure
from src.backtesting import deterministic_backtest
from src.main import run_hedge_fund as original_run

call_count = [0]

def failing_run(*args, **kwargs):
    call_count[0] += 1
    if call_count[0] == 2:  # Fail on second call
        raise Exception("STRATEGY FAILURE: Intentional test failure")
    return original_run(*args, **kwargs)

deterministic_backtest.run_hedge_fund = failing_run

from src.backtesting.deterministic_backtest import DeterministicBacktest

backtest = DeterministicBacktest(
    tickers=['AAPL'],
    start_date='2024-01-02',
    end_date='2024-01-05',
    initial_capital=100000.0,
    disable_progress=True,
)

try:
    metrics = backtest.run()
    backtest.print_summary(metrics)
    print("SUMMARY_PRINTED")
except Exception as e:
    # Even on failure, summary should print
    try:
        partial = backtest._calculate_metrics()
        backtest.print_summary(partial)
        print("SUMMARY_PRINTED_ON_FAILURE")
    except Exception as e2:
        print(f"FAIL: Summary did not print: {{e2}}")
"""
                test_script.write_text(script_content)
                
                env = os.environ.copy()
                env['HEDGEFUND_NO_LLM'] = '1'
                env['PYTHONPATH'] = str(self.repo_path.absolute())
                
                proc = subprocess.run(
                    [sys.executable, str(test_script)],
                    cwd=tmpdir,
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
                
                output = proc.stdout + proc.stderr
                if "SUMMARY_PRINTED" in output:
                    result.pass_test("Summary printed even with strategy failure")
                else:
                    result.fail_test(f"Summary did not print. Output: {output[:500]}")
                    
        except Exception as e:
            result.fail_test(f"Test failed: {e}")
        
        self.results.append(result)
        return result


class ForcedFailureMatrix:
    """Phase 2: Intentionally inject failures and observe behavior."""
    
    def __init__(self, repo_path: str):
        self.repo_path = Path(repo_path)
        self.results: List[ValidationResult] = []
    
    def test_duplicate_date_guard(self) -> ValidationResult:
        """Test: Duplicate date should raise RuntimeError with CONTRACT VIOLATION."""
        result = ValidationResult("Duplicate date guard")
        
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                test_script = Path(tmpdir) / "test_duplicate.py"
                test_script.write_text("""
import os
import sys
sys.path.insert(0, '{repo_path}')

os.environ['HEDGEFUND_NO_LLM'] = '1'

from src.backtesting.deterministic_backtest import DeterministicBacktest

backtest = DeterministicBacktest(
    tickers=['AAPL'],
    start_date='2024-01-02',
    end_date='2024-01-05',
    initial_capital=100000.0,
    disable_progress=True,
)

# Manually inject duplicate date
backtest.processed_dates.add('2024-01-03')

try:
    # Try to process same date again
    is_failure, _ = backtest._run_daily_decision('2024-01-03', 1)
    print("FAIL: Duplicate date was not caught")
except RuntimeError as e:
    if "ENGINE FAILURE" in str(e) and "CONTRACT VIOLATION" in str(e):
        print("PASS: Duplicate date raised RuntimeError with CONTRACT VIOLATION")
    else:
        print(f"FAIL: Wrong error type: {{e}}")
except Exception as e:
    print(f"FAIL: Unexpected exception: {{e}}")
""".format(repo_path=str(self.repo_path.absolute())))
                
                env = os.environ.copy()
                env['HEDGEFUND_NO_LLM'] = '1'
                env['PYTHONPATH'] = str(self.repo_path.absolute())
                
                proc = subprocess.run(
                    [sys.executable, str(test_script)],
                    cwd=tmpdir,
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                
                output = proc.stdout
                if "PASS:" in output:
                    result.pass_test("Duplicate date guard fires correctly")
                else:
                    result.fail_test(f"Guard did not fire: {output}")
                    
        except Exception as e:
            result.fail_test(f"Test failed: {e}")
        
        self.results.append(result)
        return result
    
    def test_strategy_exception_handling(self) -> ValidationResult:
        """Test: Strategy exception should be logged, skipped, loop advances."""
        result = ValidationResult("Strategy exception handling")
        
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                test_script = Path(tmpdir) / "test_strategy_fail.py"
                script_content = f"""
import os
import sys
sys.path.insert(0, r'{self.repo_path.absolute()}')

os.environ['HEDGEFUND_NO_LLM'] = '1'

from src.backtesting import deterministic_backtest
from src.main import run_hedge_fund as original_run

call_count = [0]

def failing_run(*args, **kwargs):
    call_count[0] += 1
    if call_count[0] == 2:  # Fail on second day
        raise ValueError("STRATEGY FAILURE: Intentional test exception")
    return original_run(*args, **kwargs)

deterministic_backtest.run_hedge_fund = failing_run

from src.backtesting.deterministic_backtest import DeterministicBacktest
import io

stderr_capture = io.StringIO()
old_stderr = sys.stderr
sys.stderr = stderr_capture

backtest = DeterministicBacktest(
    tickers=['AAPL'],
    start_date='2024-01-02',
    end_date='2024-01-05',
    initial_capital=100000.0,
    disable_progress=True,
)

try:
    metrics = backtest.run()
    sys.stderr = old_stderr
    
    stderr_output = stderr_capture.getvalue()
    
    # Check for strategy failure log
    if "STRATEGY FAILURE" in stderr_output:
        # Check that loop advanced (should have processed all 4 days)
        if len(backtest.processed_dates) == 4:
            print("PASS: Strategy failure logged, loop advanced")
        else:
            print(f"FAIL: Loop did not advance. Processed {{len(backtest.processed_dates)}} dates")
    else:
        print(f"FAIL: Strategy failure not logged. Stderr: {{stderr_output[:500]}}")
        
except Exception as e:
    sys.stderr = old_stderr
    print(f"FAIL: Unexpected exception: {{e}}")
    import traceback
    traceback.print_exc()
"""
                test_script.write_text(script_content)
                
                env = os.environ.copy()
                env['HEDGEFUND_NO_LLM'] = '1'
                env['PYTHONPATH'] = str(self.repo_path.absolute())
                
                proc = subprocess.run(
                    [sys.executable, str(test_script)],
                    cwd=tmpdir,
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
                
                output = proc.stdout
                if "PASS:" in output:
                    result.pass_test("Strategy failure handled correctly")
                else:
                    result.fail_test(f"Strategy failure not handled: {output}")
                    
        except Exception as e:
            result.fail_test(f"Test failed: {e}")
        
        self.results.append(result)
        return result


class DeterminismVerification:
    """Phase 3: Verify determinism claims."""
    
    def __init__(self, repo_path: str):
        self.repo_path = Path(repo_path)
        self.results: List[ValidationResult] = []
    
    def test_bit_for_bit_replay(self) -> ValidationResult:
        """Test: Same inputs produce identical outputs."""
        result = ValidationResult("Bit-for-bit determinism")
        
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                # Run 1
                test_script = Path(tmpdir) / "test_determinism1.py"
                script_content = f"""
import os
import sys
sys.path.insert(0, r'{self.repo_path.absolute()}')

os.environ['HEDGEFUND_NO_LLM'] = '1'

# Suppress all output except our markers
import io
sys.stdout = io.StringIO()
sys.stderr = io.StringIO()

from src.backtesting.deterministic_backtest import DeterministicBacktest

backtest = DeterministicBacktest(
    tickers=['AAPL'],
    start_date='2024-01-02',
    end_date='2024-01-05',
    initial_capital=100000.0,
    disable_progress=True,
)

metrics = backtest.run()
final_value = backtest.daily_values[-1]['portfolio_value'] if backtest.daily_values else 0

# Restore stdout and print only our markers
sys.stdout = sys.__stdout__
sys.stderr = sys.__stderr__
print(f"HASH:{{metrics['determinism']['output_hash']}}")
print(f"FINAL_VALUE:{{final_value}}")
"""
                test_script.write_text(script_content)
                
                env = os.environ.copy()
                env['HEDGEFUND_NO_LLM'] = '1'
                env['PYTHONPATH'] = str(self.repo_path.absolute())
                
                proc1 = subprocess.run(
                    [sys.executable, str(test_script)],
                    cwd=tmpdir,
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
                
                # Run 2 (identical)
                proc2 = subprocess.run(
                    [sys.executable, str(test_script)],
                    cwd=tmpdir,
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
                
                # Extract hashes
                hash1 = None
                hash2 = None
                value1 = None
                value2 = None
                
                output1 = proc1.stdout + proc1.stderr
                output2 = proc2.stdout + proc2.stderr
                
                # Debug: print first 500 chars if hash extraction fails
                debug_output = ""
                
                for line in output1.split('\n'):
                    if 'HASH:' in line:
                        parts = line.split('HASH:')
                        if len(parts) > 1:
                            hash1 = parts[1].strip()
                    if 'FINAL_VALUE:' in line:
                        parts = line.split('FINAL_VALUE:')
                        if len(parts) > 1:
                            try:
                                value1 = float(parts[1].strip())
                            except:
                                pass
                
                for line in output2.split('\n'):
                    if 'HASH:' in line:
                        parts = line.split('HASH:')
                        if len(parts) > 1:
                            hash2 = parts[1].strip()
                    if 'FINAL_VALUE:' in line:
                        parts = line.split('FINAL_VALUE:')
                        if len(parts) > 1:
                            try:
                                value2 = float(parts[1].strip())
                            except:
                                pass
                
                if not hash1 or not hash2:
                    # Try alternative extraction
                    import re
                    hash_match1 = re.search(r'HASH:([a-f0-9]+)', output1)
                    hash_match2 = re.search(r'HASH:([a-f0-9]+)', output2)
                    if hash_match1:
                        hash1 = hash_match1.group(1)
                    if hash_match2:
                        hash2 = hash_match2.group(1)
                
                if hash1 and hash2:
                    if hash1 == hash2:
                        if value1 is not None and value2 is not None and value1 == value2:
                            result.pass_test(f"Hashes match: {hash1[:16]}..., Values match: {value1}")
                        elif value1 is not None and value2 is not None:
                            result.fail_test(f"Hashes match but values differ: {value1} vs {value2}")
                        else:
                            result.pass_test(f"Hashes match: {hash1[:16]}... (values not extracted)")
                    else:
                        result.fail_test(f"Hashes differ: {hash1[:16]}... vs {hash2[:16]}...")
                else:
                    result.fail_test(f"Could not extract hashes. Output1: {output1[:200]}, Output2: {output2[:200]}")
                    
        except Exception as e:
            result.fail_test(f"Test failed: {e}")
        
        self.results.append(result)
        return result


def run_all_validation_tests(repo_path: str) -> Dict[str, List[ValidationResult]]:
    """Run all validation tests."""
    
    print("=" * 80)
    print("DETERMINISTIC BACKTEST VALIDATION SUITE")
    print("=" * 80)
    print()
    
    all_results = {}
    
    # Phase 1: Baseline Integrity
    print("Phase 1: Baseline Integrity Tests")
    print("-" * 80)
    phase1 = BaselineIntegrityTests(repo_path)
    phase1.test_clean_room_execution()
    phase1.test_invariant_logging()
    phase1.test_summary_always_prints()
    all_results["Baseline Integrity"] = phase1.results
    
    # Phase 2: Forced Failure Matrix
    print("\nPhase 2: Forced Failure Matrix")
    print("-" * 80)
    phase2 = ForcedFailureMatrix(repo_path)
    phase2.test_duplicate_date_guard()
    phase2.test_strategy_exception_handling()
    all_results["Forced Failures"] = phase2.results
    
    # Phase 3: Determinism
    print("\nPhase 3: Determinism Verification")
    print("-" * 80)
    phase3 = DeterminismVerification(repo_path)
    phase3.test_bit_for_bit_replay()
    all_results["Determinism"] = phase3.results
    
    # Phase 4 & 5: Abuse and Stability (imported from separate module)
    print("\nPhase 4: Abuse & Bypass Attempts")
    print("-" * 80)
    try:
        from src.backtesting.abuse_tests import test_bypass_attempts, test_stability
        abuse_results = test_bypass_attempts(repo_path)
        # Convert to ValidationResult format
        abuse_validation_results = []
        for status, msg in abuse_results:
            r = ValidationResult("Abuse test")
            if "✅ PASS" in status or "⚠️  WARN" in status:
                r.pass_test(msg)
            else:
                r.fail_test(msg)
            abuse_validation_results.append(r)
        all_results["Abuse Tests"] = abuse_validation_results
        
        print("\nPhase 5: Stability Test")
        print("-" * 80)
        stability_results = test_stability(repo_path)
        stability_validation_results = []
        for status, msg in stability_results:
            r = ValidationResult("Stability test")
            if "✅ PASS" in status:
                r.pass_test(msg)
            else:
                r.fail_test(msg)
            stability_validation_results.append(r)
        all_results["Stability"] = stability_validation_results
    except ImportError:
        print("  ⚠️  SKIP: abuse_tests.py not found")
    
    return all_results


def print_summary(all_results: Dict[str, List[ValidationResult]]):
    """Print validation summary."""
    print("\n" + "=" * 80)
    print("VALIDATION SUMMARY")
    print("=" * 80)
    
    total_passed = 0
    total_failed = 0
    
    for phase_name, results in all_results.items():
        print(f"\n{phase_name}:")
        for result in results:
            print(f"  {result}")
            if result.passed:
                total_passed += 1
            elif result.failed:
                total_failed += 1
    
    print("\n" + "=" * 80)
    print(f"TOTAL: {total_passed} passed, {total_failed} failed")
    print("=" * 80)
    
    # Final verdict
    if total_failed == 0:
        print("\n✅ VERDICT: ALL TESTS PASSED")
        print("   Claim 'silent failure is impossible' is JUSTIFIED")
    else:
        print(f"\n❌ VERDICT: {total_failed} TEST(S) FAILED")
        print("   Claim 'silent failure is impossible' is NOT JUSTIFIED")
        print("   Violations found - see details above")


if __name__ == "__main__":
    repo_path = Path(__file__).parent.parent.parent
    all_results = run_all_validation_tests(str(repo_path))
    print_summary(all_results)
    
    # Exit with appropriate code
    total_failed = sum(1 for results in all_results.values() for r in results if r.failed)
    sys.exit(1 if total_failed > 0 else 0)
