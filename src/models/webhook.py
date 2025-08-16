"""
Webhook-related Pydantic models
"""

from typing import Optional, List
from pydantic import BaseModel, Field

class ResendTag(BaseModel):
    name: str
    value: str

class ResendFailedInfo(BaseModel):
    reason: str

class ResendBounceInfo(BaseModel):
    message: str
    subType: str
    type: str

class ResendWebhookData(BaseModel):
    broadcast_id: Optional[str] = None
    created_at: str  # This is when email was created (NOT when event occurred)
    email_id: str
    from_: str = Field(alias="from")
    to: List[str]
    subject: str
    tags: Optional[List[ResendTag]] = []
    # Optional fields for different event types
    failed: Optional[ResendFailedInfo] = None
    bounce: Optional[ResendBounceInfo] = None

class ResendWebhook(BaseModel):
    type: str  # "email.opened", "email.delivered", "email.failed", "email.bounced"
    created_at: str  # This is when event occurred (webhook timestamp)
    data: ResendWebhookData