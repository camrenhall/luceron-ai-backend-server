"""
Email service using Resend API
"""

import logging
from datetime import datetime
import resend
from fastapi import HTTPException

from config.settings import FROM_EMAIL
from models.email import EmailRequest, EmailResponse
from database.connection import get_db_pool

logger = logging.getLogger(__name__)

async def send_email_via_resend(request: EmailRequest) -> EmailResponse:
    """Send email via Resend API"""
    db_pool = get_db_pool()
    
    try:
        # Send email via Resend
        email_data = {
            "from": FROM_EMAIL,
            "to": [request.recipient_email],
            "subject": request.subject,
            "html": request.html_body or f"<p>{request.body.replace(chr(10), '<br>')}</p>",
            "text": request.body
        }
        
        result = resend.Emails.send(email_data)
        # Extract just the ID string from the Resend response
        if hasattr(result, 'id'):
            resend_id = result.id
        elif isinstance(result, dict) and 'id' in result:
            resend_id = result['id']
        else:
            resend_id = None
        
        # Log to database and get the generated UUID
        async with db_pool.acquire() as conn:
            # Insert into client_communications table and get the generated id
            comm_id = await conn.fetchval("""
                INSERT INTO client_communications 
                (case_id, channel, direction, status, sender, recipient, subject, message_content, sent_at, resend_id)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                RETURNING communication_id
            """,
            request.case_id, "email", "outgoing", "sent", FROM_EMAIL, 
            request.recipient_email, request.subject, request.body, datetime.utcnow(), resend_id)
        
        logger.info(f"Email sent via Resend - ID: {resend_id}, To: {request.recipient_email}")
        
        return EmailResponse(
            message_id=str(comm_id),
            status="sent",
            recipient=request.recipient_email,
            case_id=request.case_id,
            sent_via="resend"
        )
        
    except Exception as e:
        # Log failure
        async with db_pool.acquire() as conn:
            # Insert into client_communications table and get the generated id
            await conn.fetchval("""
                INSERT INTO client_communications 
                (case_id, channel, direction, status, sender, recipient, subject, message_content, sent_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                RETURNING id
            """,
            request.case_id, "email", "outgoing", "failed", FROM_EMAIL, 
            request.recipient_email, request.subject, request.body, datetime.utcnow())
        
        logger.error(f"Email sending failed: {e}")
        raise HTTPException(status_code=500, detail=f"Email sending failed: {str(e)}")