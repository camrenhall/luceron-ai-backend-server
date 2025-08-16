"""
Workflow-related Pydantic models
"""

from typing import Optional, dict
from pydantic import BaseModel
from .enums import WorkflowStatus

class ReasoningStep(BaseModel):
    timestamp: str
    thought: str
    action: Optional[str] = None
    action_input: Optional[dict] = None
    action_output: Optional[str] = None

class WorkflowCreateRequest(BaseModel):
    workflow_id: str
    agent_type: str = "CommunicationsAgent"
    case_id: Optional[str] = None
    status: WorkflowStatus
    initial_prompt: str

class WorkflowStatusRequest(BaseModel):
    status: WorkflowStatus