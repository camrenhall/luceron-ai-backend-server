"""
Response models for agent database operations
"""

from typing import Any, Dict, List, Optional, Literal
from pydantic import BaseModel

class ResponseError(BaseModel):
    """Error details in unified response"""
    type: Literal[
        "AMBIGUOUS_INTENT",        # 422 - Low confidence writes
        "UNAUTHORIZED_OPERATION",  # 403 - Operation not allowed
        "UNAUTHORIZED_FIELD",      # 403 - Field not accessible  
        "INVALID_QUERY",          # 400 - Constraint violations
        "RESOURCE_NOT_FOUND",     # 404 - Resource doesn't exist
        "CONFLICT"                # 409 - Unique constraint violation
    ]
    message: str
    clarification: Optional[str] = None  # For 422 only
    details: Optional[Dict[str, Any]] = None

class ResponsePagination(BaseModel):
    """Pagination info for read operations"""
    limit: int
    offset: int

class AgentDbResponse(BaseModel):
    """Unified response envelope for all agent database operations"""
    ok: bool
    operation: Optional[Literal["READ", "INSERT", "UPDATE"]] = None
    resource: Optional[str] = None
    data: List[Dict[str, Any]] = []  # Post-image rows (READ or WRITE)
    count: int = 0  # READ: rows returned; WRITE: rows affected
    page: Optional[ResponsePagination] = None  # Present only on read when used
    error: Optional[ResponseError] = None

    @classmethod
    def success(
        cls,
        operation: str,
        resource: str,
        data: List[Dict[str, Any]],
        count: int = None,
        page: Optional[ResponsePagination] = None
    ) -> "AgentDbResponse":
        """Create successful response"""
        return cls(
            ok=True,
            operation=operation,
            resource=resource,
            data=data,
            count=count if count is not None else len(data),
            page=page
        )

    @classmethod
    def error(
        cls,
        error_type: str,
        message: str,
        clarification: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> "AgentDbResponse":
        """Create error response"""
        return cls(
            ok=False,
            error=ResponseError(
                type=error_type,
                message=message,
                clarification=clarification,
                details=details
            )
        )