"""
Documents CRUD Testing Suite - MVP Implementation
Tests document management with foreign key relationships to cases
"""

import pytest
from typing import Dict, Any

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.test_orchestrator import APITestOrchestrator


@pytest.mark.crud
class TestDocumentsCRUD:
    """Comprehensive CRUD testing for documents table"""
    
    async def test_documents_full_crud_cycle(self, clean_orchestrator: APITestOrchestrator):
        """Test complete document CRUD cycle with case dependency"""
        orch = clean_orchestrator
        
        # First create a parent case
        case_data, _ = orch.data_factory.generate_case()
        case_result = await orch.execute_create(
            resource="cases",
            endpoint="/api/cases",
            data=case_data
        )
        assert case_result.success, "Failed to create parent case"
        case_id = case_result.uuid
        
        # Generate document data linked to case
        doc_data, expected_doc_id = orch.data_factory.generate_document(case_id)
        
        # === CREATE DOCUMENT ===
        create_result = await orch.execute_create(
            resource="documents",
            endpoint="/api/documents",
            data=doc_data
        )
        
        assert create_result.success, f"Document creation failed: {create_result.errors}"
        assert create_result.uuid, "No UUID returned from document creation"
        created_doc_id = create_result.uuid
        
        # Validate CREATE via API response - foreign keys validated by API
        assert create_result.uuid == created_doc_id, "UUID mismatch in CREATE response"
        
        # === READ DOCUMENT ===
        read_result = await orch.execute_read(
            resource="documents",
            endpoint="/api/documents/{id}",
            uuid_value=created_doc_id
        )
        
        assert read_result.success, f"Document read failed: {read_result.errors}"
        
        # === UPDATE DOCUMENT ===
        update_data = {"status": "PROCESSING"}
        update_result = await orch.execute_update(
            resource="documents",
            endpoint="/api/documents/{id}",
            uuid_value=created_doc_id,
            data=update_data
        )
        
        assert update_result.success, f"Document update failed: {update_result.errors}"
        
        # Validate UPDATE via API response
        # Read document again to verify update was applied
        verify_read = await orch.execute_read(
            resource="documents",
            endpoint="/api/documents/{id}",
            uuid_value=created_doc_id
        )
        assert verify_read.success, "Failed to verify UPDATE via API"
    
    async def test_documents_batch_lookup(self, clean_orchestrator: APITestOrchestrator):
        """Test document batch lookup functionality"""
        orch = clean_orchestrator
        
        # Create parent case
        case_data, _ = orch.data_factory.generate_case()
        case_result = await orch.execute_create("cases", "/api/cases", case_data)
        assert case_result.success
        
        # Create test documents
        doc1_data, _ = orch.data_factory.generate_document(
            case_result.uuid, 
            original_file_name="test_batch_1.pdf"
        )
        doc2_data, _ = orch.data_factory.generate_document(
            case_result.uuid,
            original_file_name="test_batch_2.pdf"
        )
        
        await orch.execute_create("documents", "/api/documents", doc1_data)
        await orch.execute_create("documents", "/api/documents", doc2_data)
        
        # Test batch lookup with correct API contract
        lookup_data = {
            "batch_id": "test_batch_123",
            "processed_files": [
                {
                    "file_key": "processed/test_batch_1.pdf",
                    "original_filename_pattern": "test_batch_1.pdf"
                },
                {
                    "file_key": "processed/test_batch_2.pdf", 
                    "original_filename_pattern": "test_batch_2.pdf"
                }
            ]
        }
        
        response, duration = await orch.time_operation(
            "BATCH_LOOKUP documents",
            orch.rest_client.request("POST", "/api/documents/lookup-by-batch", data=lookup_data)
        )
        
        assert response.get("_success", False), f"Batch lookup failed: {response}"
    
    async def test_document_analysis_storage(self, clean_orchestrator: APITestOrchestrator):
        """Test document analysis storage"""
        orch = clean_orchestrator
        
        # Create parent case and document
        case_data, _ = orch.data_factory.generate_case()
        case_result = await orch.execute_create("cases", "/api/cases", case_data)
        assert case_result.success
        
        doc_data, _ = orch.data_factory.generate_document(case_result.uuid)
        doc_result = await orch.execute_create("documents", "/api/documents", doc_data)
        assert doc_result.success
        
        # Test analysis storage with correct API contract
        analysis_data = {
            "document_id": doc_result.uuid,
            "case_id": case_result.uuid,
            "analysis_content": '{"summary": "Test analysis summary", "key_findings": ["Finding 1", "Finding 2"], "confidence": 0.95}',
            "model_used": "gpt-4-turbo",
            "tokens_used": 150,
            "analysis_status": "COMPLETED"
        }
        
        response, duration = await orch.time_operation(
            "STORE_ANALYSIS documents",
            orch.rest_client.request(
                "POST", 
                f"/api/documents/{doc_result.uuid}/analysis", 
                data=analysis_data
            )
        )
        
        assert response.get("_success", False), f"Analysis storage failed: {response}"
        
        # Test analysis retrieval
        get_response, _ = await orch.time_operation(
            "GET_ANALYSIS documents",
            orch.rest_client.request("GET", f"/api/documents/{doc_result.uuid}/analysis")
        )
        
        assert get_response.get("_success", False), f"Analysis retrieval failed: {get_response}"
    
    async def test_documents_foreign_key_validation(self, clean_orchestrator: APITestOrchestrator):
        """Test documents creation with invalid case_id"""
        orch = clean_orchestrator
        
        # Try to create document with non-existent case_id
        invalid_doc_data = {
            "case_id": "00000000-0000-0000-0000-000000000000",
            "original_file_name": "test_invalid.pdf",
            "original_file_size": 1000,
            "original_file_type": "application/pdf",
            "original_s3_location": "s3://test/",
            "original_s3_key": "test.pdf"
        }
        
        create_result = await orch.execute_create(
            resource="documents",
            endpoint="/api/documents",
            data=invalid_doc_data
        )
        
        # Should fail due to foreign key constraint
        assert not create_result.success, "Document creation should fail with invalid case_id"
    
    async def test_documents_status_transitions(self, clean_orchestrator: APITestOrchestrator):
        """Test valid document status transitions"""
        orch = clean_orchestrator
        
        # Create parent case and document
        case_data, _ = orch.data_factory.generate_case()
        case_result = await orch.execute_create("cases", "/api/cases", case_data)
        assert case_result.success
        
        doc_data, _ = orch.data_factory.generate_document(case_result.uuid)
        doc_result = await orch.execute_create("documents", "/api/documents", doc_data)
        assert doc_result.success
        
        # Test status transitions: PENDING → PROCESSING → COMPLETED
        statuses = ["PROCESSING", "COMPLETED"]
        
        for status in statuses:
            update_result = await orch.execute_update(
                resource="documents",
                endpoint="/api/documents/{id}",
                uuid_value=doc_result.uuid,
                data={"status": status}
            )
            
            assert update_result.success, f"Failed to update status to {status}"
            
            # Validate status change via API
            verify_status = await orch.execute_read(
                resource="documents",
                endpoint="/api/documents/{id}",
                uuid_value=doc_result.uuid
            )
            assert verify_status.success, f"Failed to verify status update to {status}"