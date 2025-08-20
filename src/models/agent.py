"""
Agent state management Pydantic models
"""

from typing import Optional, Dict, Any, List
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel
from enum import Enum

class AgentType(str, Enum):
    COMMUNICATIONS_AGENT = "CommunicationsAgent"
    ANALYSIS_AGENT = "AnalysisAgent"

class MessageRole(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    FUNCTION = "function"

class ConversationStatus(str, Enum):
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    ARCHIVED = "ARCHIVED"

# Agent Conversations Models
class AgentConversationCreate(BaseModel):
    agent_type: AgentType
    status: ConversationStatus = ConversationStatus.ACTIVE

class AgentConversationUpdate(BaseModel):
    status: Optional[ConversationStatus] = None

class AgentConversationResponse(BaseModel):
    conversation_id: UUID
    agent_type: AgentType
    status: ConversationStatus
    total_tokens_used: int
    created_at: datetime
    updated_at: datetime

# Agent Messages Models
class AgentMessageCreate(BaseModel):
    conversation_id: UUID
    role: MessageRole
    content: Dict[str, Any]
    total_tokens: Optional[int] = None
    model_used: str
    function_name: Optional[str] = None
    function_arguments: Optional[Dict[str, Any]] = None
    function_response: Optional[Dict[str, Any]] = None

class AgentMessageUpdate(BaseModel):
    content: Optional[Dict[str, Any]] = None
    total_tokens: Optional[int] = None
    function_response: Optional[Dict[str, Any]] = None

class AgentMessageResponse(BaseModel):
    message_id: UUID
    conversation_id: UUID
    role: MessageRole
    content: Dict[str, Any]
    total_tokens: Optional[int]
    model_used: str
    function_name: Optional[str]
    function_arguments: Optional[Dict[str, Any]]
    function_response: Optional[Dict[str, Any]]
    created_at: datetime
    sequence_number: int

# Agent Summaries Models
class AgentSummaryCreate(BaseModel):
    conversation_id: UUID
    last_message_id: Optional[UUID] = None
    summary_content: str
    messages_summarized: int = 0

class AgentSummaryUpdate(BaseModel):
    summary_content: Optional[str] = None
    messages_summarized: Optional[int] = None

class AgentSummaryResponse(BaseModel):
    summary_id: UUID
    conversation_id: UUID
    last_message_id: Optional[UUID]
    summary_content: str
    messages_summarized: int
    created_at: datetime
    updated_at: datetime

# Agent Context Models
class AgentContextCreate(BaseModel):
    case_id: UUID
    agent_type: AgentType
    context_key: str
    context_value: Dict[str, Any]
    expires_at: Optional[datetime] = None

class AgentContextUpdate(BaseModel):
    context_value: Optional[Dict[str, Any]] = None
    expires_at: Optional[datetime] = None

class AgentContextResponse(BaseModel):
    context_id: UUID
    case_id: UUID
    agent_type: AgentType
    context_key: str
    context_value: Dict[str, Any]
    expires_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

# Composite Models for Complex Operations
class ConversationWithMessages(BaseModel):
    conversation: AgentConversationResponse
    messages: List[AgentMessageResponse]
    summaries: List[AgentSummaryResponse]

class ConversationHistoryRequest(BaseModel):
    limit: Optional[int] = 50
    include_summaries: Optional[bool] = True
    include_function_calls: Optional[bool] = True