"""
Document Analysis Aggregated API routes
"""

import json
import logging
import time
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, Query
import asyncpg

from models.document import (
    DocumentAnalysisAggregatedData,
    DocumentAnalysisAggregatedCreateRequest,
    DocumentAnalysisAggregatedCreateResponse,
    DocumentAnalysisAggregatedUpdateRequest,
    DocumentAnalysisAggregatedUpdateResponse
)
from database.connection import get_db_pool
from utils.auth import AuthConfig
from utils.error_handling import set_endpoint_context

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("", response_model=DocumentAnalysisAggregatedCreateResponse)
async def create_aggregated_analysis(
    request: DocumentAnalysisAggregatedCreateRequest,
    _: bool = Depends(AuthConfig.get_auth_dependency())
):
    """
    Create a new document analysis aggregated record.
    
    This endpoint stores aggregated analysis results for a batch of documents
    associated with a specific case.
    """
    set_endpoint_context("aggregated_analysis_creation")
    start_time = time.time()
    db_pool = get_db_pool()
    
    logger.info(f"Creating aggregated analysis for case {request.case_id} with {request.total_documents_analyzed} documents")
    
    try:
        async with db_pool.acquire() as conn:
            async with conn.transaction():
                # Validate case exists
                case_exists = await conn.fetchval(
                    "SELECT EXISTS(SELECT 1 FROM cases WHERE case_id = $1)", 
                    request.case_id
                )
                if not case_exists:
                    raise HTTPException(
                        status_code=404, 
                        detail=f"Case {request.case_id} not found"
                    )
                
                # Insert aggregated analysis record and get generated UUID
                # Convert dict to JSON string for JSONB column
                aggregated_analysis_id = await conn.fetchval("""
                    INSERT INTO document_analysis_aggregated (
                        case_id, analysis_batch_contents, model_used, 
                        total_documents_analyzed, total_tokens_used
                    ) VALUES ($1, $2::jsonb, $3, $4, $5)
                    RETURNING aggregated_analysis_id
                """, 
                request.case_id, json.dumps(request.analysis_batch_contents), request.model_used,
                request.total_documents_analyzed, request.total_tokens_used)
                
                # Get the created timestamp
                created_at = await conn.fetchval(
                    "SELECT created_at FROM document_analysis_aggregated WHERE aggregated_analysis_id = $1",
                    aggregated_analysis_id
                )
                
                processing_time = int((time.time() - start_time) * 1000)
                
                logger.info(f"Aggregated analysis created successfully: aggregated_analysis_id={aggregated_analysis_id}, "
                           f"processing_time={processing_time}ms")
                
                return DocumentAnalysisAggregatedCreateResponse(
                    success=True,
                    aggregated_analysis_id=aggregated_analysis_id,
                    case_id=request.case_id,
                    model_used=request.model_used,
                    total_documents_analyzed=request.total_documents_analyzed,
                    total_tokens_used=request.total_tokens_used,
                    created_at=created_at
                )
                
    except HTTPException:
        raise
    except Exception as e:
        processing_time = int((time.time() - start_time) * 1000)
        logger.error(f"Failed to create aggregated analysis: {e}, processing_time={processing_time}ms")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.get("/{aggregated_analysis_id}", response_model=DocumentAnalysisAggregatedData)
async def get_aggregated_analysis(
    aggregated_analysis_id: str,
    _: bool = Depends(AuthConfig.get_auth_dependency())
):
    """Get aggregated analysis by ID"""
    db_pool = get_db_pool()
    
    try:
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM document_analysis_aggregated WHERE aggregated_analysis_id = $1", 
                aggregated_analysis_id
            )
            
            if not row:
                raise HTTPException(status_code=404, detail="Aggregated analysis not found")
            
            return DocumentAnalysisAggregatedData(
                aggregated_analysis_id=row['aggregated_analysis_id'],
                case_id=row['case_id'],
                analysis_batch_contents=row['analysis_batch_contents'],
                model_used=row['model_used'],
                total_documents_analyzed=row['total_documents_analyzed'],
                total_tokens_used=row['total_tokens_used'],
                created_at=row['created_at']
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get aggregated analysis: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.get("/case/{case_id}")
async def get_aggregated_analyses_by_case(
    case_id: str,
    limit: int = Query(50, ge=1, le=500, description="Maximum number of records to return"),
    offset: int = Query(0, ge=0, description="Number of records to skip"),
    _: bool = Depends(AuthConfig.get_auth_dependency())
):
    """Get all aggregated analyses for a specific case"""
    db_pool = get_db_pool()
    
    try:
        async with db_pool.acquire() as conn:
            # Validate case exists
            case_exists = await conn.fetchval(
                "SELECT EXISTS(SELECT 1 FROM cases WHERE case_id = $1)", 
                case_id
            )
            if not case_exists:
                raise HTTPException(status_code=404, detail=f"Case {case_id} not found")
            
            # Get total count
            total_count = await conn.fetchval(
                "SELECT COUNT(*) FROM document_analysis_aggregated WHERE case_id = $1",
                case_id
            )
            
            # Get paginated results
            rows = await conn.fetch("""
                SELECT * FROM document_analysis_aggregated 
                WHERE case_id = $1 
                ORDER BY created_at DESC 
                LIMIT $2 OFFSET $3
            """, case_id, limit, offset)
            
            analyses = []
            for row in rows:
                analyses.append(DocumentAnalysisAggregatedData(
                    aggregated_analysis_id=row['aggregated_analysis_id'],
                    case_id=row['case_id'],
                    analysis_batch_contents=row['analysis_batch_contents'],
                    model_used=row['model_used'],
                    total_documents_analyzed=row['total_documents_analyzed'],
                    total_tokens_used=row['total_tokens_used'],
                    created_at=row['created_at']
                ))
            
            return {
                "case_id": case_id,
                "total_count": total_count,
                "returned_count": len(analyses),
                "limit": limit,
                "offset": offset,
                "analyses": analyses
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get aggregated analyses for case: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.put("/{aggregated_analysis_id}", response_model=DocumentAnalysisAggregatedUpdateResponse)
async def update_aggregated_analysis(
    aggregated_analysis_id: str,
    request: DocumentAnalysisAggregatedUpdateRequest,
    _: bool = Depends(AuthConfig.get_auth_dependency())
):
    """Update an existing aggregated analysis record"""
    set_endpoint_context("aggregated_analysis_update")
    start_time = time.time()
    db_pool = get_db_pool()
    
    # Validate that at least one field is provided for update
    update_data = request.dict(exclude_unset=True)
    if not update_data:
        raise HTTPException(
            status_code=400, 
            detail="At least one field must be provided for update"
        )
    
    logger.info(f"Updating aggregated analysis {aggregated_analysis_id} with fields: {list(update_data.keys())}")
    
    try:
        async with db_pool.acquire() as conn:
            async with conn.transaction():
                # Check if record exists
                exists = await conn.fetchval(
                    "SELECT EXISTS(SELECT 1 FROM document_analysis_aggregated WHERE aggregated_analysis_id = $1)",
                    aggregated_analysis_id
                )
                if not exists:
                    raise HTTPException(status_code=404, detail="Aggregated analysis not found")
                
                # Build dynamic update query
                set_clauses = []
                values = []
                param_count = 1
                
                for field, value in update_data.items():
                    # Special handling for JSONB field
                    if field == 'analysis_batch_contents':
                        set_clauses.append(f"{field} = ${param_count}::jsonb")
                        values.append(json.dumps(value))
                    else:
                        set_clauses.append(f"{field} = ${param_count}")
                        values.append(value)
                    param_count += 1
                
                # Add aggregated_analysis_id as the last parameter
                values.append(aggregated_analysis_id)
                
                query = f"""
                    UPDATE document_analysis_aggregated 
                    SET {', '.join(set_clauses)}
                    WHERE aggregated_analysis_id = ${param_count}
                    RETURNING total_documents_analyzed
                """
                
                total_documents_analyzed = await conn.fetchval(query, *values)
                
                processing_time = int((time.time() - start_time) * 1000)
                
                logger.info(f"Aggregated analysis updated successfully: aggregated_analysis_id={aggregated_analysis_id}, "
                           f"updated_fields={list(update_data.keys())}, processing_time={processing_time}ms")
                
                return DocumentAnalysisAggregatedUpdateResponse(
                    success=True,
                    aggregated_analysis_id=aggregated_analysis_id,
                    updated_fields=list(update_data.keys()),
                    total_documents_analyzed=total_documents_analyzed,
                    updated_at=datetime.utcnow()
                )
                
    except HTTPException:
        raise
    except Exception as e:
        processing_time = int((time.time() - start_time) * 1000)
        logger.error(f"Failed to update aggregated analysis: {e}, processing_time={processing_time}ms")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.delete("/{aggregated_analysis_id}")
async def delete_aggregated_analysis(
    aggregated_analysis_id: str,
    _: bool = Depends(AuthConfig.get_auth_dependency())
):
    """Delete an aggregated analysis record"""
    db_pool = get_db_pool()
    
    try:
        async with db_pool.acquire() as conn:
            async with conn.transaction():
                # Check if record exists
                exists = await conn.fetchval(
                    "SELECT EXISTS(SELECT 1 FROM document_analysis_aggregated WHERE aggregated_analysis_id = $1)",
                    aggregated_analysis_id
                )
                if not exists:
                    raise HTTPException(status_code=404, detail="Aggregated analysis not found")
                
                # Delete the record
                await conn.execute(
                    "DELETE FROM document_analysis_aggregated WHERE aggregated_analysis_id = $1",
                    aggregated_analysis_id
                )
                
                logger.info(f"Aggregated analysis deleted successfully: aggregated_analysis_id={aggregated_analysis_id}")
                
                return {
                    "success": True,
                    "aggregated_analysis_id": aggregated_analysis_id,
                    "message": "Aggregated analysis deleted successfully"
                }
                
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete aggregated analysis: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.get("")
async def list_aggregated_analyses(
    limit: int = Query(50, ge=1, le=500, description="Maximum number of records to return"),
    offset: int = Query(0, ge=0, description="Number of records to skip"),
    model_used: Optional[str] = Query(None, description="Filter by model used"),
    _: bool = Depends(AuthConfig.get_auth_dependency())
):
    """List all aggregated analyses with optional filtering"""
    db_pool = get_db_pool()
    
    try:
        async with db_pool.acquire() as conn:
            # Build query with optional filtering
            where_clause = ""
            params = []
            param_count = 1
            
            if model_used:
                where_clause = f"WHERE model_used = ${param_count}"
                params.append(model_used)
                param_count += 1
            
            # Get total count
            count_query = f"SELECT COUNT(*) FROM document_analysis_aggregated {where_clause}"
            total_count = await conn.fetchval(count_query, *params)
            
            # Get paginated results
            params.extend([limit, offset])
            list_query = f"""
                SELECT * FROM document_analysis_aggregated 
                {where_clause}
                ORDER BY created_at DESC 
                LIMIT ${param_count} OFFSET ${param_count + 1}
            """
            
            rows = await conn.fetch(list_query, *params)
            
            analyses = []
            for row in rows:
                analyses.append(DocumentAnalysisAggregatedData(
                    aggregated_analysis_id=row['aggregated_analysis_id'],
                    case_id=row['case_id'],
                    analysis_batch_contents=row['analysis_batch_contents'],
                    model_used=row['model_used'],
                    total_documents_analyzed=row['total_documents_analyzed'],
                    total_tokens_used=row['total_tokens_used'],
                    created_at=row['created_at']
                ))
            
            return {
                "total_count": total_count,
                "returned_count": len(analyses),
                "limit": limit,
                "offset": offset,
                "filters": {"model_used": model_used} if model_used else {},
                "analyses": analyses
            }
            
    except Exception as e:
        logger.error(f"Failed to list aggregated analyses: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")