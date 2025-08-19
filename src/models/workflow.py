"""
Workflow-related Pydantic models
"""

from typing import Optional, Dict, Any, List
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel
from models.enums import Status

class ReasoningStep(BaseModel):
    timestamp: str
    thought: str
    action: Optional[str] = None
    action_input: Optional[Dict[str, Any]] = None
    action_output: Optional[str] = None

class WorkflowStateData(BaseModel):
    workflow_id: UUID
    case_id: Optional[UUID] = None
    agent_type: str = "CommunicationsAgent"
    status: Status = Status.PENDING
    initial_prompt: str
    reasoning_chain: List[Dict[str, Any]] = []
    final_response: Optional[str] = None
    created_at: datetime

class WorkflowCreateRequest(BaseModel):
    agent_type: str = "CommunicationsAgent"
    case_id: Optional[UUID] = None
    status: Status = Status.PENDING
    initial_prompt: str

class WorkflowStatusRequest(BaseModel):
    status: Status

class WorkflowUpdateRequest(BaseModel):
    status: Optional[Status] = None
    reasoning_chain: Optional[List[Dict[str, Any]]] = None
    final_response: Optional[str] = None