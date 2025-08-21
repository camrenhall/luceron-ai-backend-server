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

# Unified Status enum for all processing entities (workflows, documents, analysis)
class Status(str, Enum):
    """
    Unified status enum for all processing entities in the system.
    
    - PENDING: Initial state, entity created but not yet being processed
    - PROCESSING: Entity is currently being worked on
    - COMPLETED: Processing finished successfully
    - FAILED: Processing encountered an error and stopped
    """
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

# Case status enum for database ENUM type
class CaseStatus(str, Enum):
    """
    Case status enum matching the database ENUM type.
    Only two values are allowed: OPEN and CLOSED.
    """
    OPEN = "OPEN"
    CLOSED = "CLOSED"

