#!/usr/bin/env python3
"""
CI/CD optimized test runner for CRUD comprehensive testing suite
Provides different test execution strategies based on CI context
"""

import asyncio
import os
import sys
import subprocess
import time
import json
from pathlib import Path
from typing import Dict, List, Optional
import argparse

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import get_config


class CITestRunner:
    """Optimized test runner for CI/CD environments"""
    
    def __init__(self):
        self.config = get_config()
        self.start_time = time.time()
        self.results = {}
    
    async def run_smoke_tests(self, timeout: int = 300) -> Dict:
        """Run critical smoke tests for fast feedback"""
        print("🚀 Running Smoke Tests (Fast Feedback)")
        
        cmd = [
            "pytest", "-m", "smoke", 
            "-v", "--tb=short",
            f"--timeout={timeout}",
            "--json-report", "--json-report-file=smoke-results.json",
            "--maxfail=3"
        ]
        
        result = await self._run_pytest_command(cmd, "smoke")
        return result
    
    async def run_parallel_tests(self, timeout: int = 600) -> Dict:
        """Run full test suite with parallel execution"""
        print("⚡ Running Parallel Full Test Suite")
        
        # Detect available CPU cores
        import multiprocessing
        num_cores = multiprocessing.cpu_count()
        workers = min(num_cores, 4)  # Cap at 4 to avoid resource contention
        
        cmd = [
            "pytest", "-n", str(workers),
            "-v", "--tb=short", 
            f"--timeout={timeout}",
            "--json-report", "--json-report-file=parallel-results.json",
            "--html=parallel-report.html", "--self-contained-html",
            "--maxfail=5",
            "--dist=loadgroup"  # Group tests by file for better isolation
        ]
        
        result = await self._run_pytest_command(cmd, "parallel")
        return result
    
    async def run_regression_tests(self, timeout: int = 900) -> Dict:
        """Run comprehensive regression test suite"""
        print("🧪 Running Regression Test Suite")
        
        # Run different test categories in sequence for better resource management
        categories = ["crud", "integration", "performance"]
        results = {}
        
        for category in categories:
            print(f"   Running {category} tests...")
            cmd = [
                "pytest", "-m", category,
                "-v", "--tb=short",
                f"--timeout={timeout // len(categories)}",
                "--json-report", f"--json-report-file=regression-{category}-results.json",
                "--html", f"regression-{category}-report.html", "--self-contained-html"
            ]
            
            result = await self._run_pytest_command(cmd, f"regression-{category}")
            results[category] = result
        
        return results
    
    async def run_performance_benchmarks(self) -> Dict:
        """Run performance benchmarking tests"""
        print("📊 Running Performance Benchmarks")
        
        cmd = [
            "pytest", "-m", "performance",
            "--benchmark-only",
            "--benchmark-json=benchmark-results.json",
            "--benchmark-sort=mean",
            "--benchmark-min-rounds=3"
        ]
        
        result = await self._run_pytest_command(cmd, "benchmarks")
        return result
    
    async def _run_pytest_command(self, cmd: List[str], test_type: str) -> Dict:
        """Execute pytest command and capture results"""
        start_time = time.time()
        
        try:
            # Set environment variables
            env = os.environ.copy()
            env.update({
                "PYTHONPATH": str(Path.cwd()),
                "CI": "true" if os.getenv("CI") else "false"
            })
            
            print(f"   Command: {' '.join(cmd)}")
            
            # Run pytest
            process = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=cmd[cmd.index("--timeout") + 1] if "--timeout" in cmd else 600,
                env=env,
                cwd=Path.cwd()
            )
            
            duration = time.time() - start_time
            
            # Parse results
            result = {
                "test_type": test_type,
                "duration": duration,
                "return_code": process.returncode,
                "success": process.returncode == 0,
                "stdout": process.stdout,
                "stderr": process.stderr
            }
            
            # Try to load JSON report if available
            json_file = f"{test_type}-results.json"
            if os.path.exists(json_file):
                try:
                    with open(json_file, 'r') as f:
                        result["detailed_results"] = json.load(f)
                except Exception as e:
                    print(f"   Warning: Could not parse JSON results: {e}")
            
            # Print summary
            if result["success"]:
                print(f"   ✅ {test_type} tests completed successfully in {duration:.2f}s")
            else:
                print(f"   ❌ {test_type} tests failed after {duration:.2f}s")
                print(f"   Error: {process.stderr}")
            
            return result
            
        except subprocess.TimeoutExpired:
            duration = time.time() - start_time
            print(f"   ⏰ {test_type} tests timed out after {duration:.2f}s")
            return {
                "test_type": test_type,
                "duration": duration,
                "success": False,
                "error": "timeout"
            }
        except Exception as e:
            duration = time.time() - start_time
            print(f"   💥 {test_type} tests failed with exception: {e}")
            return {
                "test_type": test_type,
                "duration": duration,
                "success": False,
                "error": str(e)
            }
    
    def generate_summary_report(self) -> Dict:
        """Generate comprehensive test execution summary"""
        total_duration = time.time() - self.start_time
        
        summary = {
            "execution_time": total_duration,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
            "environment": {
                "ci": os.getenv("CI", "false"),
                "python_version": sys.version,
                "platform": sys.platform
            },
            "results": self.results,
            "overall_success": all(r.get("success", False) for r in self.results.values()),
            "total_tests_run": sum(
                r.get("detailed_results", {}).get("summary", {}).get("total", 0) 
                for r in self.results.values()
            )
        }
        
        return summary


async def main():
    """Main CI test execution function"""
    parser = argparse.ArgumentParser(description="CI/CD Test Runner")
    parser.add_argument("--mode", choices=["smoke", "parallel", "regression", "benchmarks", "all"], 
                       default="parallel", help="Test execution mode")
    parser.add_argument("--timeout", type=int, default=600, help="Test timeout in seconds")
    parser.add_argument("--output", default="test-results.json", help="Output file for results")
    
    args = parser.parse_args()
    
    runner = CITestRunner()
    
    print("🚀 Starting CI/CD Test Execution")
    print(f"   Mode: {args.mode}")
    print(f"   Timeout: {args.timeout}s")
    print("="*50)
    
    try:
        # Execute tests based on mode
        if args.mode == "smoke":
            result = await runner.run_smoke_tests(timeout=args.timeout)
            runner.results["smoke"] = result
        
        elif args.mode == "parallel":
            result = await runner.run_parallel_tests(timeout=args.timeout)
            runner.results["parallel"] = result
        
        elif args.mode == "regression":
            results = await runner.run_regression_tests(timeout=args.timeout)
            runner.results.update(results)
        
        elif args.mode == "benchmarks":
            result = await runner.run_performance_benchmarks()
            runner.results["benchmarks"] = result
        
        elif args.mode == "all":
            # Run smoke tests first for fast feedback
            smoke_result = await runner.run_smoke_tests(timeout=300)
            runner.results["smoke"] = smoke_result
            
            if smoke_result.get("success"):
                # Run parallel tests if smoke tests pass
                parallel_result = await runner.run_parallel_tests(timeout=args.timeout)
                runner.results["parallel"] = parallel_result
            else:
                print("❌ Smoke tests failed, skipping further tests")
        
        # Generate summary report
        summary = runner.generate_summary_report()
        
        # Save results
        with open(args.output, 'w') as f:
            json.dump(summary, f, indent=2)
        
        # Print final summary
        print("="*50)
        print("🏁 Test Execution Complete")
        print(f"   Total Duration: {summary['execution_time']:.2f}s")
        print(f"   Overall Success: {'✅' if summary['overall_success'] else '❌'}")
        print(f"   Results saved to: {args.output}")
        
        # Exit with appropriate code
        sys.exit(0 if summary['overall_success'] else 1)
        
    except Exception as e:
        print(f"💥 Test execution failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())