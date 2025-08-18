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
    """Send immediate failure notification - bypasses regular email flow"""
    
    # Build alert email
    subject = f"🚨 {request.severity.upper()}: {request.component} Failure"
    html_body = f"""
    <h2>Production Alert</h2>
    <p><strong>Component:</strong> {request.component}</p>
    <p><strong>Error:</strong> {request.error_message}</p>
    <p><strong>Severity:</strong> {request.severity}</p>
    <p><strong>Time:</strong> {datetime.utcnow().isoformat()}</p>
    {f"<p><strong>Context:</strong> {request.context}</p>" if request.context else ""}
    """
    
    # Send directly via Resend to all admin emails (no database logging)
    sent_count = 0
    failed_count = 0
    
    for email in ADMIN_ALERT_EMAILS:
        try:
            await send_direct_alert(email.strip(), subject, html_body)
            sent_count += 1
        except Exception as e:
            logger.error(f"Failed to send alert to {email}: {e}")
            failed_count += 1
    
    logger.info(f"Alert sent: {request.component} - {sent_count} sent, {failed_count} failed")
    
    return {
        "status": "alerts_processed",
        "sent": sent_count,
        "failed": failed_count,
        "total_recipients": len(ADMIN_ALERT_EMAILS)
    }