"""
Error logging service with email deduplication functionality
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple
from uuid import UUID
import asyncpg

from database.connection import get_db_pool

logger = logging.getLogger(__name__)

class ErrorLogService:
    """Service for managing error logs with email deduplication"""
    
    @staticmethod
    async def log_error(
        component: str,
        error_message: str,
        severity: str = "medium",
        context: Optional[Dict[str, Any]] = None
    ) -> Tuple[UUID, bool]:
        """
        Log an error and determine if email should be sent based on 15-minute deduplication
        
        Args:
            component: The component that generated the error
            error_message: The error message
            severity: Error severity level
            context: Additional context data
            
        Returns:
            Tuple of (error_id, should_send_email)
        """
        db_pool = get_db_pool()
        
        async with db_pool.acquire() as conn:
            async with conn.transaction():
                # Check if email was sent for this component in the last 15 minutes
                should_send_email = await ErrorLogService._should_send_email(
                    conn, component
                )
                
                # Insert the error log
                error_id = await conn.fetchval("""
                    INSERT INTO error_logs (
                        component, error_message, severity, context, email_sent, created_at, updated_at
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7)
                    RETURNING error_id
                """, 
                component, error_message, severity, context, 
                should_send_email, datetime.utcnow(), datetime.utcnow())
                
                logger.info(
                    f"Error logged: {component} - {severity} - Email: {should_send_email}"
                )
                
                return error_id, should_send_email

    @staticmethod
    async def _should_send_email(conn: asyncpg.Connection, component: str) -> bool:
        """
        Check if an email should be sent for this component based on 15-minute rule
        
        Args:
            conn: Database connection
            component: The component to check
            
        Returns:
            True if email should be sent, False if within 15-minute window
        """
        # Calculate the cutoff time (15 minutes ago)
        cutoff_time = datetime.utcnow() - timedelta(minutes=15)
        
        # Check if any email was sent for this component in the last 15 minutes
        recent_email_count = await conn.fetchval("""
            SELECT COUNT(*)
            FROM error_logs 
            WHERE component = $1 
                AND email_sent = TRUE 
                AND created_at > $2
        """, component, cutoff_time)
        
        # Send email only if no email was sent in the last 15 minutes
        return recent_email_count == 0

    @staticmethod
    async def get_error_logs(
        component: Optional[str] = None,
        severity: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> list:
        """
        Retrieve error logs with optional filtering
        
        Args:
            component: Filter by component name
            severity: Filter by severity level
            limit: Maximum number of records to return
            offset: Number of records to skip
            
        Returns:
            List of error log records
        """
        db_pool = get_db_pool()
        
        query = """
            SELECT error_id, component, error_message, severity, 
                   context, email_sent, created_at, updated_at
            FROM error_logs
            WHERE 1=1
        """
        params = []
        param_count = 0
        
        if component:
            param_count += 1
            query += f" AND component = ${param_count}"
            params.append(component)
            
        if severity:
            param_count += 1
            query += f" AND severity = ${param_count}"
            params.append(severity)
        
        query += f" ORDER BY created_at DESC LIMIT ${param_count + 1} OFFSET ${param_count + 2}"
        params.extend([limit, offset])
        
        async with db_pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            
            return [dict(row) for row in rows]

    @staticmethod
    async def get_error_by_id(error_id: UUID) -> Optional[Dict[str, Any]]:
        """
        Get a specific error log by ID
        
        Args:
            error_id: The UUID of the error log
            
        Returns:
            Error log record or None if not found
        """
        db_pool = get_db_pool()
        
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT error_id, component, error_message, severity, 
                       context, email_sent, created_at, updated_at
                FROM error_logs 
                WHERE error_id = $1
            """, error_id)
            
            return dict(row) if row else None

    @staticmethod
    async def get_component_stats(component: str, hours: int = 24) -> Dict[str, Any]:
        """
        Get statistics for a specific component
        
        Args:
            component: The component name
            hours: Number of hours to look back
            
        Returns:
            Statistics dictionary
        """
        db_pool = get_db_pool()
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        
        async with db_pool.acquire() as conn:
            stats = await conn.fetchrow("""
                SELECT 
                    COUNT(*) as total_errors,
                    COUNT(CASE WHEN email_sent = TRUE THEN 1 END) as emails_sent,
                    COUNT(CASE WHEN severity = 'critical' THEN 1 END) as critical_errors,
                    COUNT(CASE WHEN severity = 'high' THEN 1 END) as high_errors,
                    COUNT(CASE WHEN severity = 'medium' THEN 1 END) as medium_errors,
                    COUNT(CASE WHEN severity = 'low' THEN 1 END) as low_errors,
                    MAX(created_at) as last_error_at,
                    MAX(CASE WHEN email_sent = TRUE THEN created_at END) as last_email_sent_at
                FROM error_logs 
                WHERE component = $1 AND created_at > $2
            """, component, cutoff_time)
            
            return dict(stats) if stats else {}