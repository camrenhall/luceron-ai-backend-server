"""
Case-related Pydantic models
"""

from typing import List, Optional, Union
from datetime import datetime
from pydantic import BaseModel, Field
from uuid import UUID
from enum import Enum
from models.enums import CaseStatus

class DateOperator(str, Enum):
    """Date comparison operators"""
    GT = "gt"  # greater than
    GTE = "gte"  # greater than or equal
    LT = "lt"  # less than
    LTE = "lte"  # less than or equal
    EQ = "eq"  # equals
    BETWEEN = "between"  # between two dates

class DateFilter(BaseModel):
    """Date filter with operator and value(s)"""
    operator: DateOperator
    value: datetime
    end_value: Optional[datetime] = None  # Used for BETWEEN operator
    
    def validate_between(self):
        """Validate that end_value is provided for BETWEEN operator"""
        if self.operator == DateOperator.BETWEEN and self.end_value is None:
            raise ValueError("end_value is required for BETWEEN operator")
        return self

class CaseData(BaseModel):
    case_id: UUID
    client_email: str
    client_name: str
    client_phone: Optional[str] = None
    status: CaseStatus
    created_at: datetime

class RequestedDocument(BaseModel):
    document_name: str
    description: Optional[str] = None

class RequestedDocumentData(BaseModel):
    requested_doc_id: UUID
    document_name: str
    description: Optional[str] = None
    is_completed: bool = False
    completed_at: Optional[datetime] = None
    is_flagged_for_review: bool = False
    notes: Optional[str] = None
    requested_at: datetime
    updated_at: datetime
    case_id: UUID

class CaseCreateRequest(BaseModel):
    client_name: str
    client_email: str
    client_phone: Optional[str] = None
    requested_documents: List[RequestedDocument]

class RequestedDocumentUpdateRequest(BaseModel):
    document_name: Optional[str] = None
    description: Optional[str] = None
    is_completed: Optional[bool] = None
    is_flagged_for_review: Optional[bool] = None
    notes: Optional[str] = None

class CaseResponse(BaseModel):
    case_id: UUID
    client_email: str
    client_name: str
    client_phone: Optional[str] = None
    status: CaseStatus
    created_at: datetime
    requested_documents: Optional[List[RequestedDocumentData]] = None

class CaseSearchQuery(BaseModel):
    """Search query parameters for cases"""
    client_name: Optional[str] = Field(None, description="Partial match on client name (first, last, or full)")
    client_email: Optional[str] = Field(None, description="Partial match on client email")
    client_phone: Optional[str] = Field(None, description="Partial match on client phone")
    status: Optional[CaseStatus] = Field(None, description="Exact match on case status")
    created_at: Optional[DateFilter] = Field(None, description="Date filter for case creation date")
    last_communication_date: Optional[DateFilter] = Field(None, description="Date filter for last communication date")
    use_fuzzy_matching: Optional[bool] = Field(False, description="Enable fuzzy matching for name and email searches")
    fuzzy_threshold: Optional[float] = Field(0.3, ge=0.0, le=1.0, description="Similarity threshold for fuzzy matching (0.0-1.0)")
    limit: Optional[int] = Field(50, ge=1, le=500, description="Maximum number of results to return")
    offset: Optional[int] = Field(0, ge=0, description="Number of results to skip")

class CaseSearchResponse(BaseModel):
    """Response model for case search"""
    total_count: int
    cases: List[dict]  # Will contain case data with last_communication_date
    limit: int
    offset: int