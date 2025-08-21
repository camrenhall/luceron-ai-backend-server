"""
Contract registry for centralized contract management
"""

from typing import Dict
from agent_gateway.contracts.base import ResourceContract
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