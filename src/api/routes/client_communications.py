"""
Client communications API routes
"""

import logging
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, Query

from models.communication import (
    ClientCommunicationCreateRequest, 
    ClientCommunicationUpdateRequest, 
    ClientCommunicationResponse
)
from models.enums import CommunicationChannel, CommunicationDirection, DeliveryStatus
from services.communications_service import get_communications_service
from services.cases_service import get_cases_service
from utils.auth import AuthConfig

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("", response_model=ClientCommunicationResponse)
async def create_communication(
    request: ClientCommunicationCreateRequest,
    _: bool = Depends(AuthConfig.get_auth_dependency())
):
    """Create a new client communication record"""
    communications_service = get_communications_service()
    cases_service = get_cases_service()
    
    try:
        # Verify case exists
        case_result = await cases_service.get_case_by_id(request.case_id)
        if not case_result.success or not case_result.data:
            raise HTTPException(status_code=404, detail="Case not found")
        
        # Convert sent_at to ISO string if needed
        sent_at_str = request.sent_at.isoformat() if request.sent_at else None
        
        result = await communications_service.create_communication(
            case_id=request.case_id,
            channel=request.channel.value,
            direction=request.direction.value,
            sender=request.sender,
            recipient=request.recipient,
            message_content=request.message_content,
            subject=request.subject,
            status=request.status.value,
            sent_at=sent_at_str,
            resend_id=request.resend_id
        )
        
        if not result.success:
            if result.error_type == "UNAUTHORIZED_OPERATION":
                raise HTTPException(status_code=403, detail=result.error)
            elif result.error_type == "INVALID_QUERY":
                raise HTTPException(status_code=400, detail=result.error)
            else:
                raise HTTPException(status_code=500, detail=result.error)
        
        communication_data = result.data[0]
        return ClientCommunicationResponse(
            communication_id=communication_data['communication_id'],
            case_id=communication_data['case_id'],
            channel=CommunicationChannel(communication_data['channel']),
            direction=CommunicationDirection(communication_data['direction']),
            status=DeliveryStatus(communication_data['status']),
            sender=communication_data['sender'],
            recipient=communication_data['recipient'],
            subject=communication_data['subject'],
            message_content=communication_data['message_content'],
            created_at=datetime.fromisoformat(communication_data['created_at'].replace('Z', '+00:00')) if isinstance(communication_data['created_at'], str) else communication_data['created_at'],
            sent_at=datetime.fromisoformat(communication_data['sent_at'].replace('Z', '+00:00')) if communication_data.get('sent_at') and isinstance(communication_data['sent_at'], str) else communication_data.get('sent_at'),
            opened_at=datetime.fromisoformat(communication_data['opened_at'].replace('Z', '+00:00')) if communication_data.get('opened_at') and isinstance(communication_data['opened_at'], str) else communication_data.get('opened_at'),
            resend_id=communication_data['resend_id']
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create communication: {e}")
        raise HTTPException(status_code=500, detail=f"Service error: {str(e)}")

@router.get("/{communication_id}", response_model=ClientCommunicationResponse)
async def get_communication(
    communication_id: str,
    _: bool = Depends(AuthConfig.get_auth_dependency())
):
    """Get communication by ID"""
    communications_service = get_communications_service()
    
    try:
        result = await communications_service.get_communication_by_id(communication_id)
        
        if not result.success:
            if result.error_type == "RESOURCE_NOT_FOUND":
                raise HTTPException(status_code=404, detail="Communication not found")
            elif result.error_type == "UNAUTHORIZED_OPERATION":
                raise HTTPException(status_code=403, detail=result.error)
            elif result.error_type == "INVALID_QUERY":
                raise HTTPException(status_code=400, detail=result.error)
            else:
                raise HTTPException(status_code=500, detail=result.error)
        
        if not result.data:
            raise HTTPException(status_code=404, detail="Communication not found")
        
        communication_data = result.data[0]
        return ClientCommunicationResponse(
            communication_id=communication_data['communication_id'],
            case_id=communication_data['case_id'],
            channel=CommunicationChannel(communication_data['channel']),
            direction=CommunicationDirection(communication_data['direction']),
            status=DeliveryStatus(communication_data['status']),
            sender=communication_data['sender'],
            recipient=communication_data['recipient'],
            subject=communication_data['subject'],
            message_content=communication_data['message_content'],
            created_at=datetime.fromisoformat(communication_data['created_at'].replace('Z', '+00:00')) if isinstance(communication_data['created_at'], str) else communication_data['created_at'],
            sent_at=datetime.fromisoformat(communication_data['sent_at'].replace('Z', '+00:00')) if communication_data.get('sent_at') and isinstance(communication_data['sent_at'], str) else communication_data.get('sent_at'),
            opened_at=datetime.fromisoformat(communication_data['opened_at'].replace('Z', '+00:00')) if communication_data.get('opened_at') and isinstance(communication_data['opened_at'], str) else communication_data.get('opened_at'),
            resend_id=communication_data['resend_id']
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get communication: {e}")
        raise HTTPException(status_code=500, detail=f"Service error: {str(e)}")

@router.put("/{communication_id}", response_model=ClientCommunicationResponse)
async def update_communication(
    communication_id: str,
    request: ClientCommunicationUpdateRequest,
    _: bool = Depends(AuthConfig.get_auth_dependency())
):
    """Update communication record"""
    communications_service = get_communications_service()
    
    try:
        # Check if communication exists first
        existing_result = await communications_service.get_communication_by_id(communication_id)
        if not existing_result.success or not existing_result.data:
            raise HTTPException(status_code=404, detail="Communication not found")
        
        # Build update data from request
        update_data = {}
        
        if request.channel is not None:
            update_data["channel"] = request.channel.value
            
        if request.direction is not None:
            update_data["direction"] = request.direction.value
            
        if request.status is not None:
            update_data["status"] = request.status.value
            
        if request.sender is not None:
            update_data["sender"] = request.sender
            
        if request.recipient is not None:
            update_data["recipient"] = request.recipient
            
        if request.subject is not None:
            update_data["subject"] = request.subject
            
        if request.message_content is not None:
            update_data["message_content"] = request.message_content
            
        if request.sent_at is not None:
            update_data["sent_at"] = request.sent_at.isoformat() if hasattr(request.sent_at, 'isoformat') else request.sent_at
            
        if request.opened_at is not None:
            update_data["opened_at"] = request.opened_at.isoformat() if hasattr(request.opened_at, 'isoformat') else request.opened_at
            
        if request.resend_id is not None:
            update_data["resend_id"] = request.resend_id
        
        if not update_data:
            raise HTTPException(status_code=400, detail="No fields provided for update")
        
        # Update the communication
        result = await communications_service.update(communication_id, update_data)
        
        if not result.success:
            if result.error_type == "RESOURCE_NOT_FOUND":
                raise HTTPException(status_code=404, detail="Communication not found")
            elif result.error_type == "UNAUTHORIZED_OPERATION":
                raise HTTPException(status_code=403, detail=result.error)
            elif result.error_type == "INVALID_QUERY":
                raise HTTPException(status_code=400, detail=result.error)
            else:
                raise HTTPException(status_code=500, detail=result.error)
        
        updated_comm = result.data[0]
        return ClientCommunicationResponse(
            communication_id=updated_comm['communication_id'],
            case_id=updated_comm['case_id'],
            channel=CommunicationChannel(updated_comm['channel']),
            direction=CommunicationDirection(updated_comm['direction']),
            status=DeliveryStatus(updated_comm['status']),
            sender=updated_comm['sender'],
            recipient=updated_comm['recipient'],
            subject=updated_comm['subject'],
            message_content=updated_comm['message_content'],
            created_at=datetime.fromisoformat(updated_comm['created_at'].replace('Z', '+00:00')) if isinstance(updated_comm['created_at'], str) else updated_comm['created_at'],
            sent_at=datetime.fromisoformat(updated_comm['sent_at'].replace('Z', '+00:00')) if updated_comm.get('sent_at') and isinstance(updated_comm['sent_at'], str) else updated_comm.get('sent_at'),
            opened_at=datetime.fromisoformat(updated_comm['opened_at'].replace('Z', '+00:00')) if updated_comm.get('opened_at') and isinstance(updated_comm['opened_at'], str) else updated_comm.get('opened_at'),
            resend_id=updated_comm['resend_id']
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update communication: {e}")
        raise HTTPException(status_code=500, detail=f"Service error: {str(e)}")

@router.delete("/{communication_id}")
async def delete_communication(
    communication_id: str,
    _: bool = Depends(AuthConfig.get_auth_dependency())
):
    """Delete communication record"""
    communications_service = get_communications_service()
    
    try:
        result = await communications_service.delete_communication(communication_id)
        
        if not result.success:
            if result.error_type == "RESOURCE_NOT_FOUND":
                raise HTTPException(status_code=404, detail="Communication not found")
            elif result.error_type == "UNAUTHORIZED_OPERATION":
                raise HTTPException(status_code=403, detail=result.error)
            elif result.error_type == "INVALID_QUERY":
                raise HTTPException(status_code=400, detail=result.error)
            else:
                raise HTTPException(status_code=500, detail=result.error)
        
        deleted_data = result.data[0]
        return {
            "message": "Communication deleted successfully",
            "communication_id": deleted_data['communication_id'],
            "case_id": deleted_data['case_id']
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete communication: {e}")
        raise HTTPException(status_code=500, detail=f"Service error: {str(e)}")

@router.get("", response_model=List[ClientCommunicationResponse])
async def list_communications(
    case_id: Optional[str] = Query(None, description="Filter by case ID"),
    channel: Optional[CommunicationChannel] = Query(None, description="Filter by channel"),
    direction: Optional[CommunicationDirection] = Query(None, description="Filter by direction"),
    status: Optional[DeliveryStatus] = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=500, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    _: bool = Depends(AuthConfig.get_auth_dependency())
):
    """List communications with optional filters"""
    communications_service = get_communications_service()
    
    try:
        result = await communications_service.search_communications(
            case_id=case_id,
            channel=channel.value if channel else None,
            direction=direction.value if direction else None,
            status=status.value if status else None,
            limit=limit,
            offset=offset
        )
        
        if not result.success:
            if result.error_type == "UNAUTHORIZED_OPERATION":
                raise HTTPException(status_code=403, detail=result.error)
            elif result.error_type == "INVALID_QUERY":
                raise HTTPException(status_code=400, detail=result.error)
            else:
                raise HTTPException(status_code=500, detail=result.error)
        
        return [
            ClientCommunicationResponse(
                communication_id=comm['communication_id'],
                case_id=comm['case_id'],
                channel=CommunicationChannel(comm['channel']),
                direction=CommunicationDirection(comm['direction']),
                status=DeliveryStatus(comm['status']),
                sender=comm['sender'],
                recipient=comm['recipient'],
                subject=comm['subject'],
                message_content=comm['message_content'],
                created_at=datetime.fromisoformat(comm['created_at'].replace('Z', '+00:00')) if isinstance(comm['created_at'], str) else comm['created_at'],
                sent_at=datetime.fromisoformat(comm['sent_at'].replace('Z', '+00:00')) if comm.get('sent_at') and isinstance(comm['sent_at'], str) else comm.get('sent_at'),
                opened_at=datetime.fromisoformat(comm['opened_at'].replace('Z', '+00:00')) if comm.get('opened_at') and isinstance(comm['opened_at'], str) else comm.get('opened_at'),
                resend_id=comm['resend_id']
            ) for comm in result.data
        ]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list communications: {e}")
        raise HTTPException(status_code=500, detail=f"Service error: {str(e)}")