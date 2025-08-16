"""
Webhook-related Pydantic models
"""

from typing import Optional, List
from pydantic import BaseModel, Field

class S3UploadFile(BaseModel):
    fileName: str
    fileSize: int
    fileType: str
    s3Location: str
    s3Key: str
    s3ETag: Optional[str] = None
    uploadedAt: str
    status: str = "success"

class S3UploadWebhookRequest(BaseModel):
    event: str
    timestamp: str
    summary: dict
    files: List[S3UploadFile]
    metadata: dict

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