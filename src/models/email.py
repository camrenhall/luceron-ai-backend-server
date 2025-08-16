"""
Email and communication-related Pydantic models
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field
from models.enums import CommunicationChannel, CommunicationDirection, DeliveryStatus

class EmailRequest(BaseModel):
    recipient_email: str
    subject: str
    body: str
    html_body: Optional[str] = None
    case_id: str
    email_type: str = "custom"
    metadata: Optional[Dict[str, Any]] = {}

class EmailResponse(BaseModel):
    message_id: str
    status: str
    recipient: str
    case_id: str
    sent_via: str

class ClientCommunication(BaseModel):
    communication_id: Optional[UUID] = None
    case_id: UUID
    channel: CommunicationChannel
    direction: CommunicationDirection
    status: DeliveryStatus
    opened_at: Optional[datetime] = None
    sender: str
    recipient: str
    subject: Optional[str] = None
    message_content: str
    created_at: Optional[datetime] = None
    sent_at: Optional[datetime] = None
    resend_id: Optional[str] = None

class ClientCommunicationCreate(BaseModel):
    case_id: UUID
    channel: CommunicationChannel
    direction: CommunicationDirection
    status: DeliveryStatus = DeliveryStatus.SENT
    sender: str
    recipient: str
    subject: Optional[str] = None
    message_content: str
    sent_at: Optional[datetime] = None
    resend_id: Optional[str] = None