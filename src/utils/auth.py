"""
Authentication utilities for API endpoints
"""

import logging
import os
from typing import Optional, List
from fastapi import HTTPException, Header, Depends
from dataclasses import dataclass
import jwt

from config.service_permissions import get_agent_permissions, is_valid_agent_role
from services.agent_jwt_service import validate_agent_jwt

logger = logging.getLogger(__name__)

@dataclass
class AuthContext:
    """Legacy authentication context for backward compatibility"""
    is_authenticated: bool
    role: str = "default"
    actor_id: Optional[str] = None


@dataclass
class AgentAuthContext:
    """Authentication context for OAuth2-authenticated agents"""
    is_authenticated: bool
    agent_type: str
    service_id: str  # Which service requested this token
    allowed_endpoints: List[str]
    allowed_resources: List[str]
    allowed_operations: List[str]


async def authenticate_api(authorization: Optional[str] = Header(None)) -> AuthContext:
    """
    FastAPI dependency for JWT Bearer token authentication.
    
    Args:
        authorization: Authorization header with Bearer JWT token
        
    Returns:
        AuthContext: Authentication context with role information
        
    Raises:
        HTTPException: 401 if authentication fails
    """
    logger.info(f"AUTH: Starting JWT authentication check")
    
    if not authorization:
        logger.error("AUTH: API request missing Authorization header - returning 401")
        raise HTTPException(
            status_code=401, 
            detail="Missing Authorization header"
        )
    
    if not authorization.startswith("Bearer "):
        logger.error(f"AUTH: Invalid Authorization header format - returning 401")
        raise HTTPException(
            status_code=401, 
            detail="Invalid authorization header format. Expected 'Bearer <token>'"
        )
    
    token = authorization[7:]  # Remove "Bearer " prefix
    logger.info(f"AUTH: Extracted JWT token: '{token[:8]}...' (first 8 chars)")
    
    try:
        # Validate JWT token and extract claims
        jwt_payload = validate_agent_jwt(token)
        agent_role = jwt_payload['sub']
        service_id = jwt_payload.get('service_id', 'unknown')
        
        logger.info(f"AUTH: Environment-isolated JWT validation successful - Agent: {agent_role}, Service: {service_id}, Environment: {jwt_payload.get('environment', 'unknown')}")
        
        # Create backward-compatible AuthContext
        return AuthContext(
            is_authenticated=True,
            role=agent_role,
            actor_id=service_id
        )
        
    except jwt.InvalidTokenError as e:
        logger.error(f"AUTH: Invalid JWT token: {str(e)}")
        raise HTTPException(401, "Invalid JWT token")
    except Exception as e:
        logger.error(f"AUTH: JWT authentication error: {str(e)}")
        raise HTTPException(401, "JWT authentication failed")


async def authenticate_agent_jwt(
    authorization: Optional[str] = Header(None)
) -> AgentAuthContext:
    """
    OAuth2 access token authentication for agents
    
    Args:
        authorization: Authorization header with Bearer access token
        
    Returns:
        AgentAuthContext: Agent authentication context
        
    Raises:
        HTTPException: 401 if authentication fails, 403 if agent role invalid
    """
    logger.info("AGENT_AUTH: Starting OAuth2 access token authentication")
    
    # Validate Authorization header
    if not authorization:
        logger.error("AGENT_AUTH: Missing Authorization header")
        raise HTTPException(401, "Missing Authorization header")
    
    if not authorization.startswith("Bearer "):
        logger.error("AGENT_AUTH: Invalid Authorization header format")
        raise HTTPException(401, "Invalid authorization header format. Expected 'Bearer <access_token>'")
    
    access_token = authorization[7:]  # Remove "Bearer " prefix
    
    try:
        # Validate access token and extract claims
        jwt_payload = validate_agent_jwt(access_token)
        agent_role = jwt_payload['sub']
        service_id = jwt_payload.get('service_id', 'unknown')
        
        logger.info(f"AGENT_AUTH: Environment-isolated access token validation successful - Agent: {agent_role}, Service: {service_id}, Environment: {jwt_payload.get('environment', 'unknown')}")
        
        # Look up permissions from backend configuration
        # This is the key security feature - backend resolves permissions
        permissions = get_agent_permissions(agent_role)
        
        if not permissions:
            logger.error(f"AGENT_AUTH: No permissions found for agent role: {agent_role}")
            raise HTTPException(403, f"Agent role '{agent_role}' not configured")
        
        # Create auth context
        auth_context = AgentAuthContext(
            is_authenticated=True,
            agent_type=agent_role,
            service_id=service_id,
            allowed_endpoints=permissions['endpoints'],
            allowed_resources=permissions['resources'],
            allowed_operations=permissions['operations']
        )
        
        logger.info(f"AGENT_AUTH: OAuth2 authentication successful for {agent_role} (service: {service_id})")
        logger.debug(f"AGENT_AUTH: Granted permissions - Resources: {permissions['resources']}, Operations: {permissions['operations']}")
        
        return auth_context
        
    except jwt.InvalidTokenError as e:
        logger.error(f"AGENT_AUTH: Invalid access token: {str(e)}")
        raise HTTPException(401, "Invalid access token")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"AGENT_AUTH: OAuth2 authentication error: {str(e)}")
        raise HTTPException(401, "OAuth2 authentication failed")


class AuthConfig:
    """
    Centralized authentication configuration for the application.
    All endpoints now require authentication.
    """
    
    
    @staticmethod
    def get_auth_dependency():
        """Get the mandatory auth dependency for all endpoints"""
        return authenticate_api
    
    @staticmethod
    def get_agent_auth_dependency():
        """Get the agent-specific auth dependency"""
        return authenticate_agent_jwt