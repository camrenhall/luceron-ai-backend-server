"""
Request models for agent database operations
"""

from typing import Optional, List
from pydantic import BaseModel

class AgentDbHints(BaseModel):
    """Optional hints to guide resource selection"""
    resources: Optional[List[str]] = None

class AgentDbRequest(BaseModel):
    """Request model for agent database operations"""
    natural_language: str
    hints: Optional[AgentDbHints] = None