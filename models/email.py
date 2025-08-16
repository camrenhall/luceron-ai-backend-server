"""
Email and communication-related Pydantic models
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field
from .enums import CommunicationChannel, CommunicationDirection, DeliveryStatus

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