"""
Error logs service - business logic for error logging and monitoring
"""

import logging
from typing import Dict, Any, List, Optional
from services.base_service import BaseService, ServiceResult

logger = logging.getLogger(__name__)

class ErrorLogsService(BaseService):
    """Service for error logging operations"""
    
    def __init__(self, role: str = "api"):
        super().__init__("error_logs", role)
    
    async def log_error(
        self,
        component: str,
        error_message: str,
        severity: str = "medium",
        context: Optional[Dict[str, Any]] = None,
        email_sent: bool = False
    ) -> ServiceResult:
        """
        Log a new error
        
        Args:
            component: Component/module where error occurred
            error_message: Detailed error message
            severity: Error severity (low, medium, high, critical)
            context: Additional context information as JSON
            email_sent: Whether error notification email was sent
            
        Returns:
            ServiceResult with created error log data
        """
        error_data = {
            "component": component,
            "error_message": error_message,
            "severity": severity,
            "email_sent": email_sent
        }
        
        if context:
            error_data["context"] = context
        
        logger.info(f"Logging {severity} error in {component}: {error_message[:100]}...")
        return await self.create(error_data)
    
    async def log_critical_error(
        self,
        component: str,
        error_message: str,
        context: Optional[Dict[str, Any]] = None
    ) -> ServiceResult:
        """Log a critical error (highest severity)"""
        return await self.log_error(
            component=component,
            error_message=error_message,
            severity="critical",
            context=context,
            email_sent=False  # Will be updated separately when email is sent
        )
    
    async def log_high_error(
        self,
        component: str,
        error_message: str,
        context: Optional[Dict[str, Any]] = None
    ) -> ServiceResult:
        """Log a high severity error"""
        return await self.log_error(
            component=component,
            error_message=error_message,
            severity="high",
            context=context
        )
    
    async def log_medium_error(
        self,
        component: str,
        error_message: str,
        context: Optional[Dict[str, Any]] = None
    ) -> ServiceResult:
        """Log a medium severity error"""
        return await self.log_error(
            component=component,
            error_message=error_message,
            severity="medium",
            context=context
        )
    
    async def log_low_error(
        self,
        component: str,
        error_message: str,
        context: Optional[Dict[str, Any]] = None
    ) -> ServiceResult:
        """Log a low severity error"""
        return await self.log_error(
            component=component,
            error_message=error_message,
            severity="low",
            context=context
        )
    
    async def get_error_by_id(self, error_id: str) -> ServiceResult:
        """Get an error log by its ID"""
        return await self.get_by_id(error_id)
    
    async def get_errors_by_component(self, component: str, limit: int = 100) -> ServiceResult:
        """Get error logs for a specific component"""
        return await self.get_by_field("component", component, limit)
    
    async def get_errors_by_severity(self, severity: str, limit: int = 100) -> ServiceResult:
        """Get error logs by severity level"""
        return await self.get_by_field("severity", severity, limit)
    
    async def get_critical_errors(self, limit: int = 100) -> ServiceResult:
        """Get all critical errors"""
        return await self.get_errors_by_severity("critical", limit)
    
    async def get_high_errors(self, limit: int = 100) -> ServiceResult:
        """Get all high severity errors"""
        return await self.get_errors_by_severity("high", limit)
    
    async def get_unsent_email_errors(self, severity_levels: Optional[List[str]] = None) -> ServiceResult:
        """
        Get errors that haven't had notification emails sent
        
        Args:
            severity_levels: List of severity levels to include (default: critical, high)
            
        Returns:
            ServiceResult with errors needing email notifications
        """
        if severity_levels is None:
            severity_levels = ["critical", "high"]
        
        filters = {
            "email_sent": False,
            "severity": {
                "op": "IN",
                "value": severity_levels
            }
        }
        
        return await self.read(
            filters=filters,
            order_by=[{"field": "created_at", "dir": "asc"}],
            limit=50
        )
    
    async def mark_email_sent(self, error_id: str) -> ServiceResult:
        """Mark that notification email has been sent for an error"""
        logger.info(f"Marking email sent for error {error_id}")
        return await self.update(error_id, {"email_sent": True})
    
    async def search_errors(
        self,
        component_pattern: Optional[str] = None,
        message_pattern: Optional[str] = None,
        severity_levels: Optional[List[str]] = None,
        email_sent: Optional[bool] = None,
        limit: int = 100,
        offset: int = 0
    ) -> ServiceResult:
        """
        Search error logs with various filters
        
        Args:
            component_pattern: Pattern to match component names (ILIKE)
            message_pattern: Pattern to match error messages (ILIKE)
            severity_levels: List of severity levels to include
            email_sent: Filter by email sent status
            limit: Maximum number of results
            offset: Number of results to skip
            
        Returns:
            ServiceResult with matching error logs
        """
        filters = {}
        
        if component_pattern:
            filters["component"] = {
                "op": "ILIKE",
                "value": f"%{component_pattern}%"
            }
        
        if message_pattern:
            filters["error_message"] = {
                "op": "ILIKE",
                "value": f"%{message_pattern}%"
            }
        
        if severity_levels:
            filters["severity"] = {
                "op": "IN",
                "value": severity_levels
            }
        
        if email_sent is not None:
            filters["email_sent"] = email_sent
        
        order_by = [{"field": "created_at", "dir": "desc"}]
        
        logger.info(f"Searching error logs with filters: {filters}")
        return await self.read(
            filters=filters,
            order_by=order_by,
            limit=limit,
            offset=offset
        )
    
    async def get_recent_errors(self, limit: int = 50) -> ServiceResult:
        """Get most recent error logs"""
        return await self.read(
            order_by=[{"field": "created_at", "dir": "desc"}],
            limit=limit
        )
    
    async def get_error_summary_by_component(self, hours: int = 24) -> ServiceResult:
        """
        Get error count summary by component for the last N hours
        Note: This is a simplified version. In production, you might want
        to use aggregation queries or a separate analytics service.
        
        Args:
            hours: Number of hours to look back (default: 24)
            
        Returns:
            ServiceResult with recent errors (client can aggregate)
        """
        from datetime import datetime, timedelta
        
        # Calculate timestamp for N hours ago
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        cutoff_iso = cutoff_time.isoformat()
        
        filters = {
            "created_at": {
                "op": ">=",
                "value": cutoff_iso
            }
        }
        
        return await self.read(
            filters=filters,
            order_by=[{"field": "component"}, {"field": "severity"}],
            limit=1000  # Large limit for summary data
        )
    
    async def delete_error_log(self, error_id: str) -> ServiceResult:
        """
        Delete an error log entry
        
        Args:
            error_id: UUID of the error log to delete
            
        Returns:
            ServiceResult indicating success/failure
        """
        logger.info(f"Deleting error log {error_id}")
        
        try:
            # Verify error log exists first
            get_result = await self.get_by_id(error_id)
            if not get_result.success:
                return get_result  # Return the same error
            
            # Use the base service delete method
            return await self.delete(error_id)
            
        except Exception as e:
            logger.error(f"Delete error log failed for {error_id}: {e}")
            return ServiceResult(
                success=False,
                error=str(e),
                error_type="EXECUTION_ERROR"
            )

# Global service instance
_error_logs_service: Optional[ErrorLogsService] = None

def get_error_logs_service() -> ErrorLogsService:
    """Get the global error logs service instance"""
    global _error_logs_service
    if _error_logs_service is None:
        _error_logs_service = ErrorLogsService()
    return _error_logs_service