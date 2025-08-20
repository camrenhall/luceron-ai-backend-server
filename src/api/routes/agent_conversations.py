"""
Agent conversations API routes
"""

import logging
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, Query
import asyncpg

from models.agent import (
    AgentConversationCreate, AgentConversationUpdate, AgentConversationResponse,
    ConversationWithMessages, ConversationHistoryRequest, AgentType, ConversationStatus,
    MessageRole
)
from database.connection import get_db_pool
from utils.auth import AuthConfig

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("", response_model=AgentConversationResponse)
async def create_conversation(
    request: AgentConversationCreate,
    _: bool = Depends(AuthConfig.get_auth_dependency())
):
    """Create a new agent conversation"""
    db_pool = get_db_pool()
    
    try:
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow("""
                INSERT INTO agent_conversations (agent_type, status)
                VALUES ($1, $2)
                RETURNING conversation_id, agent_type, status, total_tokens_used, created_at, updated_at
            """, request.agent_type.value, request.status.value)
            
            return AgentConversationResponse(
                conversation_id=row['conversation_id'],
                                agent_type=AgentType(row['agent_type']),
                status=ConversationStatus(row['status']),
                total_tokens_used=row['total_tokens_used'],
                created_at=row['created_at'],
                updated_at=row['updated_at']
            )
            
    except Exception as e:
        logger.error(f"Failed to create conversation: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.get("/{conversation_id}", response_model=AgentConversationResponse)
async def get_conversation(
    conversation_id: str,
    _: bool = Depends(AuthConfig.get_auth_dependency())
):
    """Get conversation by ID"""
    db_pool = get_db_pool()
    
    try:
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT conversation_id, agent_type, status, total_tokens_used, created_at, updated_at
                FROM agent_conversations 
                WHERE conversation_id = $1
            """, conversation_id)
            
            if not row:
                raise HTTPException(status_code=404, detail="Conversation not found")
            
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
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.put("/{conversation_id}", response_model=AgentConversationResponse)
async def update_conversation(
    conversation_id: str,
    request: AgentConversationUpdate,
    _: bool = Depends(AuthConfig.get_auth_dependency())
):
    """Update conversation status"""
    db_pool = get_db_pool()
    
    try:
        async with db_pool.acquire() as conn:
            # Build dynamic update query
            update_fields = []
            update_values = []
            param_count = 1
            
            if request.status is not None:
                update_fields.append(f"status = ${param_count}")
                update_values.append(request.status.value)
                param_count += 1
            
            if not update_fields:
                raise HTTPException(status_code=400, detail="No fields provided for update")
            
            # Add conversation_id as the final parameter
            update_values.append(conversation_id)
            query = f"""
                UPDATE agent_conversations 
                SET {', '.join(update_fields)}, updated_at = NOW()
                WHERE conversation_id = ${param_count}
                RETURNING conversation_id, agent_type, status, total_tokens_used, created_at, updated_at
            """
            
            row = await conn.fetchrow(query, *update_values)
            
            if not row:
                raise HTTPException(status_code=404, detail="Conversation not found")
            
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
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.delete("/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    _: bool = Depends(AuthConfig.get_auth_dependency())
):
    """Delete conversation (cascades to messages and summaries)"""
    db_pool = get_db_pool()
    
    try:
        async with db_pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM agent_conversations WHERE conversation_id = $1",
                conversation_id
            )
            
            if result == "DELETE 0":
                raise HTTPException(status_code=404, detail="Conversation not found")
            
            return {"message": "Conversation deleted successfully", "conversation_id": conversation_id}
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete conversation: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.get("", response_model=List[AgentConversationResponse])
async def list_conversations(
    agent_type: Optional[AgentType] = Query(None, description="Filter by agent type"),
    status: Optional[ConversationStatus] = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=500, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    _: bool = Depends(AuthConfig.get_auth_dependency())
):
    """List conversations with optional filters"""
    db_pool = get_db_pool()
    
    try:
        async with db_pool.acquire() as conn:
            # Build dynamic WHERE clause
            where_conditions = []
            query_params = []
            param_count = 1
            
            if agent_type:
                where_conditions.append(f"agent_type = ${param_count}")
                query_params.append(agent_type.value)
                param_count += 1
                
            if status:
                where_conditions.append(f"status = ${param_count}")
                query_params.append(status.value)
                param_count += 1
            
            where_clause = f"WHERE {' AND '.join(where_conditions)}" if where_conditions else ""
            
            query = f"""
                SELECT conversation_id, agent_type, status, total_tokens_used, created_at, updated_at
                FROM agent_conversations 
                {where_clause}
                ORDER BY created_at DESC
                LIMIT ${param_count} OFFSET ${param_count + 1}
            """
            query_params.extend([limit, offset])
            
            rows = await conn.fetch(query, *query_params)
            
            return [
                AgentConversationResponse(
                    conversation_id=row['conversation_id'],
                                        agent_type=AgentType(row['agent_type']),
                    status=ConversationStatus(row['status']),
                    total_tokens_used=row['total_tokens_used'],
                    created_at=row['created_at'],
                    updated_at=row['updated_at']
                ) for row in rows
            ]
            
    except Exception as e:
        logger.error(f"Failed to list conversations: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.get("/{conversation_id}/full", response_model=ConversationWithMessages)
async def get_conversation_with_messages(
    conversation_id: str,
    include_summaries: bool = Query(True, description="Include summaries in response"),
    include_function_calls: bool = Query(True, description="Include function call details"),
    _: bool = Depends(AuthConfig.get_auth_dependency())
):
    """Get conversation with all messages and summaries"""
    db_pool = get_db_pool()
    
    try:
        async with db_pool.acquire() as conn:
            # Get conversation
            conv_row = await conn.fetchrow("""
                SELECT conversation_id, agent_type, status, total_tokens_used, created_at, updated_at
                FROM agent_conversations 
                WHERE conversation_id = $1
            """, conversation_id)
            
            if not conv_row:
                raise HTTPException(status_code=404, detail="Conversation not found")
            
            # Get messages
            message_fields = "message_id, conversation_id, role, content, total_tokens, model_used, created_at, sequence_number"
            if include_function_calls:
                message_fields += ", function_name, function_arguments, function_response"
            
            messages = await conn.fetch(f"""
                SELECT {message_fields}
                FROM agent_messages 
                WHERE conversation_id = $1
                ORDER BY sequence_number ASC
            """, conversation_id)
            
            # Get summaries if requested
            summaries = []
            if include_summaries:
                summary_rows = await conn.fetch("""
                    SELECT summary_id, conversation_id, last_message_id, summary_content, 
                           messages_summarized, created_at, updated_at
                    FROM agent_summaries 
                    WHERE conversation_id = $1
                    ORDER BY created_at ASC
                """, conversation_id)
                
                from models.agent import AgentSummaryResponse
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
            
            from models.agent import AgentMessageResponse
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
                    case_id=conv_row['case_id'],
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
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")