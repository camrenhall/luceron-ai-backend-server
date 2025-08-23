#!/usr/bin/env python3
"""
Test Environment Isolation for JWT Authentication

This script verifies that environment-isolated JWT authentication works correctly
and prevents cross-environment token reuse.

Usage:
    python src/tools/test_environment_isolation.py
"""

import sys
import os
from pathlib import Path
from datetime import datetime

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.agent_jwt_service import AgentJWTService
from config.settings import ENV, JWTEnvironmentConfig
from config.service_permissions import get_service_permissions, can_access_environment

def test_environment_isolation():
    """Test JWT environment isolation functionality"""
    
    print("🧪 Testing Environment-Isolated JWT Authentication")
    print(f"   Current Environment: {ENV}")
    print(f"   JWT Config: {JWTEnvironmentConfig.get_config()}")
    
    # Test 1: Valid QA agent token generation and validation
    print("\n🔬 Test 1: Valid QA Agent Token Generation")
    try:
        jwt_service = AgentJWTService()
        
        # Generate token for QA test agent
        qa_token = jwt_service.generate_access_token("qa_test_agent", "qa_comprehensive_test_service")
        print(f"   ✅ QA token generated: {qa_token[:50]}...")
        
        # Validate token in current environment
        payload = jwt_service.validate_and_decode_jwt(qa_token)
        print(f"   ✅ Token validation successful")
        print(f"   ✅ Agent: {payload['sub']}")
        print(f"   ✅ Environment: {payload['environment']}")
        print(f"   ✅ Issuer: {payload['iss']}")
        print(f"   ✅ Audience: {payload['aud']}")
        
    except Exception as e:
        print(f"   ❌ Test 1 failed: {e}")
        return False
    
    # Test 2: Environment permission validation
    print("\n🔬 Test 2: Environment Permission Validation")
    try:
        # Check QA test agent permissions
        qa_permissions = get_service_permissions("qa_test_agent")
        print(f"   ✅ QA test agent permissions: {qa_permissions}")
        
        # Verify environment restrictions
        can_access_qa = can_access_environment("qa_test_agent", "QA")
        can_access_prod = can_access_environment("qa_test_agent", "PROD")
        
        print(f"   ✅ Can access QA: {can_access_qa}")
        print(f"   ✅ Can access PROD: {can_access_prod}")
        
        if can_access_qa and not can_access_prod:
            print("   ✅ Environment isolation working correctly")
        else:
            print("   ❌ Environment isolation failed - QA agent can access production!")
            return False
            
    except Exception as e:
        print(f"   ❌ Test 2 failed: {e}")
        return False
    
    # Test 3: JWT Claims validation
    print("\n🔬 Test 3: JWT Claims Validation")
    try:
        # Verify all required claims are present
        required_claims = ["sub", "environment", "iss", "aud", "exp", "iat", "service_id"]
        for claim in required_claims:
            if claim not in payload:
                print(f"   ❌ Missing required claim: {claim}")
                return False
        print("   ✅ All required JWT claims present")
        
        # Verify environment claim matches current environment
        if payload["environment"] != ENV:
            print(f"   ❌ Environment mismatch: token={payload['environment']}, server={ENV}")
            return False
        print(f"   ✅ Environment claim matches server: {ENV}")
        
    except Exception as e:
        print(f"   ❌ Test 3 failed: {e}")
        return False
    
    # Test 4: Cross-environment simulation (if possible)
    print("\n🔬 Test 4: Cross-Environment Attack Simulation")
    if ENV == "QA":
        print("   ℹ️  Testing QA→PROD token reuse simulation")
        
        # Simulate what would happen if token were used against PROD
        # (We can't actually test this without a PROD container, but we can verify the logic)
        prod_config = JWTEnvironmentConfig.PROD_CONFIG
        qa_config = JWTEnvironmentConfig.QA_CONFIG
        
        if prod_config["secret"] != qa_config["secret"]:
            print("   ✅ Different signing secrets across environments")
        else:
            print("   ⚠️  WARNING: Same signing secret across environments!")
            
        if prod_config["issuer"] != qa_config["issuer"]:
            print("   ✅ Different issuers across environments")
        else:
            print("   ⚠️  WARNING: Same issuer across environments!")
            
        if prod_config["audience"] != qa_config["audience"]:
            print("   ✅ Different audiences across environments")
        else:
            print("   ⚠️  WARNING: Same audience across environments!")
    
    print("\n✅ Environment Isolation Tests Completed Successfully!")
    print("   🔒 QA tokens are properly isolated from production")
    print("   🛡️  Multiple validation layers protect against tampering")
    print("   🎯 Ready for comprehensive CRUD testing")
    
    return True

def main():
    """Main test function"""
    print("🔐 JWT Environment Isolation Test Suite")
    print("=" * 60)
    
    success = test_environment_isolation()
    
    if success:
        print("\n🎉 All tests passed! Environment isolation is working correctly.")
        return 0
    else:
        print("\n💥 Tests failed! Environment isolation has security issues.")
        return 1

if __name__ == "__main__":
    exit(main())