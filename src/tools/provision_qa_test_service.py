#!/usr/bin/env python3
"""
Provision QA Test Service with Environment-Isolated Authentication

This script creates a dedicated QA testing service with:
- Unique RSA 2048-bit keypair
- Environment-restricted permissions (QA only)
- Full testing capabilities for CRUD comprehensive tests

Usage:
    python src/tools/provision_qa_test_service.py [--output-private-key]
    
Options:
    --output-private-key    Display private key for GitHub Actions secret
"""

import sys
import argparse
from datetime import datetime
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.service_auth import generate_service_keypair
from services.service_key_store import ServiceIdentity, register_service
from config.service_permissions import get_service_permissions

def provision_qa_test_service(output_private_key: bool = False) -> tuple[str, str]:
    """
    Provision QA test service with environment isolation
    
    Args:
        output_private_key: Whether to display private key for GitHub Actions
        
    Returns:
        Tuple of (service_id, private_key_pem)
    """
    
    service_id = "qa_comprehensive_test_service"
    service_name = "QA Comprehensive Test Service"
    agent_role = "qa_test_agent"
    
    print("🔧 Provisioning QA Test Service with Environment Isolation")
    print(f"   Service ID: {service_id}")
    print(f"   Agent Role: {agent_role}")
    
    # Validate QA test agent permissions exist
    permissions = get_service_permissions(agent_role)
    if not permissions:
        print(f"❌ Error: Agent role '{agent_role}' not found in service permissions")
        print("   Make sure qa_test_agent is configured in service_permissions.py")
        return None, None
    
    # Verify environment restrictions
    allowed_environments = permissions.get('environments', [])
    if allowed_environments != ["QA"]:
        print(f"❌ Error: Agent role '{agent_role}' must be restricted to QA only")
        print(f"   Current environments: {allowed_environments}")
        return None, None
    
    print(f"✅ Agent role validation passed - QA-only access confirmed")
    
    # Generate RSA 2048-bit keypair
    print("🔑 Generating RSA 2048-bit keypair...")
    try:
        private_key_pem, public_key_pem = generate_service_keypair()
        print("✅ Keypair generated successfully")
    except Exception as e:
        print(f"❌ Error generating keypair: {e}")
        return None, None
    
    # Create service identity
    service_identity = ServiceIdentity(
        service_id=service_id,
        service_name=service_name,
        agent_role=agent_role,
        public_key=public_key_pem,
        is_active=True,
        created_at=datetime.utcnow().isoformat()
    )
    
    # Register service
    print("📝 Registering service in key store...")
    try:
        success = register_service(service_identity)
        if not success:
            print(f"❌ Failed to register service (may already exist)")
            return None, None
        print("✅ Service registered successfully")
    except Exception as e:
        print(f"❌ Error registering service: {e}")
        return None, None
    
    # Display service summary
    print("\n📋 QA Test Service Provisioning Summary:")
    print(f"   ✅ Service ID: {service_id}")
    print(f"   ✅ Agent Role: {agent_role} (QA-only)")
    print(f"   ✅ Permissions: {permissions.get('description', 'N/A')}")
    print(f"   ✅ Endpoints: {permissions.get('endpoints', [])}")
    print(f"   ✅ Resources: {permissions.get('resources', [])}")
    print(f"   ✅ Operations: {permissions.get('operations', [])}")
    print(f"   ✅ Environment Restriction: {allowed_environments}")
    
    # Output private key if requested
    if output_private_key:
        print("\n🔐 Private Key for GitHub Actions Secret (TEST_OAUTH_PRIVATE_KEY):")
        print("=" * 80)
        print(private_key_pem)
        print("=" * 80)
        print("⚠️  SECURITY: Copy this private key to GitHub Actions secrets")
        print("   Secret Name: TEST_OAUTH_PRIVATE_KEY")
        print("   This key can ONLY generate tokens for QA environment")
    else:
        print("\n🔐 Private key generated (use --output-private-key to display)")
    
    print("\n🎯 Next Steps:")
    print("   1. Copy private key to GitHub Actions secret: TEST_OAUTH_PRIVATE_KEY")
    print("   2. Verify QA container environment variable: ENV=QA")
    print("   3. Test authentication with comprehensive test suite")
    
    return service_id, private_key_pem

def main():
    """Main provisioning function"""
    parser = argparse.ArgumentParser(
        description="Provision QA Test Service with Environment Isolation"
    )
    parser.add_argument(
        "--output-private-key",
        action="store_true",
        help="Display private key for GitHub Actions secret"
    )
    
    args = parser.parse_args()
    
    service_id, private_key = provision_qa_test_service(args.output_private_key)
    
    if service_id and private_key:
        print("\n✅ QA Test Service provisioning completed successfully!")
        print("   Environment isolation enforced - QA tokens cannot access production")
        return 0
    else:
        print("\n❌ QA Test Service provisioning failed!")
        return 1

if __name__ == "__main__":
    exit(main())