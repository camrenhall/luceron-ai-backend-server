#!/usr/bin/env python3
"""
Tavern Setup Verification
Quick validation that Tavern configuration is correct
"""

import os
import sys
from pathlib import Path

def check_environment():
    """Check required environment variables"""
    required_vars = ['TEST_OAUTH_PRIVATE_KEY']
    optional_vars = {
        'TEST_API_BASE_URL': 'http://localhost:8080',
        'OAUTH_SERVICE_ID': 'qa_comprehensive_test_service',
        'OAUTH_AUDIENCE': 'luceron-auth-server'
    }
    
    print("🔍 Checking Environment Variables...")
    
    missing_required = []
    for var in required_vars:
        value = os.getenv(var)
        if not value:
            missing_required.append(var)
            print(f"  ❌ {var}: Not set (REQUIRED)")
        else:
            print(f"  ✅ {var}: Set ({len(value)} characters)")
    
    for var, default in optional_vars.items():
        value = os.getenv(var, default)
        print(f"  ✅ {var}: {value}")
    
    return len(missing_required) == 0

def check_dependencies():
    """Check required Python packages"""
    print("\n📦 Checking Python Dependencies...")
    
    required_packages = [
        ('tavern', 'Tavern testing framework'),
        ('pytest', 'Testing framework'),
        ('jwt', 'JWT token handling'),
        ('cryptography', 'Cryptographic functions'),
    ]
    
    missing_packages = []
    
    for package, description in required_packages:
        try:
            __import__(package)
            print(f"  ✅ {package}: Available")
        except ImportError:
            missing_packages.append(package)
            print(f"  ❌ {package}: Missing ({description})")
    
    return len(missing_packages) == 0

def check_files():
    """Check required configuration files"""
    print("\n📁 Checking Configuration Files...")
    
    base_dir = Path(__file__).parent
    required_files = [
        ('tavern_config.yaml', 'Tavern global configuration'),
        ('tavern_helpers.py', 'Helper functions'),
        ('run_tavern_tests.py', 'Test runner script'),
        ('tavern_tests/', 'Test files directory')
    ]
    
    missing_files = []
    
    for file_path, description in required_files:
        full_path = base_dir / file_path
        if full_path.exists():
            print(f"  ✅ {file_path}: Found")
        else:
            missing_files.append(file_path)
            print(f"  ❌ {file_path}: Missing ({description})")
    
    return len(missing_files) == 0

def check_tavern_tests():
    """Check Tavern test files"""
    print("\n🧪 Checking Tavern Test Files...")
    
    tavern_dir = Path(__file__).parent / 'tavern_tests'
    if not tavern_dir.exists():
        print("  ❌ Tavern tests directory not found")
        return False
    
    test_files = list(tavern_dir.glob('*.tavern.yaml'))
    if not test_files:
        print("  ❌ No Tavern test files found")
        return False
    
    for test_file in sorted(test_files):
        print(f"  ✅ {test_file.name}: Available")
    
    return True

def test_jwt_generation():
    """Test JWT token generation"""
    print("\n🔑 Testing JWT Token Generation...")
    
    try:
        from tavern_helpers import generate_jwt_token
        token = generate_jwt_token()
        print(f"  ✅ JWT Generation: Success (token: {token[:20]}...)")
        return True
    except Exception as e:
        print(f"  ❌ JWT Generation: Failed - {str(e)}")
        return False

def main():
    """Run all verification checks"""
    print("🚀 Tavern Setup Verification\n")
    
    checks = [
        ("Environment Variables", check_environment),
        ("Python Dependencies", check_dependencies),
        ("Configuration Files", check_files),
        ("Tavern Test Files", check_tavern_tests),
        ("JWT Token Generation", test_jwt_generation),
    ]
    
    results = []
    for check_name, check_func in checks:
        try:
            result = check_func()
            results.append(result)
        except Exception as e:
            print(f"  💥 {check_name}: Error - {str(e)}")
            results.append(False)
    
    print(f"\n📊 Verification Summary:")
    total_checks = len(results)
    passed_checks = sum(results)
    
    print(f"  ✅ Passed: {passed_checks}/{total_checks}")
    print(f"  ❌ Failed: {total_checks - passed_checks}/{total_checks}")
    
    if all(results):
        print("\n🎉 All checks passed! Tavern setup is ready.")
        print("\n💡 Next steps:")
        print("  • Run: python run_tavern_tests.py --list-tests")
        print("  • Run: python run_tavern_tests.py --verbose")
        return 0
    else:
        print("\n⚠️  Some checks failed. Please resolve the issues above.")
        print("\n💡 Common solutions:")
        print("  • Install dependencies: pip install -r requirements.txt")
        print("  • Set environment variables (see README.md)")
        print("  • Check file paths and permissions")
        return 1

if __name__ == '__main__':
    sys.exit(main())