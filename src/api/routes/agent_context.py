"""
Agent context API routes
"""

import logging
import json
from typing import List, Optional, Dict, Any
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, Query

from models.agent import (
    AgentContextCreate, AgentContextUpdate, AgentContextResponse,
    AgentType
)
from services.agent_services import get_agent_context_service
from services.cases_service import get_cases_service
from utils.auth import AuthConfig

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("", response_model=AgentContextResponse)
async def create_context(
    request: AgentContextCreate,
    _: bool = Depends(AuthConfig.get_auth_dependency())
):
    """Create or update agent context (upsert based on case_id + agent_type + context_key)"""
    context_service = get_agent_context_service()
    cases_service = get_cases_service()
    
    try:
        # Verify case exists
        case_result = await cases_service.get_case_by_id(str(request.case_id))
        if not case_result.success or not case_result.data:
            raise HTTPException(status_code=404, detail="Case not found")
        
        # Check if context already exists for upsert behavior
        existing_result = await context_service.get_context_by_key(
            str(request.case_id), 
            request.agent_type.value, 
            request.context_key
        )
        
        if existing_result.success and existing_result.data:
            # Update existing context
            context_id = existing_result.data[0]['context_id']
            result = await context_service.update_context_value(context_id, request.context_value)
        else:
            # Create new context
            expires_at_str = request.expires_at.isoformat() if request.expires_at else None
            result = await context_service.create_context(
                str(request.case_id),
                request.agent_type.value,
                request.context_key,
                request.context_value,
                expires_at_str
            )
        
        if not result.success:
            if result.error_type == "UNAUTHORIZED_OPERATION":
                raise HTTPException(status_code=403, detail=result.error)
            elif result.error_type == "INVALID_QUERY":
                raise HTTPException(status_code=400, detail=result.error)
            else:
                raise HTTPException(status_code=500, detail=result.error)
        
        context_data = result.data[0]
        return AgentContextResponse(
            context_id=context_data['context_id'],
            case_id=context_data['case_id'],
            agent_type=AgentType(context_data['agent_type']),
            context_key=context_data['context_key'],
            context_value=context_data['context_value'],
            expires_at=datetime.fromisoformat(context_data['expires_at'].replace('Z', '+00:00')) if context_data.get('expires_at') and isinstance(context_data['expires_at'], str) else context_data.get('expires_at'),
            created_at=datetime.fromisoformat(context_data['created_at'].replace('Z', '+00:00')) if isinstance(context_data['created_at'], str) else context_data['created_at'],
            updated_at=datetime.fromisoformat(context_data['updated_at'].replace('Z', '+00:00')) if isinstance(context_data['updated_at'], str) else context_data['updated_at']
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create context: {e}")
        raise HTTPException(status_code=500, detail=f"Service error: {str(e)}")

@router.get("/{context_id}", response_model=AgentContextResponse)
async def get_context(
    context_id: str,
    _: bool = Depends(AuthConfig.get_auth_dependency())
):
    """Get context by ID"""
    context_service = get_agent_context_service()
    
    try:
        result = await context_service.get_context_by_id(context_id)
        
        if not result.success or not result.data:
            raise HTTPException(status_code=404, detail="Context not found or expired")
        
        context_data = result.data[0]
        return AgentContextResponse(
            context_id=context_data['context_id'],
            case_id=context_data['case_id'],
            agent_type=AgentType(context_data['agent_type']),
            context_key=context_data['context_key'],
            context_value=context_data['context_value'],
            expires_at=datetime.fromisoformat(context_data['expires_at'].replace('Z', '+00:00')) if context_data.get('expires_at') and isinstance(context_data['expires_at'], str) else context_data.get('expires_at'),
            created_at=datetime.fromisoformat(context_data['created_at'].replace('Z', '+00:00')) if isinstance(context_data['created_at'], str) else context_data['created_at'],
            updated_at=datetime.fromisoformat(context_data['updated_at'].replace('Z', '+00:00')) if isinstance(context_data['updated_at'], str) else context_data['updated_at']
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get context: {e}")
        raise HTTPException(status_code=500, detail=f"Service error: {str(e)}")

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
                update_values.append(json.dumps(request.context_value))
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
                context_value=json.loads(row['context_value']) if row['context_value'] else {},
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
                    context_value=json.loads(row['context_value']) if row['context_value'] else {},
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
            context_map = {row['context_key']: json.loads(row['context_value']) if row['context_value'] else {} for row in rows}
            
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
                "context_value": json.loads(row['context_value']) if row['context_value'] else {},
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