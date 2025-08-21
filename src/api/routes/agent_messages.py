"""
Agent messages API routes
"""

import asyncio
import logging
import json
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, Query
import asyncpg

from models.agent import (
    AgentMessageCreate, AgentMessageUpdate, AgentMessageResponse,
    MessageRole
)
from database.connection import get_db_pool
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
    db_pool = get_db_pool()
    
    try:
        async with db_pool.acquire() as conn:
            # Verify conversation exists
            conv_exists = await conn.fetchval(
                "SELECT 1 FROM agent_conversations WHERE conversation_id = $1",
                request.conversation_id
            )
            
            if not conv_exists:
                raise HTTPException(status_code=404, detail="Conversation not found")
            
            row = await conn.fetchrow("""
                INSERT INTO agent_messages 
                (conversation_id, role, content, total_tokens, model_used, function_name, function_arguments, function_response)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                RETURNING message_id, conversation_id, role, content, total_tokens, model_used, 
                         function_name, function_arguments, function_response, created_at, sequence_number
            """, 
            request.conversation_id, request.role.value, json.dumps(request.content),
            request.total_tokens, request.model_used, request.function_name,
            json.dumps(request.function_arguments) if request.function_arguments else None,
            json.dumps(request.function_response) if request.function_response else None)
            
            # Create response
            response = AgentMessageResponse(
                message_id=row['message_id'],
                conversation_id=row['conversation_id'],
                role=MessageRole(row['role']),
                content=json.loads(row['content']) if row['content'] else {},
                total_tokens=row['total_tokens'],
                model_used=row['model_used'],
                function_name=row['function_name'],
                function_arguments=json.loads(row['function_arguments']) if row['function_arguments'] else None,
                function_response=json.loads(row['function_response']) if row['function_response'] else None,
                created_at=row['created_at'],
                sequence_number=row['sequence_number']
            )
            
            # Trigger async summary generation in background
            asyncio.create_task(trigger_summary_generation(str(request.conversation_id)))
            
            return response
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create message: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.get("/{message_id}", response_model=AgentMessageResponse)
async def get_message(
    message_id: str,
    _: bool = Depends(AuthConfig.get_auth_dependency())
):
    """Get message by ID"""
    db_pool = get_db_pool()
    
    try:
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT message_id, conversation_id, role, content, total_tokens, model_used, 
                       function_name, function_arguments, function_response, created_at, sequence_number
                FROM agent_messages 
                WHERE message_id = $1
            """, message_id)
            
            if not row:
                raise HTTPException(status_code=404, detail="Message not found")
            
            return AgentMessageResponse(
                message_id=row['message_id'],
                conversation_id=row['conversation_id'],
                role=MessageRole(row['role']),
                content=json.loads(row['content']) if row['content'] else {},
                total_tokens=row['total_tokens'],
                model_used=row['model_used'],
                function_name=row['function_name'],
                function_arguments=json.loads(row['function_arguments']) if row['function_arguments'] else None,
                function_response=json.loads(row['function_response']) if row['function_response'] else None,
                created_at=row['created_at'],
                sequence_number=row['sequence_number']
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get message: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.put("/{message_id}", response_model=AgentMessageResponse)
async def update_message(
    message_id: str,
    request: AgentMessageUpdate,
    _: bool = Depends(AuthConfig.get_auth_dependency())
):
    """Update message content or metadata"""
    db_pool = get_db_pool()
    
    try:
        async with db_pool.acquire() as conn:
            # Build dynamic update query
            update_fields = []
            update_values = []
            param_count = 1
            
            if request.content is not None:
                update_fields.append(f"content = ${param_count}")
                update_values.append(json.dumps(request.content))
                param_count += 1
                
            if request.total_tokens is not None:
                update_fields.append(f"total_tokens = ${param_count}")
                update_values.append(request.total_tokens)
                param_count += 1
                
            if request.function_response is not None:
                update_fields.append(f"function_response = ${param_count}")
                update_values.append(json.dumps(request.function_response))
                param_count += 1
            
            if not update_fields:
                raise HTTPException(status_code=400, detail="No fields provided for update")
            
            # Add message_id as the final parameter
            update_values.append(message_id)
            query = f"""
                UPDATE agent_messages 
                SET {', '.join(update_fields)}
                WHERE message_id = ${param_count}
                RETURNING message_id, conversation_id, role, content, total_tokens, model_used, 
                         function_name, function_arguments, function_response, created_at, sequence_number
            """
            
            row = await conn.fetchrow(query, *update_values)
            
            if not row:
                raise HTTPException(status_code=404, detail="Message not found")
            
            # Create response
            response = AgentMessageResponse(
                message_id=row['message_id'],
                conversation_id=row['conversation_id'],
                role=MessageRole(row['role']),
                content=json.loads(row['content']) if row['content'] else {},
                total_tokens=row['total_tokens'],
                model_used=row['model_used'],
                function_name=row['function_name'],
                function_arguments=json.loads(row['function_arguments']) if row['function_arguments'] else None,
                function_response=json.loads(row['function_response']) if row['function_response'] else None,
                created_at=row['created_at'],
                sequence_number=row['sequence_number']
            )
            
            # Trigger async summary generation in background
            asyncio.create_task(trigger_summary_generation(str(row['conversation_id'])))
            
            return response
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update message: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.delete("/{message_id}")
async def delete_message(
    message_id: str,
    _: bool = Depends(AuthConfig.get_auth_dependency())
):
    """Delete message"""
    db_pool = get_db_pool()
    
    try:
        async with db_pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM agent_messages WHERE message_id = $1",
                message_id
            )
            
            if result == "DELETE 0":
                raise HTTPException(status_code=404, detail="Message not found")
            
            return {"message": "Message deleted successfully", "message_id": message_id}
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete message: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.get("", response_model=List[AgentMessageResponse])
async def list_messages(
    conversation_id: Optional[str] = Query(None, description="Filter by conversation ID"),
    role: Optional[MessageRole] = Query(None, description="Filter by message role"),
    limit: int = Query(50, ge=1, le=500, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    _: bool = Depends(AuthConfig.get_auth_dependency())
):
    """List messages with optional filters"""
    db_pool = get_db_pool()
    
    try:
        async with db_pool.acquire() as conn:
            # Build dynamic WHERE clause
            where_conditions = []
            query_params = []
            param_count = 1
            
            if conversation_id:
                where_conditions.append(f"conversation_id = ${param_count}")
                query_params.append(conversation_id)
                param_count += 1
                
            if role:
                where_conditions.append(f"role = ${param_count}")
                query_params.append(role.value)
                param_count += 1
            
            where_clause = f"WHERE {' AND '.join(where_conditions)}" if where_conditions else ""
            
            query = f"""
                SELECT message_id, conversation_id, role, content, total_tokens, model_used, 
                       function_name, function_arguments, function_response, created_at, sequence_number
                FROM agent_messages 
                {where_clause}
                ORDER BY created_at DESC
                LIMIT ${param_count} OFFSET ${param_count + 1}
            """
            query_params.extend([limit, offset])
            
            rows = await conn.fetch(query, *query_params)
            
            return [
                AgentMessageResponse(
                    message_id=row['message_id'],
                    conversation_id=row['conversation_id'],
                    role=MessageRole(row['role']),
                    content=json.loads(row['content']) if row['content'] else {},
                    total_tokens=row['total_tokens'],
                    model_used=row['model_used'],
                    function_name=row['function_name'],
                    function_arguments=json.loads(row['function_arguments']) if row['function_arguments'] else None,
                    function_response=json.loads(row['function_response']) if row['function_response'] else None,
                    created_at=row['created_at'],
                    sequence_number=row['sequence_number']
                ) for row in rows
            ]
            
    except Exception as e:
        logger.error(f"Failed to list messages: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.get("/conversation/{conversation_id}/history", response_model=List[AgentMessageResponse])
async def get_conversation_messages(
    conversation_id: str,
    limit: int = Query(50, ge=1, le=500, description="Maximum number of messages"),
    include_function_calls: bool = Query(True, description="Include function call details"),
    _: bool = Depends(AuthConfig.get_auth_dependency())
):
    """Get messages for a specific conversation in chronological order"""
    db_pool = get_db_pool()
    
    try:
        async with db_pool.acquire() as conn:
            # Verify conversation exists
            conv_exists = await conn.fetchval(
                "SELECT 1 FROM agent_conversations WHERE conversation_id = $1",
                conversation_id
            )
            
            if not conv_exists:
                raise HTTPException(status_code=404, detail="Conversation not found")
            
            # Select fields based on whether to include function calls
            message_fields = "message_id, conversation_id, role, content, total_tokens, model_used, created_at, sequence_number"
            if include_function_calls:
                message_fields += ", function_name, function_arguments, function_response"
            
            rows = await conn.fetch(f"""
                SELECT {message_fields}
                FROM agent_messages 
                WHERE conversation_id = $1
                ORDER BY sequence_number ASC
                LIMIT $2
            """, conversation_id, limit)
            
            messages = []
            for row in rows:
                message_data = {
                    "message_id": row['message_id'],
                    "conversation_id": row['conversation_id'],
                    "role": MessageRole(row['role']),
                    "content": json.loads(row['content']) if row['content'] else {},
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
                        "function_arguments": json.loads(row.get('function_arguments')) if row.get('function_arguments') else None,
                        "function_response": json.loads(row.get('function_response')) if row.get('function_response') else None
                    })
                
                messages.append(AgentMessageResponse(**message_data))
            
            return messages
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get conversation messages: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")