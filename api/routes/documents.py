"""
Document-related API routes
"""

import uuid
import asyncio
import logging
from typing import List
from datetime import datetime
from fastapi import APIRouter, HTTPException, UploadFile, File, Form

from models.document import FileUploadResponse, AnalysisResultRequest, AnalysisResultResponse
from services.file_processor import is_supported_file_type, process_uploaded_file
from services.document_analysis import trigger_document_analysis
from database.connection import get_db_pool

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/upload-documents", response_model=FileUploadResponse)
async def upload_documents(
    case_id: str = Form(...),
    files: List[UploadFile] = File(...)
):
    """Upload and process documents for a case"""
    db_pool = get_db_pool()
    
    logger.info(f"📄 Document upload request for case: {case_id}")
    logger.info(f"📄 Files to process: {len(files)}")
    
    try:
        # Verify case exists
        async with db_pool.acquire() as conn:
            case_exists = await conn.fetchval(
                "SELECT EXISTS(SELECT 1 FROM cases WHERE case_id = $1)", 
                case_id
            )
            if not case_exists:
                raise HTTPException(status_code=404, detail=f"Case {case_id} not found")
        
        all_processed_files = []
        documents_created = 0
        workflow_ids = []
        
        async with db_pool.acquire() as conn:
            for file in files:
                # Validate file type
                if not is_supported_file_type(file.filename):
                    logger.warning(f"Unsupported file type: {file.filename}")
                    continue
                
                # Process the file (convert if necessary and upload to S3)
                processed_files = await process_uploaded_file(file, case_id)
                
                # Create document records for each processed file
                for processed_file in processed_files:
                    document_id = f"doc_{uuid.uuid4().hex[:12]}"
                    
                    # Insert document record
                    await conn.execute("""
                        INSERT INTO documents 
                        (document_id, case_id, filename, file_size, file_type, 
                        s3_location, s3_key, s3_etag, status)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                    """,
                    document_id, case_id, processed_file.processed_filename, 
                    processed_file.file_size, processed_file.file_type,
                    processed_file.s3_location, processed_file.s3_key,
                    None, "uploaded")  # No ETag for direct uploads
                    
                    documents_created += 1
                    
                    logger.info(f"📄 Created document record: {document_id} for case {case_id}")
                    
                    # Generate workflow ID and trigger analysis
                    workflow_id = f"wf_upload_{uuid.uuid4().hex[:8]}"
                    workflow_ids.append(workflow_id)
                    
                    # Trigger document analysis in background
                    # Note: Using asyncio.create_task instead of BackgroundTasks for immediate execution
                    asyncio.create_task(trigger_document_analysis(
                        document_id, case_id, processed_file.s3_location, workflow_id
                    ))
                
                all_processed_files.extend(processed_files)
        
        return FileUploadResponse(
            case_id=case_id,
            total_files_processed=len(files),
            documents_created=documents_created,
            processed_files=all_processed_files,
            analysis_triggered=documents_created > 0,
            workflow_ids=workflow_ids,
            message=f"Successfully processed {len(files)} files and created {documents_created} document records"
        )
        
    except Exception as e:
        logger.error(f"Document upload failed: {e}")
        raise HTTPException(status_code=500, detail=f"Upload processing failed: {str(e)}")

@router.post("/{document_id}/analysis", response_model=AnalysisResultResponse)
async def store_document_analysis(document_id: str, request: AnalysisResultRequest):
    """Store document analysis results"""
    analysis_id = f"ana_{uuid.uuid4().hex[:12]}"
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
            
            # Insert analysis result
            await conn.execute("""
                INSERT INTO document_analysis 
                (analysis_id, document_id, case_id, workflow_id, analysis_content, 
                 analysis_status, model_used, tokens_used, analyzed_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            """, 
            analysis_id, document_id, request.case_id, request.workflow_id,
            request.analysis_content, request.analysis_status, request.model_used,
            request.tokens_used, datetime.utcnow())
            
            # Update document status to analyzed
            await conn.execute(
                "UPDATE documents SET status = 'analyzed' WHERE document_id = $1",
                document_id
            )
            
            logger.info(f"Stored analysis result {analysis_id} for document {document_id}")
            
            return AnalysisResultResponse(
                analysis_id=analysis_id,
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