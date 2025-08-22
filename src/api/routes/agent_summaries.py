"""
Agent summaries API routes - Unified Service Layer Architecture
All database operations go through consistent service layer patterns.
"""

import logging
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, Query

from models.agent import (
    AgentSummaryCreate, AgentSummaryUpdate, AgentSummaryResponse
)
from services.agent_services import get_agent_services
from utils.auth import AuthConfig

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("", response_model=AgentSummaryResponse)
async def create_summary(
    request: AgentSummaryCreate,
    _: bool = Depends(AuthConfig.get_auth_dependency())
):
    """Create a new conversation summary"""
    agent_services = get_agent_services()
    
    try:
        result = await agent_services.create_summary(
            conversation_id=request.conversation_id,
            summary_content=request.summary_content,
            messages_summarized=request.messages_summarized,
            last_message_id=request.last_message_id
        )
        
        if not result.success:
            if result.error_type == "RESOURCE_NOT_FOUND":
                raise HTTPException(status_code=404, detail=result.error)
            elif result.error_type == "INVALID_QUERY":
                raise HTTPException(status_code=400, detail=result.error)
            else:
                raise HTTPException(status_code=500, detail=result.error)
        
        summary_data = result.data[0]
        
        return AgentSummaryResponse(
            summary_id=summary_data['summary_id'],
            conversation_id=summary_data['conversation_id'],
            last_message_id=summary_data.get('last_message_id'),
            summary_content=summary_data['summary_content'],
            messages_summarized=summary_data['messages_summarized'],
            created_at=summary_data['created_at'],
            updated_at=summary_data.get('updated_at')
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create summary: {e}")
        raise HTTPException(status_code=500, detail=f"Service error: {str(e)}")

@router.get("/{summary_id}", response_model=AgentSummaryResponse)
async def get_summary(
    summary_id: str,
    _: bool = Depends(AuthConfig.get_auth_dependency())
):
    """Get summary by ID"""
    agent_services = get_agent_services()
    
    try:
        result = await agent_services.get_summary_by_id(summary_id=summary_id)
        
        if not result.success:
            if result.error_type == "RESOURCE_NOT_FOUND":
                raise HTTPException(status_code=404, detail=result.error)
            elif result.error_type == "INVALID_QUERY":
                raise HTTPException(status_code=400, detail=result.error)
            else:
                raise HTTPException(status_code=500, detail=result.error)
        
        summary_data = result.data[0]
        
        return AgentSummaryResponse(
            summary_id=summary_data['summary_id'],
            conversation_id=summary_data['conversation_id'],
            last_message_id=summary_data.get('last_message_id'),
            summary_content=summary_data['summary_content'],
            messages_summarized=summary_data['messages_summarized'],
            created_at=summary_data['created_at'],
            updated_at=summary_data.get('updated_at')
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get summary: {e}")
        raise HTTPException(status_code=500, detail=f"Service error: {str(e)}")

@router.put("/{summary_id}", response_model=AgentSummaryResponse)
async def update_summary(
    summary_id: str,
    request: AgentSummaryUpdate,
    _: bool = Depends(AuthConfig.get_auth_dependency())
):
    """Update summary content or metadata"""
    agent_services = get_agent_services()
    
    try:
        # Check if any fields are provided for update
        if request.summary_content is None and request.messages_summarized is None:
            raise HTTPException(status_code=400, detail="No fields provided for update")
        
        result = await agent_services.update_summary(
            summary_id=summary_id,
            summary_content=request.summary_content,
            messages_summarized=request.messages_summarized
        )
        
        if not result.success:
            if result.error_type == "RESOURCE_NOT_FOUND":
                raise HTTPException(status_code=404, detail=result.error)
            elif result.error_type == "INVALID_QUERY":
                raise HTTPException(status_code=400, detail=result.error)
            else:
                raise HTTPException(status_code=500, detail=result.error)
        
        summary_data = result.data[0]
        
        return AgentSummaryResponse(
            summary_id=summary_data['summary_id'],
            conversation_id=summary_data['conversation_id'],
            last_message_id=summary_data.get('last_message_id'),
            summary_content=summary_data['summary_content'],
            messages_summarized=summary_data['messages_summarized'],
            created_at=summary_data['created_at'],
            updated_at=summary_data.get('updated_at')
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update summary: {e}")
        raise HTTPException(status_code=500, detail=f"Service error: {str(e)}")

@router.delete("/{summary_id}")
async def delete_summary(
    summary_id: str,
    _: bool = Depends(AuthConfig.get_auth_dependency())
):
    """Delete summary"""
    agent_services = get_agent_services()
    
    try:
        result = await agent_services.delete_summary(summary_id=summary_id)
        
        if not result.success:
            if result.error_type == "RESOURCE_NOT_FOUND":
                raise HTTPException(status_code=404, detail=result.error)
            elif result.error_type == "INVALID_QUERY":
                raise HTTPException(status_code=400, detail=result.error)
            else:
                raise HTTPException(status_code=500, detail=result.error)
        
        return {"message": "Summary deleted successfully", "summary_id": summary_id}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete summary: {e}")
        raise HTTPException(status_code=500, detail=f"Service error: {str(e)}")

@router.get("", response_model=List[AgentSummaryResponse])
async def list_summaries(
    conversation_id: Optional[str] = Query(None, description="Filter by conversation ID"),
    limit: int = Query(50, ge=1, le=500, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    _: bool = Depends(AuthConfig.get_auth_dependency())
):
    """List summaries with optional filters"""
    agent_services = get_agent_services()
    
    try:
        if conversation_id:
            result = await agent_services.get_summaries_by_conversation(
                conversation_id=conversation_id,
                limit=limit,
                offset=offset
            )
        else:
            result = await agent_services.get_recent_summaries(
                limit=limit,
                offset=offset
            )
        
        if not result.success:
            if result.error_type == "RESOURCE_NOT_FOUND":
                raise HTTPException(status_code=404, detail=result.error)
            elif result.error_type == "INVALID_QUERY":
                raise HTTPException(status_code=400, detail=result.error)
            else:
                raise HTTPException(status_code=500, detail=result.error)
        
        return [
            AgentSummaryResponse(
                summary_id=row['summary_id'],
                conversation_id=row['conversation_id'],
                last_message_id=row.get('last_message_id'),
                summary_content=row['summary_content'],
                messages_summarized=row['messages_summarized'],
                created_at=row['created_at'],
                updated_at=row.get('updated_at')
            ) for row in result.data
        ]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list summaries: {e}")
        raise HTTPException(status_code=500, detail=f"Service error: {str(e)}")

@router.get("/conversation/{conversation_id}/latest", response_model=AgentSummaryResponse)
async def get_latest_summary(
    conversation_id: str,
    _: bool = Depends(AuthConfig.get_auth_dependency())
):
    """Get the most recent summary for a conversation"""
    agent_services = get_agent_services()
    
    try:
        result = await agent_services.get_summaries_by_conversation(
            conversation_id=conversation_id,
            limit=1,
            offset=0
        )
        
        if not result.success:
            if result.error_type == "RESOURCE_NOT_FOUND":
                raise HTTPException(status_code=404, detail=result.error)
            elif result.error_type == "INVALID_QUERY":
                raise HTTPException(status_code=400, detail=result.error)
            else:
                raise HTTPException(status_code=500, detail=result.error)
        
        if not result.data:
            raise HTTPException(status_code=404, detail="No summaries found for this conversation")
        
        summary_data = result.data[0]
        
        return AgentSummaryResponse(
            summary_id=summary_data['summary_id'],
            conversation_id=summary_data['conversation_id'],
            last_message_id=summary_data.get('last_message_id'),
            summary_content=summary_data['summary_content'],
            messages_summarized=summary_data['messages_summarized'],
            created_at=summary_data['created_at'],
            updated_at=summary_data.get('updated_at')
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get latest summary: {e}")
        raise HTTPException(status_code=500, detail=f"Service error: {str(e)}")

@router.post("/conversation/{conversation_id}/auto-summary", response_model=AgentSummaryResponse)
async def create_auto_summary(
    conversation_id: str,
    messages_to_summarize: int = Query(10, ge=1, le=100, description="Number of recent messages to summarize"),
    _: bool = Depends(AuthConfig.get_auth_dependency())
):
    """Create a summary automatically based on recent messages in the conversation"""
    agent_services = get_agent_services()
    
    try:
        # For auto-summary, we'll create a placeholder summary content.
        # In production, this would involve getting recent messages and using an LLM
        summary_content = f"Auto-generated summary of {messages_to_summarize} recent messages. "
        summary_content += "This is an auto-generated summary placeholder."
        
        result = await agent_services.create_summary(
            conversation_id=conversation_id,
            summary_content=summary_content,
            messages_summarized=messages_to_summarize,
            last_message_id=None  # For auto-summary, we'll let the service determine this
        )
        
        if not result.success:
            if result.error_type == "RESOURCE_NOT_FOUND":
                raise HTTPException(status_code=404, detail=result.error)
            elif result.error_type == "INVALID_QUERY":
                raise HTTPException(status_code=400, detail=result.error)
            else:
                raise HTTPException(status_code=500, detail=result.error)
        
        summary_data = result.data[0]
        
        return AgentSummaryResponse(
            summary_id=summary_data['summary_id'],
            conversation_id=summary_data['conversation_id'],
            last_message_id=summary_data.get('last_message_id'),
            summary_content=summary_data['summary_content'],
            messages_summarized=summary_data['messages_summarized'],
            created_at=summary_data['created_at'],
            updated_at=summary_data.get('updated_at')
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create auto-summary: {e}")
        raise HTTPException(status_code=500, detail=f"Service error: {str(e)}")