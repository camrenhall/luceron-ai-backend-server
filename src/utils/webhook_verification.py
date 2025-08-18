"""
Webhook verification utilities using Svix for Resend webhooks
"""

import logging
import os
from typing import Dict, Any
from fastapi import HTTPException, Request
from svix import Webhook

logger = logging.getLogger(__name__)


async def verify_resend_webhook(request: Request) -> Dict[str, Any]:
    """
    Verify Resend webhook signature using Svix library.
    
    Args:
        request: FastAPI Request object containing headers and raw body
        
    Returns:
        Dict[str, Any]: Parsed and verified webhook payload
        
    Raises:
        HTTPException: 400 if verification fails, 500 if secret not configured
    """
    webhook_secret = os.getenv("RESEND_WEBHOOK_SECRET")
    if not webhook_secret:
        logger.error("RESEND_WEBHOOK_SECRET environment variable not configured")
        raise HTTPException(
            status_code=500, 
            detail="Webhook secret not configured"
        )
    
    try:
        # Get the raw request body
        payload = await request.body()
        payload_str = payload.decode("utf-8")
        
        # Extract Svix headers
        headers = {
            "svix-id": request.headers.get("svix-id"),
            "svix-timestamp": request.headers.get("svix-timestamp"), 
            "svix-signature": request.headers.get("svix-signature"),
        }
        
        # Check that all required headers are present
        missing_headers = [key for key, value in headers.items() if not value]
        if missing_headers:
            logger.error(f"Missing required webhook headers: {missing_headers}")
            raise HTTPException(
                status_code=400,
                detail=f"Missing required webhook headers: {missing_headers}"
            )
        
        # Verify the webhook using Svix
        wh = Webhook(webhook_secret)
        verified_payload = wh.verify(payload_str, headers)
        
        logger.debug("Webhook signature verification successful")
        return verified_payload
        
    except Exception as e:
        logger.error(f"Webhook verification failed: {str(e)}")
        raise HTTPException(
            status_code=400,
            detail=f"Webhook verification failed: {str(e)}"
        )