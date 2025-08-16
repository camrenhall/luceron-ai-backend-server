"""
Enum definitions for the Legal Communications Backend
"""

from enum import Enum

# Communication-related enums
class CommunicationChannel(str, Enum):
    EMAIL = "email"
    SMS = "sms"

class CommunicationDirection(str, Enum):
    INCOMING = "incoming"
    OUTGOING = "outgoing"

class DeliveryStatus(str, Enum):
    SENT = "sent"
    DELIVERED = "delivered" 
    FAILED = "failed"
    OPENED = "opened"

# Workflow-related enums
class WorkflowStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    AWAITING_SCHEDULE = "AWAITING_SCHEDULE"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    PENDING_PLANNING = "PENDING_PLANNING"
    AWAITING_BATCH_COMPLETION = "AWAITING_BATCH_COMPLETION"
    SYNTHESIZING_RESULTS = "SYNTHESIZING_RESULTS"
    NEEDS_HUMAN_REVIEW = "NEEDS_HUMAN_REVIEW"

# Document-related enums
class DocumentStatus(str, Enum):
    UPLOADED = "uploaded"
    ANALYZING = "analyzing"
    ANALYZED = "analyzed"
    FAILED = "failed"

class AnalysisStatus(str, Enum):
    COMPLETED = "completed"
    FAILED = "failed"
    NEEDS_REVIEW = "needs_review"