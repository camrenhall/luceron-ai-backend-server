"""
Workflow management API routes
"""

import json
import logging
import re
from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.exceptions import RequestValidationError
import asyncpg

from models.workflow import WorkflowCreateRequest, WorkflowStatusRequest, WorkflowUpdateRequest, ReasoningStep
from database.connection import get_db_pool
from utils.auth import AuthConfig
from utils.error_handling import StructuredLogger

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
                "final_response": None,
                "created_at": row['created_at'].isoformat() if row['created_at'] else None
            }
            
    except asyncpg.UniqueViolationError:
        raise HTTPException(status_code=409, detail="Workflow ID already exists")
    except Exception as e:
        logger.error(f"Failed to create workflow: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.get("/{workflow_id}")
async def get_workflow(
    request: Request,
    workflow_id: str,
    _: bool = Depends(AuthConfig.get_auth_dependency())
):
    """Get workflow by ID"""
    logger.info(f"GET workflow request received for workflow_id: '{workflow_id}'")
    logger.info(f"Workflow ID type: {type(workflow_id)}, length: {len(workflow_id)}")
    logger.info(f"Raw workflow_id bytes: {workflow_id.encode('utf-8')}")
    logger.info(f"Request headers: {dict(request.headers)}")
    logger.info(f"Request URL: {request.url}")
    logger.info(f"Request method: {request.method}")
    logger.info(f"Request path params: {request.path_params}")
    logger.info(f"Request query params: {dict(request.query_params)}")
    
    try:
        db_pool = get_db_pool()
    except Exception as e:
        logger.error(f"Failed to get database pool: {e}")
        StructuredLogger.log_error(
            "database_connection_error",
            f"Cannot connect to database: {str(e)}",
            request=request,
            exception=e,
            extra_context={"workflow_id": workflow_id}
        )
        raise HTTPException(status_code=500, detail="Database connection failed")
    
    # Validate UUID format
    uuid_pattern = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', re.IGNORECASE)
    logger.info(f"Validating UUID format for: '{workflow_id}'")
    if not uuid_pattern.match(workflow_id):
        logger.error(f"UUID validation failed for workflow_id: '{workflow_id}' - returning 400")
        StructuredLogger.log_error(
            "invalid_uuid_format",
            f"Invalid workflow_id format. Expected UUID, got: {workflow_id}",
            request=request,
            extra_context={"workflow_id": workflow_id, "uuid_pattern": uuid_pattern.pattern}
        )
        raise HTTPException(status_code=400, detail=f"Invalid workflow_id format. Expected UUID, got: {workflow_id}")
    
    logger.info(f"UUID validation passed for workflow_id: '{workflow_id}'")
    
    try:
        logger.info(f"Attempting to acquire database connection for workflow_id: '{workflow_id}'")
        async with db_pool.acquire() as conn:
            logger.info(f"Successfully acquired database connection")
            logger.info(f"Executing query: SELECT * FROM workflow_states WHERE workflow_id = '{workflow_id}'")
            
            row = await conn.fetchrow(
                "SELECT * FROM workflow_states WHERE workflow_id = $1", workflow_id
            )
            
            logger.info(f"Database query completed. Row found: {row is not None}")
            if row:
                logger.info(f"Found workflow: {dict(row)}")
            
            if not row:
                logger.warning(f"Workflow not found for workflow_id: '{workflow_id}' - returning 404")
                StructuredLogger.log_error(
                    "workflow_not_found",
                    f"Workflow not found: {workflow_id}",
                    request=request,
                    extra_context={"workflow_id": workflow_id}
                )
                raise HTTPException(status_code=404, detail="Workflow not found")
            
            logger.info(f"Processing workflow data for response")
            reasoning_chain = json.loads(row['reasoning_chain']) if row['reasoning_chain'] else []
            logger.info(f"Reasoning chain length: {len(reasoning_chain)}")
            
            response_data = {
                "workflow_id": row['workflow_id'],
                "agent_type": row['agent_type'],
                "case_id": row['case_id'],
                "status": row['status'],
                "initial_prompt": row['initial_prompt'],
                "reasoning_chain": reasoning_chain,
                "final_response": row['final_response'],
                "created_at": row['created_at'].isoformat()
            }
            logger.info(f"Successfully prepared response for workflow_id: '{workflow_id}'")
            return response_data
            
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        logger.error(f"Failed to get workflow '{workflow_id}': {type(e).__name__}: {e}")
        StructuredLogger.log_error(
            "database_query_error",
            f"Database error while fetching workflow: {str(e)}",
            request=request,
            exception=e,
            extra_context={"workflow_id": workflow_id}
        )
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

@router.put("/{workflow_id}")
async def update_workflow(
    workflow_id: str,
    request: WorkflowUpdateRequest,
    _: bool = Depends(AuthConfig.get_auth_dependency())
):
    """Update workflow fields"""
    db_pool = get_db_pool()
    
    # Validate UUID format
    uuid_pattern = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', re.IGNORECASE)
    if not uuid_pattern.match(workflow_id):
        raise HTTPException(status_code=400, detail=f"Invalid workflow_id format. Expected UUID, got: {workflow_id}")
    
    try:
        async with db_pool.acquire() as conn:
            # Build dynamic update query based on provided fields
            update_fields = []
            update_values = []
            param_count = 1
            
            if request.status is not None:
                update_fields.append(f"status = ${param_count}")
                update_values.append(request.status.value)
                param_count += 1
                
            if request.reasoning_chain is not None:
                update_fields.append(f"reasoning_chain = ${param_count}")
                update_values.append(json.dumps(request.reasoning_chain))
                param_count += 1
                
            if request.final_response is not None:
                update_fields.append(f"final_response = ${param_count}")
                update_values.append(request.final_response)
                param_count += 1
            
            if not update_fields:
                raise HTTPException(status_code=400, detail="No fields provided for update")
            
            # Add workflow_id as the final parameter
            update_values.append(workflow_id)
            query = f"UPDATE workflow_states SET {', '.join(update_fields)} WHERE workflow_id = ${param_count}"
            
            result = await conn.execute(query, *update_values)
            
            if result == "UPDATE 0":
                raise HTTPException(status_code=404, detail="Workflow not found")
            
            return {"status": "updated", "workflow_id": workflow_id}
            
    except Exception as e:
        logger.error(f"Failed to update workflow: {e}")
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