"""
Service permissions configuration - Single source of truth for all service capabilities
"""

from typing import Dict, List, Any

# Service permissions - centralized configuration for all authenticated services
SERVICE_PERMISSIONS: Dict[str, Dict[str, Any]] = {
    "manager_agent": {
        "endpoints": ["/agent/db"],  # Can be expanded later for orchestration endpoints
        "resources": ["*"],  # Full access to all resources via wildcard
        "operations": ["READ", "INSERT", "UPDATE"],
        "description": "Full orchestration and data access"
    },
    "communications_agent": {
        "endpoints": ["/agent/db"],
        "resources": [
            "cases", 
            "client_communications", 
            "agent_messages",
            "agent_context"  # Needs context for conversations
        ],
        "operations": ["READ", "INSERT", "UPDATE"],
        "description": "Client communication and case data access"
    },
    "analysis_agent": {
        "endpoints": ["/agent/db"],
        "resources": [
            "cases", 
            "document_analysis", 
            "agent_context"
        ],
        "operations": ["READ", "INSERT"],  # Mostly read-only, can create analysis records
        "description": "Document analysis and case review"
    },
    "aws_document_lambdas": {
        "endpoints": [
            "/api/documents",
            "/api/documents/analysis"
        ],
        "resources": [
            "documents", 
            "document_analysis"
        ],
        "operations": ["READ", "INSERT"],  # Can read documents, write analysis results
        "description": "AWS Lambda document processing pipeline"
    },
    "camren_master": {
        "endpoints": ["*"],  # Full access to all endpoints
        "resources": ["*"],  # Full access to all resources
        "operations": ["READ", "INSERT", "UPDATE", "DELETE"],  # All operations
        "description": "Master access - full system permissions"
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

def get_available_service_roles() -> List[str]:
    """Get list of all configured service roles"""
    return list(SERVICE_PERMISSIONS.keys())

# Backward compatibility aliases for agent-specific usage
get_agent_permissions = get_service_permissions
is_valid_agent_role = is_valid_service_role
get_available_agent_roles = get_available_service_roles