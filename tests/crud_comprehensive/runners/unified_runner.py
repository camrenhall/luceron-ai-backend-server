#!/usr/bin/env python3
"""
Unified Test Runner - Consolidates all test execution modes
Replaces run_tests.py + scripts/ci_test_runner.py with single configurable runner
"""

import asyncio
import sys
import time
import argparse
import json
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from datetime import datetime

# Add current directory to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.test_orchestrator import TestOrchestrator
from config import get_config


@dataclass
class RunnerConfig:
    """Configuration for test runner execution"""
    mode: str = "full"  # full, smoke, fast, performance, regression
    parallel: bool = True
    max_workers: int = 2
    timeout: int = 300
    verbose: bool = False
    coverage: bool = False
    output_format: str = "console"  # console, json, junit
    fail_fast: bool = False
    test_pattern: Optional[str] = None
    cleanup_after: bool = True
    performance_tracking: bool = False


class UnifiedTestRunner:
    """Unified test execution with multiple modes and reporting"""
    
    def __init__(self, config: RunnerConfig):
        self.config = config
        self.test_config = get_config()
        self.start_time = time.time()
        self.results = []
        
    async def run_connectivity_test(self) -> bool:
        """Test basic connectivity and authentication"""
        print("🔍 Testing Connectivity & Authentication...")
        
        try:
            orch = TestOrchestrator()
            await orch.setup()
            
            # Test OAuth token generation (skip in test environment)
            import os
            if os.getenv('ENVIRONMENT') == 'test':
                token = "dummy_test_token_12345"
                print(f"   ✅ OAuth token mocked for test environment: {token[:20]}...")
            else:
                token = await orch.rest_client._get_access_token()
                print(f"   ✅ OAuth token obtained: {token[:20]}...")
            
            # Test basic API connectivity
            response, duration = await orch.time_operation(
                "HEALTH_CHECK",
                orch.rest_client.request("GET", "/")
            )
            
            if response.get("_success", False):
                print(f"   ✅ API health check passed ({duration:.2f}s)")
            else:
                print(f"   ⚠️  API health check returned {response.get('_status_code', 'unknown')} (expected issue)")
            
            # Test database connectivity
            await orch.db_validator.connect()
            case_count = await orch.db_validator.count_records("cases")
            print(f"   ✅ Database connected, found {case_count} existing cases")
            
            await orch.teardown()
            return True
            
        except Exception as e:
            print(f"   ❌ Connectivity test failed: {e}")
            return False
    
    def build_pytest_command(self) -> List[str]:
        """Build pytest command based on configuration"""
        cmd = ["pytest"]
        
        # Test selection based on mode
        if self.config.mode == "smoke":
            cmd.extend(["--smoke-only"])
        elif self.config.mode == "fast":
            cmd.extend(["--fast"])
        elif self.config.mode == "performance":
            cmd.extend(["-m", "performance"])
        elif self.config.mode == "regression":
            cmd.extend(["-m", "regression"])
        
        # Parallel execution
        if self.config.parallel:
            cmd.extend(["-n", str(self.config.max_workers)])
            cmd.extend(["--dist=loadfile"])
        
        # Timeout
        cmd.extend([f"--timeout={self.config.timeout}"])
        
        # Verbosity
        if self.config.verbose:
            cmd.extend(["-v"])
        else:
            cmd.extend(["-q"])
        
        # Coverage
        if self.config.coverage:
            cmd.extend([
                "--cov=core",
                "--cov=suites", 
                "--cov=config",
                "--cov-report=xml:coverage.xml",
                "--cov-report=term-missing"
            ])
        
        # Fail fast
        if self.config.fail_fast:
            cmd.extend(["-x", "--maxfail=3"])
        else:
            cmd.extend(["--maxfail=10"])
        
        # Output format
        if self.config.output_format == "junit":
            cmd.extend(["--junit-xml=test-results.xml"])
        elif self.config.output_format == "json":
            cmd.extend(["--json-report", "--json-report-file=test-results.json"])
        
        # Test pattern
        if self.config.test_pattern:
            cmd.extend(["-k", self.config.test_pattern])
        
        # Additional optimizations
        cmd.extend([
            "--tb=short",
            "--strict-markers",
            "--strict-config"
        ])
        
        # Test paths
        if self.config.mode == "full":
            cmd.extend(["suites/", "integration/"])
        else:
            cmd.extend(["suites/"])
        
        return cmd
    
    async def run_pytest_suite(self) -> Dict[str, Any]:
        """Execute pytest suite with current configuration"""
        print(f"\n🧪 Running {self.config.mode.upper()} test suite...")
        
        cmd = self.build_pytest_command()
        
        if self.config.verbose:
            print(f"   Command: {' '.join(cmd)}")
        
        try:
            start_time = time.time()
            
            # Run pytest
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.config.timeout + 60,  # Buffer for cleanup
                cwd=Path(__file__).parent.parent
            )
            
            duration = time.time() - start_time
            
            # Parse output
            output_lines = result.stdout.split('\n') if result.stdout else []
            error_lines = result.stderr.split('\n') if result.stderr else []
            
            # Extract test statistics
            stats = self.parse_pytest_output(output_lines)
            
            return {
                "success": result.returncode == 0,
                "return_code": result.returncode,
                "duration": duration,
                "stats": stats,
                "output": result.stdout,
                "errors": result.stderr,
                "command": cmd
            }
            
        except subprocess.TimeoutExpired:
            print(f"   ❌ Tests timed out after {self.config.timeout}s")
            return {
                "success": False,
                "return_code": -1,
                "duration": self.config.timeout,
                "stats": {"error": "timeout"},
                "output": "",
                "errors": f"Tests timed out after {self.config.timeout}s",
                "command": cmd
            }
        except Exception as e:
            print(f"   ❌ Test execution failed: {e}")
            return {
                "success": False,
                "return_code": -2,
                "duration": 0,
                "stats": {"error": str(e)},
                "output": "",
                "errors": str(e),
                "command": cmd
            }
    
    def parse_pytest_output(self, output_lines: List[str]) -> Dict[str, Any]:
        """Parse pytest output for statistics"""
        stats = {"passed": 0, "failed": 0, "errors": 0, "skipped": 0, "warnings": 0}
        
        for line in output_lines:
            line = line.strip()
            
            # Look for final summary line
            if "failed" in line and "passed" in line:
                # Extract numbers from summary
                parts = line.split()
                for i, part in enumerate(parts):
                    if part == "passed":
                        try:
                            stats["passed"] = int(parts[i-1])
                        except (ValueError, IndexError):
                            pass
                    elif part == "failed":
                        try:
                            stats["failed"] = int(parts[i-1])
                        except (ValueError, IndexError):
                            pass
                    elif part == "error" or part == "errors":
                        try:
                            stats["errors"] = int(parts[i-1])
                        except (ValueError, IndexError):
                            pass
                    elif part == "skipped":
                        try:
                            stats["skipped"] = int(parts[i-1])
                        except (ValueError, IndexError):
                            pass
            
            # Count warnings
            if "warning" in line.lower():
                stats["warnings"] += 1
        
        return stats
    
    async def cleanup_test_data(self):
        """Clean up test data after run"""
        if not self.config.cleanup_after:
            return
            
        print("\n🧹 Cleaning up test data...")
        try:
            orch = TestOrchestrator()
            await orch.setup()
            cleanup_count = await orch.db_validator.cleanup_test_data(self.test_config.test_data_prefix)
            print(f"   ✅ Cleaned up {cleanup_count} test records")
            await orch.teardown()
        except Exception as e:
            print(f"   ⚠️  Cleanup failed: {e}")
    
    def generate_performance_report(self, results: Dict[str, Any]):
        """Generate performance analysis report"""
        if not self.config.performance_tracking:
            return
            
        print("\n📊 Performance Analysis:")
        print(f"   Total Duration: {results['duration']:.2f}s")
        
        if results['stats'].get('passed', 0) > 0:
            avg_test_time = results['duration'] / results['stats']['passed']
            print(f"   Average Test Time: {avg_test_time:.2f}s")
            
            # Performance thresholds
            if avg_test_time > 5.0:
                print(f"   ⚠️  Performance concern: Average test time exceeds 5s")
            else:
                print(f"   ✅ Performance good: Average test time within limits")
    
    def print_summary(self, connectivity_ok: bool, test_results: Dict[str, Any]):
        """Print final summary"""
        total_duration = time.time() - self.start_time
        
        print("\n" + "=" * 60)
        print(f"🏁 {self.config.mode.upper()} Test Suite Complete ({total_duration:.2f}s)")
        print("=" * 60)
        
        # Connectivity
        status = "✅" if connectivity_ok else "❌"
        print(f"{status} Connectivity: {'PASS' if connectivity_ok else 'FAIL'}")
        
        # Test Results
        if test_results['success']:
            print(f"✅ Tests: PASS")
            stats = test_results['stats']
            if 'passed' in stats:
                print(f"   • Passed: {stats['passed']}")
                print(f"   • Failed: {stats['failed']}")
                print(f"   • Skipped: {stats['skipped']}")
        else:
            print(f"❌ Tests: FAIL (code: {test_results['return_code']})")
        
        # Performance
        self.generate_performance_report(test_results)
        
        # Recommendations
        print(f"\n📋 Next Steps:")
        if not connectivity_ok:
            print("   1. Fix connectivity issues before running full tests")
        elif not test_results['success']:
            print("   1. Review failed tests and fix issues")
            print("   2. Re-run with --verbose for detailed output")
        else:
            print("   1. Consider running full regression suite")
            print("   2. Review performance metrics for optimization")
        
        print(f"\n🔧 Configuration Used:")
        print(f"   Mode: {self.config.mode}")
        print(f"   Parallel: {self.config.parallel} (workers: {self.config.max_workers})")
        print(f"   Coverage: {self.config.coverage}")
        print(f"   Timeout: {self.config.timeout}s")
    
    async def run(self) -> int:
        """Execute complete test run"""
        print("=" * 60)
        print(f"🚀 UNIFIED CRUD TEST RUNNER - {self.config.mode.upper()} MODE")
        print("=" * 60)
        
        # Step 1: Connectivity test (unless in fast mode)
        connectivity_ok = True
        if self.config.mode != "fast":
            connectivity_ok = await self.run_connectivity_test()
            if not connectivity_ok and self.config.fail_fast:
                print("\n❌ Connectivity failed, aborting test run")
                return 1
        
        # Step 2: Run test suite
        test_results = await self.run_pytest_suite()
        
        # Step 3: Cleanup
        await self.cleanup_test_data()
        
        # Step 4: Summary
        self.print_summary(connectivity_ok, test_results)
        
        # Return appropriate exit code
        if not connectivity_ok or not test_results['success']:
            return 1
        return 0


def create_argument_parser() -> argparse.ArgumentParser:
    """Create command line argument parser"""
    parser = argparse.ArgumentParser(
        description="Unified CRUD Test Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python runners/unified_runner.py                    # Full test suite
  python runners/unified_runner.py --mode smoke       # Smoke tests only
  python runners/unified_runner.py --mode fast --no-parallel  # Fast tests, no parallel
  python runners/unified_runner.py --coverage --verbose       # Full suite with coverage
  python runners/unified_runner.py --mode performance         # Performance tests only
        """
    )
    
    parser.add_argument(
        "--mode",
        choices=["full", "smoke", "fast", "performance", "regression"],
        default="full",
        help="Test execution mode (default: full)"
    )
    
    parser.add_argument(
        "--no-parallel",
        action="store_true",
        help="Disable parallel test execution"
    )
    
    parser.add_argument(
        "--workers",
        type=int,
        default=2,
        help="Number of parallel workers (default: 2)"
    )
    
    parser.add_argument(
        "--timeout",
        type=int, 
        default=300,
        help="Test timeout in seconds (default: 300)"
    )
    
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Verbose output"
    )
    
    parser.add_argument(
        "--coverage",
        action="store_true",
        help="Enable code coverage reporting"
    )
    
    parser.add_argument(
        "--output",
        choices=["console", "json", "junit"],
        default="console", 
        help="Output format (default: console)"
    )
    
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="Stop on first failure"
    )
    
    parser.add_argument(
        "--pattern",
        help="Test name pattern to match"
    )
    
    parser.add_argument(
        "--no-cleanup",
        action="store_true",
        help="Skip test data cleanup"
    )
    
    parser.add_argument(
        "--performance-tracking",
        action="store_true",
        help="Enable detailed performance analysis"
    )
    
    parser.add_argument(
        "--db-mode",
        choices=["isolated", "production", "hybrid"],
        default="isolated",
        help="Database testing mode (default: isolated)"
    )
    
    parser.add_argument(
        "--db-engine",
        choices=["docker", "embedded"],
        default="docker", 
        help="Test database engine (default: docker)"
    )
    
    parser.add_argument(
        "--no-schema-validation",
        action="store_true",
        help="Skip schema change detection"
    )
    
    return parser


def main():
    """Main entry point"""
    parser = create_argument_parser()
    args = parser.parse_args()
    
    # Set environment variables for database configuration
    import os
    os.environ["DB_MODE"] = args.db_mode
    os.environ["TEST_DB_ENGINE"] = args.db_engine
    os.environ["FAIL_ON_SCHEMA_CHANGES"] = "false" if args.no_schema_validation else "true"
    
    # Build configuration
    config = RunnerConfig(
        mode=args.mode,
        parallel=not args.no_parallel,
        max_workers=args.workers,
        timeout=args.timeout,
        verbose=args.verbose,
        coverage=args.coverage,
        output_format=args.output,
        fail_fast=args.fail_fast,
        test_pattern=args.pattern,
        cleanup_after=not args.no_cleanup,
        performance_tracking=args.performance_tracking
    )
    
    # Run tests
    runner = UnifiedTestRunner(config)
    exit_code = asyncio.run(runner.run())
    
    sys.exit(exit_code)


if __name__ == "__main__":
    main()