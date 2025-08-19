"""
Document analysis-related Pydantic models
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field, validator
from models.enums import Status

class DocumentData(BaseModel):
    document_id: UUID
    case_id: UUID
    original_file_name: str
    original_file_size: int
    original_file_type: str
    original_s3_location: str
    original_s3_key: str
    status: Status = Status.PENDING
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
    analysis_content: str
    analysis_status: Status = Status.COMPLETED
    model_used: str
    tokens_used: Optional[int] = None
    analyzed_at: datetime
    created_at: datetime
    analysis_reasoning: Optional[str] = None

class AnalysisResultRequest(BaseModel):
    document_id: UUID
    case_id: UUID
    analysis_content: str
    model_used: str = "o3"
    tokens_used: Optional[int] = None
    analysis_status: Status = Status.COMPLETED
    analysis_reasoning: Optional[str] = None

class AnalysisResultResponse(BaseModel):
    analysis_id: UUID
    document_id: UUID
    case_id: UUID
    status: str
    analyzed_at: datetime


# Lambda Integration Models

class ProcessedFile(BaseModel):
    """Represents a processed file from the Lambda team"""
    file_key: str = Field(..., description="S3 key or identifier for the processed file")
    original_filename_pattern: str = Field(..., description="Pattern to match against original filenames")
    
    @validator('file_key')
    def validate_file_key(cls, v):
        if not v or not v.strip():
            raise ValueError('file_key cannot be empty')
        return v.strip()
    
    @validator('original_filename_pattern')
    def validate_filename_pattern(cls, v):
        if not v or not v.strip():
            raise ValueError('original_filename_pattern cannot be empty')
        return v.strip()


class DocumentLookupRequest(BaseModel):
    """Request model for batch document lookup"""
    batch_id: str = Field(..., description="Batch identifier to lookup documents for")
    processed_files: List[ProcessedFile] = Field(..., description="List of processed files to match")
    
    @validator('batch_id')
    def validate_batch_id(cls, v):
        if not v or not v.strip():
            raise ValueError('batch_id cannot be empty')
        return v.strip()
    
    @validator('processed_files')
    def validate_processed_files(cls, v):
        if not v:
            raise ValueError('processed_files cannot be empty')
        if len(v) > 1000:  # Reasonable limit for batch operations
            raise ValueError('processed_files cannot exceed 1000 items')
        return v


class DocumentMapping(BaseModel):
    """Represents a mapping between processed file and document"""
    file_key: str
    document_id: Optional[str] = None
    found: bool
    confidence_score: Optional[float] = Field(None, ge=0.0, le=1.0, description="Matching confidence (0-1)")


class DocumentLookupResponse(BaseModel):
    """Response model for batch document lookup"""
    success: bool
    batch_id: str
    total_requested: int
    total_found: int
    mappings: List[DocumentMapping]


class BulkAnalysisRecord(BaseModel):
    """Individual analysis record for bulk operations"""
    document_id: UUID = Field(..., description="Document UUID to associate analysis with")
    case_id: UUID = Field(..., description="Case UUID for the analysis")
    analysis_content: str = Field(..., description="JSON string containing analysis results")
    analysis_status: Status = Field(Status.COMPLETED, description="Status of the analysis")
    model_used: str = Field(..., description="Model identifier used for analysis")
    tokens_used: Optional[int] = Field(None, ge=0, description="Number of tokens consumed")
    analyzed_at: datetime = Field(..., description="ISO timestamp when analysis was performed")
    analysis_reasoning: Optional[str] = Field(None, description="Reasoning behind the analysis process")
    
    @validator('analysis_content')
    def validate_analysis_content(cls, v):
        if not v or not v.strip():
            raise ValueError('analysis_content cannot be empty')
        # Attempt to validate JSON structure
        try:
            import json
            json.loads(v)
        except json.JSONDecodeError:
            raise ValueError('analysis_content must be valid JSON')
        return v.strip()
    
    @validator('model_used')
    def validate_model_used(cls, v):
        if not v or not v.strip():
            raise ValueError('model_used cannot be empty')
        return v.strip()
    
    @validator('analysis_reasoning')
    def validate_analysis_reasoning(cls, v):
        if v is not None and not v.strip():
            raise ValueError('analysis_reasoning cannot be empty string')
        return v.strip() if v else v


class BulkAnalysisRequest(BaseModel):
    """Request model for bulk analysis persistence"""
    analyses: List[BulkAnalysisRecord] = Field(..., description="List of analysis records to persist")
    
    @validator('analyses')
    def validate_analyses(cls, v):
        if not v:
            raise ValueError('analyses cannot be empty')
        if len(v) > 500:  # Reasonable limit for bulk operations
            raise ValueError('analyses cannot exceed 500 items per request')
        return v


class AnalysisFailure(BaseModel):
    """Represents a failed analysis record"""
    index: int
    record_id: Optional[str] = None
    error: str
    error_code: Optional[str] = None


class BulkAnalysisResponse(BaseModel):
    """Response model for bulk analysis persistence"""
    success: bool
    total_requested: int
    inserted_count: int
    failed_count: int = 0
    failed_records: Optional[List[AnalysisFailure]] = None
    processing_time_ms: Optional[int] = None


# Document Management Models

class DocumentCreateRequest(BaseModel):
    """Request model for creating a new document record (Upload Time)"""
    case_id: UUID = Field(..., description="Case UUID that this document belongs to")
    original_file_name: str = Field(..., max_length=500, description="Original filename")
    original_file_size: int = Field(..., gt=0, description="File size in bytes")
    original_file_type: str = Field(..., max_length=100, description="MIME type or file extension")
    original_s3_location: str = Field(..., description="S3 bucket/region location")
    original_s3_key: str = Field(..., max_length=1000, description="S3 object key")
    batch_id: Optional[str] = Field(None, max_length=255, description="Optional batch identifier")
    status: Status = Field(Status.PENDING, description="Initial document status")
    
    @validator('original_file_name')
    def validate_filename(cls, v):
        if not v or not v.strip():
            raise ValueError('original_file_name cannot be empty')
        return v.strip()
    
    @validator('original_file_type')
    def validate_file_type(cls, v):
        if not v or not v.strip():
            raise ValueError('original_file_type cannot be empty')
        return v.strip()
    
    @validator('original_s3_location')
    def validate_s3_location(cls, v):
        if not v or not v.strip():
            raise ValueError('original_s3_location cannot be empty')
        return v.strip()
    
    @validator('original_s3_key')
    def validate_s3_key(cls, v):
        if not v or not v.strip():
            raise ValueError('original_s3_key cannot be empty')
        return v.strip()


class DocumentUpdateRequest(BaseModel):
    """Request model for updating document record (Processing Time)"""
    processed_file_name: Optional[str] = Field(None, max_length=500, description="Processed filename (e.g., PNG)")
    processed_file_size: Optional[int] = Field(None, gt=0, description="Processed file size in bytes")
    processed_s3_location: Optional[str] = Field(None, description="Processed file S3 location")
    processed_s3_key: Optional[str] = Field(None, max_length=1000, description="Processed file S3 key")
    status: Optional[Status] = Field(None, description="Updated document status")
    
    @validator('processed_file_name')
    def validate_processed_filename(cls, v):
        if v is not None and (not v or not v.strip()):
            raise ValueError('processed_file_name cannot be empty string')
        return v.strip() if v else v
    
    @validator('processed_s3_location')
    def validate_processed_s3_location(cls, v):
        if v is not None and (not v or not v.strip()):
            raise ValueError('processed_s3_location cannot be empty string')
        return v.strip() if v else v
    
    @validator('processed_s3_key')
    def validate_processed_s3_key(cls, v):
        if v is not None and (not v or not v.strip()):
            raise ValueError('processed_s3_key cannot be empty string')
        return v.strip() if v else v
    
    class Config:
        # Ensure at least one field is provided for update
        extra = "forbid"


class DocumentCreateResponse(BaseModel):
    """Response model for document creation"""
    success: bool
    document_id: UUID
    case_id: UUID
    original_file_name: str
    status: Status
    created_at: datetime
    message: str = "Document record created successfully"


class DocumentUpdateResponse(BaseModel):
    """Response model for document update"""
    success: bool
    document_id: UUID
    updated_fields: List[str]
    status: Status
    updated_at: datetime
    message: str = "Document record updated successfully"


# Enhanced Document Analysis Models

class DocumentAnalysisUpdateRequest(BaseModel):
    """Request model for updating document analysis"""
    analysis_content: Optional[str] = Field(None, description="Updated analysis content JSON")
    analysis_status: Optional[Status] = Field(None, description="Updated analysis status")
    model_used: Optional[str] = Field(None, description="Updated model identifier")
    tokens_used: Optional[int] = Field(None, ge=0, description="Updated token count")
    analysis_reasoning: Optional[str] = Field(None, description="Updated reasoning behind the analysis process")
    
    @validator('analysis_content')
    def validate_analysis_content(cls, v):
        if v is not None:
            if not v or not v.strip():
                raise ValueError('analysis_content cannot be empty string')
            try:
                import json
                json.loads(v)
            except json.JSONDecodeError:
                raise ValueError('analysis_content must be valid JSON')
        return v.strip() if v else v
    
    @validator('model_used')
    def validate_model_used(cls, v):
        if v is not None and (not v or not v.strip()):
            raise ValueError('model_used cannot be empty string')
        return v.strip() if v else v
    
    @validator('analysis_reasoning')
    def validate_analysis_reasoning(cls, v):
        if v is not None and (not v or not v.strip()):
            raise ValueError('analysis_reasoning cannot be empty string')
        return v.strip() if v else v
    
    class Config:
        extra = "forbid"


class DocumentAnalysisUpdateResponse(BaseModel):
    """Response model for document analysis update"""
    success: bool
    analysis_id: UUID
    updated_fields: List[str]
    updated_at: datetime
    message: str = "Analysis updated successfully"


class DocumentAnalysisByCaseResponse(BaseModel):
    """Response model for retrieving all analyses for a case"""
    case_id: UUID
    total_analyses: int
    total_tokens_used: Optional[int]
    analyses: List[DocumentAnalysisData]
    aggregated_content: Optional[Dict[str, Any]] = Field(None, description="Optional aggregated analysis data")


class DocumentAnalysisAggregatedSummary(BaseModel):
    """Model for aggregated analysis summary computed via SQL"""
    case_id: UUID
    total_documents: int
    total_tokens: Optional[int]
    models_used: List[str]
    status_breakdown: Dict[str, int]
    earliest_analysis: Optional[datetime]
    latest_analysis: Optional[datetime]
    aggregated_insights: Optional[Dict[str, Any]]