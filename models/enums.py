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
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"