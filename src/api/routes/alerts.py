"""
Alert notification API routes
Handles production failure notifications sent directly to admin emails
"""

import logging
from datetime import datetime
from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from services.email_service import send_direct_alert
from services.error_log_service import ErrorLogService
from models.error_log import ErrorLogResponse, ErrorLogStats
from config.settings import ADMIN_ALERT_EMAILS
from utils.auth import AuthConfig

router = APIRouter()
logger = logging.getLogger(__name__)

class AlertRequest(BaseModel):
    component: str
    error_message: str
    severity: str = "medium"
    context: Optional[Dict[str, Any]] = None

@router.post("/alert")
async def send_failure_alert(
    request: AlertRequest,
    _: bool = Depends(AuthConfig.get_auth_dependency())
):
    """Send immediate failure notification with deduplication - logs all errors but limits emails"""
    
    try:
        # Log error and check if email should be sent (15-minute deduplication)
        error_id, should_send_email = await ErrorLogService.log_error(
            component=request.component,
            error_message=request.error_message,
            severity=request.severity,
            context=request.context
        )
        
        sent_count = 0
        failed_count = 0
        
        if should_send_email:
            # Build alert email
            subject = f"🚨 {request.severity.upper()}: {request.component} Failure"
            html_body = f"""
            <h2>Production Alert</h2>
            <p><strong>Component:</strong> {request.component}</p>
            <p><strong>Error:</strong> {request.error_message}</p>
            <p><strong>Severity:</strong> {request.severity}</p>
            <p><strong>Time:</strong> {datetime.utcnow().isoformat()}</p>
            <p><strong>Error ID:</strong> {error_id}</p>
            {f"<p><strong>Context:</strong> {request.context}</p>" if request.context else ""}
            """
            
            # Send directly via Resend to all admin emails
            for email in ADMIN_ALERT_EMAILS:
                try:
                    await send_direct_alert(email.strip(), subject, html_body)
                    sent_count += 1
                except Exception as e:
                    logger.error(f"Failed to send alert to {email}: {e}")
                    failed_count += 1
            
            logger.info(f"Alert sent: {request.component} - {sent_count} sent, {failed_count} failed")
        else:
            logger.info(f"Alert suppressed (15-min rule): {request.component} - logged as {error_id}")
        
        return {
            "status": "alert_processed",
            "error_id": str(error_id),
            "email_sent": should_send_email,
            "sent": sent_count,
            "failed": failed_count,
            "total_recipients": len(ADMIN_ALERT_EMAILS) if should_send_email else 0,
            "message": "Email sent" if should_send_email else "Error logged but email suppressed (sent within last 15 minutes)"
        }
        
    except Exception as e:
        logger.error(f"Error processing alert: {e}")
        return {
            "status": "error",
            "message": f"Failed to process alert: {str(e)}"
        }

@router.get("/logs")
async def get_error_logs(
    component: Optional[str] = None,
    severity: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    _: bool = Depends(AuthConfig.get_auth_dependency())
):
    """Get error logs with optional filtering"""
    try:
        logs = await ErrorLogService.get_error_logs(
            component=component,
            severity=severity,
            limit=limit,
            offset=offset
        )
        
        return {
            "status": "success",
            "data": logs,
            "count": len(logs),
            "filters": {
                "component": component,
                "severity": severity,
                "limit": limit,
                "offset": offset
            }
        }
    except Exception as e:
        logger.error(f"Error retrieving error logs: {e}")
        return {
            "status": "error",
            "message": f"Failed to retrieve error logs: {str(e)}"
        }

@router.get("/stats/{component}")
async def get_component_stats(
    component: str,
    hours: int = 24,
    _: bool = Depends(AuthConfig.get_auth_dependency())
):
    """Get statistics for a specific component"""
    try:
        stats = await ErrorLogService.get_component_stats(component, hours)
        
        return {
            "status": "success",
            "component": component,
            "period_hours": hours,
            "stats": stats
        }
    except Exception as e:
        logger.error(f"Error retrieving component stats: {e}")
        return {
            "status": "error",
            "message": f"Failed to retrieve component stats: {str(e)}"
        }