"""
Emergency control endpoints - Kill-switch and resume functionality
"""

import logging
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional

from utils.auth import authenticate_agent_jwt, AgentContext
from utils.suspension import suspension_manager

router = APIRouter()
logger = logging.getLogger(__name__)

class SuspensionRequest(BaseModel):
    reason: Optional[str] = "Emergency kill-switch activated"

class SuspensionResponse(BaseModel):
    success: bool
    message: str
    suspension_info: dict

@router.post("/emergency/suspend", response_model=SuspensionResponse, tags=["emergency"])
async def suspend_server(
    request: SuspensionRequest,
    agent_context: AgentContext = Depends(authenticate_agent_jwt)
):
    """
    🔴 EMERGENCY KILL-SWITCH - Suspend all server operations
    
    This endpoint immediately suspends all server operations while keeping
    the server healthy for Cloud Deploy monitoring. Only camren_master can
    access this endpoint.
    
    **WARNING: This will block all API requests except health checks**
    """
    try:
        if suspension_manager.is_suspended:
            return SuspensionResponse(
                success=False,
                message="Server is already suspended",
                suspension_info=suspension_manager.get_suspension_info()
            )
        
        # Suspend the server
        suspension_manager.suspend(
            suspended_by=agent_context.service_id,
            reason=request.reason
        )
        
        logger.critical(f"🔴 EMERGENCY SUSPENSION activated by {agent_context.service_id}: {request.reason}")
        
        return SuspensionResponse(
            success=True,
            message="Server suspended successfully",
            suspension_info=suspension_manager.get_suspension_info()
        )
        
    except Exception as e:
        logger.error(f"Error during suspension: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to suspend server: {str(e)}")

@router.post("/emergency/resume", response_model=SuspensionResponse, tags=["emergency"])
async def resume_server(
    agent_context: AgentContext = Depends(authenticate_agent_jwt)
):
    """
    🟢 RESUME SERVER - Resume all server operations
    
    This endpoint resumes normal server operations after suspension.
    Only camren_master can access this endpoint.
    """
    try:
        was_suspended = suspension_manager.is_suspended
        
        # Resume the server
        suspension_manager.resume(resumed_by=agent_context.service_id)
        
        logger.warning(f"🟢 SERVER RESUMED by {agent_context.service_id}")
        
        return SuspensionResponse(
            success=True,
            message="Server resumed successfully" if was_suspended else "Server was not suspended",
            suspension_info=suspension_manager.get_suspension_info()
        )
        
    except Exception as e:
        logger.error(f"Error during resume: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to resume server: {str(e)}")

@router.get("/emergency/status", response_model=dict, tags=["emergency"])
async def get_suspension_status(
    agent_context: AgentContext = Depends(authenticate_agent_jwt)
):
    """
    Get current suspension status
    
    Only camren_master can access this endpoint.
    """
    return {
        "suspension_info": suspension_manager.get_suspension_info(),
        "requested_by": agent_context.service_id
    }