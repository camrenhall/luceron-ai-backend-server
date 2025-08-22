"""
Webhook API routes - Unified Service Layer Architecture
Webhook signature verification stays in route, database operations use service layer.
"""

import logging
from fastapi import APIRouter, HTTPException, Request

from models.webhook import ResendWebhook
from utils.helpers import parse_uploaded_timestamp
from services.communications_service import get_communications_service
from utils.webhook_verification import verify_resend_webhook

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/resend")
async def handle_resend_webhook(request: Request):
    """Handle Resend webhooks (email.opened, email.delivered, email.failed, email.bounced)"""
    # Verify webhook signature and get parsed payload
    payload = await verify_resend_webhook(request)
    
    # Parse the verified payload into ResendWebhook model
    webhook = ResendWebhook(**payload)
    
    communications_service = get_communications_service()
    
    logger.info(f"📧 Resend webhook received: type={webhook.type}, email_id={webhook.data.email_id}")
    
    try:
        # Process different webhook types
        if webhook.type == "email.opened":
            # Parse the opened timestamp (top-level created_at is when email was opened)
            opened_at = parse_uploaded_timestamp(webhook.created_at)
            
            # Update via service layer
            result = await communications_service.update_communication_status(
                resend_id=webhook.data.email_id,
                status="opened",
                opened_at=opened_at
            )
            
            action = "opened"
            
        elif webhook.type == "email.failed":
            # Update status to "failed"
            result = await communications_service.update_communication_status(
                resend_id=webhook.data.email_id,
                status="failed"
            )
            
            failure_reason = webhook.data.failed.reason if webhook.data.failed else "unknown"
            logger.info(f"❌ Email failed: reason={failure_reason}")
            action = f"failed (reason: {failure_reason})"
            
        elif webhook.type == "email.bounced":
            # Update status to "failed"  
            result = await communications_service.update_communication_status(
                resend_id=webhook.data.email_id,
                status="failed"
            )
            
            bounce_info = ""
            if webhook.data.bounce:
                bounce_info = f"{webhook.data.bounce.type}/{webhook.data.bounce.subType}: {webhook.data.bounce.message}"
            
            logger.info(f"🔄 Email bounced: {bounce_info}")
            action = f"bounced ({bounce_info})"
            
        elif webhook.type == "email.delivered":
            # Update status to "delivered"
            result = await communications_service.update_communication_status(
                resend_id=webhook.data.email_id,
                status="delivered"
            )
            
            action = "delivered"
            
        else:
            logger.warning(f"⚠️ Unsupported webhook type: {webhook.type}")
            return {"status": "unsupported", "type": webhook.type, "message": "Webhook type not supported"}
        
        # Check result from service
        if result.success:
            rows_updated = 1 if result.data else 0
            logger.info(f"✅ Email {action}: Updated {rows_updated} record(s) for email_id={webhook.data.email_id}")
            return {"status": "updated", "email_id": webhook.data.email_id, "rows_updated": rows_updated, "action": action}
        else:
            if result.error_type == "RESOURCE_NOT_FOUND":
                # Email ID not found - log but don't fail (as per requirements)
                logger.info(f"ℹ️ Resend webhook: email_id={webhook.data.email_id} not found in database (likely from another system)")
                return {"status": "not_found", "email_id": webhook.data.email_id, "message": "Email ID not found in database"}
            else:
                raise HTTPException(status_code=500, detail=result.error)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Resend webhook processing failed: {e}")
        raise HTTPException(status_code=500, detail=f"Webhook processing failed: {str(e)}")