#!/usr/bin/env python3
"""
Service provisioning tool for generating and registering agent services
"""

import os
import sys
import argparse
import json
from datetime import datetime
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from services.service_auth import generate_service_keypair, create_service_jwt
from services.service_key_store import ServiceIdentity, register_service
from config.service_permissions import get_available_agent_roles, get_agent_permissions


class ServiceProvisioner:
    """Tool for provisioning new agent services"""
    
    def __init__(self):
        self.output_dir = Path("provisioned_services")
        self.output_dir.mkdir(exist_ok=True)
    
    def provision_service(self, service_id: str, service_name: str, agent_role: str) -> dict:
        """
        Provision a new service with cryptographic identity
        
        Args:
            service_id: Unique service identifier
            service_name: Human-readable service name
            agent_role: Agent role for permissions
            
        Returns:
            Dict with service details and credentials
        """
        print(f"🔧 Provisioning service: {service_id}")
        
        # Validate agent role
        if agent_role not in get_available_agent_roles():
            raise ValueError(f"Invalid agent role: {agent_role}. Available: {get_available_agent_roles()}")
        
        # Generate RSA keypair
        print("🔑 Generating RSA 2048-bit keypair...")
        private_key_pem, public_key_pem = generate_service_keypair()
        
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
        if not register_service(service_identity):
            raise RuntimeError(f"Failed to register service: {service_id}")
        
        # Generate test service JWT
        print("🎫 Generating test service JWT...")
        test_service_jwt = create_service_jwt(service_id, private_key_pem)
        
        # Get agent permissions for reference
        permissions = get_agent_permissions(agent_role)
        
        # Prepare service configuration
        service_config = {
            "service_id": service_id,
            "service_name": service_name,
            "agent_role": agent_role,
            "permissions": permissions,
            "private_key": private_key_pem,
            "public_key": public_key_pem,
            "test_service_jwt": test_service_jwt,
            "oauth2_endpoint": "/oauth2/token",
            "provisioned_at": datetime.utcnow().isoformat()
        }
        
        # Save to file
        config_file = self.output_dir / f"{service_id}_config.json"
        with open(config_file, 'w') as f:
            json.dump(service_config, f, indent=2)
        
        print(f"✅ Service provisioned successfully!")
        print(f"📄 Configuration saved to: {config_file}")
        
        return service_config
    
    def provision_all_agent_services(self) -> dict:
        """
        Provision services for all available agent roles
        
        Returns:
            Dict mapping service_id to service config
        """
        print("🚀 Provisioning services for all agent roles...")
        
        all_services = {}
        agent_roles = get_available_agent_roles()
        
        for agent_role in agent_roles:
            service_id = f"{agent_role}_service"
            service_name = f"{agent_role.replace('_', ' ').title()} Service"
            
            try:
                service_config = self.provision_service(service_id, service_name, agent_role)
                all_services[service_id] = service_config
                print()  # Add spacing between services
                
            except Exception as e:
                print(f"❌ Failed to provision {service_id}: {str(e)}")
        
        # Create summary file
        summary_file = self.output_dir / "services_summary.json"
        summary = {
            "provisioned_at": datetime.utcnow().isoformat(),
            "total_services": len(all_services),
            "services": {
                service_id: {
                    "service_name": config["service_name"],
                    "agent_role": config["agent_role"],
                    "permissions": config["permissions"]
                }
                for service_id, config in all_services.items()
            }
        }
        
        with open(summary_file, 'w') as f:
            json.dump(summary, f, indent=2)
        
        print(f"📋 Services summary saved to: {summary_file}")
        
        return all_services
    
    def show_service_info(self, service_id: str):
        """Show information about a provisioned service"""
        config_file = self.output_dir / f"{service_id}_config.json"
        
        if not config_file.exists():
            print(f"❌ Service {service_id} not found. Available configs:")
            for config in self.output_dir.glob("*_config.json"):
                print(f"   - {config.stem.replace('_config', '')}")
            return
        
        with open(config_file, 'r') as f:
            config = json.load(f)
        
        print(f"🔍 Service Information: {service_id}")
        print("=" * 50)
        print(f"Service Name: {config['service_name']}")
        print(f"Agent Role: {config['agent_role']}")
        print(f"Provisioned: {config['provisioned_at']}")
        print(f"Endpoints: {config['permissions']['endpoints']}")
        print(f"Resources: {config['permissions']['resources']}")
        print(f"Operations: {config['permissions']['operations']}")
        print()
        print("🔑 Private Key (keep secure):")
        print(config['private_key'])
        print()
        print("🎫 Test Service JWT:")
        print(config['test_service_jwt'])
        print()
        print("📡 OAuth2 Usage:")
        print("curl -X POST /oauth2/token \\")
        print("  -H 'Content-Type: application/x-www-form-urlencoded' \\")
        print("  -d 'grant_type=client_credentials' \\")
        print("  -d 'client_assertion_type=urn:ietf:params:oauth:client-assertion-type:jwt-bearer' \\")
        print(f"  -d 'client_assertion={config['test_service_jwt']}'")


def main():
    """Main CLI interface"""
    parser = argparse.ArgumentParser(description="Provision agent services with cryptographic identity")
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Provision single service
    provision_parser = subparsers.add_parser("provision", help="Provision a single service")
    provision_parser.add_argument("service_id", help="Unique service identifier")
    provision_parser.add_argument("service_name", help="Human-readable service name")
    provision_parser.add_argument("agent_role", help="Agent role for permissions")
    
    # Provision all services
    subparsers.add_parser("provision-all", help="Provision services for all agent roles")
    
    # Show service info
    info_parser = subparsers.add_parser("info", help="Show service information")
    info_parser.add_argument("service_id", help="Service identifier")
    
    # List available roles
    subparsers.add_parser("list-roles", help="List available agent roles")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    provisioner = ServiceProvisioner()
    
    try:
        if args.command == "provision":
            provisioner.provision_service(args.service_id, args.service_name, args.agent_role)
        
        elif args.command == "provision-all":
            provisioner.provision_all_agent_services()
        
        elif args.command == "info":
            provisioner.show_service_info(args.service_id)
        
        elif args.command == "list-roles":
            roles = get_available_agent_roles()
            print("Available agent roles:")
            for role in roles:
                permissions = get_agent_permissions(role)
                print(f"  - {role}: {permissions['description']}")
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()