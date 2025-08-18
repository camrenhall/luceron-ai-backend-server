"""
Webhook API routes
"""

import logging
from fastapi import APIRouter, HTTPException, Request

from models.webhook import ResendWebhook
from utils.helpers import parse_uploaded_timestamp
from database.connection import get_db_pool
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
    
    db_pool = get_db_pool()
    
    logger.info(f"📧 Resend webhook received: type={webhook.type}, email_id={webhook.data.email_id}")
    
    try:
        async with db_pool.acquire() as conn:
            if webhook.type == "email.opened":
                # Parse the opened timestamp (top-level created_at is when email was opened)
                opened_at = parse_uploaded_timestamp(webhook.created_at)
                
                # Update opened_at timestamp AND set status to "opened"
                result = await conn.execute("""
                    UPDATE client_communications 
                    SET opened_at = $1, status = 'opened'
                    WHERE resend_id = $2
                """, opened_at, webhook.data.email_id)
                
                action = "opened"
                
            elif webhook.type == "email.failed":
                # Only update status to "failed" (no timestamp update)
                result = await conn.execute("""
                    UPDATE client_communications 
                    SET status = 'failed'
                    WHERE resend_id = $1
                """, webhook.data.email_id)
                
                failure_reason = webhook.data.failed.reason if webhook.data.failed else "unknown"
                logger.info(f"❌ Email failed: reason={failure_reason}")
                action = f"failed (reason: {failure_reason})"
                
            elif webhook.type == "email.bounced":
                # Only update status to "failed" (no timestamp update)
                result = await conn.execute("""
                    UPDATE client_communications 
                    SET status = 'failed'
                    WHERE resend_id = $1
                """, webhook.data.email_id)
                
                bounce_info = ""
                if webhook.data.bounce:
                    bounce_info = f"{webhook.data.bounce.type}/{webhook.data.bounce.subType}: {webhook.data.bounce.message}"
                
                logger.info(f"🔄 Email bounced: {bounce_info}")
                action = f"bounced ({bounce_info})"
                
            elif webhook.type == "email.delivered":
                # Only update status to "delivered" (no timestamp update)
                result = await conn.execute("""
                    UPDATE client_communications 
                    SET status = 'delivered'
                    WHERE resend_id = $1
                """, webhook.data.email_id)
                
                action = "delivered"
                
            else:
                logger.warning(f"⚠️ Unsupported webhook type: {webhook.type}")
                return {"status": "unsupported", "type": webhook.type, "message": "Webhook type not supported"}
            
            # Check if any row was updated
            rows_updated = int(result.split()[-1]) if result.startswith("UPDATE") else 0
            
            if rows_updated > 0:
                logger.info(f"✅ Email {action}: Updated {rows_updated} record(s) for email_id={webhook.data.email_id}")
                return {"status": "updated", "email_id": webhook.data.email_id, "rows_updated": rows_updated, "action": action}
            else:
                # Email ID not found - log but don't fail (as per requirements)
                logger.info(f"ℹ️ Resend webhook: email_id={webhook.data.email_id} not found in database (likely from another system)")
                return {"status": "not_found", "email_id": webhook.data.email_id, "message": "Email ID not found in database"}
        
    except Exception as e:
        logger.error(f"Resend webhook processing failed: {e}")
        raise HTTPException(status_code=500, detail=f"Webhook processing failed: {str(e)}")