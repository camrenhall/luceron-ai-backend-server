"""
Suspension middleware for blocking requests during emergency suspension
"""

import logging
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from utils.suspension import suspension_manager

logger = logging.getLogger(__name__)

class SuspensionMiddleware(BaseHTTPMiddleware):
    """
    Middleware that blocks all requests when server is suspended
    
    Exceptions:
    - Health check endpoints (keep server appearing healthy)
    - Emergency control endpoints (allow resume)
    - Static files and documentation
    """
    
    # Endpoints that are allowed during suspension
    ALLOWED_DURING_SUSPENSION = {
        "/",                           # Health check
        "/health",                     # Health check
        "/emergency/resume",           # Allow resume
        "/emergency/status",           # Allow status check
        "/docs",                       # API documentation
        "/redoc",                      # API documentation
        "/openapi.json",              # OpenAPI spec
    }
    
    async def dispatch(self, request: Request, call_next):
        # Check if server is suspended
        if suspension_manager.is_suspended:
            path = request.url.path
            
            # Allow certain endpoints during suspension
            if self._is_allowed_during_suspension(path):
                response = await call_next(request)
                return response
            
            # Block all other requests with 503 Service Unavailable
            suspension_info = suspension_manager.get_suspension_info()
            
            logger.warning(f"🔴 BLOCKED REQUEST during suspension: {request.method} {path}")
            
            return JSONResponse(
                status_code=503,
                content={
                    "detail": "Server is currently suspended for emergency maintenance",
                    "error_code": "SERVER_SUSPENDED",
                    "suspension_info": {
                        "suspended_at": suspension_info["suspended_at"],
                        "reason": suspension_info["reason"]
                    },
                    "contact": "Contact system administrator to resume operations"
                }
            )
        
        # Normal operation - process request
        response = await call_next(request)
        return response
    
    def _is_allowed_during_suspension(self, path: str) -> bool:
        """
        Check if a path is allowed during suspension
        
        Args:
            path: Request path
            
        Returns:
            True if path is allowed during suspension
        """
        # Exact path matches
        if path in self.ALLOWED_DURING_SUSPENSION:
            return True
        
        # Prefix matches for emergency endpoints
        if path.startswith("/emergency/"):
            return True
        
        # Static files and docs
        if path.startswith(("/static/", "/docs", "/redoc")):
            return True
        
        return False