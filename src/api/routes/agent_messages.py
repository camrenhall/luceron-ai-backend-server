"""
Agent messages API routes
"""

import asyncio
import logging
import json
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, Query

from models.agent import (
    AgentMessageCreate, AgentMessageUpdate, AgentMessageResponse,
    MessageRole
)
from services.agent_services import get_agent_messages_service, get_agent_conversations_service
from services.base_service import ServiceResult
from utils.auth import AuthConfig
from services.summary_service import trigger_summary_generation

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("", response_model=AgentMessageResponse)
async def create_message(
    request: AgentMessageCreate,
    _: bool = Depends(AuthConfig.get_auth_dependency())
):
    """Create a new message in a conversation"""
    messages_service = get_agent_messages_service()
    conversations_service = get_agent_conversations_service()
    
    try:
        # Verify conversation exists
        conv_result = await conversations_service.get_conversation_by_id(str(request.conversation_id))
        if not conv_result.success or not conv_result.data:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        # Create message using service (sequence number auto-generated)
        result = await messages_service.create_message(
            conversation_id=str(request.conversation_id),
            role=request.role.value,
            content=request.content,
            model_used=request.model_used,
            total_tokens=request.total_tokens,
            function_name=request.function_name,
            function_arguments=request.function_arguments,
            function_response=request.function_response
        )
        
        if not result.success:
            if result.error_type == "NOT_FOUND":
                raise HTTPException(status_code=404, detail=result.error)
            elif result.error_type == "CONFLICT":
                raise HTTPException(status_code=409, detail=result.error)
            elif result.error_type in ["INVALID_QUERY", "UNAUTHORIZED_FIELD", "RESOURCE_NOT_FOUND", "UNAUTHORIZED_OPERATION"]:
                raise HTTPException(status_code=400, detail=result.error)
            elif result.error_type == "FOREIGN_KEY_ERROR":
                raise HTTPException(status_code=400, detail=result.error)
            else:
                raise HTTPException(status_code=500, detail=result.error)
        
        if not result.data:
            raise HTTPException(status_code=500, detail="No data returned from service")
        
        message_data = result.data[0]
        
        # Create response
        response = AgentMessageResponse(
            message_id=message_data['message_id'],
            conversation_id=message_data['conversation_id'],
            role=MessageRole(message_data['role']),
            content=message_data['content'],
            total_tokens=message_data.get('total_tokens'),
            model_used=message_data['model_used'],
            function_name=message_data.get('function_name'),
            function_arguments=message_data.get('function_arguments'),
            function_response=message_data.get('function_response'),
            created_at=message_data['created_at'],
            sequence_number=message_data['sequence_number']
        )
        
        # Trigger async summary generation in background
        asyncio.create_task(trigger_summary_generation(str(request.conversation_id)))
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create message: {e}")
        raise HTTPException(status_code=500, detail=f"Service error: {str(e)}")

@router.get("/{message_id}", response_model=AgentMessageResponse)
async def get_message(
    message_id: str,
    _: bool = Depends(AuthConfig.get_auth_dependency())
):
    """Get message by ID"""
    messages_service = get_agent_messages_service()
    
    try:
        result = await messages_service.get_message_by_id(message_id)
        
        if not result.success:
            if result.error_type == "NOT_FOUND":
                raise HTTPException(status_code=404, detail="Message not found")
            elif result.error_type in ["INVALID_QUERY", "UNAUTHORIZED_FIELD", "RESOURCE_NOT_FOUND", "UNAUTHORIZED_OPERATION"]:
                raise HTTPException(status_code=400, detail=result.error)
            else:
                raise HTTPException(status_code=500, detail=result.error)
        
        if not result.data:
            raise HTTPException(status_code=404, detail="Message not found")
        
        message_data = result.data[0]
        
        return AgentMessageResponse(
            message_id=message_data['message_id'],
            conversation_id=message_data['conversation_id'],
            role=MessageRole(message_data['role']),
            content=message_data['content'],
            total_tokens=message_data.get('total_tokens'),
            model_used=message_data['model_used'],
            function_name=message_data.get('function_name'),
            function_arguments=message_data.get('function_arguments'),
            function_response=message_data.get('function_response'),
            created_at=message_data['created_at'],
            sequence_number=message_data['sequence_number']
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get message: {e}")
        raise HTTPException(status_code=500, detail=f"Service error: {str(e)}")

@router.put("/{message_id}", response_model=AgentMessageResponse)
async def update_message(
    message_id: str,
    request: AgentMessageUpdate,
    _: bool = Depends(AuthConfig.get_auth_dependency())
):
    """Update message content or metadata"""
    messages_service = get_agent_messages_service()
    
    try:
        # Build update data from request
        updates = {}
        
        if request.content is not None:
            updates["content"] = request.content
            
        if request.total_tokens is not None:
            updates["total_tokens"] = request.total_tokens
            
        if request.function_response is not None:
            updates["function_response"] = request.function_response
        
        if not updates:
            raise HTTPException(status_code=400, detail="No fields provided for update")
        
        # Update message using service
        result = await messages_service.update_message(message_id, updates)
        
        if not result.success:
            if result.error_type == "NOT_FOUND":
                raise HTTPException(status_code=404, detail="Message not found")
            elif result.error_type == "CONFLICT":
                raise HTTPException(status_code=409, detail=result.error)
            elif result.error_type in ["INVALID_QUERY", "UNAUTHORIZED_FIELD", "RESOURCE_NOT_FOUND", "UNAUTHORIZED_OPERATION"]:
                raise HTTPException(status_code=400, detail=result.error)
            elif result.error_type == "FOREIGN_KEY_ERROR":
                raise HTTPException(status_code=400, detail=result.error)
            else:
                raise HTTPException(status_code=500, detail=result.error)
        
        if not result.data:
            raise HTTPException(status_code=404, detail="Message not found")
        
        message_data = result.data[0]
        
        # Create response
        response = AgentMessageResponse(
            message_id=message_data['message_id'],
            conversation_id=message_data['conversation_id'],
            role=MessageRole(message_data['role']),
            content=message_data['content'],
            total_tokens=message_data.get('total_tokens'),
            model_used=message_data['model_used'],
            function_name=message_data.get('function_name'),
            function_arguments=message_data.get('function_arguments'),
            function_response=message_data.get('function_response'),
            created_at=message_data['created_at'],
            sequence_number=message_data['sequence_number']
        )
        
        # Trigger async summary generation in background
        asyncio.create_task(trigger_summary_generation(str(message_data['conversation_id'])))
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update message: {e}")
        raise HTTPException(status_code=500, detail=f"Service error: {str(e)}")

@router.delete("/{message_id}")
async def delete_message(
    message_id: str,
    _: bool = Depends(AuthConfig.get_auth_dependency())
):
    """Delete message"""
    messages_service = get_agent_messages_service()
    
    try:
        result = await messages_service.delete_message(message_id)
        
        if not result.success:
            if result.error_type == "NOT_FOUND":
                raise HTTPException(status_code=404, detail="Message not found")
            elif result.error_type in ["INVALID_QUERY", "UNAUTHORIZED_FIELD", "RESOURCE_NOT_FOUND", "UNAUTHORIZED_OPERATION"]:
                raise HTTPException(status_code=400, detail=result.error)
            elif result.error_type == "FOREIGN_KEY_ERROR":
                raise HTTPException(status_code=400, detail=result.error)
            else:
                raise HTTPException(status_code=500, detail=result.error)
        
        return {"message": "Message deleted successfully", "message_id": message_id}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete message: {e}")
        raise HTTPException(status_code=500, detail=f"Service error: {str(e)}")

@router.get("", response_model=List[AgentMessageResponse])
async def list_messages(
    conversation_id: Optional[str] = Query(None, description="Filter by conversation ID"),
    role: Optional[MessageRole] = Query(None, description="Filter by message role"),
    limit: int = Query(50, ge=1, le=500, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    _: bool = Depends(AuthConfig.get_auth_dependency())
):
    """List messages with optional filters"""
    messages_service = get_agent_messages_service()
    
    try:
        # Get messages with filters using service
        result = await messages_service.get_messages_with_filters(
            conversation_id=conversation_id,
            role=role.value if role else None,
            limit=limit,
            offset=offset
        )
        
        if not result.success:
            if result.error_type in ["INVALID_QUERY", "UNAUTHORIZED_FIELD", "RESOURCE_NOT_FOUND", "UNAUTHORIZED_OPERATION"]:
                raise HTTPException(status_code=400, detail=result.error)
            else:
                raise HTTPException(status_code=500, detail=result.error)
        
        # Convert data to response models
        messages = []
        for message_data in result.data or []:
            messages.append(AgentMessageResponse(
                message_id=message_data['message_id'],
                conversation_id=message_data['conversation_id'],
                role=MessageRole(message_data['role']),
                content=message_data['content'],
                total_tokens=message_data.get('total_tokens'),
                model_used=message_data['model_used'],
                function_name=message_data.get('function_name'),
                function_arguments=message_data.get('function_arguments'),
                function_response=message_data.get('function_response'),
                created_at=message_data['created_at'],
                sequence_number=message_data['sequence_number']
            ))
        
        return messages
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list messages: {e}")
        raise HTTPException(status_code=500, detail=f"Service error: {str(e)}")

@router.get("/conversation/{conversation_id}/history", response_model=List[AgentMessageResponse])
async def get_conversation_messages(
    conversation_id: str,
    limit: int = Query(50, ge=1, le=500, description="Maximum number of messages"),
    include_function_calls: bool = Query(True, description="Include function call details"),
    _: bool = Depends(AuthConfig.get_auth_dependency())
):
    """Get messages for a specific conversation in chronological order"""
    messages_service = get_agent_messages_service()
    
    try:
        # Get conversation history using service
        result = await messages_service.get_conversation_history(
            conversation_id=conversation_id,
            limit=limit,
            include_function_calls=include_function_calls
        )
        
        if not result.success:
            if result.error_type == "NOT_FOUND":
                raise HTTPException(status_code=404, detail="Conversation not found")
            elif result.error_type in ["INVALID_QUERY", "UNAUTHORIZED_FIELD", "RESOURCE_NOT_FOUND", "UNAUTHORIZED_OPERATION"]:
                raise HTTPException(status_code=400, detail=result.error)
            else:
                raise HTTPException(status_code=500, detail=result.error)
        
        # Convert data to response models
        messages = []
        for message_data in result.data or []:
            # Handle optional function call fields based on include_function_calls
            function_name = message_data.get('function_name') if include_function_calls else None
            function_arguments = message_data.get('function_arguments') if include_function_calls else None
            function_response = message_data.get('function_response') if include_function_calls else None
            
            messages.append(AgentMessageResponse(
                message_id=message_data['message_id'],
                conversation_id=message_data['conversation_id'],
                role=MessageRole(message_data['role']),
                content=message_data['content'],
                total_tokens=message_data.get('total_tokens'),
                model_used=message_data['model_used'],
                function_name=function_name,
                function_arguments=function_arguments,
                function_response=function_response,
                created_at=message_data['created_at'],
                sequence_number=message_data['sequence_number']
            ))
        
        return messages
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get conversation messages: {e}")
        raise HTTPException(status_code=500, detail=f"Service error: {str(e)}")