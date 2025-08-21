"""
Agent services - business logic for AI agent operations and context management
"""

import logging
from typing import Dict, Any, List, Optional
from services.base_service import BaseService, ServiceResult

logger = logging.getLogger(__name__)

class AgentContextService(BaseService):
    """Service for agent context management"""
    
    def __init__(self, role: str = "api"):
        super().__init__("agent_context", role)
    
    async def create_context(
        self,
        case_id: str,
        agent_type: str,
        context_key: str,
        context_value: Dict[str, Any],
        expires_at: Optional[str] = None
    ) -> ServiceResult:
        """
        Create or update agent context
        
        Args:
            case_id: UUID of the associated case
            agent_type: Type of agent (e.g., 'document_analyzer', 'case_manager')
            context_key: Unique key for this context item
            context_value: JSON context data
            expires_at: Optional expiration timestamp (ISO format)
            
        Returns:
            ServiceResult with created/updated context data
        """
        context_data = {
            "case_id": case_id,
            "agent_type": agent_type,
            "context_key": context_key,
            "context_value": context_value
        }
        
        if expires_at:
            context_data["expires_at"] = expires_at
        
        logger.info(f"Creating context for {agent_type} agent - case {case_id}, key: {context_key}")
        return await self.create(context_data)
    
    async def get_context_by_id(self, context_id: str) -> ServiceResult:
        """Get context by ID"""
        return await self.get_by_id(context_id)
    
    async def get_context_by_case_and_agent(self, case_id: str, agent_type: str) -> ServiceResult:
        """Get all context for a specific case and agent type"""
        filters = {
            "case_id": case_id,
            "agent_type": agent_type
        }
        return await self.read(filters=filters)
    
    async def get_context_by_key(self, case_id: str, agent_type: str, context_key: str) -> ServiceResult:
        """Get specific context by case, agent, and key"""
        filters = {
            "case_id": case_id,
            "agent_type": agent_type,
            "context_key": context_key
        }
        return await self.read(filters=filters, limit=1)
    
    async def update_context_value(self, context_id: str, context_value: Dict[str, Any]) -> ServiceResult:
        """Update context value"""
        return await self.update(context_id, {"context_value": context_value})

class AgentConversationsService(BaseService):
    """Service for agent conversation management"""
    
    def __init__(self, role: str = "api"):
        super().__init__("agent_conversations", role)
    
    async def create_conversation(
        self,
        agent_type: str,
        status: str = "ACTIVE"
    ) -> ServiceResult:
        """
        Create a new agent conversation
        
        Args:
            agent_type: Type of agent starting the conversation
            status: Initial conversation status (default: ACTIVE)
            
        Returns:
            ServiceResult with created conversation data
        """
        conversation_data = {
            "agent_type": agent_type,
            "status": status,
            "total_tokens_used": 0
        }
        
        logger.info(f"Creating new conversation for {agent_type} agent")
        return await self.create(conversation_data)
    
    async def get_conversation_by_id(self, conversation_id: str) -> ServiceResult:
        """Get conversation by ID"""
        return await self.get_by_id(conversation_id)
    
    async def get_conversations_by_agent_type(self, agent_type: str, limit: int = 100) -> ServiceResult:
        """Get conversations for a specific agent type"""
        return await self.get_by_field("agent_type", agent_type, limit)
    
    async def get_active_conversations(self, agent_type: Optional[str] = None) -> ServiceResult:
        """Get active conversations, optionally filtered by agent type"""
        filters = {"status": "ACTIVE"}
        if agent_type:
            filters["agent_type"] = agent_type
        
        return await self.read(filters=filters)
    
    async def update_conversation_status(self, conversation_id: str, status: str) -> ServiceResult:
        """Update conversation status"""
        return await self.update(conversation_id, {"status": status})
    
    async def add_tokens_used(self, conversation_id: str, tokens: int) -> ServiceResult:
        """Add tokens to the conversation total (requires current value)"""
        # Note: This is a simplified approach. In production, you might want
        # to use atomic SQL updates like: UPDATE ... SET total_tokens_used = total_tokens_used + ?
        current = await self.get_conversation_by_id(conversation_id)
        if not current.success or not current.data:
            return ServiceResult(success=False, error="Conversation not found")
        
        current_tokens = current.data[0].get("total_tokens_used", 0)
        new_total = current_tokens + tokens
        
        return await self.update(conversation_id, {"total_tokens_used": new_total})

class AgentMessagesService(BaseService):
    """Service for agent message management"""
    
    def __init__(self, role: str = "api"):
        super().__init__("agent_messages", role)
    
    async def create_message(
        self,
        conversation_id: str,
        role: str,
        content: Dict[str, Any],
        model_used: str,
        sequence_number: int,
        total_tokens: Optional[int] = None,
        function_name: Optional[str] = None,
        function_arguments: Optional[Dict[str, Any]] = None,
        function_response: Optional[Dict[str, Any]] = None
    ) -> ServiceResult:
        """
        Create a new agent message
        
        Args:
            conversation_id: UUID of the conversation
            role: Message role (user, assistant, system, function)
            content: Message content as JSON
            model_used: Name of the AI model used
            sequence_number: Sequence number within conversation
            total_tokens: Number of tokens consumed
            function_name: Name of function called (if applicable)
            function_arguments: Function arguments (if applicable)
            function_response: Function response (if applicable)
            
        Returns:
            ServiceResult with created message data
        """
        message_data = {
            "conversation_id": conversation_id,
            "role": role,
            "content": content,
            "model_used": model_used,
            "sequence_number": sequence_number
        }
        
        if total_tokens is not None:
            message_data["total_tokens"] = total_tokens
        
        if function_name:
            message_data["function_name"] = function_name
        
        if function_arguments:
            message_data["function_arguments"] = function_arguments
        
        if function_response:
            message_data["function_response"] = function_response
        
        logger.info(f"Creating {role} message for conversation {conversation_id}")
        return await self.create(message_data)
    
    async def get_message_by_id(self, message_id: str) -> ServiceResult:
        """Get message by ID"""
        return await self.get_by_id(message_id)
    
    async def get_messages_by_conversation(self, conversation_id: str) -> ServiceResult:
        """Get all messages for a conversation, ordered by sequence"""
        filters = {"conversation_id": conversation_id}
        order_by = [{"field": "sequence_number", "dir": "asc"}]
        
        return await self.read(filters=filters, order_by=order_by)
    
    async def get_recent_messages(self, conversation_id: str, limit: int = 10) -> ServiceResult:
        """Get recent messages for a conversation"""
        filters = {"conversation_id": conversation_id}
        order_by = [{"field": "sequence_number", "dir": "desc"}]
        
        return await self.read(filters=filters, order_by=order_by, limit=limit)

class AgentSummariesService(BaseService):
    """Service for agent conversation summaries"""
    
    def __init__(self, role: str = "api"):
        super().__init__("agent_summaries", role)
    
    async def create_summary(
        self,
        conversation_id: str,
        summary_content: str,
        messages_summarized: int,
        last_message_id: Optional[str] = None
    ) -> ServiceResult:
        """
        Create a conversation summary
        
        Args:
            conversation_id: UUID of the conversation
            summary_content: The summary text
            messages_summarized: Number of messages included in summary
            last_message_id: ID of the last message included in summary
            
        Returns:
            ServiceResult with created summary data
        """
        summary_data = {
            "conversation_id": conversation_id,
            "summary_content": summary_content,
            "messages_summarized": messages_summarized
        }
        
        if last_message_id:
            summary_data["last_message_id"] = last_message_id
        
        logger.info(f"Creating summary for conversation {conversation_id} - {messages_summarized} messages")
        return await self.create(summary_data)
    
    async def get_summary_by_id(self, summary_id: str) -> ServiceResult:
        """Get summary by ID"""
        return await self.get_by_id(summary_id)
    
    async def get_summaries_by_conversation(self, conversation_id: str) -> ServiceResult:
        """Get all summaries for a conversation"""
        filters = {"conversation_id": conversation_id}
        order_by = [{"field": "created_at", "dir": "desc"}]
        
        return await self.read(filters=filters, order_by=order_by)
    
    async def get_latest_summary(self, conversation_id: str) -> ServiceResult:
        """Get the most recent summary for a conversation"""
        filters = {"conversation_id": conversation_id}
        order_by = [{"field": "created_at", "dir": "desc"}]
        
        return await self.read(filters=filters, order_by=order_by, limit=1)
    
    async def update_summary_content(self, summary_id: str, summary_content: str) -> ServiceResult:
        """Update summary content"""
        return await self.update(summary_id, {"summary_content": summary_content})

# Global service instances
_agent_context_service: Optional[AgentContextService] = None
_agent_conversations_service: Optional[AgentConversationsService] = None
_agent_messages_service: Optional[AgentMessagesService] = None
_agent_summaries_service: Optional[AgentSummariesService] = None

def get_agent_context_service() -> AgentContextService:
    """Get the global agent context service instance"""
    global _agent_context_service
    if _agent_context_service is None:
        _agent_context_service = AgentContextService()
    return _agent_context_service

def get_agent_conversations_service() -> AgentConversationsService:
    """Get the global agent conversations service instance"""
    global _agent_conversations_service
    if _agent_conversations_service is None:
        _agent_conversations_service = AgentConversationsService()
    return _agent_conversations_service

def get_agent_messages_service() -> AgentMessagesService:
    """Get the global agent messages service instance"""
    global _agent_messages_service
    if _agent_messages_service is None:
        _agent_messages_service = AgentMessagesService()
    return _agent_messages_service

def get_agent_summaries_service() -> AgentSummariesService:
    """Get the global agent summaries service instance"""
    global _agent_summaries_service
    if _agent_summaries_service is None:
        _agent_summaries_service = AgentSummariesService()
    return _agent_summaries_service