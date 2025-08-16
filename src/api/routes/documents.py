"""
Document-related API routes
"""

import logging
from datetime import datetime
from fastapi import APIRouter, HTTPException

from models.document import AnalysisResultRequest, AnalysisResultResponse
from database.connection import get_db_pool

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/{document_id}/analysis", response_model=AnalysisResultResponse)
async def store_document_analysis(document_id: str, request: AnalysisResultRequest):
    """Store document analysis results"""
    db_pool = get_db_pool()
    
    try:
        async with db_pool.acquire() as conn:
            # Verify document exists
            doc_exists = await conn.fetchval(
                "SELECT EXISTS(SELECT 1 FROM documents WHERE document_id = $1)", 
                document_id
            )
            if not doc_exists:
                raise HTTPException(status_code=404, detail="Document not found")
            
            # Verify case exists
            case_exists = await conn.fetchval(
                "SELECT EXISTS(SELECT 1 FROM cases WHERE case_id = $1)", 
                request.case_id
            )
            if not case_exists:
                raise HTTPException(status_code=404, detail="Case not found")
            
            # Insert analysis result and get the generated UUID
            analysis_id = await conn.fetchval("""
                INSERT INTO document_analysis 
                (document_id, case_id, workflow_id, analysis_content, 
                 analysis_status, model_used, tokens_used, analyzed_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                RETURNING analysis_id
            """, 
            document_id, request.case_id, request.workflow_id,
            request.analysis_content, request.analysis_status, request.model_used,
            request.tokens_used, datetime.utcnow())
            
            # Update document status to analyzed
            await conn.execute(
                "UPDATE documents SET status = 'analyzed' WHERE document_id = $1",
                document_id
            )
            
            logger.info(f"Stored analysis result {analysis_id} for document {document_id}")
            
            return AnalysisResultResponse(
                analysis_id=str(analysis_id),
                document_id=document_id,
                case_id=request.case_id,
                status="stored",
                analyzed_at=datetime.utcnow().isoformat()
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to store analysis result: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.get("/{document_id}/analysis")
async def get_document_analysis(document_id: str):
    """Get analysis results for a document"""
    db_pool = get_db_pool()
    
    try:
        async with db_pool.acquire() as conn:
            analysis_row = await conn.fetchrow("""
                SELECT analysis_id, document_id, case_id, workflow_id, analysis_content,
                       analysis_status, model_used, tokens_used, analyzed_at, created_at
                FROM document_analysis 
                WHERE document_id = $1
                ORDER BY analyzed_at DESC
                LIMIT 1
            """, document_id)
            
            if not analysis_row:
                raise HTTPException(status_code=404, detail="Analysis not found for document")
            
            result = dict(analysis_row)
            
            # Convert timestamps to ISO format
            for field in ['analyzed_at', 'created_at']:
                if result[field]:
                    result[field] = result[field].isoformat()
            
            return result
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get analysis result: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.get("/{document_id}")
async def get_document(document_id: str):
    """Get document metadata by document ID"""
    db_pool = get_db_pool()
    
    try:
        async with db_pool.acquire() as conn:
            doc_row = await conn.fetchrow("""
                SELECT document_id, case_id, filename, file_size, file_type,
                       s3_location, s3_key, s3_etag, status, created_at
                FROM documents 
                WHERE document_id = $1
            """, document_id)
            
            if not doc_row:
                raise HTTPException(status_code=404, detail="Document not found")
            
            result = dict(doc_row)
            
            # Convert timestamps to ISO format
            for field in ['created_at']:
                if result[field]:
                    result[field] = result[field].isoformat()
            
            return result
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get document: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")