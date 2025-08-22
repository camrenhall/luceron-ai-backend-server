"""
Agent conversations API routes
"""

import logging
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, Query

from models.agent import (
    AgentConversationCreate, AgentConversationUpdate, AgentConversationResponse,
    ConversationWithMessages, ConversationHistoryRequest, AgentType, ConversationStatus,
    MessageRole, AgentMessageResponse, AgentSummaryResponse
)
from services.agent_services import (
    get_agent_conversations_service, get_agent_messages_service, get_agent_summaries_service
)
from utils.auth import AuthConfig

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("", response_model=AgentConversationResponse)
async def create_conversation(
    request: AgentConversationCreate,
    _: bool = Depends(AuthConfig.get_auth_dependency())
):
    """Create a new agent conversation"""
    agent_conversations_service = get_agent_conversations_service()
    
    try:
        result = await agent_conversations_service.create_conversation(
            agent_type=request.agent_type.value,
            status=request.status.value
        )
        
        if not result.success:
            logger.error(f"Failed to create conversation: {result.error}")
            raise HTTPException(status_code=500, detail=result.error)
        
        if not result.data or len(result.data) == 0:
            raise HTTPException(status_code=500, detail="No data returned from service")
        
        row = result.data[0]
        return AgentConversationResponse(
            conversation_id=row['conversation_id'],
            agent_type=AgentType(row['agent_type']),
            status=ConversationStatus(row['status']),
            total_tokens_used=row['total_tokens_used'],
            created_at=row['created_at'],
            updated_at=row['updated_at']
        )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create conversation: {e}")
        raise HTTPException(status_code=500, detail=f"Service error: {str(e)}")

@router.get("/{conversation_id}", response_model=AgentConversationResponse)
async def get_conversation(
    conversation_id: str,
    _: bool = Depends(AuthConfig.get_auth_dependency())
):
    """Get conversation by ID"""
    agent_conversations_service = get_agent_conversations_service()
    
    try:
        result = await agent_conversations_service.get_conversation_by_id(conversation_id)
        
        if not result.success:
            if result.error_type == "NOT_FOUND":
                raise HTTPException(status_code=404, detail="Conversation not found")
            logger.error(f"Failed to get conversation: {result.error}")
            raise HTTPException(status_code=500, detail=result.error)
        
        if not result.data or len(result.data) == 0:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        row = result.data[0]
        return AgentConversationResponse(
            conversation_id=row['conversation_id'],
            agent_type=AgentType(row['agent_type']),
            status=ConversationStatus(row['status']),
            total_tokens_used=row['total_tokens_used'],
            created_at=row['created_at'],
            updated_at=row['updated_at']
        )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get conversation: {e}")
        raise HTTPException(status_code=500, detail=f"Service error: {str(e)}")

@router.put("/{conversation_id}", response_model=AgentConversationResponse)
async def update_conversation(
    conversation_id: str,
    request: AgentConversationUpdate,
    _: bool = Depends(AuthConfig.get_auth_dependency())
):
    """Update conversation status"""
    agent_conversations_service = get_agent_conversations_service()
    
    try:
        # Build update data
        update_data = {}
        
        if request.status is not None:
            update_data["status"] = request.status.value
        
        if not update_data:
            raise HTTPException(status_code=400, detail="No fields provided for update")
        
        result = await agent_conversations_service.update(conversation_id, update_data)
        
        if not result.success:
            if result.error_type == "NOT_FOUND":
                raise HTTPException(status_code=404, detail="Conversation not found")
            logger.error(f"Failed to update conversation: {result.error}")
            raise HTTPException(status_code=500, detail=result.error)
        
        if not result.data or len(result.data) == 0:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        row = result.data[0]
        return AgentConversationResponse(
            conversation_id=row['conversation_id'],
            agent_type=AgentType(row['agent_type']),
            status=ConversationStatus(row['status']),
            total_tokens_used=row['total_tokens_used'],
            created_at=row['created_at'],
            updated_at=row['updated_at']
        )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update conversation: {e}")
        raise HTTPException(status_code=500, detail=f"Service error: {str(e)}")

@router.delete("/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    _: bool = Depends(AuthConfig.get_auth_dependency())
):
    """Delete conversation (cascades to messages and summaries)"""
    agent_conversations_service = get_agent_conversations_service()
    
    try:
        result = await agent_conversations_service.delete(conversation_id)
        
        if not result.success:
            if result.error_type == "NOT_FOUND":
                raise HTTPException(status_code=404, detail="Conversation not found")
            logger.error(f"Failed to delete conversation: {result.error}")
            raise HTTPException(status_code=500, detail=result.error)
        
        return {"message": "Conversation deleted successfully", "conversation_id": conversation_id}
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete conversation: {e}")
        raise HTTPException(status_code=500, detail=f"Service error: {str(e)}")

@router.get("", response_model=List[AgentConversationResponse])
async def list_conversations(
    agent_type: Optional[AgentType] = Query(None, description="Filter by agent type"),
    status: Optional[ConversationStatus] = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=500, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    _: bool = Depends(AuthConfig.get_auth_dependency())
):
    """List conversations with optional filters"""
    agent_conversations_service = get_agent_conversations_service()
    
    try:
        # Build filters
        filters = {}
        
        if agent_type:
            filters["agent_type"] = agent_type.value
                
        if status:
            filters["status"] = status.value
        
        # Build order_by for descending order by created_at
        order_by = [{"field": "created_at", "dir": "desc"}]
        
        result = await agent_conversations_service.read(
            filters=filters,
            order_by=order_by,
            limit=limit,
            offset=offset
        )
        
        if not result.success:
            logger.error(f"Failed to list conversations: {result.error}")
            raise HTTPException(status_code=500, detail=result.error)
        
        if not result.data:
            return []
        
        return [
            AgentConversationResponse(
                conversation_id=row['conversation_id'],
                agent_type=AgentType(row['agent_type']),
                status=ConversationStatus(row['status']),
                total_tokens_used=row['total_tokens_used'],
                created_at=row['created_at'],
                updated_at=row['updated_at']
            ) for row in result.data
        ]
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list conversations: {e}")
        raise HTTPException(status_code=500, detail=f"Service error: {str(e)}")

@router.get("/{conversation_id}/full", response_model=ConversationWithMessages)
async def get_conversation_with_messages(
    conversation_id: str,
    include_summaries: bool = Query(True, description="Include summaries in response"),
    include_function_calls: bool = Query(True, description="Include function call details"),
    _: bool = Depends(AuthConfig.get_auth_dependency())
):
    """Get conversation with all messages and summaries"""
    agent_conversations_service = get_agent_conversations_service()
    agent_messages_service = get_agent_messages_service()
    agent_summaries_service = get_agent_summaries_service()
    
    try:
        # Get conversation
        conv_result = await agent_conversations_service.get_conversation_by_id(conversation_id)
        
        if not conv_result.success:
            if conv_result.error_type == "NOT_FOUND":
                raise HTTPException(status_code=404, detail="Conversation not found")
            logger.error(f"Failed to get conversation: {conv_result.error}")
            raise HTTPException(status_code=500, detail=conv_result.error)
        
        if not conv_result.data or len(conv_result.data) == 0:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        conv_row = conv_result.data[0]
        
        # Get messages
        messages_result = await agent_messages_service.get_messages_by_conversation(conversation_id)
        
        if not messages_result.success:
            logger.error(f"Failed to get messages: {messages_result.error}")
            raise HTTPException(status_code=500, detail=messages_result.error)
        
        messages = messages_result.data or []
        
        # Get summaries if requested
        summaries = []
        if include_summaries:
            summaries_result = await agent_summaries_service.get_summaries_by_conversation(conversation_id)
            
            if not summaries_result.success:
                logger.error(f"Failed to get summaries: {summaries_result.error}")
                # Don't fail the whole request if summaries fail, just log and continue
                summaries = []
            else:
                summary_rows = summaries_result.data or []
                summaries = [
                    AgentSummaryResponse(
                        summary_id=row['summary_id'],
                        conversation_id=row['conversation_id'],
                        last_message_id=row['last_message_id'],
                        summary_content=row['summary_content'],
                        messages_summarized=row['messages_summarized'],
                        created_at=row['created_at'],
                        updated_at=row['updated_at']
                    ) for row in summary_rows
                ]
        
        # Build message responses
        message_responses = []
        for row in messages:
            message_data = {
                "message_id": row['message_id'],
                "conversation_id": row['conversation_id'],
                "role": MessageRole(row['role']),
                "content": row['content'],
                "total_tokens": row['total_tokens'],
                "model_used": row['model_used'],
                "created_at": row['created_at'],
                "sequence_number": row['sequence_number'],
                "function_name": None,
                "function_arguments": None,
                "function_response": None
            }
            
            if include_function_calls:
                message_data.update({
                    "function_name": row.get('function_name'),
                    "function_arguments": row.get('function_arguments'),
                    "function_response": row.get('function_response')
                })
            
            message_responses.append(AgentMessageResponse(**message_data))
        
        return ConversationWithMessages(
            conversation=AgentConversationResponse(
                conversation_id=conv_row['conversation_id'],
                agent_type=AgentType(conv_row['agent_type']),
                status=ConversationStatus(conv_row['status']),
                total_tokens_used=conv_row['total_tokens_used'],
                created_at=conv_row['created_at'],
                updated_at=conv_row['updated_at']
            ),
            messages=message_responses,
            summaries=summaries
        )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get conversation with messages: {e}")
        raise HTTPException(status_code=500, detail=f"Service error: {str(e)}")