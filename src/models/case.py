"""
Case-related Pydantic models
"""

from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel
from uuid import UUID

class CaseData(BaseModel):
    case_id: UUID
    client_email: str
    client_name: str
    client_phone: Optional[str] = None
    status: str
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

class CaseResponse(BaseModel):
    case_id: UUID
    client_email: str
    client_name: str
    client_phone: Optional[str] = None
    status: str
    created_at: datetime
    requested_documents: Optional[List[RequestedDocumentData]] = None