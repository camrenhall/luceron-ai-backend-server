"""
Email management API routes
"""

from fastapi import APIRouter, Depends
from models.email import EmailRequest
from services.email_service import send_email_via_resend
from utils.auth import AuthConfig

router = APIRouter()

@router.post("/send-email")
async def send_email(
    request: EmailRequest,
    _: bool = Depends(AuthConfig.get_auth_dependency())
):
    """Send email via Resend"""
    return await send_email_via_resend(request)