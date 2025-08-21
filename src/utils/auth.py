"""
Authentication utilities for API endpoints
"""

import logging
from typing import Optional
from fastapi import HTTPException, Header, Depends

from config.settings import API_KEY

logger = logging.getLogger(__name__)


async def authenticate_api(authorization: Optional[str] = Header(None)):
    """
    FastAPI dependency for Bearer token authentication.
    
    Args:
        authorization: Authorization header with Bearer token
        
    Returns:
        bool: True if authentication successful
        
    Raises:
        HTTPException: 401 if authentication fails
    """
    logger.info(f"AUTH: Starting authentication check")
    logger.info(f"AUTH: Authorization header present: {authorization is not None}")
    if authorization:
        logger.info(f"AUTH: Authorization header value: '{authorization[:20]}...' (first 20 chars)")
    
    if not authorization:
        logger.error("AUTH: API request missing Authorization header - returning 401")
        raise HTTPException(
            status_code=401, 
            detail="Missing Authorization header"
        )
    
    if not authorization.startswith("Bearer "):
        logger.error(f"AUTH: Invalid Authorization header format: '{authorization}' - returning 401")
        raise HTTPException(
            status_code=401, 
            detail="Invalid authorization header format. Expected 'Bearer <token>'"
        )
    
    token = authorization[7:]  # Remove "Bearer " prefix
    logger.info(f"AUTH: Extracted token: '{token[:8]}...' (first 8 chars)")
    
    if not API_KEY:
        logger.error("AUTH: API_KEY environment variable not configured - returning 500")
        raise HTTPException(
            status_code=500,
            detail="Server authentication not configured"
        )
    
    logger.info(f"AUTH: Comparing with configured API_KEY: '{API_KEY[:8] if API_KEY else 'NONE'}...' (first 8 chars)")
    if token != API_KEY:
        logger.error(f"AUTH: Invalid token provided: '{token[:8]}...' - returning 401")
        raise HTTPException(
            status_code=401, 
            detail="Invalid API key"
        )
    
    logger.info("AUTH: Authentication successful")
    return True



class AuthConfig:
    """
    Centralized authentication configuration for the application.
    All endpoints now require authentication.
    """
    
    @staticmethod
    def is_auth_enabled() -> bool:
        """Authentication is always enabled - API_KEY is required"""
        return True
    
    @staticmethod
    def get_auth_dependency():
        """Get the mandatory auth dependency for all endpoints"""
        return authenticate_api