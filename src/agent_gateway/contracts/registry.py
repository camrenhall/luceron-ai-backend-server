"""
Contract registry for centralized contract management
"""

from typing import Dict, List
from agent_gateway.contracts.base import ResourceContract, Operation
from agent_gateway.contracts.cases import get_cases_contract
from agent_gateway.contracts.client_communications import get_client_communications_contract
from agent_gateway.contracts.documents import get_documents_contract, get_document_analysis_contract
from agent_gateway.contracts.error_logs import get_error_logs_contract
from agent_gateway.contracts.agent_context import get_agent_context_contract
from agent_gateway.contracts.agent_conversations import get_agent_conversations_contract
from agent_gateway.contracts.agent_messages import get_agent_messages_contract
from agent_gateway.contracts.agent_summaries import get_agent_summaries_contract

def get_all_contracts(role: str = "default") -> Dict[str, ResourceContract]:
    """Get all resource contracts for the specified role"""
    return {
        "cases": get_cases_contract(role),
        "client_communications": get_client_communications_contract(role),
        "documents": get_documents_contract(role),
        "document_analysis": get_document_analysis_contract(role),
        "error_logs": get_error_logs_contract(role),
        "agent_context": get_agent_context_contract(role),
        "agent_conversations": get_agent_conversations_contract(role),
        "agent_messages": get_agent_messages_contract(role),
        "agent_summaries": get_agent_summaries_contract(role)
    }

def get_available_resources() -> list[str]:
    """Get list of all available resource names"""
    return list(get_all_contracts().keys())


def get_agent_contracts(agent_auth_context) -> Dict[str, ResourceContract]:
    """
    Get contracts filtered by agent permissions
    
    Args:
        agent_auth_context: AgentAuthContext containing permissions
        
    Returns:
        Dict of resource contracts filtered by agent permissions
    """
    # Import here to avoid circular imports
    from utils.auth import AgentAuthContext
    
    if not isinstance(agent_auth_context, AgentAuthContext):
        raise ValueError("Expected AgentAuthContext")
    
    # Get all available contracts
    all_contracts = get_all_contracts(agent_auth_context.agent_type)
    
    # Filter contracts by agent's allowed resources
    agent_contracts = {}
    
    for resource_name, contract in all_contracts.items():
        # Check if agent can access this resource
        if _can_access_resource(agent_auth_context.allowed_resources, resource_name):
            # Filter contract operations by agent permissions
            filtered_contract = _filter_contract_operations(
                contract, 
                agent_auth_context.allowed_operations
            )
            agent_contracts[resource_name] = filtered_contract
    
    return agent_contracts


def _can_access_resource(allowed_resources: List[str], resource_name: str) -> bool:
    """Check if agent has permission to access resource"""
    # Wildcard permission grants access to all resources
    if "*" in allowed_resources:
        return True
    
    # Direct resource permission
    return resource_name in allowed_resources


def _filter_contract_operations(contract: ResourceContract, allowed_operations: List[str]) -> ResourceContract:
    """
    Filter contract operations based on agent permissions
    
    Args:
        contract: Original resource contract
        allowed_operations: List of operations agent can perform (READ, INSERT, UPDATE)
        
    Returns:
        Filtered contract with only allowed operations
    """
    # Convert string operations to Operation enum
    operation_mapping = {
        "READ": Operation.READ,
        "INSERT": Operation.INSERT, 
        "UPDATE": Operation.UPDATE,
        "DELETE": Operation.DELETE
    }
    
    allowed_ops = [
        operation_mapping[op] for op in allowed_operations 
        if op in operation_mapping
    ]
    
    # Filter the contract's allowed operations
    filtered_ops = [
        op for op in contract.ops_allowed 
        if op in allowed_ops
    ]
    
    # Create a new contract with filtered operations
    # Note: This creates a copy of the contract with modified operations
    filtered_contract = ResourceContract(
        version=contract.version,
        resource=contract.resource,
        ops_allowed=filtered_ops,
        fields=contract.fields,
        filters_allowed=contract.filters_allowed,
        order_allowed=contract.order_allowed,
        limits=contract.limits,
        joins_allowed=getattr(contract, 'joins_allowed', [])
    )
    
    return filtered_contract