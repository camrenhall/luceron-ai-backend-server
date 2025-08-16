"""
Document and analysis-related Pydantic models
"""

from typing import Optional, List
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

class ProcessedFile(BaseModel):
    original_filename: str
    processed_filename: str
    file_type: str
    file_size: int
    s3_location: str
    s3_key: str
    page_number: Optional[int] = None  # For multi-page PDFs

class FileUploadResponse(BaseModel):
    case_id: str
    total_files_processed: int
    documents_created: int
    processed_files: List[ProcessedFile]
    analysis_triggered: bool
    workflow_ids: List[str]
    message: str

class DocumentUploadResponse(BaseModel):
    documents_created: int
    analysis_triggered: bool
    workflow_ids: List[str]
    message: str