"""
Centralized Error Handling and Logging System
Provides enterprise-grade error handling with structured logging, security, and observability.
"""

import json
import logging
import traceback
import uuid
from datetime import datetime
from typing import Any, Dict, Optional, Union
from contextvars import ContextVar

from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.middleware.base import BaseHTTPMiddleware

# Context variables for request tracing
request_id_var: ContextVar[str] = ContextVar('request_id', default='')
endpoint_context_var: ContextVar[str] = ContextVar('endpoint_context', default='')

logger = logging.getLogger(__name__)

class ErrorHandlingConfig:
    """Centralized configuration for error handling behavior"""
    
    # Security settings
    SANITIZE_SENSITIVE_FIELDS = True
    SENSITIVE_FIELD_PATTERNS = [
        'password', 'token', 'key', 'secret', 'authorization', 
        'auth', 'bearer', 'credential', 'api_key'
    ]
    
    # Logging settings
    LOG_REQUEST_BODIES = True
    LOG_RESPONSE_BODIES = False  # Disable by default for performance
    LOG_HEADERS = True
    MAX_BODY_LOG_SIZE = 5000  # Truncate large bodies
    
    # Error response settings
    INCLUDE_TRACE_ID = True
    INCLUDE_TIMESTAMP = True
    DETAILED_VALIDATION_ERRORS = True
    
    @classmethod
    def is_sensitive_field(cls, field_name: str) -> bool:
        """Check if a field contains sensitive data"""
        field_lower = field_name.lower()
        return any(pattern in field_lower for pattern in cls.SENSITIVE_FIELD_PATTERNS)
    
    @classmethod
    def sanitize_data(cls, data: Union[Dict, str, Any]) -> Any:
        """Recursively sanitize sensitive data from logs"""
        if not cls.SANITIZE_SENSITIVE_FIELDS:
            return data
            
        if isinstance(data, dict):
            return {
                key: "***REDACTED***" if cls.is_sensitive_field(key) else cls.sanitize_data(value)
                for key, value in data.items()
            }
        elif isinstance(data, list):
            return [cls.sanitize_data(item) for item in data]
        elif isinstance(data, str) and len(data) > cls.MAX_BODY_LOG_SIZE:
            return data[:cls.MAX_BODY_LOG_SIZE] + "...[TRUNCATED]"
        else:
            return data

class StructuredLogger:
    """Structured logging with consistent format and context"""
    
    @staticmethod
    def log_error(
        error_type: str,
        message: str,
        request: Optional[Request] = None,
        exception: Optional[Exception] = None,
        extra_context: Optional[Dict] = None,
        include_traceback: bool = True
    ) -> str:
        """Log structured error with full context"""
        
        # Generate trace ID for this error
        trace_id = str(uuid.uuid4())[:8]
        request_id_var.set(trace_id)
        
        # Build structured log entry
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "trace_id": trace_id,
            "error_type": error_type,
            "message": message,
            "level": "ERROR"
        }
        
        # Add request context if available
        if request:
            headers = dict(request.headers)
            log_entry.update({
                "request": {
                    "method": request.method,
                    "url": str(request.url),
                    "path": request.url.path,
                    "query_params": dict(request.query_params),
                    "headers": ErrorHandlingConfig.sanitize_data(headers) if ErrorHandlingConfig.LOG_HEADERS else {},
                    "client_ip": request.client.host if request.client else None,
                    "user_agent": headers.get("user-agent", "unknown")
                }
            })
            
            # Add request body if configured and available
            if ErrorHandlingConfig.LOG_REQUEST_BODIES:
                try:
                    # This won't work for already consumed bodies, but we'll handle that in middleware
                    pass
                except Exception:
                    log_entry["request"]["body"] = "BODY_ALREADY_CONSUMED"
        
        # Add exception details
        if exception:
            log_entry["exception"] = {
                "type": type(exception).__name__,
                "details": str(exception),
                "module": getattr(exception, '__module__', 'unknown')
            }
            
            if include_traceback:
                log_entry["exception"]["traceback"] = traceback.format_exc()
        
        # Add extra context
        if extra_context:
            log_entry["context"] = ErrorHandlingConfig.sanitize_data(extra_context)
        
        # Add endpoint context if available
        endpoint_context = endpoint_context_var.get('')
        if endpoint_context:
            log_entry["endpoint_context"] = endpoint_context
        
        # Log the structured entry
        logger.error(json.dumps(log_entry, indent=2))
        
        return trace_id

class RequestContextMiddleware(BaseHTTPMiddleware):
    """Middleware to capture request context and add request IDs"""
    
    async def dispatch(self, request: Request, call_next):
        # Generate unique request ID
        trace_id = str(uuid.uuid4())[:8]
        request_id_var.set(trace_id)
        
        # Store request body for potential error logging
        body = None
        if ErrorHandlingConfig.LOG_REQUEST_BODIES:
            try:
                body = await request.body()
                # Re-create request with body for downstream processing
                request._body = body
            except Exception as e:
                StructuredLogger.log_error(
                    "middleware_error",
                    "Failed to capture request body",
                    request=request,
                    exception=e,
                    include_traceback=False
                )
        
        # Add request body to state for error handlers
        request.state.captured_body = body
        request.state.trace_id = trace_id
        
        # Process request
        try:
            response = await call_next(request)
            # Add trace ID to response headers for client-side debugging
            response.headers["X-Trace-ID"] = trace_id
            return response
        except Exception as e:
            # Log unexpected exceptions
            StructuredLogger.log_error(
                "unhandled_exception",
                f"Unhandled exception in request processing: {str(e)}",
                request=request,
                exception=e,
                extra_context={"body": ErrorHandlingConfig.sanitize_data(body.decode('utf-8')) if body else None}
            )
            raise

# Global Exception Handlers
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Handle HTTP exceptions with logging"""
    
    # Log HTTP exceptions (but not 4xx client errors unless configured)
    should_log = exc.status_code >= 500 or (exc.status_code >= 400 and ErrorHandlingConfig.LOG_REQUEST_BODIES)
    
    trace_id = None
    if should_log:
        body_str = None
        if hasattr(request.state, 'captured_body') and request.state.captured_body:
            try:
                body_str = request.state.captured_body.decode('utf-8')
            except Exception:
                body_str = "DECODE_ERROR"
        
        trace_id = StructuredLogger.log_error(
            f"http_{exc.status_code}",
            f"HTTP {exc.status_code}: {exc.detail}",
            request=request,
            exception=exc,
            extra_context={
                "status_code": exc.status_code,
                "request_body": ErrorHandlingConfig.sanitize_data(body_str) if body_str else None
            },
            include_traceback=exc.status_code >= 500
        )
    
    # Build response
    response_content = {
        "error": f"HTTP {exc.status_code}",
        "message": exc.detail,
    }
    
    if ErrorHandlingConfig.INCLUDE_TRACE_ID and trace_id:
        response_content["trace_id"] = trace_id
    
    if ErrorHandlingConfig.INCLUDE_TIMESTAMP:
        response_content["timestamp"] = datetime.utcnow().isoformat()
    
    return JSONResponse(
        status_code=exc.status_code,
        content=response_content
    )

async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Handle FastAPI validation errors (HTTP 422)"""
    
    body_str = None
    if hasattr(request.state, 'captured_body') and request.state.captured_body:
        try:
            body_str = request.state.captured_body.decode('utf-8')
        except Exception:
            body_str = "DECODE_ERROR"
    
    # Extract detailed validation error information
    validation_details = []
    for error in exc.errors():
        validation_details.append({
            "field": " -> ".join(str(loc) for loc in error.get("loc", [])),
            "message": error.get("msg", "Unknown validation error"),
            "type": error.get("type", "unknown"),
            "input": error.get("input", "not_provided")
        })
    
    trace_id = StructuredLogger.log_error(
        "validation_error_422",
        f"Request validation failed: {len(exc.errors())} validation errors",
        request=request,
        exception=exc,
        extra_context={
            "validation_errors": validation_details,
            "error_count": len(exc.errors()),
            "request_body": ErrorHandlingConfig.sanitize_data(body_str) if body_str else None,
            "raw_errors": exc.errors()
        },
        include_traceback=False
    )
    
    # Build detailed response for debugging
    response_content = {
        "error": "Validation Error",
        "message": "Request validation failed",
        "detail": validation_details,
        "error_count": len(exc.errors())
    }
    
    if ErrorHandlingConfig.INCLUDE_TRACE_ID:
        response_content["trace_id"] = trace_id
    
    if ErrorHandlingConfig.INCLUDE_TIMESTAMP:
        response_content["timestamp"] = datetime.utcnow().isoformat()
    
    return JSONResponse(
        status_code=422,
        content=response_content
    )

async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle all other exceptions"""
    
    body_str = None
    if hasattr(request.state, 'captured_body') and request.state.captured_body:
        try:
            body_str = request.state.captured_body.decode('utf-8')
        except Exception:
            body_str = "DECODE_ERROR"
    
    trace_id = StructuredLogger.log_error(
        "internal_server_error",
        f"Unhandled exception: {str(exc)}",
        request=request,
        exception=exc,
        extra_context={
            "request_body": ErrorHandlingConfig.sanitize_data(body_str) if body_str else None
        },
        include_traceback=True
    )
    
    # Build safe response (don't expose internal details)
    response_content = {
        "error": "Internal Server Error",
        "message": "An unexpected error occurred",
    }
    
    if ErrorHandlingConfig.INCLUDE_TRACE_ID:
        response_content["trace_id"] = trace_id
    
    if ErrorHandlingConfig.INCLUDE_TIMESTAMP:
        response_content["timestamp"] = datetime.utcnow().isoformat()
    
    return JSONResponse(
        status_code=500,
        content=response_content
    )

def setup_error_handling(app):
    """Setup comprehensive error handling for FastAPI app"""
    
    # Add middleware for request context
    app.add_middleware(RequestContextMiddleware)
    
    # Add exception handlers (order matters - most specific first)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(Exception, general_exception_handler)
    
    logger.info("Centralized error handling system initialized with validation error handling")

# Utility for endpoint-specific logging
def set_endpoint_context(context: str):
    """Set context for current endpoint (call at start of endpoint functions)"""
    endpoint_context_var.set(context)

def log_business_error(error_type: str, message: str, context: Dict = None):
    """Log business logic errors (not exceptions)"""
    StructuredLogger.log_error(
        f"business_error_{error_type}",
        message,
        extra_context=context,
        include_traceback=False
    )