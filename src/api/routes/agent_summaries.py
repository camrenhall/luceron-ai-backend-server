"""
Agent summaries API routes
"""

import logging
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, Query
import asyncpg

from models.agent import (
    AgentSummaryCreate, AgentSummaryUpdate, AgentSummaryResponse
)
from database.connection import get_db_pool
from utils.auth import AuthConfig

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("", response_model=AgentSummaryResponse)
async def create_summary(
    request: AgentSummaryCreate,
    _: bool = Depends(AuthConfig.get_auth_dependency())
):
    """Create a new conversation summary"""
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
            
            # Verify last_message_id exists if provided
            if request.last_message_id:
                msg_exists = await conn.fetchval(
                    "SELECT 1 FROM agent_messages WHERE message_id = $1 AND conversation_id = $2",
                    request.last_message_id, request.conversation_id
                )
                
                if not msg_exists:
                    raise HTTPException(status_code=404, detail="Last message not found in this conversation")
            
            row = await conn.fetchrow("""
                INSERT INTO agent_summaries 
                (conversation_id, last_message_id, summary_content, messages_summarized)
                VALUES ($1, $2, $3, $4)
                RETURNING summary_id, conversation_id, last_message_id, summary_content, 
                         messages_summarized, created_at, updated_at
            """, 
            request.conversation_id, request.last_message_id, 
            request.summary_content, request.messages_summarized)
            
            return AgentSummaryResponse(
                summary_id=row['summary_id'],
                conversation_id=row['conversation_id'],
                last_message_id=row['last_message_id'],
                summary_content=row['summary_content'],
                messages_summarized=row['messages_summarized'],
                created_at=row['created_at'],
                updated_at=row['updated_at']
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create summary: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.get("/{summary_id}", response_model=AgentSummaryResponse)
async def get_summary(
    summary_id: str,
    _: bool = Depends(AuthConfig.get_auth_dependency())
):
    """Get summary by ID"""
    db_pool = get_db_pool()
    
    try:
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT summary_id, conversation_id, last_message_id, summary_content, 
                       messages_summarized, created_at, updated_at
                FROM agent_summaries 
                WHERE summary_id = $1
            """, summary_id)
            
            if not row:
                raise HTTPException(status_code=404, detail="Summary not found")
            
            return AgentSummaryResponse(
                summary_id=row['summary_id'],
                conversation_id=row['conversation_id'],
                last_message_id=row['last_message_id'],
                summary_content=row['summary_content'],
                messages_summarized=row['messages_summarized'],
                created_at=row['created_at'],
                updated_at=row['updated_at']
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get summary: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.put("/{summary_id}", response_model=AgentSummaryResponse)
async def update_summary(
    summary_id: str,
    request: AgentSummaryUpdate,
    _: bool = Depends(AuthConfig.get_auth_dependency())
):
    """Update summary content or metadata"""
    db_pool = get_db_pool()
    
    try:
        async with db_pool.acquire() as conn:
            # Build dynamic update query
            update_fields = []
            update_values = []
            param_count = 1
            
            if request.summary_content is not None:
                update_fields.append(f"summary_content = ${param_count}")
                update_values.append(request.summary_content)
                param_count += 1
                
            if request.messages_summarized is not None:
                update_fields.append(f"messages_summarized = ${param_count}")
                update_values.append(request.messages_summarized)
                param_count += 1
            
            if not update_fields:
                raise HTTPException(status_code=400, detail="No fields provided for update")
            
            # Add summary_id as the final parameter
            update_values.append(summary_id)
            query = f"""
                UPDATE agent_summaries 
                SET {', '.join(update_fields)}, updated_at = NOW()
                WHERE summary_id = ${param_count}
                RETURNING summary_id, conversation_id, last_message_id, summary_content, 
                         messages_summarized, created_at, updated_at
            """
            
            row = await conn.fetchrow(query, *update_values)
            
            if not row:
                raise HTTPException(status_code=404, detail="Summary not found")
            
            return AgentSummaryResponse(
                summary_id=row['summary_id'],
                conversation_id=row['conversation_id'],
                last_message_id=row['last_message_id'],
                summary_content=row['summary_content'],
                messages_summarized=row['messages_summarized'],
                created_at=row['created_at'],
                updated_at=row['updated_at']
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update summary: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.delete("/{summary_id}")
async def delete_summary(
    summary_id: str,
    _: bool = Depends(AuthConfig.get_auth_dependency())
):
    """Delete summary"""
    db_pool = get_db_pool()
    
    try:
        async with db_pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM agent_summaries WHERE summary_id = $1",
                summary_id
            )
            
            if result == "DELETE 0":
                raise HTTPException(status_code=404, detail="Summary not found")
            
            return {"message": "Summary deleted successfully", "summary_id": summary_id}
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete summary: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.get("", response_model=List[AgentSummaryResponse])
async def list_summaries(
    conversation_id: Optional[str] = Query(None, description="Filter by conversation ID"),
    limit: int = Query(50, ge=1, le=500, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    _: bool = Depends(AuthConfig.get_auth_dependency())
):
    """List summaries with optional filters"""
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
            
            where_clause = f"WHERE {' AND '.join(where_conditions)}" if where_conditions else ""
            
            query = f"""
                SELECT summary_id, conversation_id, last_message_id, summary_content, 
                       messages_summarized, created_at, updated_at
                FROM agent_summaries 
                {where_clause}
                ORDER BY created_at DESC
                LIMIT ${param_count} OFFSET ${param_count + 1}
            """
            query_params.extend([limit, offset])
            
            rows = await conn.fetch(query, *query_params)
            
            return [
                AgentSummaryResponse(
                    summary_id=row['summary_id'],
                    conversation_id=row['conversation_id'],
                    last_message_id=row['last_message_id'],
                    summary_content=row['summary_content'],
                    messages_summarized=row['messages_summarized'],
                    created_at=row['created_at'],
                    updated_at=row['updated_at']
                ) for row in rows
            ]
            
    except Exception as e:
        logger.error(f"Failed to list summaries: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.get("/conversation/{conversation_id}/latest", response_model=AgentSummaryResponse)
async def get_latest_summary(
    conversation_id: str,
    _: bool = Depends(AuthConfig.get_auth_dependency())
):
    """Get the most recent summary for a conversation"""
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
            
            row = await conn.fetchrow("""
                SELECT summary_id, conversation_id, last_message_id, summary_content, 
                       messages_summarized, created_at, updated_at
                FROM agent_summaries 
                WHERE conversation_id = $1
                ORDER BY created_at DESC
                LIMIT 1
            """, conversation_id)
            
            if not row:
                raise HTTPException(status_code=404, detail="No summaries found for this conversation")
            
            return AgentSummaryResponse(
                summary_id=row['summary_id'],
                conversation_id=row['conversation_id'],
                last_message_id=row['last_message_id'],
                summary_content=row['summary_content'],
                messages_summarized=row['messages_summarized'],
                created_at=row['created_at'],
                updated_at=row['updated_at']
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get latest summary: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.post("/conversation/{conversation_id}/auto-summary", response_model=AgentSummaryResponse)
async def create_auto_summary(
    conversation_id: str,
    messages_to_summarize: int = Query(10, ge=1, le=100, description="Number of recent messages to summarize"),
    _: bool = Depends(AuthConfig.get_auth_dependency())
):
    """Create a summary automatically based on recent messages in the conversation"""
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
            
            # Get recent messages to determine what needs summarizing
            recent_messages = await conn.fetch("""
                SELECT message_id, content, role, sequence_number
                FROM agent_messages 
                WHERE conversation_id = $1
                ORDER BY sequence_number DESC
                LIMIT $2
            """, conversation_id, messages_to_summarize)
            
            if not recent_messages:
                raise HTTPException(status_code=400, detail="No messages found to summarize")
            
            # Get the last message ID (most recent)
            last_message_id = recent_messages[0]['message_id']
            
            # Create a basic summary (in production, this would use an LLM)
            summary_content = f"Summary of {len(recent_messages)} messages in conversation. "
            summary_content += f"Latest message sequence: {recent_messages[0]['sequence_number']}. "
            summary_content += "This is an auto-generated summary placeholder."
            
            row = await conn.fetchrow("""
                INSERT INTO agent_summaries 
                (conversation_id, last_message_id, summary_content, messages_summarized)
                VALUES ($1, $2, $3, $4)
                RETURNING summary_id, conversation_id, last_message_id, summary_content, 
                         messages_summarized, created_at, updated_at
            """, conversation_id, last_message_id, summary_content, len(recent_messages))
            
            return AgentSummaryResponse(
                summary_id=row['summary_id'],
                conversation_id=row['conversation_id'],
                last_message_id=row['last_message_id'],
                summary_content=row['summary_content'],
                messages_summarized=row['messages_summarized'],
                created_at=row['created_at'],
                updated_at=row['updated_at']
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create auto-summary: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")