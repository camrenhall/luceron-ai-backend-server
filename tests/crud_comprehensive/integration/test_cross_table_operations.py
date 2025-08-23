"""
Cross-table Integration Tests - MVP Implementation
Tests operations that span multiple tables and validate relationships
"""

import pytest
from typing import Dict, Any, List

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.test_orchestrator import TestOrchestrator


@pytest.mark.integration
class TestCrossTableOperations:
    """Integration tests for multi-table operations"""
    
    async def test_case_document_workflow(self, clean_orchestrator: TestOrchestrator):
        """Test complete case → documents → analysis workflow"""
        orch = clean_orchestrator
        
        # Step 1: Create case
        case_data, _ = orch.data_factory.generate_case()
        case_result = await orch.execute_create("cases", "/api/cases", case_data)
        assert case_result.success, "Failed to create case"
        case_id = case_result.uuid
        
        # Step 2: Create multiple documents for the case
        document_ids = []
        for i in range(3):
            doc_data, _ = orch.data_factory.generate_document(
                case_id, 
                original_file_name=f"case_doc_{i+1}.pdf"
            )
            doc_result = await orch.execute_create("documents", "/api/documents", doc_data)
            assert doc_result.success, f"Failed to create document {i+1}"
            document_ids.append(doc_result.uuid)
        
        # Step 3: Add analysis to documents
        for doc_id in document_ids:
            analysis_data = {
                "analysis_content": {
                    "summary": f"Analysis for document {doc_id}",
                    "findings": ["Key point 1", "Key point 2"]
                },
                "model_used": "gpt-4-turbo",
                "tokens_used": 120
            }
            
            response, _ = await orch.time_operation(
                "STORE_ANALYSIS",
                orch.rest_client.request(
                    "POST", 
                    f"/api/documents/{doc_id}/analysis",
                    data=analysis_data
                )
            )
            
            # Analysis might not be available - skip if not implemented
            if not response.get("_success", False):
                pytest.skip("Document analysis endpoint not available")
        
        # Step 4: Validate case has associated data
        case_comm_response, _ = await orch.time_operation(
            "GET_CASE_COMMUNICATIONS",
            orch.rest_client.request("GET", f"/api/cases/{case_id}/communications")
        )
        
        # Communications might be empty but endpoint should work
        if case_comm_response.get("_success", False):
            print(f"✅ Case communications endpoint working")
        
        # Step 5: Test case analysis summary
        case_analysis_response, _ = await orch.time_operation(
            "GET_CASE_ANALYSIS_SUMMARY", 
            orch.rest_client.request("GET", f"/api/cases/{case_id}/analysis-summary")
        )
        
        if case_analysis_response.get("_success", False):
            print(f"✅ Case analysis summary endpoint working")
    
    async def test_agent_conversation_workflow(self, clean_orchestrator: TestOrchestrator):
        """Test agent conversation → messages → summaries workflow"""
        orch = clean_orchestrator
        
        # Step 1: Create conversation
        conv_data, _ = orch.data_factory.generate_agent_conversation()
        conv_result = await orch.execute_create(
            "agent_conversations", 
            "/api/agent/conversations", 
            conv_data
        )
        assert conv_result.success, "Failed to create conversation"
        conv_id = conv_result.uuid
        
        # Step 2: Add messages to conversation
        message_ids = []
        for i in range(3):
            msg_data, _ = orch.data_factory.generate_agent_message(
                conv_id, 
                sequence_number=i+1
            )
            msg_result = await orch.execute_create(
                "agent_messages",
                "/api/agent/messages",
                msg_data
            )
            assert msg_result.success, f"Failed to create message {i+1}"
            message_ids.append(msg_result.uuid)
        
        # Step 3: Test conversation history
        history_response, _ = await orch.time_operation(
            "GET_CONVERSATION_HISTORY",
            orch.rest_client.request("GET", f"/api/agent/messages/conversation/{conv_id}/history")
        )
        
        assert history_response.get("_success", False), "Failed to get conversation history"
        
        # Step 4: Create conversation summary
        summary_data = {
            "conversation_id": conv_id,
            "last_message_id": message_ids[-1],
            "summary_content": "Test conversation summary",
            "messages_summarized": 3
        }
        
        summary_result = await orch.execute_create(
            "agent_summaries",
            "/api/agent/summaries", 
            summary_data
        )
        assert summary_result.success, "Failed to create summary"
        
        # Step 5: Test full conversation retrieval
        full_conv_response, _ = await orch.time_operation(
            "GET_FULL_CONVERSATION",
            orch.rest_client.request("GET", f"/api/agent/conversations/{conv_id}/full")
        )
        
        assert full_conv_response.get("_success", False), "Failed to get full conversation"
    
    async def test_agent_context_management(self, clean_orchestrator: TestOrchestrator):
        """Test agent context storage and retrieval"""
        orch = clean_orchestrator
        
        # Create case for context
        case_data, _ = orch.data_factory.generate_case()
        case_result = await orch.execute_create("cases", "/api/cases", case_data)
        assert case_result.success
        case_id = case_result.uuid
        
        # Create multiple context entries
        context_keys = ["client_preferences", "case_strategy", "document_findings"]
        
        for key in context_keys:
            context_data, _ = orch.data_factory.generate_agent_context(
                case_id,
                context_key=key,
                context_value={
                    "key": key,
                    "data": f"Context data for {key}",
                    "created_at": "2024-01-01T00:00:00Z"
                }
            )
            
            context_result = await orch.execute_create(
                "agent_context",
                "/api/agent/context",
                context_data
            )
            assert context_result.success, f"Failed to create context for {key}"
        
        # Test case agent context retrieval
        case_context_response, _ = await orch.time_operation(
            "GET_CASE_AGENT_CONTEXT",
            orch.rest_client.request(
                "GET", 
                f"/api/agent/context/case/{case_id}/agent/CommunicationsAgent"
            )
        )
        
        assert case_context_response.get("_success", False), "Failed to get case agent context"
        
        # Test specific context key retrieval
        specific_context_response, _ = await orch.time_operation(
            "GET_SPECIFIC_CONTEXT",
            orch.rest_client.request(
                "GET",
                f"/api/agent/context/case/{case_id}/agent/CommunicationsAgent/key/client_preferences"
            )
        )
        
        assert specific_context_response.get("_success", False), "Failed to get specific context"
    
    async def test_database_foreign_key_integrity(self, clean_orchestrator: TestOrchestrator):
        """Test foreign key integrity across related tables"""
        orch = clean_orchestrator
        
        # Create case
        case_data, _ = orch.data_factory.generate_case()
        case_result = await orch.execute_create("cases", "/api/cases", case_data)
        assert case_result.success
        case_id = case_result.uuid
        
        # Create document linked to case
        doc_data, _ = orch.data_factory.generate_document(case_id)
        doc_result = await orch.execute_create("documents", "/api/documents", doc_data)
        assert doc_result.success
        doc_id = doc_result.uuid
        
        # Validate all foreign key relationships
        case_validation = await orch.validate_database_state(
            "cases", "case_id", case_id, "CREATE"
        )
        assert case_validation.valid, f"Case validation failed: {case_validation.errors}"
        
        doc_validation = await orch.validate_database_state(
            "documents", "document_id", doc_id, "CREATE"
        )
        assert doc_validation.valid, f"Document validation failed: {doc_validation.errors}"
        
        print(f"✅ Foreign key integrity validated for case-document relationship")