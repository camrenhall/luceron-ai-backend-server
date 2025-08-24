#!/usr/bin/env python3
"""
Standalone REST API Test Runner
Runs Tavern tests without dependency on pytest infrastructure
"""

import os
import sys
import subprocess
import argparse
from pathlib import Path
from typing import List, Optional


def validate_environment() -> bool:
    """Validate required environment variables"""
    required_vars = ['TEST_OAUTH_PRIVATE_KEY']
    missing_vars = []
    
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        print("❌ Missing required environment variables:")
        for var in missing_vars:
            print(f"   {var}")
        print("\n💡 Set the required variables:")
        print("   export TEST_OAUTH_PRIVATE_KEY='your_private_key_here'")
        return False
    
    print("✅ Environment configuration valid")
    return True


def get_test_files(pattern: Optional[str] = None) -> List[Path]:
    """Get list of test files, optionally filtered by pattern"""
    test_dir = Path(__file__).parent
    
    if pattern:
        test_files = list(test_dir.glob(f"*{pattern}*.tavern.yaml"))
    else:
        test_files = list(test_dir.glob("test_*.tavern.yaml"))
    
    return sorted(test_files)


def prepare_test_environment():
    """Prepare environment variables for JWT token generation"""
    import os
    import auth_helpers
    
    # Generate JWT token if possible and inject as environment variable
    try:
        jwt_token = auth_helpers.generate_jwt_token()
        os.environ['TAVERN_JWT_TOKEN'] = jwt_token
        print("   🔑 JWT token generated and injected")
    except Exception as e:
        print(f"   ⚠️  JWT generation failed: {e}")
        os.environ['TAVERN_JWT_TOKEN'] = 'test_placeholder_token'


def create_temp_test_file(original_file: Path) -> Path:
    """Create a temporary test file with environment variable substitutions"""
    import os
    
    # Read original file
    content = original_file.read_text()
    
    # Remove include dependency
    content = content.replace('includes:\n  - !include config.yaml\n', '')
    
    # Replace template variables with actual values
    replacements = {
        '{api_base_url}': os.getenv('AGENT_DB_BASE_URL', 'http://localhost:8080'),
        '{oauth_service_id}': os.getenv('OAUTH_SERVICE_ID', 'qa_comprehensive_test_service'),
        '{oauth_audience}': os.getenv('OAUTH_AUDIENCE', 'luceron-auth-server'),
        '{test_data_prefix}': os.getenv('TEST_DATA_PREFIX', 'REST_TEST'),
        '{jwt_token}': os.getenv('TAVERN_JWT_TOKEN', 'test_placeholder_token')
    }
    
    for placeholder, value in replacements.items():
        content = content.replace(placeholder, value)
    
    # Create temp file in same directory
    temp_file = original_file.parent / f"temp_{original_file.name}"
    temp_file.write_text(content)
    return temp_file


def run_tavern_tests(test_files: List[Path], verbose: bool = False) -> bool:
    """Run Tavern tests using tavern-ci command with environment setup"""
    if not test_files:
        print("❌ No test files found")
        return False
    
    print(f"🚀 Running {len(test_files)} test file(s)...")
    
    # Prepare environment
    prepare_test_environment()
    
    all_passed = True
    temp_files = []
    
    try:
        for test_file in test_files:
            print(f"\n📋 Running {test_file.name}...")
            
            # Create temp file with substitutions
            temp_file = create_temp_test_file(test_file)
            temp_files.append(temp_file)
            
            # Try tavern-ci command
            cmd = ['tavern-ci', str(temp_file)]
            if not verbose:
                cmd.extend(['-q'])
            
            try:
                result = subprocess.run(
                    cmd,
                    cwd=Path(__file__).parent,
                    capture_output=not verbose,
                    text=True
                )
                
                if result.returncode == 0:
                    print(f"   ✅ {test_file.name} - PASSED")
                else:
                    print(f"   ❌ {test_file.name} - FAILED")
                    if not verbose and result.stderr:
                        print(f"      Error: {result.stderr.strip()}")
                    if not verbose and result.stdout:
                        print(f"      Output: {result.stdout.strip()}")
                    all_passed = False
                    
            except FileNotFoundError:
                print(f"   ❌ {test_file.name} - FAILED (tavern-ci not found)")
                all_passed = False
            except Exception as e:
                print(f"   ❌ Error running {test_file.name}: {e}")
                all_passed = False
    
    finally:
        # Cleanup temp files
        for temp_file in temp_files:
            if temp_file.exists():
                temp_file.unlink()
    
    return all_passed


def list_test_files():
    """List available test files"""
    test_files = get_test_files()
    
    if not test_files:
        print("❌ No test files found")
        return
    
    print(f"📋 Available test files ({len(test_files)}):")
    for test_file in test_files:
        print(f"   • {test_file.name}")


def show_environment_info():
    """Show current environment configuration"""
    print("🔍 Environment Configuration:")
    
    env_vars = {
        'AGENT_DB_BASE_URL': 'http://localhost:8080',
        'OAUTH_SERVICE_ID': 'qa_comprehensive_test_service',
        'OAUTH_AUDIENCE': 'luceron-auth-server',
        'TEST_DATA_PREFIX': 'REST_TEST'
    }
    
    for var, default in env_vars.items():
        value = os.getenv(var, default)
        print(f"   {var}: {value}")
    
    oauth_key = os.getenv('TEST_OAUTH_PRIVATE_KEY')
    if oauth_key:
        print(f"   TEST_OAUTH_PRIVATE_KEY: Set ({len(oauth_key)} characters)")
    else:
        print("   TEST_OAUTH_PRIVATE_KEY: ❌ NOT SET")


def main():
    parser = argparse.ArgumentParser(description='Run REST API Database Tests')
    parser.add_argument('--pattern', '-p',
                       help='Filter tests by pattern (e.g., "cases", "documents")')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Run tests in verbose mode')
    parser.add_argument('--list', '-l', action='store_true',
                       help='List available test files')
    parser.add_argument('--env', '-e', action='store_true',
                       help='Show environment configuration')
    
    args = parser.parse_args()
    
    if args.list:
        list_test_files()
        return 0
    
    if args.env:
        show_environment_info()
        return 0
    
    print("🎯 REST API Database Tests")
    print("=" * 50)
    
    # Validate environment
    if not validate_environment():
        return 1
    
    # Show environment info
    show_environment_info()
    print()
    
    # Get and run tests
    test_files = get_test_files(args.pattern)
    
    if not test_files:
        if args.pattern:
            print(f"❌ No test files found matching pattern: {args.pattern}")
        else:
            print("❌ No test files found")
        return 1
    
    success = run_tavern_tests(test_files, args.verbose)
    
    print("\n" + "=" * 50)
    if success:
        print("🎉 All tests PASSED!")
        return 0
    else:
        print("❌ Some tests FAILED")
        return 1


if __name__ == '__main__':
    sys.exit(main())