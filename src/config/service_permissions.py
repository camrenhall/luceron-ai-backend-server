"""
Service permissions configuration - Single source of truth for all service capabilities
"""

from typing import Dict, List, Any

# Environment-aware service permissions - centralized configuration with environment isolation
SERVICE_PERMISSIONS: Dict[str, Dict[str, Any]] = {
    "manager_agent": {
        "environments": ["PROD", "QA"],  # Production service
        "endpoints": ["/agent/db"],
        "resources": ["*"],
        "operations": ["READ", "INSERT", "UPDATE"],
        "description": "Full orchestration and data access"
    },
    "communications_agent": {
        "environments": ["PROD", "QA"],  # Production service 
        "endpoints": ["/agent/db"],
        "resources": [
            "cases", 
            "client_communications", 
            "agent_messages",
            "agent_context"
        ],
        "operations": ["READ", "INSERT", "UPDATE"],
        "description": "Client communication and case data access"
    },
    "analysis_agent": {
        "environments": ["PROD", "QA"],  # Production service
        "endpoints": ["/agent/db"],
        "resources": [
            "cases", 
            "document_analysis", 
            "agent_context"
        ],
        "operations": ["READ", "INSERT"],
        "description": "Document analysis and case review"
    },
    "aws_document_lambdas": {
        "environments": ["PROD", "QA"],  # Production service
        "endpoints": [
            "/api/documents",
            "/api/documents/analysis"
        ],
        "resources": [
            "documents", 
            "document_analysis"
        ],
        "operations": ["READ", "INSERT"],
        "description": "AWS Lambda document processing pipeline"
    },
    "gcp_cloud_functions": {
        "environments": ["PROD", "QA"],  # Production service
        "endpoints": ["/alert"],
        "resources": [],
        "operations": [],
        "description": "GCP Cloud Functions with REST access to alerts endpoint only"
    },
    "camren_master": {
        "environments": ["PROD", "QA"],  # Master access in both environments
        "endpoints": ["*"],
        "resources": ["*"],
        "operations": ["READ", "INSERT", "UPDATE", "DELETE"],
        "description": "Master access - full system permissions including emergency kill-switch"
    },
    "qa_test_agent": {
        "environments": ["QA"],  # 🔑 QA-ONLY - Cannot access production
        "endpoints": ["*"],      # Full endpoint access for comprehensive testing
        "resources": ["*"],      # Full resource access for CRUD testing
        "operations": ["READ", "INSERT", "UPDATE", "DELETE"],  # All operations for testing
        "description": "QA comprehensive testing agent - RESTRICTED to QA environment only"
    }
}

def get_service_permissions(service_role: str) -> Dict[str, Any]:
    """
    Get permissions for a specific service role
    
    Args:
        service_role: The service role (e.g., "communications_agent", "aws_document_lambdas")
        
    Returns:
        Dict containing permissions or empty dict if role not found
    """
    return SERVICE_PERMISSIONS.get(service_role, {})

def is_valid_service_role(service_role: str) -> bool:
    """Check if service role exists in configuration"""
    return service_role in SERVICE_PERMISSIONS

def can_access_endpoint(service_role: str, endpoint: str) -> bool:
    """Check if service role can access specific endpoint"""
    permissions = get_service_permissions(service_role)
    allowed_endpoints = permissions.get('endpoints', [])
    return endpoint in allowed_endpoints

def can_access_resource(service_role: str, resource: str) -> bool:
    """Check if service role can access specific resource"""
    permissions = get_service_permissions(service_role)
    allowed_resources = permissions.get('resources', [])
    return resource in allowed_resources or "*" in allowed_resources

def can_perform_operation(service_role: str, operation: str) -> bool:
    """Check if service role can perform specific operation"""
    permissions = get_service_permissions(service_role)
    allowed_operations = permissions.get('operations', [])
    return operation in allowed_operations

def can_access_environment(service_role: str, environment: str) -> bool:
    """Check if service role is authorized for specific environment"""
    permissions = get_service_permissions(service_role)
    allowed_environments = permissions.get('environments', [])
    return environment in allowed_environments

def get_available_service_roles() -> List[str]:
    """Get list of all configured service roles"""
    return list(SERVICE_PERMISSIONS.keys())

def get_qa_only_roles() -> List[str]:
    """Get list of roles restricted to QA environment only"""
    qa_roles = []
    for role, permissions in SERVICE_PERMISSIONS.items():
        environments = permissions.get('environments', [])
        if environments == ["QA"]:  # Only QA, not PROD
            qa_roles.append(role)
    return qa_roles

def get_production_roles() -> List[str]:
    """Get list of roles authorized for production environment"""
    prod_roles = []
    for role, permissions in SERVICE_PERMISSIONS.items():
        environments = permissions.get('environments', [])
        if "PROD" in environments:
            prod_roles.append(role)
    return prod_roles

# Backward compatibility aliases for agent-specific usage
get_agent_permissions = get_service_permissions
is_valid_agent_role = is_valid_service_role
get_available_agent_roles = get_available_service_roles