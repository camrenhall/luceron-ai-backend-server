"""
Agent context API routes
"""

import logging
from typing import List, Optional, Dict, Any
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, Query
import asyncpg

from models.agent import (
    AgentContextCreate, AgentContextUpdate, AgentContextResponse,
    AgentType
)
from database.connection import get_db_pool
from utils.auth import AuthConfig

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("", response_model=AgentContextResponse)
async def create_context(
    request: AgentContextCreate,
    _: bool = Depends(AuthConfig.get_auth_dependency())
):
    """Create or update agent context (upsert based on case_id + agent_type + context_key)"""
    db_pool = get_db_pool()
    
    try:
        async with db_pool.acquire() as conn:
            # Verify case exists
            case_exists = await conn.fetchval(
                "SELECT 1 FROM cases WHERE case_id = $1",
                request.case_id
            )
            
            if not case_exists:
                raise HTTPException(status_code=404, detail="Case not found")
            
            # Use upsert to handle duplicate key constraints
            row = await conn.fetchrow("""
                INSERT INTO agent_context 
                (case_id, agent_type, context_key, context_value, expires_at)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (case_id, agent_type, context_key) 
                DO UPDATE SET 
                    context_value = EXCLUDED.context_value,
                    expires_at = EXCLUDED.expires_at,
                    updated_at = NOW()
                RETURNING context_id, case_id, agent_type, context_key, context_value, 
                         expires_at, created_at, updated_at
            """, 
            request.case_id, request.agent_type.value, request.context_key,
            request.context_value, request.expires_at)
            
            return AgentContextResponse(
                context_id=row['context_id'],
                case_id=row['case_id'],
                agent_type=AgentType(row['agent_type']),
                context_key=row['context_key'],
                context_value=row['context_value'],
                expires_at=row['expires_at'],
                created_at=row['created_at'],
                updated_at=row['updated_at']
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create context: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.get("/{context_id}", response_model=AgentContextResponse)
async def get_context(
    context_id: str,
    _: bool = Depends(AuthConfig.get_auth_dependency())
):
    """Get context by ID"""
    db_pool = get_db_pool()
    
    try:
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT context_id, case_id, agent_type, context_key, context_value, 
                       expires_at, created_at, updated_at
                FROM agent_context 
                WHERE context_id = $1 
                AND (expires_at IS NULL OR expires_at > NOW())
            """, context_id)
            
            if not row:
                raise HTTPException(status_code=404, detail="Context not found or expired")
            
            return AgentContextResponse(
                context_id=row['context_id'],
                case_id=row['case_id'],
                agent_type=AgentType(row['agent_type']),
                context_key=row['context_key'],
                context_value=row['context_value'],
                expires_at=row['expires_at'],
                created_at=row['created_at'],
                updated_at=row['updated_at']
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get context: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.put("/{context_id}", response_model=AgentContextResponse)
async def update_context(
    context_id: str,
    request: AgentContextUpdate,
    _: bool = Depends(AuthConfig.get_auth_dependency())
):
    """Update context value or expiration"""
    db_pool = get_db_pool()
    
    try:
        async with db_pool.acquire() as conn:
            # Build dynamic update query
            update_fields = []
            update_values = []
            param_count = 1
            
            if request.context_value is not None:
                update_fields.append(f"context_value = ${param_count}")
                update_values.append(request.context_value)
                param_count += 1
                
            if request.expires_at is not None:
                update_fields.append(f"expires_at = ${param_count}")
                update_values.append(request.expires_at)
                param_count += 1
            
            if not update_fields:
                raise HTTPException(status_code=400, detail="No fields provided for update")
            
            # Add context_id as the final parameter
            update_values.append(context_id)
            query = f"""
                UPDATE agent_context 
                SET {', '.join(update_fields)}, updated_at = NOW()
                WHERE context_id = ${param_count}
                AND (expires_at IS NULL OR expires_at > NOW())
                RETURNING context_id, case_id, agent_type, context_key, context_value, 
                         expires_at, created_at, updated_at
            """
            
            row = await conn.fetchrow(query, *update_values)
            
            if not row:
                raise HTTPException(status_code=404, detail="Context not found or expired")
            
            return AgentContextResponse(
                context_id=row['context_id'],
                case_id=row['case_id'],
                agent_type=AgentType(row['agent_type']),
                context_key=row['context_key'],
                context_value=row['context_value'],
                expires_at=row['expires_at'],
                created_at=row['created_at'],
                updated_at=row['updated_at']
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update context: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.delete("/{context_id}")
async def delete_context(
    context_id: str,
    _: bool = Depends(AuthConfig.get_auth_dependency())
):
    """Delete context"""
    db_pool = get_db_pool()
    
    try:
        async with db_pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM agent_context WHERE context_id = $1",
                context_id
            )
            
            if result == "DELETE 0":
                raise HTTPException(status_code=404, detail="Context not found")
            
            return {"message": "Context deleted successfully", "context_id": context_id}
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete context: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.get("", response_model=List[AgentContextResponse])
async def list_context(
    case_id: Optional[str] = Query(None, description="Filter by case ID"),
    agent_type: Optional[AgentType] = Query(None, description="Filter by agent type"),
    context_key: Optional[str] = Query(None, description="Filter by context key"),
    include_expired: bool = Query(False, description="Include expired context"),
    limit: int = Query(50, ge=1, le=500, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    _: bool = Depends(AuthConfig.get_auth_dependency())
):
    """List context entries with optional filters"""
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
                
            if agent_type:
                where_conditions.append(f"agent_type = ${param_count}")
                query_params.append(agent_type.value)
                param_count += 1
                
            if context_key:
                where_conditions.append(f"context_key = ${param_count}")
                query_params.append(context_key)
                param_count += 1
            
            # Add expiration filter unless explicitly including expired
            if not include_expired:
                where_conditions.append("(expires_at IS NULL OR expires_at > NOW())")
            
            where_clause = f"WHERE {' AND '.join(where_conditions)}" if where_conditions else ""
            
            query = f"""
                SELECT context_id, case_id, agent_type, context_key, context_value, 
                       expires_at, created_at, updated_at
                FROM agent_context 
                {where_clause}
                ORDER BY created_at DESC
                LIMIT ${param_count} OFFSET ${param_count + 1}
            """
            query_params.extend([limit, offset])
            
            rows = await conn.fetch(query, *query_params)
            
            return [
                AgentContextResponse(
                    context_id=row['context_id'],
                    case_id=row['case_id'],
                    agent_type=AgentType(row['agent_type']),
                    context_key=row['context_key'],
                    context_value=row['context_value'],
                    expires_at=row['expires_at'],
                    created_at=row['created_at'],
                    updated_at=row['updated_at']
                ) for row in rows
            ]
            
    except Exception as e:
        logger.error(f"Failed to list context: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.get("/case/{case_id}/agent/{agent_type}", response_model=Dict[str, Any])
async def get_case_agent_context(
    case_id: str,
    agent_type: AgentType,
    _: bool = Depends(AuthConfig.get_auth_dependency())
):
    """Get all context for a specific case and agent type as a key-value map"""
    db_pool = get_db_pool()
    
    try:
        async with db_pool.acquire() as conn:
            # Verify case exists
            case_exists = await conn.fetchval(
                "SELECT 1 FROM cases WHERE case_id = $1",
                case_id
            )
            
            if not case_exists:
                raise HTTPException(status_code=404, detail="Case not found")
            
            rows = await conn.fetch("""
                SELECT context_key, context_value
                FROM agent_context 
                WHERE case_id = $1 AND agent_type = $2
                AND (expires_at IS NULL OR expires_at > NOW())
                ORDER BY updated_at DESC
            """, case_id, agent_type.value)
            
            # Return as a dictionary mapping context_key to context_value
            context_map = {row['context_key']: row['context_value'] for row in rows}
            
            return context_map
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get case agent context: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.get("/case/{case_id}/agent/{agent_type}/key/{context_key}", response_model=Dict[str, Any])
async def get_specific_context_value(
    case_id: str,
    agent_type: AgentType,
    context_key: str,
    _: bool = Depends(AuthConfig.get_auth_dependency())
):
    """Get a specific context value by case, agent type, and key"""
    db_pool = get_db_pool()
    
    try:
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT context_value, expires_at
                FROM agent_context 
                WHERE case_id = $1 AND agent_type = $2 AND context_key = $3
                AND (expires_at IS NULL OR expires_at > NOW())
            """, case_id, agent_type.value, context_key)
            
            if not row:
                raise HTTPException(status_code=404, detail="Context not found or expired")
            
            return {
                "context_key": context_key,
                "context_value": row['context_value'],
                "expires_at": row['expires_at'].isoformat() if row['expires_at'] else None
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get specific context value: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.delete("/case/{case_id}/agent/{agent_type}")
async def delete_case_agent_context(
    case_id: str,
    agent_type: AgentType,
    _: bool = Depends(AuthConfig.get_auth_dependency())
):
    """Delete all context for a specific case and agent type"""
    db_pool = get_db_pool()
    
    try:
        async with db_pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM agent_context WHERE case_id = $1 AND agent_type = $2",
                case_id, agent_type.value
            )
            
            # Extract the number of deleted rows
            deleted_count = int(result.split()[-1]) if result.startswith("DELETE") else 0
            
            return {
                "message": f"Deleted {deleted_count} context entries",
                "case_id": case_id,
                "agent_type": agent_type.value,
                "deleted_count": deleted_count
            }
            
    except Exception as e:
        logger.error(f"Failed to delete case agent context: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.post("/cleanup-expired")
async def cleanup_expired_context(
    _: bool = Depends(AuthConfig.get_auth_dependency())
):
    """Clean up all expired context entries"""
    db_pool = get_db_pool()
    
    try:
        async with db_pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM agent_context WHERE expires_at IS NOT NULL AND expires_at <= NOW()"
            )
            
            # Extract the number of deleted rows
            deleted_count = int(result.split()[-1]) if result.startswith("DELETE") else 0
            
            return {
                "message": f"Cleaned up {deleted_count} expired context entries",
                "deleted_count": deleted_count,
                "cleanup_time": datetime.utcnow().isoformat()
            }
            
    except Exception as e:
        logger.error(f"Failed to cleanup expired context: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")