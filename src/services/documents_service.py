"""
Documents service - business logic for document and document analysis management
"""

import logging
from typing import Dict, Any, List, Optional
from services.base_service import BaseService, ServiceResult

logger = logging.getLogger(__name__)

class DocumentsService(BaseService):
    """Service for document management operations"""
    
    def __init__(self, role: str = "api"):
        super().__init__("documents", role)
    
    async def create_document(
        self,
        case_id: str,
        original_file_name: str,
        original_file_size: int,
        original_file_type: str,
        original_s3_location: str,
        original_s3_key: str,
        batch_id: Optional[str] = None,
        status: str = "PENDING"
    ) -> ServiceResult:
        """
        Create a new document record
        
        Args:
            case_id: UUID of the associated case
            original_file_name: Original name of the uploaded file
            original_file_size: Size of the file in bytes
            original_file_type: MIME type of the file
            original_s3_location: S3 bucket location
            original_s3_key: S3 key for the file
            batch_id: Optional batch ID for bulk uploads
            status: Initial document status (default: PENDING)
            
        Returns:
            ServiceResult with created document data
        """
        document_data = {
            "case_id": case_id,
            "original_file_name": original_file_name,
            "original_file_size": original_file_size,
            "original_file_type": original_file_type,
            "original_s3_location": original_s3_location,
            "original_s3_key": original_s3_key,
            "status": status
        }
        
        if batch_id:
            document_data["batch_id"] = batch_id
        
        logger.info(f"Creating document for case {case_id}: {original_file_name}")
        return await self.create(document_data)
    
    async def get_document_by_id(self, document_id: str) -> ServiceResult:
        """Get a document by its ID"""
        return await self.get_by_id(document_id)
    
    async def get_documents_by_case(self, case_id: str) -> ServiceResult:
        """Get all documents for a specific case"""
        return await self.get_by_field("case_id", case_id)
    
    async def get_documents_by_status(self, status: str, limit: int = 100) -> ServiceResult:
        """Get documents by processing status"""
        return await self.get_by_field("status", status, limit)
    
    async def get_documents_by_batch(self, batch_id: str) -> ServiceResult:
        """Get all documents in a specific batch"""
        return await self.get_by_field("batch_id", batch_id)
    
    async def update_document_status(self, document_id: str, status: str) -> ServiceResult:
        """Update the processing status of a document"""
        logger.info(f"Updating document {document_id} status to: {status}")
        return await self.update(document_id, {"status": status})
    
    async def update_processed_info(
        self,
        document_id: str,
        processed_file_name: str,
        processed_file_size: int,
        processed_s3_location: str,
        processed_s3_key: str,
        status: str = "COMPLETED"
    ) -> ServiceResult:
        """
        Update document with processed file information
        
        Args:
            document_id: UUID of the document
            processed_file_name: Name of processed file
            processed_file_size: Size of processed file
            processed_s3_location: S3 location of processed file
            processed_s3_key: S3 key of processed file
            status: New status (default: COMPLETED)
            
        Returns:
            ServiceResult with updated document data
        """
        update_data = {
            "processed_file_name": processed_file_name,
            "processed_file_size": processed_file_size,
            "processed_s3_location": processed_s3_location,
            "processed_s3_key": processed_s3_key,
            "status": status
        }
        
        logger.info(f"Updating processed info for document {document_id}")
        return await self.update(document_id, update_data)

class DocumentAnalysisService(BaseService):
    """Service for document analysis operations"""
    
    def __init__(self, role: str = "api"):
        super().__init__("document_analysis", role)
    
    async def create_analysis(
        self,
        document_id: str,
        case_id: str,
        analysis_content: str,
        model_used: str,
        tokens_used: Optional[int] = None,
        analysis_reasoning: Optional[str] = None,
        analysis_status: str = "COMPLETED"
    ) -> ServiceResult:
        """
        Create a new document analysis record
        
        Args:
            document_id: UUID of the analyzed document
            case_id: UUID of the associated case
            analysis_content: The analysis content/result
            model_used: Name of the AI model used for analysis
            tokens_used: Number of tokens consumed (optional)
            analysis_reasoning: Reasoning behind the analysis (optional)
            analysis_status: Status of analysis (default: COMPLETED)
            
        Returns:
            ServiceResult with created analysis data
        """
        analysis_data = {
            "document_id": document_id,
            "case_id": case_id,
            "analysis_content": analysis_content,
            "model_used": model_used,
            "analysis_status": analysis_status,
            "analyzed_at": "NOW()",  # Will be handled by SQL
            "context_summary_created": False
        }
        
        if tokens_used is not None:
            analysis_data["tokens_used"] = tokens_used
        
        if analysis_reasoning:
            analysis_data["analysis_reasoning"] = analysis_reasoning
        
        logger.info(f"Creating analysis for document {document_id}")
        return await self.create(analysis_data)
    
    async def get_analysis_by_id(self, analysis_id: str) -> ServiceResult:
        """Get an analysis by its ID"""
        return await self.get_by_id(analysis_id)
    
    async def get_analyses_by_document(self, document_id: str) -> ServiceResult:
        """Get all analyses for a specific document"""
        return await self.get_by_field("document_id", document_id)
    
    async def get_analyses_by_case(self, case_id: str) -> ServiceResult:
        """Get all analyses for a specific case"""
        return await self.get_by_field("case_id", case_id)
    
    async def get_analyses_by_status(self, status: str, limit: int = 100) -> ServiceResult:
        """Get analyses by status"""
        return await self.get_by_field("analysis_status", status, limit)
    
    async def update_analysis_status(self, analysis_id: str, status: str) -> ServiceResult:
        """Update the status of an analysis"""
        logger.info(f"Updating analysis {analysis_id} status to: {status}")
        return await self.update(analysis_id, {"analysis_status": status})
    
    async def mark_context_summary_created(self, analysis_id: str) -> ServiceResult:
        """Mark that a context summary has been created for this analysis"""
        logger.info(f"Marking context summary created for analysis {analysis_id}")
        return await self.update(analysis_id, {"context_summary_created": True})
    
    async def get_pending_context_summaries(self, limit: int = 50) -> ServiceResult:
        """Get analyses that need context summaries created"""
        filters = {
            "context_summary_created": False,
            "analysis_status": "COMPLETED"
        }
        
        return await self.read(
            filters=filters,
            order_by=[{"field": "created_at", "dir": "asc"}],
            limit=limit
        )

# Global service instances
_documents_service: Optional[DocumentsService] = None
_document_analysis_service: Optional[DocumentAnalysisService] = None

def get_documents_service() -> DocumentsService:
    """Get the global documents service instance"""
    global _documents_service
    if _documents_service is None:
        _documents_service = DocumentsService()
    return _documents_service

def get_document_analysis_service() -> DocumentAnalysisService:
    """Get the global document analysis service instance"""
    global _document_analysis_service
    if _document_analysis_service is None:
        _document_analysis_service = DocumentAnalysisService()
    return _document_analysis_service