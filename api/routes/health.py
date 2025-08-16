"""
Health check API route
"""

from datetime import datetime
from fastapi import APIRouter, HTTPException
from database.connection import get_db_pool

router = APIRouter()

@router.get("/")
async def health_check():
    """Health check"""
    db_pool = get_db_pool()
    
    try:
        async with db_pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        
        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "database": "connected",
            "email": "resend_configured"
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Health check failed: {str(e)}")