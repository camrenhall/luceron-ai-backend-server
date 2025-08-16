"""
Case-related Pydantic models
"""

from typing import List, Optional
from pydantic import BaseModel

class CaseData(BaseModel):
    case_id: str
    client_email: str
    client_name: str
    client_phone: Optional[str] = None
    status: str

class RequestedDocument(BaseModel):
    document_name: str
    description: Optional[str] = None

class CaseCreateRequest(BaseModel):
    case_id: str
    client_name: str
    client_email: str
    client_phone: Optional[str] = None
    requested_documents: List[RequestedDocument]