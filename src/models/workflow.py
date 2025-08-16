"""
Workflow-related Pydantic models
"""

from typing import Optional, Dict, Any
from pydantic import BaseModel
from models.enums import WorkflowStatus

class ReasoningStep(BaseModel):
    timestamp: str
    thought: str
    action: Optional[str] = None
    action_input: Optional[Dict[str, Any]] = None
    action_output: Optional[str] = None

class WorkflowCreateRequest(BaseModel):
    workflow_id: str
    agent_type: str = "CommunicationsAgent"
    case_id: Optional[str] = None
    status: WorkflowStatus
    initial_prompt: str

class WorkflowStatusRequest(BaseModel):
    status: WorkflowStatus