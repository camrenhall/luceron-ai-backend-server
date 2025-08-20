"""
Error logs API routes
"""

import logging
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, Query
import asyncpg

from models.error_log import (
    ErrorLogCreate, 
    ErrorLogUpdateRequest, 
    ErrorLogResponse, 
    ErrorLogStats,
    ErrorSeverity
)
from database.connection import get_db_pool
from utils.auth import AuthConfig

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("", response_model=ErrorLogResponse)
async def create_error_log(
    request: ErrorLogCreate,
    _: bool = Depends(AuthConfig.get_auth_dependency())
):
    """Create a new error log record"""
    db_pool = get_db_pool()
    
    try:
        async with db_pool.acquire() as conn:
            error_id = await conn.fetchval("""
                INSERT INTO error_logs 
                (component, error_message, severity, context, email_sent, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                RETURNING error_id
            """,
            request.component, request.error_message, request.severity.value,
            request.context, request.email_sent, datetime.utcnow(), datetime.utcnow())
            
            # Get the created error log
            error_log = await conn.fetchrow("""
                SELECT error_id, component, error_message, severity, context, email_sent, created_at, updated_at
                FROM error_logs 
                WHERE error_id = $1
            """, error_id)
            
            return ErrorLogResponse(
                error_id=error_log['error_id'],
                component=error_log['component'],
                error_message=error_log['error_message'],
                severity=ErrorSeverity(error_log['severity']),
                context=error_log['context'],
                email_sent=error_log['email_sent'],
                created_at=error_log['created_at'],
                updated_at=error_log['updated_at']
            )
            
    except Exception as e:
        logger.error(f"Failed to create error log: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.get("/{error_id}", response_model=ErrorLogResponse)
async def get_error_log(
    error_id: str,
    _: bool = Depends(AuthConfig.get_auth_dependency())
):
    """Get error log by ID"""
    db_pool = get_db_pool()
    
    try:
        async with db_pool.acquire() as conn:
            error_log = await conn.fetchrow("""
                SELECT error_id, component, error_message, severity, context, email_sent, created_at, updated_at
                FROM error_logs 
                WHERE error_id = $1
            """, error_id)
            
            if not error_log:
                raise HTTPException(status_code=404, detail="Error log not found")
            
            return ErrorLogResponse(
                error_id=error_log['error_id'],
                component=error_log['component'],
                error_message=error_log['error_message'],
                severity=ErrorSeverity(error_log['severity']),
                context=error_log['context'],
                email_sent=error_log['email_sent'],
                created_at=error_log['created_at'],
                updated_at=error_log['updated_at']
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get error log: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.put("/{error_id}", response_model=ErrorLogResponse)
async def update_error_log(
    error_id: str,
    request: ErrorLogUpdateRequest,
    _: bool = Depends(AuthConfig.get_auth_dependency())
):
    """Update error log record"""
    db_pool = get_db_pool()
    
    try:
        async with db_pool.acquire() as conn:
            # Check if error log exists
            existing_log = await conn.fetchrow(
                "SELECT * FROM error_logs WHERE error_id = $1", 
                error_id
            )
            
            if not existing_log:
                raise HTTPException(status_code=404, detail="Error log not found")
            
            # Build dynamic update query
            update_fields = []
            update_values = []
            param_count = 1
            
            if request.component is not None:
                update_fields.append(f"component = ${param_count}")
                update_values.append(request.component)
                param_count += 1
                
            if request.error_message is not None:
                update_fields.append(f"error_message = ${param_count}")
                update_values.append(request.error_message)
                param_count += 1
                
            if request.severity is not None:
                update_fields.append(f"severity = ${param_count}")
                update_values.append(request.severity.value)
                param_count += 1
                
            if request.context is not None:
                update_fields.append(f"context = ${param_count}")
                update_values.append(request.context)
                param_count += 1
                
            if request.email_sent is not None:
                update_fields.append(f"email_sent = ${param_count}")
                update_values.append(request.email_sent)
                param_count += 1
            
            if not update_fields:
                raise HTTPException(status_code=400, detail="No fields provided for update")
            
            # Always update the updated_at timestamp
            update_fields.append(f"updated_at = ${param_count}")
            update_values.append(datetime.utcnow())
            update_values.append(error_id)  # for WHERE clause
            
            query = f"""
                UPDATE error_logs 
                SET {', '.join(update_fields)}
                WHERE error_id = ${param_count + 1}
                RETURNING error_id, component, error_message, severity, context, email_sent, created_at, updated_at
            """
            
            updated_log = await conn.fetchrow(query, *update_values)
            
            return ErrorLogResponse(
                error_id=updated_log['error_id'],
                component=updated_log['component'],
                error_message=updated_log['error_message'],
                severity=ErrorSeverity(updated_log['severity']),
                context=updated_log['context'],
                email_sent=updated_log['email_sent'],
                created_at=updated_log['created_at'],
                updated_at=updated_log['updated_at']
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update error log: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.delete("/{error_id}")
async def delete_error_log(
    error_id: str,
    _: bool = Depends(AuthConfig.get_auth_dependency())
):
    """Delete error log record"""
    db_pool = get_db_pool()
    
    try:
        async with db_pool.acquire() as conn:
            # Check if error log exists
            existing_log = await conn.fetchrow(
                "SELECT error_id, component FROM error_logs WHERE error_id = $1", 
                error_id
            )
            
            if not existing_log:
                raise HTTPException(status_code=404, detail="Error log not found")
            
            # Delete the error log
            await conn.execute(
                "DELETE FROM error_logs WHERE error_id = $1",
                error_id
            )
            
            return {
                "message": "Error log deleted successfully",
                "error_id": error_id,
                "component": existing_log['component']
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete error log: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

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
    db_pool = get_db_pool()
    
    try:
        async with db_pool.acquire() as conn:
            # Build dynamic WHERE clause
            where_conditions = []
            query_params = []
            param_count = 1
            
            if component:
                where_conditions.append(f"component = ${param_count}")
                query_params.append(component)
                param_count += 1
                
            if severity:
                where_conditions.append(f"severity = ${param_count}")
                query_params.append(severity.value)
                param_count += 1
                
            if email_sent is not None:
                where_conditions.append(f"email_sent = ${param_count}")
                query_params.append(email_sent)
                param_count += 1
            
            where_clause = f"WHERE {' AND '.join(where_conditions)}" if where_conditions else ""
            
            query = f"""
                SELECT error_id, component, error_message, severity, context, email_sent, created_at, updated_at
                FROM error_logs 
                {where_clause}
                ORDER BY created_at DESC
                LIMIT ${param_count} OFFSET ${param_count + 1}
            """
            query_params.extend([limit, offset])
            
            error_logs = await conn.fetch(query, *query_params)
            
            return [
                ErrorLogResponse(
                    error_id=log['error_id'],
                    component=log['component'],
                    error_message=log['error_message'],
                    severity=ErrorSeverity(log['severity']),
                    context=log['context'],
                    email_sent=log['email_sent'],
                    created_at=log['created_at'],
                    updated_at=log['updated_at']
                ) for log in error_logs
            ]
            
    except Exception as e:
        logger.error(f"Failed to list error logs: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.get("/stats", response_model=ErrorLogStats)
async def get_error_log_stats(
    _: bool = Depends(AuthConfig.get_auth_dependency())
):
    """Get error log statistics"""
    db_pool = get_db_pool()
    
    try:
        async with db_pool.acquire() as conn:
            stats = await conn.fetchrow("""
                SELECT 
                    COUNT(*) as total_errors,
                    SUM(CASE WHEN email_sent = true THEN 1 ELSE 0 END) as emails_sent,
                    SUM(CASE WHEN severity = 'critical' THEN 1 ELSE 0 END) as critical_errors,
                    SUM(CASE WHEN severity = 'high' THEN 1 ELSE 0 END) as high_errors,
                    SUM(CASE WHEN severity = 'medium' THEN 1 ELSE 0 END) as medium_errors,
                    SUM(CASE WHEN severity = 'low' THEN 1 ELSE 0 END) as low_errors,
                    MAX(created_at) as last_error_at
                FROM error_logs
            """)
            
            last_email_sent_at = await conn.fetchval("""
                SELECT MAX(created_at)
                FROM error_logs
                WHERE email_sent = true
            """)
            
            return ErrorLogStats(
                total_errors=stats['total_errors'] or 0,
                emails_sent=stats['emails_sent'] or 0,
                critical_errors=stats['critical_errors'] or 0,
                high_errors=stats['high_errors'] or 0,
                medium_errors=stats['medium_errors'] or 0,
                low_errors=stats['low_errors'] or 0,
                last_error_at=stats['last_error_at'],
                last_email_sent_at=last_email_sent_at
            )
            
    except Exception as e:
        logger.error(f"Failed to get error log stats: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")