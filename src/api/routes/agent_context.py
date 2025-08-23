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
        
        if not result.success:
            if result.error_type == "NOT_FOUND":
                raise HTTPException(status_code=404, detail="Context not found or expired")
            elif result.error_type in ["INVALID_QUERY", "UNAUTHORIZED_FIELD", "RESOURCE_NOT_FOUND", "UNAUTHORIZED_OPERATION"]:
                raise HTTPException(status_code=400, detail=result.error)
            else:
                raise HTTPException(status_code=500, detail=result.error)
        
        if not result.data:
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
    context_service = get_agent_context_service()
    
    try:
        # Build update data
        updates = {}
        
        if request.context_value is not None:
            updates["context_value"] = request.context_value
            
        if request.expires_at is not None:
            updates["expires_at"] = request.expires_at.isoformat() if hasattr(request.expires_at, 'isoformat') else request.expires_at
        
        if not updates:
            raise HTTPException(status_code=400, detail="No fields provided for update")
        
        result = await context_service.update_context(context_id, updates)
        
        if not result.success:
            if result.error_type == "NOT_FOUND" or "No record found" in result.error:
                raise HTTPException(status_code=404, detail="Context not found or expired")
            elif result.error_type == "UNAUTHORIZED_OPERATION":
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
        logger.error(f"Failed to update context: {e}")
        raise HTTPException(status_code=500, detail=f"Service error: {str(e)}")

@router.delete("/{context_id}")
async def delete_context(
    context_id: str,
    _: bool = Depends(AuthConfig.get_auth_dependency())
):
    """Delete context"""
    context_service = get_agent_context_service()
    
    try:
        result = await context_service.delete_context(context_id)
        
        if not result.success:
            if result.error_type == "NOT_FOUND":
                raise HTTPException(status_code=404, detail="Context not found")
            elif result.error_type == "UNAUTHORIZED_OPERATION":
                raise HTTPException(status_code=403, detail=result.error)
            else:
                raise HTTPException(status_code=500, detail=result.error)
        
        return {"message": "Context deleted successfully", "context_id": context_id}
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete context: {e}")
        raise HTTPException(status_code=500, detail=f"Service error: {str(e)}")

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
    context_service = get_agent_context_service()
    
    try:
        result = await context_service.get_contexts_with_filters(
            case_id=case_id,
            agent_type=agent_type.value if agent_type else None,
            context_key=context_key,
            include_expired=include_expired,
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
            AgentContextResponse(
                context_id=row['context_id'],
                case_id=row['case_id'],
                agent_type=AgentType(row['agent_type']),
                context_key=row['context_key'],
                context_value=row['context_value'] if isinstance(row['context_value'], dict) else json.loads(row['context_value']) if row['context_value'] else {},
                expires_at=datetime.fromisoformat(row['expires_at'].replace('Z', '+00:00')) if row.get('expires_at') and isinstance(row['expires_at'], str) else row.get('expires_at'),
                created_at=datetime.fromisoformat(row['created_at'].replace('Z', '+00:00')) if isinstance(row['created_at'], str) else row['created_at'],
                updated_at=datetime.fromisoformat(row['updated_at'].replace('Z', '+00:00')) if isinstance(row['updated_at'], str) else row['updated_at']
            ) for row in result.data
        ]
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list context: {e}")
        raise HTTPException(status_code=500, detail=f"Service error: {str(e)}")

@router.get("/case/{case_id}/agent/{agent_type}", response_model=Dict[str, Any])
async def get_case_agent_context(
    case_id: str,
    agent_type: AgentType,
    _: bool = Depends(AuthConfig.get_auth_dependency())
):
    """Get all context for a specific case and agent type as a key-value map"""
    context_service = get_agent_context_service()
    cases_service = get_cases_service()
    
    try:
        # Verify case exists
        case_result = await cases_service.get_case_by_id(case_id)
        if not case_result.success or not case_result.data:
            raise HTTPException(status_code=404, detail="Case not found")
        
        # Get context for this case and agent type
        result = await context_service.get_contexts_with_filters(
            case_id=case_id,
            agent_type=agent_type.value,
            include_expired=False
        )
        
        if not result.success:
            if result.error_type == "UNAUTHORIZED_OPERATION":
                raise HTTPException(status_code=403, detail=result.error)
            elif result.error_type == "INVALID_QUERY":
                raise HTTPException(status_code=400, detail=result.error)
            else:
                raise HTTPException(status_code=500, detail=result.error)
        
        # Return as a dictionary mapping context_key to context_value
        context_map = {}
        for row in result.data:
            context_value = row['context_value']
            if isinstance(context_value, str):
                try:
                    context_value = json.loads(context_value)
                except (json.JSONDecodeError, TypeError):
                    pass
            context_map[row['context_key']] = context_value or {}
        
        return context_map
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get case agent context: {e}")
        raise HTTPException(status_code=500, detail=f"Service error: {str(e)}")

@router.get("/case/{case_id}/agent/{agent_type}/key/{context_key}", response_model=Dict[str, Any])
async def get_specific_context_value(
    case_id: str,
    agent_type: AgentType,
    context_key: str,
    _: bool = Depends(AuthConfig.get_auth_dependency())
):
    """Get a specific context value by case, agent type, and key"""
    context_service = get_agent_context_service()
    
    try:
        result = await context_service.get_context_by_key_non_expired(case_id, agent_type.value, context_key)
        
        if not result.success:
            if result.error_type == "NOT_FOUND":
                raise HTTPException(status_code=404, detail="Context not found or expired")
            elif result.error_type in ["INVALID_QUERY", "UNAUTHORIZED_FIELD", "RESOURCE_NOT_FOUND", "UNAUTHORIZED_OPERATION"]:
                raise HTTPException(status_code=400, detail=result.error)
            else:
                raise HTTPException(status_code=500, detail=result.error)
        
        if not result.data:
            raise HTTPException(status_code=404, detail="Context not found or expired")
        
        context_data = result.data[0]
        context_value = context_data['context_value']
        
        # Handle JSON parsing if needed
        if isinstance(context_value, str):
            try:
                context_value = json.loads(context_value)
            except (json.JSONDecodeError, TypeError):
                pass
        
        expires_at = context_data.get('expires_at')
        if isinstance(expires_at, str):
            expires_at = expires_at
        elif hasattr(expires_at, 'isoformat'):
            expires_at = expires_at.isoformat()
        else:
            expires_at = None
        
        return {
            "context_key": context_key,
            "context_value": context_value or {},
            "expires_at": expires_at
        }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get specific context value: {e}")
        raise HTTPException(status_code=500, detail=f"Service error: {str(e)}")

@router.delete("/case/{case_id}/agent/{agent_type}")
async def delete_case_agent_context(
    case_id: str,
    agent_type: AgentType,
    _: bool = Depends(AuthConfig.get_auth_dependency())
):
    """Delete all context for a specific case and agent type"""
    context_service = get_agent_context_service()
    
    try:
        result = await context_service.delete_contexts_by_case_and_agent(case_id, agent_type.value)
        
        if not result.success:
            if result.error_type == "UNAUTHORIZED_OPERATION":
                raise HTTPException(status_code=403, detail=result.error)
            else:
                raise HTTPException(status_code=500, detail=result.error)
        
        deleted_count = result.data[0]['deleted_count'] if result.data else 0
        
        return {
            "message": f"Deleted {deleted_count} context entries",
            "case_id": case_id,
            "agent_type": agent_type.value,
            "deleted_count": deleted_count
        }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete case agent context: {e}")
        raise HTTPException(status_code=500, detail=f"Service error: {str(e)}")

@router.post("/cleanup-expired")
async def cleanup_expired_context(
    _: bool = Depends(AuthConfig.get_auth_dependency())
):
    """Clean up all expired context entries"""
    context_service = get_agent_context_service()
    
    try:
        result = await context_service.cleanup_expired_contexts()
        
        if not result.success:
            if result.error_type == "UNAUTHORIZED_OPERATION":
                raise HTTPException(status_code=403, detail=result.error)
            else:
                raise HTTPException(status_code=500, detail=result.error)
        
        deleted_count = result.data[0]['deleted_count'] if result.data else 0
        
        return {
            "message": f"Cleaned up {deleted_count} expired context entries",
            "deleted_count": deleted_count,
            "cleanup_time": datetime.utcnow().isoformat()
        }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to cleanup expired context: {e}")
        raise HTTPException(status_code=500, detail=f"Service error: {str(e)}")