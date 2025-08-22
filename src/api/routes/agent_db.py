"""
Agent database gateway API route
Single endpoint for natural language to database operations
"""

import logging
import uuid
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any, Optional

from agent_gateway.models.request import AgentDbRequest
from agent_gateway.models.response import AgentDbResponse, ResponsePagination
from agent_gateway.router import get_router
from agent_gateway.planner import get_planner
from agent_gateway.validator import get_validator
from agent_gateway.executor import get_executor
from agent_gateway.contracts.registry import get_all_contracts
from utils.auth import AuthConfig, AuthContext, AgentAuthContext

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/agent/db", response_model=AgentDbResponse)
async def agent_database_operation(
    request: AgentDbRequest,
    agent_auth: AgentAuthContext = Depends(AuthConfig.get_agent_auth_dependency())
):
    """
    Single endpoint for natural language database operations with agent authentication
    
    Implements the NL-to-CRUD Gateway specification:
    1. Router: NL + hints → resources + intent
    2. Contracts: Load resource contracts for agent role
    3. Planner: NL + contracts → DSL
    4. Validator: Validate DSL against contracts
    5. Executor: Execute DSL via internal CRUD
    
    Authentication: Requires agent JWT token in Authorization: Bearer header
    """
    
    # Generate request ID for logging/tracing
    request_id = str(uuid.uuid4())[:8]
    start_time = datetime.utcnow()
    
    logger.info(f"[{request_id}] Agent DB request started", extra={
        "request_id": request_id,
        "agent_type": agent_auth.agent_type,
        "service_id": agent_auth.service_id,
        "agent_resources": agent_auth.allowed_resources,
        "natural_language": request.natural_language,
        "hints": request.hints.dict() if request.hints else None
    })
    
    try:
        # Step 1: Router - Map NL to resources and determine intent
        router_component = get_router()
        router_result = await router_component.route(
            natural_language=request.natural_language,
            hints=request.hints.dict() if request.hints else None
        )
        
        logger.info(f"[{request_id}] Router result: {router_result}")
        
        # Step 2: Load contracts for selected resources based on agent permissions
        from agent_gateway.contracts.registry import get_agent_contracts
        
        # Get contracts filtered by agent permissions
        all_agent_contracts = get_agent_contracts(agent_auth)
        
        # Filter to only contracts for selected resources that agent can access
        selected_contracts = {
            resource: all_agent_contracts[resource]
            for resource in router_result.resources
            if resource in all_agent_contracts
        }
        
        # Check if agent has permissions for requested resources
        unauthorized_resources = [
            resource for resource in router_result.resources
            if resource not in all_agent_contracts
        ]
        
        if unauthorized_resources:
            logger.warning(f"[{request_id}] Agent {agent_auth.agent_type} denied access to resources: {unauthorized_resources}")
            return AgentDbResponse.error(
                error_type="UNAUTHORIZED_OPERATION",
                message=f"Agent '{agent_auth.agent_type}' not authorized to access resources: {unauthorized_resources}"
            )
        
        if not selected_contracts:
            return AgentDbResponse.error(
                error_type="RESOURCE_NOT_FOUND",
                message=f"No accessible contracts found for resources: {router_result.resources}. Agent has access to: {list(all_agent_contracts.keys())}"
            )
        
        logger.info(f"[{request_id}] Loaded contracts for: {list(selected_contracts.keys())}")
        
        # Step 3: Planner - Convert NL + contracts to DSL
        planner_component = get_planner()
        planner_result = await planner_component.plan(
            natural_language=request.natural_language,
            contracts=selected_contracts,
            intent=router_result.intent,
            resources=router_result.resources
        )
        
        logger.info(f"[{request_id}] DSL generated with fingerprint: {planner_result.fingerprint}")
        
        # Step 4: Validator - Validate DSL against contracts
        validator_component = get_validator()
        validation_error = validator_component.validate(
            dsl=planner_result.dsl,
            contracts=selected_contracts,
            role=agent_auth.agent_type  # Use agent type as role
        )
        
        if validation_error:
            logger.warning(f"[{request_id}] Validation failed: {validation_error}")
            
            # Map validation error to HTTP status
            status_code = 400  # Default
            if validation_error.error_type == "UNAUTHORIZED_OPERATION":
                status_code = 403
            elif validation_error.error_type == "UNAUTHORIZED_FIELD":
                status_code = 403
            elif validation_error.error_type == "RESOURCE_NOT_FOUND":
                status_code = 404
            elif validation_error.error_type == "AMBIGUOUS_INTENT":
                status_code = 422
            elif validation_error.error_type == "CONFLICT":
                status_code = 409
            
            raise HTTPException(
                status_code=status_code,
                detail=AgentDbResponse.error(
                    error_type=validation_error.error_type,
                    message=validation_error.message
                ).dict()
            )
        
        logger.info(f"[{request_id}] DSL validation successful")
        
        # Step 5: Executor - Execute DSL via internal CRUD
        executor_component = get_executor()
        executor_result = await executor_component.execute(
            dsl=planner_result.dsl,
            contracts=selected_contracts,
            role=agent_auth.agent_type  # Use agent type as role
        )
        
        # Build response pagination if present
        page = None
        if executor_result.page_info:
            page = ResponsePagination(
                limit=executor_result.page_info["limit"],
                offset=executor_result.page_info["offset"]
            )
        
        # Build successful response
        response = AgentDbResponse.success(
            operation=executor_result.operation,
            resource=executor_result.resource,
            data=executor_result.data,
            count=executor_result.count,
            page=page
        )
        
        # Log successful completion
        end_time = datetime.utcnow()
        duration_ms = (end_time - start_time).total_seconds() * 1000
        
        logger.info(f"[{request_id}] Request completed successfully", extra={
            "request_id": request_id,
            "agent_type": agent_auth.agent_type,
            "service_id": agent_auth.service_id,
            "operation": executor_result.operation,
            "resource": executor_result.resource,
            "rows_returned": executor_result.count,
            "duration_ms": duration_ms,
            "dsl_fingerprint": planner_result.fingerprint
        })
        
        return response
        
    except HTTPException:
        # Re-raise HTTP exceptions (validation errors)
        raise
    except ValueError as e:
        # Router/Planner validation errors
        if "AMBIGUOUS_INTENT" in str(e):
            raise HTTPException(
                status_code=422,
                detail=AgentDbResponse.error(
                    error_type="AMBIGUOUS_INTENT",
                    message=str(e).replace("AMBIGUOUS_INTENT: ", ""),
                    clarification=str(e).replace("AMBIGUOUS_INTENT: ", "")
                ).dict()
            )
        else:
            raise HTTPException(
                status_code=400,
                detail=AgentDbResponse.error(
                    error_type="INVALID_QUERY",
                    message=str(e)
                ).dict()
            )
    except RuntimeError as e:
        # Handle executor errors (including CONFLICT)
        error_msg = str(e)
        if "CONFLICT:" in error_msg:
            raise HTTPException(
                status_code=409,
                detail=AgentDbResponse.error(
                    error_type="CONFLICT",
                    message=error_msg.replace("CONFLICT: ", "")
                ).dict()
            )
        else:
            raise HTTPException(
                status_code=500,
                detail=AgentDbResponse.error(
                    error_type="INVALID_QUERY",
                    message=error_msg
                ).dict()
            )
    except Exception as e:
        # Log unexpected errors
        end_time = datetime.utcnow()
        duration_ms = (end_time - start_time).total_seconds() * 1000
        
        logger.error(f"[{request_id}] Request failed with error", extra={
            "request_id": request_id,
            "agent_type": agent_auth.agent_type,
            "service_id": agent_auth.service_id,
            "error": str(e),
            "duration_ms": duration_ms
        })
        
        raise HTTPException(
            status_code=500,
            detail=AgentDbResponse.error(
                error_type="INVALID_QUERY",
                message="Internal server error during request processing"
            ).dict()
        )