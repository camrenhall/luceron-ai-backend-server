"""
Document analysis-related Pydantic models
"""

from typing import Optional
from pydantic import BaseModel

class AnalysisResultRequest(BaseModel):
    document_id: str
    case_id: str
    workflow_id: Optional[str] = None
    analysis_content: str
    model_used: str = "o3"
    tokens_used: Optional[int] = None
    analysis_status: str = "completed"

class AnalysisResultResponse(BaseModel):
    analysis_id: str
    document_id: str
    case_id: str
    status: str
    analyzed_at: str