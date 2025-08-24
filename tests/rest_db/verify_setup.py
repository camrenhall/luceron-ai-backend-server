#!/usr/bin/env python3
"""
Verification script for standalone REST API tests
Validates that all dependencies and configuration are correct
"""

import os
import sys
import subprocess
from pathlib import Path


def check_dependencies():
    """Check that required Python packages are installed"""
    print("📦 Checking Dependencies...")
    
    required_packages = [
        ('tavern', 'Tavern API testing framework'),
        ('jwt', 'JWT token handling'),
        ('yaml', 'YAML configuration parsing'),
        ('requests', 'HTTP client library')
    ]
    
    missing_packages = []
    
    for package, description in required_packages:
        try:
            __import__(package)
            print(f"   ✅ {package}: Available")
        except ImportError:
            missing_packages.append(package)
            print(f"   ❌ {package}: Missing ({description})")
    
    if missing_packages:
        print(f"\n💡 Install missing packages:")
        print(f"   pip install -r requirements.txt")
        return False
    
    return True


def check_tavern_command():
    """Check that tavern-ci command is available"""
    print("\n🔧 Checking Tavern Command...")
    
    try:
        result = subprocess.run(
            ['tavern-ci', '--version'],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            print(f"   ✅ tavern-ci: Available")
            return True
        else:
            print(f"   ❌ tavern-ci: Command failed")
            return False
            
    except FileNotFoundError:
        print(f"   ❌ tavern-ci: Command not found")
        print("   💡 Install tavern: pip install tavern")
        return False


def check_test_files():
    """Check that test files exist and are valid"""
    print("\n📁 Checking Test Files...")
    
    test_dir = Path(__file__).parent
    test_files = list(test_dir.glob("test_*.tavern.yaml"))
    
    if not test_files:
        print("   ❌ No test files found")
        return False
    
    print(f"   ✅ Found {len(test_files)} test files:")
    for test_file in sorted(test_files):
        print(f"      • {test_file.name}")
    
    return True


def check_configuration():
    """Check configuration files"""
    print("\n⚙️  Checking Configuration...")
    
    config_file = Path(__file__).parent / "config.yaml"
    
    if config_file.exists():
        print("   ✅ config.yaml: Found")
    else:
        print("   ❌ config.yaml: Missing")
        return False
    
    auth_file = Path(__file__).parent / "auth_helpers.py"
    
    if auth_file.exists():
        print("   ✅ auth_helpers.py: Found")
    else:
        print("   ❌ auth_helpers.py: Missing")
        return False
    
    return True


def check_environment():
    """Check environment variables"""
    print("\n🔍 Checking Environment...")
    
    required_vars = ['TEST_OAUTH_PRIVATE_KEY']
    optional_vars = {
        'AGENT_DB_BASE_URL': 'http://localhost:8080',
        'OAUTH_SERVICE_ID': 'qa_comprehensive_test_service',
        'OAUTH_AUDIENCE': 'luceron-auth-server'
    }
    
    missing_required = []
    
    for var in required_vars:
        if os.getenv(var):
            print(f"   ✅ {var}: Set")
        else:
            missing_required.append(var)
            print(f"   ❌ {var}: Missing")
    
    for var, default in optional_vars.items():
        value = os.getenv(var, default)
        print(f"   ✅ {var}: {value}")
    
    if missing_required:
        print(f"\n💡 Set required variables:")
        for var in missing_required:
            print(f"   export {var}='your_value_here'")
        return False
    
    return True


def test_jwt_generation():
    """Test JWT token generation"""
    print("\n🔑 Testing JWT Generation...")
    
    try:
        from auth_helpers import generate_jwt_token
        token = generate_jwt_token()
        print(f"   ✅ JWT generation: Success (token: {token[:20]}...)")
        return True
    except Exception as e:
        print(f"   ❌ JWT generation: Failed - {str(e)}")
        return False


def main():
    print("🚀 REST API Test Setup Verification")
    print("=" * 50)
    
    checks = [
        ("Dependencies", check_dependencies),
        ("Tavern Command", check_tavern_command),
        ("Test Files", check_test_files),
        ("Configuration", check_configuration),
        ("Environment", check_environment),
        ("JWT Generation", test_jwt_generation)
    ]
    
    results = []
    
    for check_name, check_func in checks:
        try:
            result = check_func()
            results.append(result)
        except Exception as e:
            print(f"   💥 {check_name}: Error - {str(e)}")
            results.append(False)
    
    print("\n" + "=" * 50)
    print("📊 Verification Results:")
    
    passed = sum(results)
    total = len(results)
    
    print(f"   ✅ Passed: {passed}/{total}")
    print(f"   ❌ Failed: {total - passed}/{total}")
    
    if all(results):
        print("\n🎉 Setup verification PASSED!")
        print("\n💡 Ready to run tests:")
        print("   python run_tests.py --list")
        print("   python run_tests.py")
        return 0
    else:
        print("\n⚠️  Setup verification FAILED")
        print("   Fix the issues above before running tests")
        return 1


if __name__ == '__main__':
    sys.exit(main())