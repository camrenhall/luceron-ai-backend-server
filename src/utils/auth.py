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
    if not authorization:
        logger.warning("API request missing Authorization header")
        raise HTTPException(
            status_code=401, 
            detail="Missing Authorization header"
        )
    
    if not authorization.startswith("Bearer "):
        logger.warning("API request with invalid Authorization header format")
        raise HTTPException(
            status_code=401, 
            detail="Invalid authorization header format. Expected 'Bearer <token>'"
        )
    
    token = authorization[7:]  # Remove "Bearer " prefix
    
    if not API_KEY:
        logger.error("API_KEY environment variable not configured")
        raise HTTPException(
            status_code=500,
            detail="Server authentication not configured"
        )
    
    if token != API_KEY:
        logger.warning(f"API request with invalid token: {token[:8]}...")
        raise HTTPException(
            status_code=401, 
            detail="Invalid API key"
        )
    
    logger.debug("API request authenticated successfully")
    return True


def optional_auth():
    """
    Optional authentication dependency that can be easily added/removed from endpoints.
    
    Usage:
        @router.post("/endpoint", dependencies=[Depends(optional_auth)])
    """
    return Depends(authenticate_api) if API_KEY else None


class AuthConfig:
    """
    Centralized authentication configuration for the application.
    """
    
    @staticmethod
    def is_auth_enabled() -> bool:
        """Check if authentication is enabled (API_KEY is set)"""
        return bool(API_KEY)
    
    @staticmethod
    def get_auth_dependency():
        """Get the appropriate auth dependency based on configuration"""
        return Depends(authenticate_api) if AuthConfig.is_auth_enabled() else None