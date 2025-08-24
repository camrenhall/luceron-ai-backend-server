#!/usr/bin/env python3
"""
Test script to validate Tavern setup for local container testing
This replaces the original Python test functionality
"""

import os
import subprocess
import sys
from pathlib import Path

def test_environment_variables():
    """Test that environment variables are properly configured"""
    print("🔍 Validating Environment Configuration...")
    
    # Required variables (same as original Python tests)
    required_vars = {
        'TEST_OAUTH_PRIVATE_KEY': 'OAuth private key for authentication'
    }
    
    # Optional variables with defaults
    optional_vars = {
        'AGENT_DB_BASE_URL': 'http://localhost:8080',
        'OAUTH_SERVICE_ID': 'qa_comprehensive_test_service',
        'OAUTH_AUDIENCE': 'luceron-auth-server'
    }
    
    missing_required = []
    for var, desc in required_vars.items():
        if not os.getenv(var):
            missing_required.append(f"{var} ({desc})")
            print(f"  ❌ {var}: Missing")
        else:
            print(f"  ✅ {var}: Set")
    
    for var, default in optional_vars.items():
        value = os.getenv(var, default)
        print(f"  ✅ {var}: {value}")
    
    if missing_required:
        print(f"\n❌ Missing required variables:")
        for var in missing_required:
            print(f"     {var}")
        return False
    
    return True

def test_tavern_functionality():
    """Test that Tavern can execute basic tests"""
    print("\n🧪 Testing Tavern Functionality...")
    
    # Test the working standalone test
    try:
        result = subprocess.run([
            'tavern-ci', 
            'tavern_tests/test_standalone.tavern.yaml', 
            '--no-cov', 
            '-q'
        ], capture_output=True, text=True, cwd=Path(__file__).parent)
        
        if result.returncode == 0:
            print("  ✅ Tavern framework working correctly")
            return True
        else:
            print(f"  ❌ Tavern test failed: {result.stderr}")
            return False
    except FileNotFoundError:
        print("  ❌ Tavern not installed or not in PATH")
        return False

def test_runner_functionality():
    """Test that the Tavern test runner works"""
    print("\n🚀 Testing Tavern Runner...")
    
    try:
        # Test the list functionality
        result = subprocess.run([
            'python', 'run_tavern_tests.py', '--list-tests'
        ], capture_output=True, text=True, cwd=Path(__file__).parent)
        
        if result.returncode == 0 and "tavern.yaml" in result.stdout:
            print("  ✅ Tavern runner working correctly")
            return True
        else:
            print(f"  ❌ Tavern runner failed: {result.stderr}")
            return False
    except Exception as e:
        print(f"  ❌ Runner test error: {e}")
        return False

def main():
    """Main test function"""
    print("🎯 Tavern Replacement Validation for Local Container Testing\n")
    
    print("This validates that Tavern tests can replace the original Python tests")
    print("for testing your locally deployed container at localhost:8080\n")
    
    tests = [
        ("Environment Variables", test_environment_variables),
        ("Tavern Framework", test_tavern_functionality),  
        ("Tavern Runner", test_runner_functionality)
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append(result)
        except Exception as e:
            print(f"  💥 {test_name}: Error - {str(e)}")
            results.append(False)
    
    print(f"\n📊 Test Results:")
    passed = sum(results)
    total = len(results)
    
    print(f"  ✅ Passed: {passed}/{total}")
    print(f"  ❌ Failed: {total - passed}/{total}")
    
    if all(results):
        print("\n🎉 Tavern is ready to replace Python tests!")
        print("\n💡 Next steps:")
        print("  1. Set TEST_OAUTH_PRIVATE_KEY environment variable")
        print("  2. Start your local container at localhost:8080")
        print("  3. Run: python run_tavern_tests.py")
        print("  4. Replace Python tests with Tavern in your CI/CD pipeline")
        return 0
    else:
        print("\n⚠️  Some tests failed. Fix the issues above before proceeding.")
        return 1

if __name__ == '__main__':
    sys.exit(main())