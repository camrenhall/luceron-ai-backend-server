"""
Client communications-related Pydantic models
"""

from typing import Optional
from datetime import datetime
from pydantic import BaseModel
from uuid import UUID
from enum import Enum
from models.enums import CommunicationChannel, CommunicationDirection, DeliveryStatus

class ClientCommunicationCreateRequest(BaseModel):
    case_id: str
    channel: CommunicationChannel
    direction: CommunicationDirection
    status: DeliveryStatus
    sender: str
    recipient: str
    subject: Optional[str] = None
    message_content: str
    sent_at: Optional[datetime] = None
    resend_id: Optional[str] = None

class ClientCommunicationUpdateRequest(BaseModel):
    channel: Optional[CommunicationChannel] = None
    direction: Optional[CommunicationDirection] = None
    status: Optional[DeliveryStatus] = None
    sender: Optional[str] = None
    recipient: Optional[str] = None
    subject: Optional[str] = None
    message_content: Optional[str] = None
    sent_at: Optional[datetime] = None
    opened_at: Optional[datetime] = None
    resend_id: Optional[str] = None

class ClientCommunicationResponse(BaseModel):
    communication_id: UUID
    case_id: UUID
    channel: CommunicationChannel
    direction: CommunicationDirection
    status: DeliveryStatus
    sender: str
    recipient: str
    subject: Optional[str]
    message_content: str
    created_at: datetime
    sent_at: Optional[datetime]
    opened_at: Optional[datetime]
    resend_id: Optional[str]