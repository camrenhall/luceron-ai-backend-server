"""
Workflow management API routes
"""

import json
import logging
import re
from fastapi import APIRouter, HTTPException, Depends
import asyncpg

from models.workflow import WorkflowCreateRequest, WorkflowStatusRequest, ReasoningStep
from database.connection import get_db_pool
from utils.auth import AuthConfig

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("")
async def create_workflow(
    request: WorkflowCreateRequest,
    _: bool = Depends(AuthConfig.get_auth_dependency())
):
    """Create a new workflow"""
    logger.info(f"POST workflow request received: agent_type='{request.agent_type}', case_id='{request.case_id}', status='{request.status.value}'")
    db_pool = get_db_pool()
    
    try:
        async with db_pool.acquire() as conn:
            # Insert workflow and get the generated UUID
            row = await conn.fetchrow("""
                INSERT INTO workflow_states 
                (agent_type, case_id, status, initial_prompt, reasoning_chain)
                VALUES ($1, $2, $3, $4, $5)
                RETURNING workflow_id, created_at
            """,
            request.agent_type, request.case_id, request.status.value,
            request.initial_prompt, json.dumps([]))
            
            logger.info(f"Created workflow with database-generated UUID: '{row['workflow_id']}'")
            
            return {
                "workflow_id": str(row['workflow_id']),
                "agent_type": request.agent_type,
                "case_id": request.case_id,
                "status": request.status.value,
                "initial_prompt": request.initial_prompt,
                "reasoning_chain": [],
                "created_at": row['created_at'].isoformat() if row['created_at'] else None
            }
            
    except asyncpg.UniqueViolationError:
        raise HTTPException(status_code=409, detail="Workflow ID already exists")
    except Exception as e:
        logger.error(f"Failed to create workflow: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.get("/{workflow_id}")
async def get_workflow(
    workflow_id: str,
    _: bool = Depends(AuthConfig.get_auth_dependency())
):
    """Get workflow by ID"""
    logger.info(f"GET workflow request received for workflow_id: '{workflow_id}'")
    db_pool = get_db_pool()
    
    # Validate UUID format
    uuid_pattern = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', re.IGNORECASE)
    if not uuid_pattern.match(workflow_id):
        raise HTTPException(status_code=400, detail=f"Invalid workflow_id format. Expected UUID, got: {workflow_id}")
    
    try:
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM workflow_states WHERE workflow_id = $1", workflow_id
            )
            
            if not row:
                raise HTTPException(status_code=404, detail="Workflow not found")
            
            reasoning_chain = json.loads(row['reasoning_chain']) if row['reasoning_chain'] else []
            
            return {
                "workflow_id": row['workflow_id'],
                "agent_type": row['agent_type'],
                "case_id": row['case_id'],
                "status": row['status'],
                "initial_prompt": row['initial_prompt'],
                "reasoning_chain": reasoning_chain,
                "created_at": row['created_at'].isoformat()
            }
            
    except Exception as e:
        logger.error(f"Failed to get workflow: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.put("/{workflow_id}/status")
async def update_workflow_status(
    workflow_id: str,
    request: WorkflowStatusRequest,
    _: bool = Depends(AuthConfig.get_auth_dependency())
):
    """Update workflow status"""
    db_pool = get_db_pool()
    
    # Validate UUID format
    uuid_pattern = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', re.IGNORECASE)
    if not uuid_pattern.match(workflow_id):
        raise HTTPException(status_code=400, detail=f"Invalid workflow_id format. Expected UUID, got: {workflow_id}")
    
    try:
        async with db_pool.acquire() as conn:
            result = await conn.execute(
                "UPDATE workflow_states SET status = $1 WHERE workflow_id = $2",
                request.status.value, workflow_id
            )
            
            if result == "UPDATE 0":
                raise HTTPException(status_code=404, detail="Workflow not found")
            
            return {"status": "updated", "workflow_id": workflow_id}
            
    except Exception as e:
        logger.error(f"Failed to update workflow status: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.post("/{workflow_id}/reasoning-step")
async def add_reasoning_step(
    workflow_id: str,
    step: ReasoningStep,
    _: bool = Depends(AuthConfig.get_auth_dependency())
):
    """Add a reasoning step to workflow"""
    db_pool = get_db_pool()
    
    # Validate UUID format
    uuid_pattern = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', re.IGNORECASE)
    if not uuid_pattern.match(workflow_id):
        raise HTTPException(status_code=400, detail=f"Invalid workflow_id format. Expected UUID, got: {workflow_id}")
    
    try:
        async with db_pool.acquire() as conn:
            # Get current reasoning chain
            current_chain = await conn.fetchval(
                "SELECT reasoning_chain FROM workflow_states WHERE workflow_id = $1",
                workflow_id
            )
            
            if current_chain is None:
                raise HTTPException(status_code=404, detail="Workflow not found")
            
            # Parse and append new step
            chain = json.loads(current_chain) if current_chain else []
            chain.append(step.model_dump())
            
            # Update database
            await conn.execute(
                "UPDATE workflow_states SET reasoning_chain = $1 WHERE workflow_id = $2",
                json.dumps(chain), workflow_id
            )
            
            return {"status": "step_added", "workflow_id": workflow_id}
            
    except Exception as e:
        logger.error(f"Failed to add reasoning step: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.get("/pending")
async def get_pending_workflows(
    _: bool = Depends(AuthConfig.get_auth_dependency())
):
    """Get workflows that need processing"""
    db_pool = get_db_pool()
    
    try:
        async with db_pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT workflow_id FROM workflow_states 
                WHERE status = 'PENDING'
                ORDER BY created_at ASC
                LIMIT 50
            """)
            
            workflow_ids = [row['workflow_id'] for row in rows]
            return {"workflow_ids": workflow_ids}
            
    except Exception as e:
        logger.error(f"Failed to get pending workflows: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")