#!/usr/bin/env python3
"""
Tavern Test Runner
Simplified runner for Tavern-based API tests
"""

import os
import sys
import subprocess
import argparse
from pathlib import Path
from typing import List, Optional

def setup_environment():
    """Setup environment variables for testing (same as original Python tests)"""
    env_vars = {
        # Use same variable names as original tests for consistency
        'AGENT_DB_BASE_URL': os.getenv('AGENT_DB_BASE_URL', 'http://localhost:8080'),
        'TEST_API_BASE_URL': os.getenv('AGENT_DB_BASE_URL', 'http://localhost:8080'),  # Alias for Tavern
        'OAUTH_SERVICE_ID': os.getenv('OAUTH_SERVICE_ID', 'qa_comprehensive_test_service'),
        'TEST_OAUTH_PRIVATE_KEY': os.getenv('TEST_OAUTH_PRIVATE_KEY', ''),
        'OAUTH_AUDIENCE': os.getenv('OAUTH_AUDIENCE', 'luceron-auth-server'),
        'TEST_DATA_PREFIX': 'TAVERN_TEST',
        # Performance thresholds (same as original)
        'CREATE_THRESHOLD': os.getenv('CREATE_THRESHOLD', '3.0'),
        'READ_THRESHOLD': os.getenv('READ_THRESHOLD', '2.0'),
        'UPDATE_THRESHOLD': os.getenv('UPDATE_THRESHOLD', '2.0'),
        'DELETE_THRESHOLD': os.getenv('DELETE_THRESHOLD', '2.0')
    }
    
    # Validate required environment variables
    missing_vars = []
    for var, value in env_vars.items():
        if not value and var in ['TEST_OAUTH_PRIVATE_KEY']:
            missing_vars.append(var)
        os.environ[var] = value
    
    if missing_vars:
        print(f"❌ Missing required environment variables: {', '.join(missing_vars)}")
        print("Please set these variables before running tests")
        print("💡 For local container testing, you need:")
        print("   export TEST_OAUTH_PRIVATE_KEY='your_private_key_here'")
        return False
    
    return True

def run_tavern_tests(test_pattern: Optional[str] = None, verbose: bool = False) -> bool:
    """Run Tavern tests using pytest"""
    
    if not setup_environment():
        return False
    
    # Base pytest command
    cmd = ['pytest', '-v'] if verbose else ['pytest']
    
    # Add Tavern test directory
    tavern_dir = Path(__file__).parent / 'tavern_tests'
    if not tavern_dir.exists():
        print(f"❌ Tavern tests directory not found: {tavern_dir}")
        return False
    
    # Add test pattern if specified
    if test_pattern:
        # Use glob to find matching files
        matching_files = list(tavern_dir.glob(f"*{test_pattern}*.tavern.yaml"))
        if not matching_files:
            print(f"❌ No test files found matching pattern: {test_pattern}")
            return False
        cmd.extend(str(f) for f in matching_files)
    else:
        cmd.append(str(tavern_dir / "*.tavern.yaml"))
    
    # Add additional pytest options for Tavern
    cmd.extend([
        '--tb=short',
        '--strict-config',
        '--strict-markers',
        '--no-cov'  # Disable coverage for Tavern tests
    ])
    
    print(f"🚀 Running Tavern tests...")
    print(f"📁 Test directory: {tavern_dir}")
    print(f"🔍 Test pattern: {test_pattern or 'all'}")
    print(f"🌐 API Base URL: {os.getenv('TEST_API_BASE_URL')}")
    print()
    
    try:
        result = subprocess.run(cmd, cwd=Path(__file__).parent)
        return result.returncode == 0
    except KeyboardInterrupt:
        print("\n⚠️  Tests interrupted by user")
        return False
    except Exception as e:
        print(f"❌ Error running tests: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description='Run Tavern API tests')
    parser.add_argument('--pattern', '-p', 
                       help='Test file pattern to match (e.g., "cases", "documents")')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Run tests in verbose mode')
    parser.add_argument('--list-tests', '-l', action='store_true',
                       help='List available test files')
    
    args = parser.parse_args()
    
    if args.list_tests:
        tavern_dir = Path(__file__).parent / 'tavern_tests'
        if tavern_dir.exists():
            print("📋 Available Tavern test files:")
            for test_file in sorted(tavern_dir.glob('*.tavern.yaml')):
                print(f"  • {test_file.name}")
        else:
            print("❌ No Tavern tests directory found")
        return
    
    success = run_tavern_tests(args.pattern, args.verbose)
    
    if success:
        print("\n✅ All Tavern tests passed!")
        sys.exit(0)
    else:
        print("\n❌ Some Tavern tests failed")
        sys.exit(1)

if __name__ == '__main__':
    main()