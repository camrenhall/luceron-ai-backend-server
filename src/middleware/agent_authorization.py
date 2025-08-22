"""
Agent authorization middleware for endpoint-level permission enforcement
"""

import logging
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from config.service_permissions import can_access_endpoint
from utils.auth import authenticate_agent_jwt

logger = logging.getLogger(__name__)

class AgentAuthorizationMiddleware(BaseHTTPMiddleware):
    """
    Middleware that enforces endpoint-level permissions for agent requests
    
    This middleware:
    1. Identifies agent-based requests (by presence of JWT in Authorization header)
    2. Validates JWT authentication
    3. Checks if agent is authorized to access the requested endpoint
    4. Injects auth context for downstream use
    """
    
    # Endpoints that don't require agent authorization
    PUBLIC_ENDPOINTS = {
        "/health",
        "/docs", 
        "/openapi.json",
        "/redoc"
    }
    
    async def dispatch(self, request: Request, call_next):
        """Process request through agent authorization"""
        
        # Skip authorization for public endpoints
        if request.url.path in self.PUBLIC_ENDPOINTS:
            logger.debug(f"Skipping agent auth for public endpoint: {request.url.path}")
            return await call_next(request)
        
        # Check if this is an agent request (has JWT in Authorization header)
        authorization = request.headers.get("authorization")
        
        if not authorization or not authorization.startswith("Bearer "):
            # Not an agent request - let it proceed with regular auth
            logger.debug(f"Non-JWT request to {request.url.path} - skipping agent authorization")
            return await call_next(request)
        
        # This is an agent request - perform JWT authentication
        try:
            auth_context = await self._authenticate_agent_request(request)
            logger.info(f"Agent {auth_context.agent_type} authenticated for {request.url.path}")
            
        except HTTPException as e:
            logger.warning(f"Agent authentication failed for {request.url.path}: {e.detail}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error during agent authentication: {str(e)}")
            raise HTTPException(500, "Internal authentication error")
        
        # Check endpoint authorization
        if not self._is_endpoint_authorized(request.url.path, auth_context):
            logger.warning(f"Agent {auth_context.agent_type} denied access to {request.url.path}")
            raise HTTPException(
                403, 
                f"Agent '{auth_context.agent_type}' not authorized to access {request.url.path}"
            )
        
        logger.info(f"Agent {auth_context.agent_type} authorized for {request.url.path}")
        
        # Inject auth context for downstream use
        request.state.agent_auth = auth_context
        
        # Proceed with request
        return await call_next(request)
    
    async def _authenticate_agent_request(self, request: Request):
        """Extract headers and perform JWT authentication"""
        
        authorization = request.headers.get("authorization")
        
        # Use the JWT authentication function
        # We need to simulate the FastAPI dependency injection
        from utils.auth import authenticate_agent_jwt
        
        try:
            auth_context = await authenticate_agent_jwt(
                authorization=authorization
            )
            return auth_context
            
        except HTTPException:
            # Re-raise HTTP exceptions as-is
            raise
        except Exception as e:
            # Wrap other exceptions
            logger.error(f"Authentication error: {str(e)}")
            raise HTTPException(401, "Authentication failed")
    
    def _is_endpoint_authorized(self, endpoint_path: str, auth_context) -> bool:
        """
        Check if agent is authorized to access the requested endpoint
        
        Args:
            endpoint_path: The requested endpoint path
            auth_context: Agent authentication context
            
        Returns:
            bool: True if authorized, False otherwise
        """
        # Check against agent's allowed endpoints
        allowed_endpoints = auth_context.allowed_endpoints
        
        # Direct match
        if endpoint_path in allowed_endpoints:
            return True
        
        # Wildcard match (if we want to support patterns later)
        for allowed_pattern in allowed_endpoints:
            if allowed_pattern.endswith("*") and endpoint_path.startswith(allowed_pattern[:-1]):
                return True
        
        logger.debug(f"Endpoint {endpoint_path} not in allowed endpoints: {allowed_endpoints}")
        return False


class AgentOnlyMiddleware(BaseHTTPMiddleware):
    """
    Alternative middleware that ONLY allows agent requests to specific endpoints
    Use this if you want to completely block non-agent access to certain endpoints
    """
    
    # Endpoints that ONLY agents can access
    AGENT_ONLY_ENDPOINTS = {
        "/agent/db"
    }
    
    async def dispatch(self, request: Request, call_next):
        """Ensure only agents can access agent-only endpoints"""
        
        if request.url.path in self.AGENT_ONLY_ENDPOINTS:
            authorization = request.headers.get("authorization")
            
            if not authorization or not authorization.startswith("Bearer "):
                logger.warning(f"Non-agent request blocked from agent-only endpoint: {request.url.path}")
                raise HTTPException(
                    403, 
                    f"Endpoint {request.url.path} is only accessible to authenticated agents"
                )
        
        return await call_next(request)