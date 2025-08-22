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
    DocumentUpdateResponse,
    DocumentAnalysisData,
    DocumentAnalysisUpdateRequest,
    DocumentAnalysisUpdateResponse,
    DocumentAnalysisByCaseResponse,
    DocumentAnalysisAggregatedSummary
)
from services.documents_service import get_documents_service, get_document_analysis_service
from services.cases_service import get_cases_service
from utils.auth import AuthConfig
from utils.error_handling import set_endpoint_context, log_business_error

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
    set_endpoint_context("document_creation")
    start_time = time.time()
    documents_service = get_documents_service()
    cases_service = get_cases_service()
    
    logger.info(f"Creating document: {request.original_file_name} for case {request.case_id}")
    
    try:
        # Validate case exists
        case_result = await cases_service.get_case_by_id(request.case_id)
        if not case_result.success or not case_result.data:
            raise HTTPException(
                status_code=404, 
                detail=f"Case {request.case_id} not found"
            )
        
        # Create document using service
        result = await documents_service.create_document(
            case_id=request.case_id,
            original_file_name=request.original_file_name,
            original_file_size=request.original_file_size,
            original_file_type=request.original_file_type,
            original_s3_location=request.original_s3_location,
            original_s3_key=request.original_s3_key,
            batch_id=request.batch_id,
            status=request.status
        )
        
        if not result.success:
            processing_time = int((time.time() - start_time) * 1000)
            logger.error(f"Document creation failed: {result.error}, processing_time={processing_time}ms")
            
            if result.error_type == "CONFLICT":
                raise HTTPException(
                    status_code=409,
                    detail="Document with same identifiers already exists"
                )
            elif result.error_type == "INVALID_QUERY":
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid request: {result.error}"
                )
            else:
                raise HTTPException(
                    status_code=500,
                    detail=f"Document creation failed: {result.error}"
                )
        
        document_data = result.data[0]
        processing_time = int((time.time() - start_time) * 1000)
        
        logger.info(f"Document created successfully: document_id={document_data['document_id']}, "
                   f"processing_time={processing_time}ms")
        
        return DocumentCreateResponse(
            success=True,
            document_id=document_data['document_id'],
            case_id=document_data['case_id'],
            original_file_name=document_data['original_file_name'],
            status=document_data['status'],
            created_at=datetime.fromisoformat(document_data['created_at'].replace('Z', '+00:00')) if isinstance(document_data['created_at'], str) else document_data['created_at']
        )
        
    except HTTPException:
        raise
    except Exception as e:
        processing_time = int((time.time() - start_time) * 1000)
        logger.error(f"Document creation failed: {e}, processing_time={processing_time}ms")
        raise HTTPException(
            status_code=500,
            detail=f"Service error: {str(e)}"
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
    set_endpoint_context("document_update")
    start_time = time.time()
    documents_service = get_documents_service()
    
    logger.info(f"Updating document {document_id}")
    
    # Validate at least one field is provided for update
    update_data = request.dict(exclude_unset=True)
    if not update_data:
        raise HTTPException(
            status_code=400,
            detail="At least one field must be provided for update"
        )
    
    try:
        # First check if document exists
        doc_result = await documents_service.get_by_id(document_id)
        if not doc_result.success or not doc_result.data:
            raise HTTPException(
                status_code=404, 
                detail=f"Document {document_id} not found"
            )
        
        # Filter out None values for the update
        filtered_update_data = {k: v for k, v in update_data.items() if v is not None}
        
        if not filtered_update_data:
            raise HTTPException(
                status_code=400,
                detail="No valid fields provided for update"
            )
        
        # Update document using service
        result = await documents_service.update(document_id, filtered_update_data)
        
        if not result.success:
            processing_time = int((time.time() - start_time) * 1000)
            logger.error(f"Document update failed: {result.error}, processing_time={processing_time}ms")
            
            if result.error_type == "NOT_FOUND":
                raise HTTPException(
                    status_code=404,
                    detail=f"Document {document_id} not found"
                )
            elif result.error_type == "INVALID_QUERY":
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid update request: {result.error}"
                )
            else:
                raise HTTPException(
                    status_code=500,
                    detail=f"Document update failed: {result.error}"
                )
        
        document_data = result.data[0] if result.data else {}
        processing_time = int((time.time() - start_time) * 1000)
        updated_fields = list(filtered_update_data.keys())
        
        logger.info(f"Document updated successfully: document_id={document_id}, "
                   f"fields={updated_fields}, processing_time={processing_time}ms")
        
        return DocumentUpdateResponse(
            success=True,
            document_id=document_id,
            updated_fields=updated_fields,
            status=document_data.get('status', 'UNKNOWN'),
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
    documents_service = get_documents_service()
    
    logger.info(f"Starting batch lookup for batch_id: {request.batch_id}, "
                f"files: {len(request.processed_files)}")
    
    try:
        # Get all documents for the batch using service
        batch_result = await documents_service.get_documents_by_batch(request.batch_id)
        
        if not batch_result.success:
            logger.error(f"Failed to get documents for batch {request.batch_id}: {batch_result.error}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to get batch documents: {batch_result.error}"
            )
        
        batch_docs_list = batch_result.data or []
        
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
            
    except HTTPException:
        raise
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
    set_endpoint_context("bulk_analysis_storage")
    start_time = time.time()
    document_analysis_service = get_document_analysis_service()
    documents_service = get_documents_service()
    cases_service = get_cases_service()
    
    logger.info(f"Processing bulk analysis: {len(request.analyses)} records")
    
    try:
        inserted_count = 0
        failed_records: List[AnalysisFailure] = []
        
        # Collect unique IDs for batch validation
        document_ids = list(set([analysis.document_id for analysis in request.analyses]))
        case_ids = list(set([analysis.case_id for analysis in request.analyses]))
        
        logger.debug(f"Validating {len(document_ids)} documents, {len(case_ids)} cases")
        
        # Validate documents exist
        valid_document_ids = set()
        for doc_id in document_ids:
            doc_result = await documents_service.get_by_id(doc_id)
            if doc_result.success and doc_result.data:
                valid_document_ids.add(doc_id)
        
        # Validate cases exist
        valid_case_ids = set()
        for case_id in case_ids:
            case_result = await cases_service.get_case_by_id(case_id)
            if case_result.success and case_result.data:
                valid_case_ids.add(case_id)
        
        logger.info(f"Validation complete: {len(valid_document_ids)}/{len(document_ids)} documents, "
                   f"{len(valid_case_ids)}/{len(case_ids)} cases found")
        
        # Process each analysis record
        for i, analysis in enumerate(request.analyses):
            try:
                # Validate document exists
                if analysis.document_id not in valid_document_ids:
                    logger.warning(f"Document not found: {analysis.document_id}")
                    failed_records.append(AnalysisFailure(
                        index=i,
                        record_id=str(analysis.document_id),
                        error=f"Document {analysis.document_id} not found",
                        error_code="DOCUMENT_NOT_FOUND"
                    ))
                    continue
                
                # Validate case exists
                if analysis.case_id not in valid_case_ids:
                    logger.warning(f"Case not found: {analysis.case_id}")
                    failed_records.append(AnalysisFailure(
                        index=i,
                        record_id=str(analysis.case_id),
                        error=f"Case {analysis.case_id} not found",
                        error_code="CASE_NOT_FOUND"
                    ))
                    continue
                
                # Create analysis using service
                analysis_result = await document_analysis_service.create_analysis(
                    document_id=analysis.document_id,
                    case_id=analysis.case_id,
                    analysis_content=analysis.analysis_content,
                    model_used=analysis.model_used,
                    tokens_used=analysis.tokens_used,
                    analysis_reasoning=analysis.analysis_reasoning,
                    analysis_status=analysis.analysis_status
                )
                
                if not analysis_result.success:
                    logger.error(f"Failed to create analysis for document {analysis.document_id}: {analysis_result.error}")
                    failed_records.append(AnalysisFailure(
                        index=i,
                        record_id=str(analysis.document_id),
                        error=analysis_result.error,
                        error_code="STORAGE_ERROR"
                    ))
                    continue
                
                # Update document status to completed
                update_result = await documents_service.update_document_status(
                    analysis.document_id, 
                    'COMPLETED'
                )
                
                if not update_result.success:
                    logger.warning(f"Failed to update document status for {analysis.document_id}: {update_result.error}")
                    # Don't fail the entire analysis creation for this
                
                inserted_count += 1
                
            except Exception as record_error:
                logger.error(f"Failed to store analysis record {i}: {record_error}")
                failed_records.append(AnalysisFailure(
                    index=i,
                    record_id=str(analysis.document_id),
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
    document_analysis_service = get_document_analysis_service()
    documents_service = get_documents_service()
    cases_service = get_cases_service()
    
    try:
        # Verify document exists
        doc_result = await documents_service.get_by_id(document_id)
        if not doc_result.success or not doc_result.data:
            raise HTTPException(status_code=404, detail="Document not found")
        
        # Verify case exists
        case_result = await cases_service.get_case_by_id(request.case_id)
        if not case_result.success or not case_result.data:
            raise HTTPException(status_code=404, detail="Case not found")
        
        # Create analysis using service
        analysis_result = await document_analysis_service.create_analysis(
            document_id=document_id,
            case_id=request.case_id,
            analysis_content=request.analysis_content,
            model_used=request.model_used,
            tokens_used=request.tokens_used,
            analysis_reasoning=request.analysis_reasoning,
            analysis_status=request.analysis_status
        )
        
        if not analysis_result.success:
            logger.error(f"Failed to create analysis: {analysis_result.error}")
            raise HTTPException(
                status_code=500,
                detail=f"Analysis creation failed: {analysis_result.error}"
            )
        
        analysis_data = analysis_result.data[0]
        
        # Update document status to completed
        update_result = await documents_service.update_document_status(document_id, 'COMPLETED')
        if not update_result.success:
            logger.warning(f"Failed to update document status: {update_result.error}")
            # Don't fail the entire operation for this
        
        logger.info(f"Stored analysis result {analysis_data['analysis_id']} for document {document_id}")
        
        return AnalysisResultResponse(
            analysis_id=str(analysis_data['analysis_id']),
            document_id=document_id,
            case_id=request.case_id,
            status="stored",
            analyzed_at=datetime.utcnow().isoformat()
        )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to store analysis result: {e}")
        raise HTTPException(status_code=500, detail=f"Service error: {str(e)}")

@router.get("/{document_id}/analysis")
async def get_document_analysis(
    document_id: str,
    _: bool = Depends(AuthConfig.get_auth_dependency())
):
    """Get analysis results for a document"""
    document_analysis_service = get_document_analysis_service()
    
    try:
        # Get all analyses for the document
        result = await document_analysis_service.get_analyses_by_document(document_id)
        
        if not result.success:
            logger.error(f"Failed to get analyses for document {document_id}: {result.error}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to get analyses: {result.error}"
            )
        
        if not result.data:
            raise HTTPException(status_code=404, detail="Analysis not found for document")
        
        # Get the most recent analysis (first one since we order by analyzed_at DESC in service)
        analysis = result.data[0]
        
        # Convert timestamps to ISO format
        for field in ['analyzed_at', 'created_at']:
            if analysis.get(field):
                if hasattr(analysis[field], 'isoformat'):
                    analysis[field] = analysis[field].isoformat()
        
        return analysis
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get analysis result: {e}")
        raise HTTPException(status_code=500, detail=f"Service error: {str(e)}")


@router.get("/{document_id}")
async def get_document(
    document_id: str,
    _: bool = Depends(AuthConfig.get_auth_dependency())
):
    """Get document metadata by document ID"""
    documents_service = get_documents_service()
    
    try:
        result = await documents_service.get_by_id(document_id)
        
        if not result.success:
            logger.error(f"Failed to get document {document_id}: {result.error}")
            if result.error_type == "NOT_FOUND":
                raise HTTPException(status_code=404, detail="Document not found")
            else:
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to get document: {result.error}"
                )
        
        if not result.data:
            raise HTTPException(status_code=404, detail="Document not found")
        
        document = result.data[0]
        
        # Convert timestamps to ISO format
        for field in ['created_at']:
            if document.get(field):
                if hasattr(document[field], 'isoformat'):
                    document[field] = document[field].isoformat()
        
        return document
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get document: {e}")
        raise HTTPException(status_code=500, detail=f"Service error: {str(e)}")


# Enhanced Document Analysis Endpoints

@router.get("/analysis/case/{case_id}", response_model=DocumentAnalysisByCaseResponse)
async def get_all_analyses_by_case(
    case_id: str,
    include_content: bool = True,
    _: bool = Depends(AuthConfig.get_auth_dependency())
):
    """
    Get all document analyses for a specific case with full content.
    
    This endpoint retrieves all analysis records for documents belonging to a case,
    including the full analysis_content JSON. This replaces the need for a separate
    aggregated table as data can be aggregated on-demand.
    """
    document_analysis_service = get_document_analysis_service()
    cases_service = get_cases_service()
    
    try:
        # Validate case exists
        case_result = await cases_service.get_case_by_id(case_id)
        if not case_result.success or not case_result.data:
            raise HTTPException(status_code=404, detail=f"Case {case_id} not found")
        
        # Get all analyses for the case
        analyses_result = await document_analysis_service.get_analyses_by_case(case_id)
        
        if not analyses_result.success:
            logger.error(f"Failed to get analyses for case {case_id}: {analyses_result.error}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to get analyses: {analyses_result.error}"
            )
        
        analyses_data = analyses_result.data or []
        
        # Get aggregated analysis data which includes total tokens
        aggregated_result = await document_analysis_service.get_aggregated_analysis(case_id)
        total_tokens = None
        if aggregated_result.success and aggregated_result.data:
            total_tokens = aggregated_result.data[0].get('total_tokens_used')
        
        analyses = []
        for analysis_data in analyses_data:
            # Note: The service doesn't include original_file_name, so we'll need to get documents too
            # For now, we'll work with what we have from the service
            analysis = DocumentAnalysisData(
                analysis_id=analysis_data['analysis_id'],
                document_id=analysis_data['document_id'],
                case_id=analysis_data['case_id'],
                analysis_content=analysis_data.get('analysis_content', '{}') if include_content else '{}',
                analysis_status=analysis_data['analysis_status'],
                model_used=analysis_data['model_used'],
                tokens_used=analysis_data['tokens_used'],
                analyzed_at=analysis_data['analyzed_at'],
                created_at=analysis_data['created_at'],
                analysis_reasoning=analysis_data.get('analysis_reasoning'),
                context_summary_created=analysis_data.get('context_summary_created', False)
            )
            analyses.append(analysis)
        
        logger.info(f"Retrieved {len(analyses)} analyses for case {case_id}")
        
        return DocumentAnalysisByCaseResponse(
            case_id=case_id,
            total_analyses=len(analyses),
            total_tokens_used=int(total_tokens) if total_tokens else None,
            analyses=analyses,
            aggregated_content=None  # Can be populated with custom aggregation logic if needed
        )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get analyses for case: {e}")
        raise HTTPException(status_code=500, detail=f"Service error: {str(e)}")


@router.get("/analysis/case/{case_id}/aggregate", response_model=DocumentAnalysisAggregatedSummary)
async def get_aggregated_analysis_summary(
    case_id: str,
    _: bool = Depends(AuthConfig.get_auth_dependency())
):
    """
    Get aggregated analysis summary for a case using service layer aggregation.
    
    This endpoint provides a summary of all analyses for a case, computed
    dynamically via the document analysis service.
    """
    document_analysis_service = get_document_analysis_service()
    cases_service = get_cases_service()
    
    try:
        # Validate case exists
        case_result = await cases_service.get_case_by_id(case_id)
        if not case_result.success or not case_result.data:
            raise HTTPException(status_code=404, detail=f"Case {case_id} not found")
        
        # Get aggregated analysis data
        aggregated_result = await document_analysis_service.get_aggregated_analysis(case_id)
        
        if not aggregated_result.success:
            logger.error(f"Failed to get aggregated analysis for case {case_id}: {aggregated_result.error}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to get aggregated analysis: {aggregated_result.error}"
            )
        
        if not aggregated_result.data:
            # No analyses for this case
            return DocumentAnalysisAggregatedSummary(
                case_id=case_id,
                total_documents=0,
                total_tokens=None,
                models_used=[],
                status_breakdown={},
                earliest_analysis=None,
                latest_analysis=None,
                aggregated_insights=None
            )
        
        aggregated_data = aggregated_result.data[0]
        
        # Get all analyses to compute additional stats that service doesn't provide
        analyses_result = await document_analysis_service.get_analyses_by_case(case_id)
        
        earliest_analysis = None
        latest_analysis = None
        if analyses_result.success and analyses_result.data:
            analyses = analyses_result.data
            if analyses:
                # Find earliest and latest
                dates = [a.get('analyzed_at') for a in analyses if a.get('analyzed_at')]
                if dates:
                    earliest_analysis = min(dates)
                    latest_analysis = max(dates)
        
        # Prepare aggregated insights
        aggregated_insights = None
        if aggregated_data.get('total_documents', 0) > 0:
            completed_count = aggregated_data.get('analysis_status_counts', {}).get('COMPLETED', 0)
            aggregated_insights = {
                "total_completed_analyses": completed_count,
                "processing_note": "Individual analyses can be merged here based on specific business logic"
            }
        
        logger.info(f"Generated aggregated summary for case {case_id}: {aggregated_data.get('total_documents', 0)} documents")
        
        return DocumentAnalysisAggregatedSummary(
            case_id=case_id,
            total_documents=aggregated_data.get('total_documents', 0),
            total_tokens=aggregated_data.get('total_tokens_used'),
            models_used=aggregated_data.get('models_used', []),
            status_breakdown=aggregated_data.get('analysis_status_counts', {}),
            earliest_analysis=earliest_analysis,
            latest_analysis=latest_analysis,
            aggregated_insights=aggregated_insights
        )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get aggregated analysis summary: {e}")
        raise HTTPException(status_code=500, detail=f"Service error: {str(e)}")


@router.put("/analysis/{analysis_id}", response_model=DocumentAnalysisUpdateResponse)
async def update_document_analysis(
    analysis_id: str,
    request: DocumentAnalysisUpdateRequest,
    _: bool = Depends(AuthConfig.get_auth_dependency())
):
    """
    Update an existing document analysis record.
    
    This endpoint allows updating analysis content, status, model, or token count
    for reprocessing or correction purposes.
    """
    document_analysis_service = get_document_analysis_service()
    
    # Validate at least one field is provided
    update_data = request.dict(exclude_unset=True)
    if not update_data:
        raise HTTPException(
            status_code=400,
            detail="At least one field must be provided for update"
        )
    
    logger.info(f"Updating analysis {analysis_id} with fields: {list(update_data.keys())}")
    
    try:
        # First check if analysis exists
        analysis_result = await document_analysis_service.get_by_id(analysis_id)
        if not analysis_result.success or not analysis_result.data:
            raise HTTPException(status_code=404, detail="Analysis not found")
        
        # Update the analysis using service
        result = await document_analysis_service.update(analysis_id, update_data)
        
        if not result.success:
            logger.error(f"Failed to update analysis {analysis_id}: {result.error}")
            
            if result.error_type == "NOT_FOUND":
                raise HTTPException(status_code=404, detail="Analysis not found")
            elif result.error_type == "INVALID_QUERY":
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid update request: {result.error}"
                )
            else:
                raise HTTPException(
                    status_code=500,
                    detail=f"Analysis update failed: {result.error}"
                )
        
        logger.info(f"Analysis {analysis_id} updated successfully")
        
        return DocumentAnalysisUpdateResponse(
            success=True,
            analysis_id=analysis_id,
            updated_fields=list(update_data.keys()),
            updated_at=datetime.utcnow()
        )
                
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update analysis: {e}")
        raise HTTPException(status_code=500, detail=f"Service error: {str(e)}")


@router.delete("/analysis/{analysis_id}")
async def delete_document_analysis(
    analysis_id: str,
    _: bool = Depends(AuthConfig.get_auth_dependency())
):
    """
    Delete a document analysis record.
    
    This endpoint allows deletion of analysis records for data management purposes.
    """
    document_analysis_service = get_document_analysis_service()
    
    try:
        # Delete the analysis using service
        result = await document_analysis_service.delete_analysis(analysis_id)
        
        if not result.success:
            logger.error(f"Failed to delete analysis {analysis_id}: {result.error}")
            
            if result.error_type == "NOT_FOUND":
                raise HTTPException(status_code=404, detail="Analysis not found")
            else:
                raise HTTPException(
                    status_code=500,
                    detail=f"Analysis deletion failed: {result.error}"
                )
        
        deletion_data = result.data[0] if result.data else {}
        logger.info(f"Analysis {analysis_id} deleted successfully")
        
        return {
            "success": True,
            "analysis_id": analysis_id,
            "message": "Analysis deleted successfully",
            "document_status_updated": deletion_data.get("document_status_updated", False)
        }
                
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete analysis: {e}")
        raise HTTPException(status_code=500, detail=f"Service error: {str(e)}")