"""
Resource configuration for CRUD testing
Centralized definition of all testable resources and their properties
"""

from typing import Dict, Any, List
from dataclasses import dataclass


@dataclass
class ResourceConfig:
    """Configuration for a testable resource"""
    name: str
    endpoint: str
    table: str
    uuid_field: str
    factory_method: str
    dependencies: List[str] = None
    search_endpoint: str = None
    list_params: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.dependencies is None:
            self.dependencies = []
        if self.list_params is None:
            self.list_params = {"limit": 10}
        if self.search_endpoint is None:
            self.search_endpoint = f"{self.endpoint}/search"


# Resource configurations for all CRUD testable entities
RESOURCE_CONFIGS = {
    "cases": ResourceConfig(
        name="cases",
        endpoint="/api/cases",
        table="cases",
        uuid_field="case_id",
        factory_method="generate_case",
        dependencies=[],
        list_params={"limit": 10}
    ),
    
    "documents": ResourceConfig(
        name="documents", 
        endpoint="/api/documents",
        table="documents",
        uuid_field="document_id",
        factory_method="generate_document",
        dependencies=["cases"]
    ),
    
    "communications": ResourceConfig(
        name="communications",
        endpoint="/api/communications", 
        table="client_communications",
        uuid_field="communication_id",
        factory_method="generate_communication",
        dependencies=["cases"]
    ),
    
    "agent_conversations": ResourceConfig(
        name="agent_conversations",
        endpoint="/api/agent/conversations",
        table="agent_conversations", 
        uuid_field="conversation_id",
        factory_method="generate_agent_conversation",
        dependencies=[]
    ),
    
    "agent_messages": ResourceConfig(
        name="agent_messages",
        endpoint="/api/agent/messages",
        table="agent_messages",
        uuid_field="message_id", 
        factory_method="generate_agent_message",
        dependencies=["agent_conversations"]
    ),
    
    "agent_context": ResourceConfig(
        name="agent_context",
        endpoint="/api/agent/context",
        table="agent_context",
        uuid_field="context_id",
        factory_method="generate_agent_context", 
        dependencies=["cases"]
    ),
    
    "error_logs": ResourceConfig(
        name="error_logs",
        endpoint="/api/errors",
        table="error_logs",
        uuid_field="error_id",
        factory_method="generate_error_log",
        dependencies=[]
    )
}


def get_resource_config(resource_name: str) -> ResourceConfig:
    """Get configuration for a specific resource"""
    if resource_name not in RESOURCE_CONFIGS:
        raise ValueError(f"Unknown resource: {resource_name}")
    return RESOURCE_CONFIGS[resource_name]


def get_cleanup_order() -> List[str]:
    """Get resources in proper cleanup order (children first)"""
    return [
        'agent_messages',
        'agent_summaries', 
        'agent_context',
        'document_analysis',
        'communications',
        'documents',
        'agent_conversations',
        'error_logs',
        'cases'
    ]


def get_dependency_graph() -> Dict[str, List[str]]:
    """Get dependency relationships for test ordering"""
    return {
        resource: config.dependencies 
        for resource, config in RESOURCE_CONFIGS.items()
    }