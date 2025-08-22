"""
Error logs API routes
"""

import logging
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, Query

from models.error_log import (
    ErrorLogCreate, 
    ErrorLogUpdateRequest, 
    ErrorLogResponse, 
    ErrorLogStats,
    ErrorSeverity
)
from services.error_logs_service import get_error_logs_service
from utils.auth import AuthConfig

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("", response_model=ErrorLogResponse)
async def create_error_log(
    request: ErrorLogCreate,
    _: bool = Depends(AuthConfig.get_auth_dependency())
):
    """Create a new error log record"""
    error_service = get_error_logs_service()
    
    try:
        result = await error_service.log_error(
            component=request.component,
            error_message=request.error_message,
            severity=request.severity.value,
            context=request.context,
            email_sent=request.email_sent
        )
        
        if not result.success:
            if result.error_type == "UNAUTHORIZED_OPERATION":
                raise HTTPException(status_code=403, detail=result.error)
            elif result.error_type == "UNAUTHORIZED_FIELD":
                raise HTTPException(status_code=403, detail=result.error)
            elif result.error_type == "INVALID_QUERY":
                raise HTTPException(status_code=400, detail=result.error)
            else:
                raise HTTPException(status_code=500, detail=result.error)
        
        error_log = result.data[0]
        return ErrorLogResponse(
            error_id=error_log['error_id'],
            component=error_log['component'],
            error_message=error_log['error_message'],
            severity=ErrorSeverity(error_log['severity']),
            context=error_log['context'],
            email_sent=error_log['email_sent'],
            created_at=datetime.fromisoformat(error_log['created_at'].replace('Z', '+00:00')) if isinstance(error_log['created_at'], str) else error_log['created_at'],
            updated_at=datetime.fromisoformat(error_log['updated_at'].replace('Z', '+00:00')) if isinstance(error_log['updated_at'], str) else error_log['updated_at']
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create error log: {e}")
        raise HTTPException(status_code=500, detail=f"Service error: {str(e)}")

@router.get("/{error_id}", response_model=ErrorLogResponse)
async def get_error_log(
    error_id: str,
    _: bool = Depends(AuthConfig.get_auth_dependency())
):
    """Get error log by ID"""
    error_service = get_error_logs_service()
    
    try:
        result = await error_service.get_error_by_id(error_id)
        
        if not result.success:
            if result.error_type == "RESOURCE_NOT_FOUND":
                raise HTTPException(status_code=404, detail="Error log not found")
            elif result.error_type == "UNAUTHORIZED_OPERATION":
                raise HTTPException(status_code=403, detail=result.error)
            else:
                raise HTTPException(status_code=500, detail=result.error)
        
        if not result.data:
            raise HTTPException(status_code=404, detail="Error log not found")
        
        error_log = result.data[0]
        return ErrorLogResponse(
            error_id=error_log['error_id'],
            component=error_log['component'],
            error_message=error_log['error_message'],
            severity=ErrorSeverity(error_log['severity']),
            context=error_log['context'],
            email_sent=error_log['email_sent'],
            created_at=datetime.fromisoformat(error_log['created_at'].replace('Z', '+00:00')) if isinstance(error_log['created_at'], str) else error_log['created_at'],
            updated_at=datetime.fromisoformat(error_log['updated_at'].replace('Z', '+00:00')) if isinstance(error_log['updated_at'], str) else error_log['updated_at']
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get error log: {e}")
        raise HTTPException(status_code=500, detail=f"Service error: {str(e)}")

@router.put("/{error_id}", response_model=ErrorLogResponse)
async def update_error_log(
    error_id: str,
    request: ErrorLogUpdateRequest,
    _: bool = Depends(AuthConfig.get_auth_dependency())
):
    """Update error log record"""
    error_service = get_error_logs_service()
    
    try:
        # Build update data from request
        update_data = {}
        
        if request.component is not None:
            update_data["component"] = request.component
        if request.error_message is not None:
            update_data["error_message"] = request.error_message
        if request.severity is not None:
            update_data["severity"] = request.severity.value
        if request.context is not None:
            update_data["context"] = request.context
        if request.email_sent is not None:
            update_data["email_sent"] = request.email_sent
        
        if not update_data:
            raise HTTPException(status_code=400, detail="No fields provided for update")
        
        result = await error_service.update(error_id, update_data)
        
        if not result.success:
            if result.error_type == "RESOURCE_NOT_FOUND" or "not found" in result.error.lower():
                raise HTTPException(status_code=404, detail="Error log not found")
            elif result.error_type == "UNAUTHORIZED_OPERATION":
                raise HTTPException(status_code=403, detail=result.error)
            elif result.error_type == "UNAUTHORIZED_FIELD":
                raise HTTPException(status_code=403, detail=result.error)
            elif result.error_type == "INVALID_QUERY":
                raise HTTPException(status_code=400, detail=result.error)
            else:
                raise HTTPException(status_code=500, detail=result.error)
        
        error_log = result.data[0]
        return ErrorLogResponse(
            error_id=error_log['error_id'],
            component=error_log['component'],
            error_message=error_log['error_message'],
            severity=ErrorSeverity(error_log['severity']),
            context=error_log['context'],
            email_sent=error_log['email_sent'],
            created_at=datetime.fromisoformat(error_log['created_at'].replace('Z', '+00:00')) if isinstance(error_log['created_at'], str) else error_log['created_at'],
            updated_at=datetime.fromisoformat(error_log['updated_at'].replace('Z', '+00:00')) if isinstance(error_log['updated_at'], str) else error_log['updated_at']
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update error log: {e}")
        raise HTTPException(status_code=500, detail=f"Service error: {str(e)}")

@router.delete("/{error_id}")
async def delete_error_log(
    error_id: str,
    _: bool = Depends(AuthConfig.get_auth_dependency())
):
    """Delete error log record"""
    # NOTE: DELETE operations are discouraged in MVP Agent Gateway spec,
    # but maintaining existing API for backward compatibility
    error_service = get_error_logs_service()
    
    try:
        # First check if error log exists
        get_result = await error_service.get_error_by_id(error_id)
        
        if not get_result.success or not get_result.data:
            raise HTTPException(status_code=404, detail="Error log not found")
        
        existing_log = get_result.data[0]
        
        # Use service layer for delete operation
        delete_result = await error_service.delete_error_log(error_id)
        
        if not delete_result.success:
            if delete_result.error_type == "RESOURCE_NOT_FOUND":
                raise HTTPException(status_code=404, detail="Error log not found")
            else:
                raise HTTPException(status_code=500, detail=delete_result.error)
        
        return {
            "message": "Error log deleted successfully",
            "error_id": error_id,
            "component": existing_log['component']
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete error log: {e}")
        raise HTTPException(status_code=500, detail=f"Service error: {str(e)}")

@router.get("", response_model=List[ErrorLogResponse])
async def list_error_logs(
    component: Optional[str] = Query(None, description="Filter by component"),
    severity: Optional[ErrorSeverity] = Query(None, description="Filter by severity"),
    email_sent: Optional[bool] = Query(None, description="Filter by email sent status"),
    limit: int = Query(50, ge=1, le=500, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    _: bool = Depends(AuthConfig.get_auth_dependency())
):
    """List error logs with optional filters"""
    error_service = get_error_logs_service()
    
    try:
        # Build filters for service call
        filters = {}
        
        if component:
            filters["component"] = component
        if severity:
            filters["severity"] = severity.value
        if email_sent is not None:
            filters["email_sent"] = email_sent
        
        result = await error_service.read(
            filters=filters,
            order_by=[{"field": "created_at", "dir": "desc"}],
            limit=limit,
            offset=offset
        )
        
        if not result.success:
            raise HTTPException(status_code=500, detail=result.error)
        
        return [
            ErrorLogResponse(
                error_id=log['error_id'],
                component=log['component'],
                error_message=log['error_message'],
                severity=ErrorSeverity(log['severity']),
                context=log['context'],
                email_sent=log['email_sent'],
                created_at=datetime.fromisoformat(log['created_at'].replace('Z', '+00:00')) if isinstance(log['created_at'], str) else log['created_at'],
                updated_at=datetime.fromisoformat(log['updated_at'].replace('Z', '+00:00')) if isinstance(log['updated_at'], str) else log['updated_at']
            ) for log in result.data
        ]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list error logs: {e}")
        raise HTTPException(status_code=500, detail=f"Service error: {str(e)}")

@router.get("/stats", response_model=ErrorLogStats)
async def get_error_log_stats(
    _: bool = Depends(AuthConfig.get_auth_dependency())
):
    """Get error log statistics"""
    error_service = get_error_logs_service()
    
    try:
        # Get all error logs for aggregation (limited to reasonable size)
        result = await error_service.read(limit=10000)
        
        if not result.success:
            raise HTTPException(status_code=500, detail=result.error)
        
        error_logs = result.data
        
        # Calculate statistics
        total_errors = len(error_logs)
        emails_sent = sum(1 for log in error_logs if log.get('email_sent', False))
        critical_errors = sum(1 for log in error_logs if log.get('severity') == 'critical')
        high_errors = sum(1 for log in error_logs if log.get('severity') == 'high')
        medium_errors = sum(1 for log in error_logs if log.get('severity') == 'medium')
        low_errors = sum(1 for log in error_logs if log.get('severity') == 'low')
        
        # Find latest timestamps
        last_error_at = None
        last_email_sent_at = None
        
        if error_logs:
            # Convert timestamps and find max
            all_timestamps = []
            email_sent_timestamps = []
            
            for log in error_logs:
                created_at = log.get('created_at')
                if created_at:
                    if isinstance(created_at, str):
                        timestamp = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                    else:
                        timestamp = created_at
                    all_timestamps.append(timestamp)
                    
                    if log.get('email_sent', False):
                        email_sent_timestamps.append(timestamp)
            
            if all_timestamps:
                last_error_at = max(all_timestamps)
            if email_sent_timestamps:
                last_email_sent_at = max(email_sent_timestamps)
        
        return ErrorLogStats(
            total_errors=total_errors,
            emails_sent=emails_sent,
            critical_errors=critical_errors,
            high_errors=high_errors,
            medium_errors=medium_errors,
            low_errors=low_errors,
            last_error_at=last_error_at,
            last_email_sent_at=last_email_sent_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get error log stats: {e}")
        raise HTTPException(status_code=500, detail=f"Service error: {str(e)}")