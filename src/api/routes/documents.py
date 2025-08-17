"""
Document-related API routes
"""

import logging
import time
import re
from datetime import datetime
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Depends

from models.document import (
    AnalysisResultRequest, 
    AnalysisResultResponse,
    DocumentLookupRequest,
    DocumentLookupResponse,
    DocumentMapping,
    BulkAnalysisRequest,
    BulkAnalysisResponse,
    AnalysisFailure,
    BulkAnalysisRecord,
    DocumentCreateRequest,
    DocumentCreateResponse,
    DocumentUpdateRequest,
    DocumentUpdateResponse
)
from database.connection import get_db_pool
from utils.auth import AuthConfig

router = APIRouter()
logger = logging.getLogger(__name__)


def normalize_filename(filename: str) -> str:
    """
    Normalize filename for matching by removing special characters and converting to lowercase.
    
    Args:
        filename: Original filename string
        
    Returns:
        Normalized filename string for comparison
    """
    if not filename:
        return ""
    
    # Remove file extensions
    name_without_ext = re.sub(r'\.[^.]*$', '', filename)
    
    # Remove special characters, keep only alphanumeric
    normalized = re.sub(r'[^a-zA-Z0-9]', '', name_without_ext)
    
    return normalized.lower()


def calculate_filename_similarity(pattern: str, original: str) -> float:
    """
    Calculate similarity score between filename pattern and original filename.
    
    Args:
        pattern: Pattern from processed file
        original: Original filename from database
        
    Returns:
        Similarity score between 0.0 and 1.0
    """
    normalized_pattern = normalize_filename(pattern)
    normalized_original = normalize_filename(original)
    
    if not normalized_pattern or not normalized_original:
        return 0.0
    
    # Exact match gets perfect score
    if normalized_pattern == normalized_original:
        return 1.0
    
    # Check if pattern is contained in original (common for processed files)
    if normalized_pattern in normalized_original:
        return 0.8
    
    # Check if original is contained in pattern
    if normalized_original in normalized_pattern:
        return 0.7
    
    # Calculate character overlap ratio
    pattern_set = set(normalized_pattern)
    original_set = set(normalized_original)
    
    if not pattern_set and not original_set:
        return 0.0
    
    intersection = len(pattern_set.intersection(original_set))
    union = len(pattern_set.union(original_set))
    
    overlap_ratio = intersection / union if union > 0 else 0.0
    
    # Only consider matches with significant overlap
    return overlap_ratio if overlap_ratio >= 0.5 else 0.0


def find_best_document_match(pattern: str, documents: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    Find the best matching document for a given filename pattern.
    
    Args:
        pattern: Filename pattern to match
        documents: List of document records with original_file_name
        
    Returns:
        Best matching document record or None
    """
    if not documents:
        return None
    
    best_match = None
    best_score = 0.0
    
    for doc in documents:
        score = calculate_filename_similarity(pattern, doc.get('original_file_name', ''))
        
        if score > best_score:
            best_score = score
            best_match = doc
    
    # Only return matches with sufficient confidence
    if best_score >= 0.5:
        return best_match
    
    return None


@router.post("", response_model=DocumentCreateResponse)
async def create_document(
    request: DocumentCreateRequest,
    _: bool = Depends(AuthConfig.get_auth_dependency())
):
    """
    Create a new document record (Upload Time).
    
    This endpoint is used by AWS State Machine when a file is first uploaded
    to create the initial document record with original file metadata.
    """
    start_time = time.time()
    db_pool = get_db_pool()
    
    logger.info(f"Creating document record: file={request.original_file_name}, "
                f"case_id={request.case_id}, batch_id={request.batch_id}")
    
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
                
                # Insert document record and get generated UUID
                document_id = await conn.fetchval("""
                    INSERT INTO documents (
                        case_id, original_file_name, original_file_size, 
                        original_file_type, original_s3_location, original_s3_key,
                        batch_id, status
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    RETURNING document_id
                """, 
                request.case_id, request.original_file_name, request.original_file_size,
                request.original_file_type, request.original_s3_location, 
                request.original_s3_key, request.batch_id, request.status)
                
                # Get the created timestamp
                created_at = await conn.fetchval(
                    "SELECT created_at FROM documents WHERE document_id = $1",
                    document_id
                )
                
                processing_time = int((time.time() - start_time) * 1000)
                
                logger.info(f"Document created successfully: document_id={document_id}, "
                           f"processing_time={processing_time}ms")
                
                return DocumentCreateResponse(
                    success=True,
                    document_id=document_id,
                    case_id=request.case_id,
                    original_file_name=request.original_file_name,
                    status=request.status,
                    created_at=created_at
                )
                
    except HTTPException:
        raise
    except Exception as e:
        processing_time = int((time.time() - start_time) * 1000)
        logger.error(f"Document creation failed: {e}, processing_time={processing_time}ms")
        
        # Check for constraint violations
        if "foreign key constraint" in str(e).lower():
            raise HTTPException(
                status_code=400,
                detail=f"Invalid case_id: {request.case_id}"
            )
        elif "duplicate key" in str(e).lower():
            raise HTTPException(
                status_code=409,
                detail="Document with same identifiers already exists"
            )
        else:
            raise HTTPException(
                status_code=500,
                detail=f"Document creation failed: {str(e)}"
            )


@router.put("/{document_id}", response_model=DocumentUpdateResponse)
async def update_document(
    document_id: str,
    request: DocumentUpdateRequest,
    _: bool = Depends(AuthConfig.get_auth_dependency())
):
    """
    Update document record (Processing Time).
    
    This endpoint is used by AWS State Machine to update document records
    with processed file metadata and status changes during the pipeline.
    """
    start_time = time.time()
    db_pool = get_db_pool()
    
    logger.info(f"Updating document {document_id}: {dict(request)}")
    
    # Validate at least one field is provided for update
    update_data = request.dict(exclude_unset=True)
    if not update_data:
        raise HTTPException(
            status_code=400,
            detail="At least one field must be provided for update"
        )
    
    try:
        async with db_pool.acquire() as conn:
            async with conn.transaction():
                # Verify document exists
                doc_exists = await conn.fetchval(
                    "SELECT EXISTS(SELECT 1 FROM documents WHERE document_id = $1)", 
                    document_id
                )
                if not doc_exists:
                    raise HTTPException(
                        status_code=404, 
                        detail=f"Document {document_id} not found"
                    )
                
                # Build dynamic update query
                set_clauses = []
                values = []
                param_counter = 1
                
                for field, value in update_data.items():
                    if value is not None:
                        set_clauses.append(f"{field} = ${param_counter}")
                        values.append(value)
                        param_counter += 1
                
                if not set_clauses:
                    raise HTTPException(
                        status_code=400,
                        detail="No valid fields provided for update"
                    )
                
                # Add document_id as final parameter
                values.append(document_id)
                
                query = f"""
                    UPDATE documents 
                    SET {', '.join(set_clauses)}
                    WHERE document_id = ${param_counter}
                    RETURNING status
                """
                
                updated_status = await conn.fetchval(query, *values)
                
                processing_time = int((time.time() - start_time) * 1000)
                updated_fields = list(update_data.keys())
                
                logger.info(f"Document updated successfully: document_id={document_id}, "
                           f"fields={updated_fields}, processing_time={processing_time}ms")
                
                return DocumentUpdateResponse(
                    success=True,
                    document_id=document_id,
                    updated_fields=updated_fields,
                    status=updated_status,
                    updated_at=datetime.utcnow()
                )
                
    except HTTPException:
        raise
    except Exception as e:
        processing_time = int((time.time() - start_time) * 1000)
        logger.error(f"Document update failed: {e}, processing_time={processing_time}ms")
        
        raise HTTPException(
            status_code=500,
            detail=f"Document update failed: {str(e)}"
        )


@router.post("/lookup-by-batch", response_model=DocumentLookupResponse)
async def lookup_documents_by_batch(
    request: DocumentLookupRequest,
    _: bool = Depends(AuthConfig.get_auth_dependency())
):
    """
    Lookup documents by batch ID and match processed files to original documents.
    
    This endpoint is optimized for Lambda integration and supports batch processing
    of document lookups with intelligent filename matching.
    """
    start_time = time.time()
    db_pool = get_db_pool()
    
    logger.info(f"Starting batch lookup for batch_id: {request.batch_id}, "
                f"files: {len(request.processed_files)}")
    
    try:
        async with db_pool.acquire() as conn:
            # Single optimized query to get all documents for the batch
            batch_documents = await conn.fetch("""
                SELECT document_id, original_file_name, case_id, status, created_at
                FROM documents 
                WHERE batch_id = $1
                ORDER BY created_at ASC
            """, request.batch_id)
            
            batch_docs_list = [dict(doc) for doc in batch_documents]
            
            logger.info(f"Found {len(batch_docs_list)} documents for batch {request.batch_id}")
            
            # Process each file and find matches
            mappings = []
            found_count = 0
            
            for processed_file in request.processed_files:
                match = find_best_document_match(
                    processed_file.original_filename_pattern,
                    batch_docs_list
                )
                
                if match:
                    confidence = calculate_filename_similarity(
                        processed_file.original_filename_pattern,
                        match['original_file_name']
                    )
                    
                    mapping = DocumentMapping(
                        file_key=processed_file.file_key,
                        document_id=str(match['document_id']),
                        found=True,
                        confidence_score=confidence
                    )
                    found_count += 1
                    
                    logger.debug(f"Matched file {processed_file.file_key} to document "
                                f"{match['document_id']} (confidence: {confidence:.2f})")
                else:
                    mapping = DocumentMapping(
                        file_key=processed_file.file_key,
                        document_id=None,
                        found=False,
                        confidence_score=0.0
                    )
                    
                    logger.debug(f"No match found for file {processed_file.file_key}")
                
                mappings.append(mapping)
            
            processing_time = int((time.time() - start_time) * 1000)
            
            logger.info(f"Batch lookup completed: {found_count}/{len(request.processed_files)} "
                       f"matches found in {processing_time}ms")
            
            return DocumentLookupResponse(
                success=True,
                batch_id=request.batch_id,
                total_requested=len(request.processed_files),
                total_found=found_count,
                mappings=mappings
            )
            
    except Exception as e:
        processing_time = int((time.time() - start_time) * 1000)
        logger.error(f"Batch lookup failed for batch {request.batch_id}: {e}")
        logger.error(f"Processing time before failure: {processing_time}ms")
        
        raise HTTPException(
            status_code=500, 
            detail=f"Batch lookup failed: {str(e)}"
        )


@router.post("/analysis/bulk", response_model=BulkAnalysisResponse)
async def bulk_store_document_analysis(
    request: BulkAnalysisRequest,
    _: bool = Depends(AuthConfig.get_auth_dependency())
):
    """
    Bulk store document analysis results with optimized PostgreSQL operations.
    
    This endpoint is designed for high-throughput batch processing from Lambda functions
    and supports atomic transactions with detailed error reporting.
    """
    start_time = time.time()
    db_pool = get_db_pool()
    
    logger.info(f"Processing bulk analysis: {len(request.analyses)} records")
    
    try:
        async with db_pool.acquire() as conn:
            async with conn.transaction():
                inserted_count = 0
                failed_records: List[AnalysisFailure] = []
                
                # Collect unique IDs for batch validation
                document_ids = {str(analysis.document_id) for analysis in request.analyses}
                case_ids = {str(analysis.case_id) for analysis in request.analyses}
                
                logger.debug(f"Validating {len(document_ids)} documents, {len(case_ids)} cases")
                
                # Batch validate document existence
                existing_documents = await conn.fetch("""
                    SELECT document_id::text as document_id 
                    FROM documents 
                    WHERE document_id::text = ANY($1)
                """, list(document_ids))
                
                valid_document_ids = {str(doc['document_id']) for doc in existing_documents}
                
                # Batch validate case existence
                existing_cases = await conn.fetch("""
                    SELECT case_id::text as case_id 
                    FROM cases 
                    WHERE case_id::text = ANY($1)
                """, list(case_ids))
                
                valid_case_ids = {str(case['case_id']) for case in existing_cases}
                
                logger.info(f"Validation complete: {len(valid_document_ids)}/{len(document_ids)} documents, "
                           f"{len(valid_case_ids)}/{len(case_ids)} cases found")
                
                # Process each analysis record
                for i, analysis in enumerate(request.analyses):
                    try:
                        analysis_doc_id = str(analysis.document_id)
                        analysis_case_id = str(analysis.case_id)
                        
                        # Validate document exists
                        if analysis_doc_id not in valid_document_ids:
                            logger.warning(f"Document not found: {analysis_doc_id}")
                            failed_records.append(AnalysisFailure(
                                index=i,
                                record_id=analysis_doc_id,
                                error=f"Document {analysis.document_id} not found",
                                error_code="DOCUMENT_NOT_FOUND"
                            ))
                            continue
                        
                        # Validate case exists
                        if analysis_case_id not in valid_case_ids:
                            logger.warning(f"Case not found: {analysis_case_id}")
                            failed_records.append(AnalysisFailure(
                                index=i,
                                record_id=analysis_case_id,
                                error=f"Case {analysis.case_id} not found",
                                error_code="CASE_NOT_FOUND"
                            ))
                            continue
                        
                        # Insert analysis record
                        analysis_id = await conn.fetchval("""
                            INSERT INTO document_analysis 
                            (document_id, case_id, workflow_id, analysis_content, 
                             analysis_status, model_used, tokens_used, analyzed_at)
                            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                            RETURNING analysis_id
                        """, 
                        analysis.document_id, analysis.case_id, analysis.workflow_id,
                        analysis.analysis_content, analysis.analysis_status, 
                        analysis.model_used, analysis.tokens_used, analysis.analyzed_at)
                        
                        # Update document status to analyzed
                        await conn.execute("""
                            UPDATE documents 
                            SET status = 'analyzed' 
                            WHERE document_id = $1
                        """, analysis.document_id)
                        
                        inserted_count += 1
                        
                    except Exception as record_error:
                        logger.error(f"Failed to store analysis record {i}: {record_error}")
                        failed_records.append(AnalysisFailure(
                            index=i,
                            record_id=analysis_doc_id,
                            error=str(record_error),
                            error_code="STORAGE_ERROR"
                        ))
                        continue
                
                processing_time = int((time.time() - start_time) * 1000)
                
                # Determine overall success
                success = len(failed_records) == 0
                failed_count = len(failed_records)
                
                logger.info(f"Bulk analysis complete: {inserted_count} inserted, "
                           f"{failed_count} failed ({processing_time}ms)")
                
                if failed_records:
                    error_codes = [f.error_code for f in failed_records]
                    logger.warning(f"Failed records: {error_codes}")
                
                return BulkAnalysisResponse(
                    success=success,
                    total_requested=len(request.analyses),
                    inserted_count=inserted_count,
                    failed_count=failed_count,
                    failed_records=failed_records if failed_records else None,
                    processing_time_ms=processing_time
                )
                
    except Exception as e:
        processing_time = int((time.time() - start_time) * 1000)
        logger.error(f"Bulk analysis storage failed: {e}")
        logger.error(f"Processing time before failure: {processing_time}ms")
        
        raise HTTPException(
            status_code=500,
            detail=f"Bulk analysis storage failed: {str(e)}"
        )


@router.post("/{document_id}/analysis", response_model=AnalysisResultResponse)
async def store_document_analysis(
    document_id: str, 
    request: AnalysisResultRequest,
    _: bool = Depends(AuthConfig.get_auth_dependency())
):
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
async def get_document_analysis(
    document_id: str,
    _: bool = Depends(AuthConfig.get_auth_dependency())
):
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

@router.get("/{document_id}/validate")
async def validate_document_exists(
    document_id: str,
    _: bool = Depends(AuthConfig.get_auth_dependency())
):
    """
    Diagnostic endpoint to validate if a document exists in the database.
    Useful for troubleshooting 404 errors in bulk analysis endpoint.
    """
    db_pool = get_db_pool()
    
    try:
        async with db_pool.acquire() as conn:
            # Check if document exists using the exact same logic as bulk analysis
            doc_exists = await conn.fetchval(
                "SELECT EXISTS(SELECT 1 FROM documents WHERE document_id::text = $1)", 
                document_id
            )
            
            if doc_exists:
                # Get document details for debugging
                doc_details = await conn.fetchrow("""
                    SELECT document_id::text as document_id, case_id::text as case_id, 
                           original_file_name, status, created_at
                    FROM documents 
                    WHERE document_id::text = $1
                """, document_id)
                
                return {
                    "exists": True,
                    "document_id": document_id,
                    "validation_query": "document_id::text = $1",
                    "details": dict(doc_details) if doc_details else None,
                    "message": "Document found in database"
                }
            else:
                # Check if it exists with UUID casting (for comparison)
                try:
                    uuid_exists = await conn.fetchval(
                        "SELECT EXISTS(SELECT 1 FROM documents WHERE document_id = $1::uuid)", 
                        document_id
                    )
                except Exception:
                    uuid_exists = False
                
                return {
                    "exists": False,
                    "document_id": document_id,
                    "validation_query": "document_id::text = $1",
                    "uuid_cast_exists": uuid_exists,
                    "message": "Document not found with text comparison",
                    "debug_info": "Check if document was created in same database instance"
                }
                
    except Exception as e:
        logger.error(f"Document validation failed for {document_id}: {e}")
        return {
            "exists": False,
            "document_id": document_id,
            "error": str(e),
            "message": "Validation query failed"
        }


@router.get("/{document_id}")
async def get_document(
    document_id: str,
    _: bool = Depends(AuthConfig.get_auth_dependency())
):
    """Get document metadata by document ID"""
    db_pool = get_db_pool()
    
    try:
        async with db_pool.acquire() as conn:
            doc_row = await conn.fetchrow("""
                SELECT document_id, case_id, original_file_name, original_file_size, original_file_type,
                       original_s3_location, original_s3_key, status, created_at,
                       processed_file_name, processed_file_size, processed_s3_location, processed_s3_key, batch_id
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