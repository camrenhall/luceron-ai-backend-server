"""
Document analysis-related Pydantic models
"""

from typing import Optional
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel
from models.enums import DocumentStatus, AnalysisStatus

class DocumentData(BaseModel):
    document_id: UUID
    case_id: UUID
    original_file_name: str
    original_file_size: int
    original_file_type: str
    original_s3_location: str
    original_s3_key: str
    status: DocumentStatus = DocumentStatus.UPLOADED
    created_at: datetime
    processed_file_name: Optional[str] = None
    processed_file_size: Optional[int] = None
    processed_s3_location: Optional[str] = None
    processed_s3_key: Optional[str] = None
    batch_id: Optional[str] = None

class DocumentAnalysisData(BaseModel):
    analysis_id: UUID
    document_id: UUID
    case_id: UUID
    workflow_id: Optional[UUID] = None
    analysis_content: str
    analysis_status: AnalysisStatus = AnalysisStatus.COMPLETED
    model_used: str
    tokens_used: Optional[int] = None
    analyzed_at: datetime
    created_at: datetime

class AnalysisResultRequest(BaseModel):
    document_id: UUID
    case_id: UUID
    workflow_id: Optional[UUID] = None
    analysis_content: str
    model_used: str = "o3"
    tokens_used: Optional[int] = None
    analysis_status: AnalysisStatus = AnalysisStatus.COMPLETED

class AnalysisResultResponse(BaseModel):
    analysis_id: UUID
    document_id: UUID
    case_id: UUID
    status: str
    analyzed_at: datetime