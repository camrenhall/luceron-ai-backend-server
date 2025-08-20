"""
Client communications API routes
"""

import logging
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, Query
import asyncpg

from models.communication import (
    ClientCommunicationCreateRequest, 
    ClientCommunicationUpdateRequest, 
    ClientCommunicationResponse
)
from models.enums import CommunicationChannel, CommunicationDirection, DeliveryStatus
from database.connection import get_db_pool
from utils.auth import AuthConfig

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("", response_model=ClientCommunicationResponse)
async def create_communication(
    request: ClientCommunicationCreateRequest,
    _: bool = Depends(AuthConfig.get_auth_dependency())
):
    """Create a new client communication record"""
    db_pool = get_db_pool()
    
    try:
        async with db_pool.acquire() as conn:
            # Verify case exists
            case_exists = await conn.fetchval(
                "SELECT EXISTS(SELECT 1 FROM cases WHERE case_id = $1)", 
                request.case_id
            )
            if not case_exists:
                raise HTTPException(status_code=404, detail="Case not found")
            
            communication_id = await conn.fetchval("""
                INSERT INTO client_communications 
                (case_id, channel, direction, status, sender, recipient, subject, message_content, sent_at, resend_id)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                RETURNING communication_id
            """,
            request.case_id, request.channel.value, request.direction.value,
            request.status.value, request.sender, request.recipient, request.subject,
            request.message_content, request.sent_at, request.resend_id)
            
            # Get the created communication
            communication = await conn.fetchrow("""
                SELECT communication_id, case_id, channel, direction, status, sender, recipient,
                       subject, message_content, created_at, sent_at, opened_at, resend_id
                FROM client_communications 
                WHERE communication_id = $1
            """, communication_id)
            
            return ClientCommunicationResponse(
                communication_id=communication['communication_id'],
                case_id=communication['case_id'],
                channel=CommunicationChannel(communication['channel']),
                direction=CommunicationDirection(communication['direction']),
                status=DeliveryStatus(communication['status']),
                sender=communication['sender'],
                recipient=communication['recipient'],
                subject=communication['subject'],
                message_content=communication['message_content'],
                created_at=communication['created_at'],
                sent_at=communication['sent_at'],
                opened_at=communication['opened_at'],
                resend_id=communication['resend_id']
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create communication: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.get("/{communication_id}", response_model=ClientCommunicationResponse)
async def get_communication(
    communication_id: str,
    _: bool = Depends(AuthConfig.get_auth_dependency())
):
    """Get communication by ID"""
    db_pool = get_db_pool()
    
    try:
        async with db_pool.acquire() as conn:
            communication = await conn.fetchrow("""
                SELECT communication_id, case_id, channel, direction, status, sender, recipient,
                       subject, message_content, created_at, sent_at, opened_at, resend_id
                FROM client_communications 
                WHERE communication_id = $1
            """, communication_id)
            
            if not communication:
                raise HTTPException(status_code=404, detail="Communication not found")
            
            return ClientCommunicationResponse(
                communication_id=communication['communication_id'],
                case_id=communication['case_id'],
                channel=CommunicationChannel(communication['channel']),
                direction=CommunicationDirection(communication['direction']),
                status=DeliveryStatus(communication['status']),
                sender=communication['sender'],
                recipient=communication['recipient'],
                subject=communication['subject'],
                message_content=communication['message_content'],
                created_at=communication['created_at'],
                sent_at=communication['sent_at'],
                opened_at=communication['opened_at'],
                resend_id=communication['resend_id']
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get communication: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.put("/{communication_id}", response_model=ClientCommunicationResponse)
async def update_communication(
    communication_id: str,
    request: ClientCommunicationUpdateRequest,
    _: bool = Depends(AuthConfig.get_auth_dependency())
):
    """Update communication record"""
    db_pool = get_db_pool()
    
    try:
        async with db_pool.acquire() as conn:
            # Check if communication exists
            existing_comm = await conn.fetchrow(
                "SELECT * FROM client_communications WHERE communication_id = $1", 
                communication_id
            )
            
            if not existing_comm:
                raise HTTPException(status_code=404, detail="Communication not found")
            
            # Build dynamic update query
            update_fields = []
            update_values = []
            param_count = 1
            
            if request.channel is not None:
                update_fields.append(f"channel = ${param_count}")
                update_values.append(request.channel.value)
                param_count += 1
                
            if request.direction is not None:
                update_fields.append(f"direction = ${param_count}")
                update_values.append(request.direction.value)
                param_count += 1
                
            if request.status is not None:
                update_fields.append(f"status = ${param_count}")
                update_values.append(request.status.value)
                param_count += 1
                
            if request.sender is not None:
                update_fields.append(f"sender = ${param_count}")
                update_values.append(request.sender)
                param_count += 1
                
            if request.recipient is not None:
                update_fields.append(f"recipient = ${param_count}")
                update_values.append(request.recipient)
                param_count += 1
                
            if request.subject is not None:
                update_fields.append(f"subject = ${param_count}")
                update_values.append(request.subject)
                param_count += 1
                
            if request.message_content is not None:
                update_fields.append(f"message_content = ${param_count}")
                update_values.append(request.message_content)
                param_count += 1
                
            if request.sent_at is not None:
                update_fields.append(f"sent_at = ${param_count}")
                update_values.append(request.sent_at)
                param_count += 1
                
            if request.opened_at is not None:
                update_fields.append(f"opened_at = ${param_count}")
                update_values.append(request.opened_at)
                param_count += 1
                
            if request.resend_id is not None:
                update_fields.append(f"resend_id = ${param_count}")
                update_values.append(request.resend_id)
                param_count += 1
            
            if not update_fields:
                raise HTTPException(status_code=400, detail="No fields provided for update")
            
            update_values.append(communication_id)  # for WHERE clause
            
            query = f"""
                UPDATE client_communications 
                SET {', '.join(update_fields)}
                WHERE communication_id = ${param_count}
                RETURNING communication_id, case_id, channel, direction, status, sender, recipient,
                          subject, message_content, created_at, sent_at, opened_at, resend_id
            """
            
            updated_comm = await conn.fetchrow(query, *update_values)
            
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
                created_at=updated_comm['created_at'],
                sent_at=updated_comm['sent_at'],
                opened_at=updated_comm['opened_at'],
                resend_id=updated_comm['resend_id']
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update communication: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.delete("/{communication_id}")
async def delete_communication(
    communication_id: str,
    _: bool = Depends(AuthConfig.get_auth_dependency())
):
    """Delete communication record"""
    db_pool = get_db_pool()
    
    try:
        async with db_pool.acquire() as conn:
            # Check if communication exists
            existing_comm = await conn.fetchrow(
                "SELECT communication_id, case_id FROM client_communications WHERE communication_id = $1", 
                communication_id
            )
            
            if not existing_comm:
                raise HTTPException(status_code=404, detail="Communication not found")
            
            # Delete the communication
            await conn.execute(
                "DELETE FROM client_communications WHERE communication_id = $1",
                communication_id
            )
            
            return {
                "message": "Communication deleted successfully",
                "communication_id": communication_id,
                "case_id": str(existing_comm['case_id'])
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete communication: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

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
    db_pool = get_db_pool()
    
    try:
        async with db_pool.acquire() as conn:
            # Build dynamic WHERE clause
            where_conditions = []
            query_params = []
            param_count = 1
            
            if case_id:
                where_conditions.append(f"case_id = ${param_count}")
                query_params.append(case_id)
                param_count += 1
                
            if channel:
                where_conditions.append(f"channel = ${param_count}")
                query_params.append(channel.value)
                param_count += 1
                
            if direction:
                where_conditions.append(f"direction = ${param_count}")
                query_params.append(direction.value)
                param_count += 1
                
            if status:
                where_conditions.append(f"status = ${param_count}")
                query_params.append(status.value)
                param_count += 1
            
            where_clause = f"WHERE {' AND '.join(where_conditions)}" if where_conditions else ""
            
            query = f"""
                SELECT communication_id, case_id, channel, direction, status, sender, recipient,
                       subject, message_content, created_at, sent_at, opened_at, resend_id
                FROM client_communications 
                {where_clause}
                ORDER BY created_at DESC
                LIMIT ${param_count} OFFSET ${param_count + 1}
            """
            query_params.extend([limit, offset])
            
            communications = await conn.fetch(query, *query_params)
            
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
                    created_at=comm['created_at'],
                    sent_at=comm['sent_at'],
                    opened_at=comm['opened_at'],
                    resend_id=comm['resend_id']
                ) for comm in communications
            ]
            
    except Exception as e:
        logger.error(f"Failed to list communications: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")