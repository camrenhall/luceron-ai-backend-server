"""
Health check API route
"""

from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends
from database.connection import get_db_pool
from utils.auth import AuthConfig
from utils.suspension import suspension_manager

router = APIRouter()

@router.get("/")
async def health_check(
    _: bool = Depends(AuthConfig.get_auth_dependency())
):
    """
    Health check - Always reports healthy even during suspension
    
    This ensures Cloud Deploy doesn't restart the container during
    emergency suspension. The suspension middleware handles blocking
    actual requests.
    """
    db_pool = get_db_pool()
    
    try:
        # Check database connectivity (even during suspension)
        async with db_pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        
        # Always report healthy, but include suspension status for monitoring
        response = {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "database": "connected",
            "email": "resend_configured"
        }
        
        # Add suspension status for monitoring (but don't affect health)
        if suspension_manager.is_suspended:
            suspension_info = suspension_manager.get_suspension_info()
            response["suspension"] = {
                "is_suspended": True,
                "suspended_at": suspension_info["suspended_at"],
                "reason": suspension_info["reason"],
                "note": "Server is healthy but operations are suspended"
            }
        
        return response
        
    except Exception as e:
        # Only report unhealthy for actual infrastructure issues
        raise HTTPException(status_code=503, detail=f"Health check failed: {str(e)}")