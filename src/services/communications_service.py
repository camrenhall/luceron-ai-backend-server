"""
Communications service - business logic for client communication management
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from services.base_service import BaseService, ServiceResult

logger = logging.getLogger(__name__)

class CommunicationsService(BaseService):
    """Service for client communication operations"""
    
    def __init__(self, role: str = "api"):
        super().__init__("client_communications", role)
    
    async def create_communication(
        self,
        case_id: str,
        channel: str,
        direction: str,
        sender: str,
        recipient: str,
        message_content: str,
        subject: Optional[str] = None,
        status: str = "sent",
        sent_at: Optional[str] = None,
        resend_id: Optional[str] = None
    ) -> ServiceResult:
        """
        Create a new communication record
        
        Args:
            case_id: UUID of the associated case
            channel: Communication channel (EMAIL, SMS, etc.)
            direction: Direction (INBOUND, OUTBOUND)
            sender: Sender identifier
            recipient: Recipient identifier
            message_content: Content of the communication
            subject: Subject line (for emails)
            status: Delivery status (default: sent)
            sent_at: When the message was sent (ISO timestamp)
            resend_id: External service ID (e.g., Resend ID)
            
        Returns:
            ServiceResult with created communication data
        """
        communication_data = {
            "case_id": case_id,
            "channel": channel,
            "direction": direction,
            "sender": sender,
            "recipient": recipient,
            "message_content": message_content,
            "status": status
        }
        
        if subject:
            communication_data["subject"] = subject
        
        if sent_at:
            communication_data["sent_at"] = sent_at
        
        if resend_id:
            communication_data["resend_id"] = resend_id
        
        logger.info(f"Creating {direction} {channel} communication for case {case_id}")
        return await self.create(communication_data)
    
    async def create_email(
        self,
        case_id: str,
        direction: str,
        sender: str,
        recipient: str,
        subject: str,
        message_content: str,
        status: str = "sent",
        sent_at: Optional[str] = None,
        resend_id: Optional[str] = None
    ) -> ServiceResult:
        """
        Create an email communication record
        
        Args:
            case_id: UUID of the associated case
            direction: Direction (INBOUND, OUTBOUND)
            sender: Email sender
            recipient: Email recipient
            subject: Email subject
            message_content: Email content
            status: Delivery status (default: sent)
            sent_at: When email was sent (ISO timestamp)
            resend_id: Resend service ID
            
        Returns:
            ServiceResult with created email data
        """
        return await self.create_communication(
            case_id=case_id,
            channel="EMAIL",
            direction=direction,
            sender=sender,
            recipient=recipient,
            message_content=message_content,
            subject=subject,
            status=status,
            sent_at=sent_at,
            resend_id=resend_id
        )
    
    async def create_sms(
        self,
        case_id: str,
        direction: str,
        sender: str,
        recipient: str,
        message_content: str,
        status: str = "sent",
        sent_at: Optional[str] = None
    ) -> ServiceResult:
        """
        Create an SMS communication record
        
        Args:
            case_id: UUID of the associated case
            direction: Direction (INBOUND, OUTBOUND)
            sender: Phone number sender
            recipient: Phone number recipient
            message_content: SMS content
            status: Delivery status (default: sent)
            sent_at: When SMS was sent (ISO timestamp)
            
        Returns:
            ServiceResult with created SMS data
        """
        return await self.create_communication(
            case_id=case_id,
            channel="SMS",
            direction=direction,
            sender=sender,
            recipient=recipient,
            message_content=message_content,
            status=status,
            sent_at=sent_at
        )
    
    async def get_communication_by_id(self, communication_id: str) -> ServiceResult:
        """Get a communication by its ID"""
        return await self.get_by_id(communication_id)
    
    async def get_communications_by_case(self, case_id: str) -> ServiceResult:
        """Get all communications for a specific case"""
        return await self.read(
            filters={"case_id": case_id},
            order_by=[{"field": "created_at", "dir": "desc"}]
        )
    
    async def get_communications_by_channel(self, channel: str, limit: int = 100) -> ServiceResult:
        """Get communications by channel type"""
        return await self.get_by_field("channel", channel, limit)
    
    async def get_communications_by_direction(self, direction: str, limit: int = 100) -> ServiceResult:
        """Get communications by direction"""
        return await self.get_by_field("direction", direction, limit)
    
    async def get_communications_by_status(self, status: str, limit: int = 100) -> ServiceResult:
        """Get communications by delivery status"""
        return await self.get_by_field("status", status, limit)
    
    async def update_communication_status(self, communication_id: str, status: str) -> ServiceResult:
        """Update the delivery status of a communication"""
        logger.info(f"Updating communication {communication_id} status to: {status}")
        return await self.update(communication_id, {"status": status})
    
    async def mark_email_opened(self, communication_id: str, opened_at: Optional[str] = None) -> ServiceResult:
        """
        Mark an email as opened
        
        Args:
            communication_id: UUID of the communication
            opened_at: When email was opened (ISO timestamp, default: now)
            
        Returns:
            ServiceResult with updated communication data
        """
        update_data = {"status": "opened"}
        
        if opened_at:
            update_data["opened_at"] = opened_at
        else:
            update_data["opened_at"] = datetime.utcnow().isoformat()
        
        logger.info(f"Marking email {communication_id} as opened")
        return await self.update(communication_id, update_data)
    
    async def search_communications(
        self,
        case_id: Optional[str] = None,
        channel: Optional[str] = None,
        direction: Optional[str] = None,
        status: Optional[str] = None,
        sender_pattern: Optional[str] = None,
        recipient_pattern: Optional[str] = None,
        subject_pattern: Optional[str] = None,
        content_pattern: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> ServiceResult:
        """
        Search communications with various filters
        
        Args:
            case_id: Filter by case ID
            channel: Filter by channel
            direction: Filter by direction
            status: Filter by status
            sender_pattern: Pattern to match senders (ILIKE)
            recipient_pattern: Pattern to match recipients (ILIKE)
            subject_pattern: Pattern to match subjects (ILIKE)
            content_pattern: Pattern to match message content (ILIKE)
            limit: Maximum number of results
            offset: Number of results to skip
            
        Returns:
            ServiceResult with matching communications
        """
        filters = {}
        
        if case_id:
            filters["case_id"] = case_id
        
        if channel:
            filters["channel"] = channel
        
        if direction:
            filters["direction"] = direction
        
        if status:
            filters["status"] = status
        
        if sender_pattern:
            filters["sender"] = {
                "op": "ILIKE",
                "value": f"%{sender_pattern}%"
            }
        
        if recipient_pattern:
            filters["recipient"] = {
                "op": "ILIKE",
                "value": f"%{recipient_pattern}%"
            }
        
        if subject_pattern:
            filters["subject"] = {
                "op": "ILIKE",
                "value": f"%{subject_pattern}%"
            }
        
        if content_pattern:
            filters["message_content"] = {
                "op": "ILIKE",
                "value": f"%{content_pattern}%"
            }
        
        order_by = [{"field": "created_at", "dir": "desc"}]
        
        logger.info(f"Searching communications with filters: {filters}")
        return await self.read(
            filters=filters,
            order_by=order_by,
            limit=limit,
            offset=offset
        )
    
    async def get_recent_communications(self, limit: int = 50) -> ServiceResult:
        """Get most recent communications"""
        return await self.read(
            order_by=[{"field": "created_at", "dir": "desc"}],
            limit=limit
        )
    
    async def get_failed_communications(self, limit: int = 100) -> ServiceResult:
        """Get communications with failed delivery status"""
        return await self.get_by_field("status", "failed", limit)

# Global service instance
_communications_service: Optional[CommunicationsService] = None

def get_communications_service() -> CommunicationsService:
    """Get the global communications service instance"""
    global _communications_service
    if _communications_service is None:
        _communications_service = CommunicationsService()
    return _communications_service