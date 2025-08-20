"""
Error log Pydantic models
"""

from typing import Optional, Dict, Any
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel
from enum import Enum

class ErrorSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class ErrorLogCreate(BaseModel):
    component: str
    error_message: str
    severity: ErrorSeverity = ErrorSeverity.MEDIUM
    context: Optional[Dict[str, Any]] = None
    email_sent: bool = False

class ErrorLogUpdateRequest(BaseModel):
    component: Optional[str] = None
    error_message: Optional[str] = None
    severity: Optional[ErrorSeverity] = None
    context: Optional[Dict[str, Any]] = None
    email_sent: Optional[bool] = None

class ErrorLogResponse(BaseModel):
    error_id: UUID
    component: str
    error_message: str
    severity: ErrorSeverity
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