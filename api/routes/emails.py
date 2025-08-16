"""
Email management API routes
"""

from fastapi import APIRouter
from models.email import EmailRequest
from services.email_service import send_email_via_resend

router = APIRouter()

@router.post("/send-email")
async def send_email(request: EmailRequest):
    """Send email via Resend"""
    return await send_email_via_resend(request)