"""
Error log Pydantic models
"""

from typing import Optional, Dict, Any
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel

class ErrorLogCreate(BaseModel):
    component: str
    error_message: str
    severity: str = "medium"
    context: Optional[Dict[str, Any]] = None

class ErrorLogResponse(BaseModel):
    error_id: UUID
    component: str
    error_message: str
    severity: str
    context: Optional[Dict[str, Any]]
    email_sent: bool
    created_at: datetime
    updated_at: datetime

class ErrorLogStats(BaseModel):
    total_errors: int
    emails_sent: int
    critical_errors: int
    high_errors: int
    medium_errors: int
    low_errors: int
    last_error_at: Optional[datetime]
    last_email_sent_at: Optional[datetime]