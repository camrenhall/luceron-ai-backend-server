"""
Agent State CRUD Testing Suite - Complete Implementation  
Tests all agent state tables: conversations, messages, summaries, context
CRITICAL: These are core functionality tables, not optional
"""

import pytest
from typing import Dict, Any

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.test_orchestrator import CRUDTestOrchestrator


@pytest.mark.crud
class TestAgentConversationsCRUD:
    """Complete CRUD testing for agent_conversations table"""
    
    async def test_agent_conversations_full_crud_cycle(self, clean_orchestrator: CRUDTestOrchestrator):
        """Test complete CREATE → READ → UPDATE → DELETE cycle for conversations"""
        orch = clean_orchestrator
        
        # Generate conversation data
        conv_data, expected_conv_id = orch.data_factory.generate_agent_conversation()
        
        # === CREATE ===
        create_result = await orch.execute_create(
            resource="agent_conversations",
            endpoint="/api/agent/conversations",
            data=conv_data
        )
        
        assert create_result.success, f"Conversation creation failed: {create_result.errors}"
        assert create_result.uuid, "No UUID returned from conversation creation"
        created_conv_id = create_result.uuid
        
        # Database validation after CREATE
        create_validation = await orch.validate_database_state(
            table="agent_conversations", 
            uuid_field="conversation_id", 
            uuid_value=created_conv_id, 
            operation="CREATE"
        )
        assert create_validation.valid, f"Database validation failed after CREATE: {create_validation.errors}"
        
        # === READ ===
        read_result = await orch.execute_read(
            resource="agent_conversations",
            endpoint="/api/agent/conversations/{id}",
            uuid_value=created_conv_id
        )
        
        assert read_result.success, f"Conversation read failed: {read_result.errors}"
        
        # === UPDATE ===
        update_data = {"status": "COMPLETED", "total_tokens_used": 500}
        update_result = await orch.execute_update(
            resource="agent_conversations",
            endpoint="/api/agent/conversations/{id}",
            uuid_value=created_conv_id,
            data=update_data
        )
        
        assert update_result.success, f"Conversation update failed: {update_result.errors}"
        
        # Database validation after UPDATE
        update_validation = await orch.validate_database_state(
            table="agent_conversations",
            uuid_field="conversation_id", 
            uuid_value=created_conv_id,
            operation="UPDATE"
        )
        assert update_validation.valid, f"Database validation failed after UPDATE: {update_validation.errors}"
        
        # === DELETE ===
        delete_result = await orch.execute_delete(
            resource="agent_conversations",
            endpoint="/api/agent/conversations/{id}",
            uuid_value=created_conv_id
        )
        
        assert delete_result.success, f"Conversation delete failed: {delete_result.errors}"
        
        # Database validation after DELETE
        delete_validation = await orch.validate_database_state(
            table="agent_conversations",
            uuid_field="conversation_id",
            uuid_value=created_conv_id,
            operation="DELETE"
        )
        assert delete_validation.valid, f"Database validation failed after DELETE: {delete_validation.errors}"


@pytest.mark.crud
class TestAgentMessagesCRUD:
    """Complete CRUD testing for agent_messages table"""
    
    async def test_agent_messages_full_crud_cycle(self, clean_orchestrator: CRUDTestOrchestrator):
        """Test complete message CRUD cycle with conversation dependency"""
        orch = clean_orchestrator
        
        # First create parent conversation
        conv_data, _ = orch.data_factory.generate_agent_conversation()
        conv_result = await orch.execute_create(
            resource="agent_conversations",
            endpoint="/api/agent/conversations",
            data=conv_data
        )
        assert conv_result.success, "Failed to create parent conversation"
        conv_id = conv_result.uuid
        
        # Generate message data linked to conversation
        msg_data, expected_msg_id = orch.data_factory.generate_agent_message(conv_id)
        
        # === CREATE MESSAGE ===
        create_result = await orch.execute_create(
            resource="agent_messages",
            endpoint="/api/agent/messages",
            data=msg_data
        )
        
        assert create_result.success, f"Message creation failed: {create_result.errors}"
        assert create_result.uuid, "No UUID returned from message creation"
        created_msg_id = create_result.uuid
        
        # Validate database state and foreign keys
        create_validation = await orch.validate_database_state(
            table="agent_messages",
            uuid_field="message_id",
            uuid_value=created_msg_id,
            operation="CREATE"
        )
        assert create_validation.valid, f"Database validation failed after CREATE: {create_validation.errors}"
        
        # === READ MESSAGE ===
        read_result = await orch.execute_read(
            resource="agent_messages",
            endpoint="/api/agent/messages/{id}",
            uuid_value=created_msg_id
        )
        
        assert read_result.success, f"Message read failed: {read_result.errors}"
        
        # === UPDATE MESSAGE ===
        update_data = {
            "content": {"text": "Updated message content", "updated": True},
            "total_tokens": 150
        }
        update_result = await orch.execute_update(
            resource="agent_messages",
            endpoint="/api/agent/messages/{id}",
            uuid_value=created_msg_id,
            data=update_data
        )
        
        assert update_result.success, f"Message update failed: {update_result.errors}"
        
        # === DELETE MESSAGE ===
        delete_result = await orch.execute_delete(
            resource="agent_messages",
            endpoint="/api/agent/messages/{id}",
            uuid_value=created_msg_id
        )
        
        assert delete_result.success, f"Message delete failed: {delete_result.errors}"
    
    async def test_conversation_history_endpoint(self, clean_orchestrator: CRUDTestOrchestrator):
        """Test conversation history retrieval - CRITICAL endpoint"""
        orch = clean_orchestrator
        
        # Create conversation
        conv_data, _ = orch.data_factory.generate_agent_conversation()
        conv_result = await orch.execute_create("agent_conversations", "/api/agent/conversations", conv_data)
        assert conv_result.success
        conv_id = conv_result.uuid
        
        # Create multiple messages
        for i in range(3):
            msg_data, _ = orch.data_factory.generate_agent_message(conv_id, sequence_number=i+1)
            msg_result = await orch.execute_create("agent_messages", "/api/agent/messages", msg_data)
            assert msg_result.success, f"Failed to create message {i+1}"
        
        # Test history endpoint
        response, duration = await orch.time_operation(
            "GET_CONVERSATION_HISTORY",
            orch.rest_client.request("GET", f"/api/agent/messages/conversation/{conv_id}/history")
        )
        
        assert response.get("_success", False), f"Conversation history failed: {response}"


@pytest.mark.crud
class TestAgentSummariesCRUD:
    """Complete CRUD testing for agent_summaries table"""
    
    async def test_agent_summaries_full_crud_cycle(self, clean_orchestrator: CRUDTestOrchestrator):
        """Test complete summary CRUD cycle"""
        orch = clean_orchestrator
        
        # Create conversation and message for foreign key dependencies
        conv_data, _ = orch.data_factory.generate_agent_conversation()
        conv_result = await orch.execute_create("agent_conversations", "/api/agent/conversations", conv_data)
        assert conv_result.success
        conv_id = conv_result.uuid
        
        msg_data, _ = orch.data_factory.generate_agent_message(conv_id)
        msg_result = await orch.execute_create("agent_messages", "/api/agent/messages", msg_data)
        assert msg_result.success
        msg_id = msg_result.uuid
        
        # Create summary
        summary_data = {
            "conversation_id": conv_id,
            "last_message_id": msg_id,
            "summary_content": "Comprehensive test summary covering key conversation points",
            "messages_summarized": 5
        }
        
        # === CREATE SUMMARY ===
        create_result = await orch.execute_create(
            resource="agent_summaries",
            endpoint="/api/agent/summaries",
            data=summary_data
        )
        
        assert create_result.success, f"Summary creation failed: {create_result.errors}"
        summary_id = create_result.uuid
        
        # Database validation
        create_validation = await orch.validate_database_state(
            table="agent_summaries",
            uuid_field="summary_id",
            uuid_value=summary_id,
            operation="CREATE"
        )
        assert create_validation.valid, f"Database validation failed: {create_validation.errors}"
        
        # === READ SUMMARY ===
        read_result = await orch.execute_read(
            resource="agent_summaries",
            endpoint="/api/agent/summaries/{id}",
            uuid_value=summary_id
        )
        
        assert read_result.success, f"Summary read failed: {read_result.errors}"
        
        # === UPDATE SUMMARY ===
        update_data = {
            "summary_content": "Updated summary with additional insights",
            "messages_summarized": 7
        }
        update_result = await orch.execute_update(
            resource="agent_summaries",
            endpoint="/api/agent/summaries/{id}",
            uuid_value=summary_id,
            data=update_data
        )
        
        assert update_result.success, f"Summary update failed: {update_result.errors}"
        
        # === DELETE SUMMARY ===
        delete_result = await orch.execute_delete(
            resource="agent_summaries",
            endpoint="/api/agent/summaries/{id}",
            uuid_value=summary_id
        )
        
        assert delete_result.success, f"Summary delete failed: {delete_result.errors}"
    
    async def test_latest_summary_endpoint(self, clean_orchestrator: CRUDTestOrchestrator):
        """Test get latest summary - CRITICAL functionality"""
        orch = clean_orchestrator
        
        # Create conversation
        conv_data, _ = orch.data_factory.generate_agent_conversation()
        conv_result = await orch.execute_create("agent_conversations", "/api/agent/conversations", conv_data)
        assert conv_result.success
        conv_id = conv_result.uuid
        
        # Create summary
        summary_data = {
            "conversation_id": conv_id,
            "summary_content": "Latest summary test",
            "messages_summarized": 3
        }
        
        summary_result = await orch.execute_create("agent_summaries", "/api/agent/summaries", summary_data)
        assert summary_result.success
        
        # Test latest summary endpoint
        response, duration = await orch.time_operation(
            "GET_LATEST_SUMMARY",
            orch.rest_client.request("GET", f"/api/agent/summaries/conversation/{conv_id}/latest")
        )
        
        assert response.get("_success", False), f"Latest summary retrieval failed: {response}"


@pytest.mark.crud
class TestAgentContextCRUD:
    """Complete CRUD testing for agent_context table"""
    
    async def test_agent_context_full_crud_cycle(self, clean_orchestrator: CRUDTestOrchestrator):
        """Test complete context CRUD cycle with case dependency"""
        orch = clean_orchestrator
        
        # Create parent case
        case_data, _ = orch.data_factory.generate_case()
        case_result = await orch.execute_create("cases", "/api/cases", case_data)
        assert case_result.success
        case_id = case_result.uuid
        
        # Generate context data
        context_data, expected_context_id = orch.data_factory.generate_agent_context(case_id)
        
        # === CREATE CONTEXT ===
        create_result = await orch.execute_create(
            resource="agent_context",
            endpoint="/api/agent/context",
            data=context_data
        )
        
        assert create_result.success, f"Context creation failed: {create_result.errors}"
        context_id = create_result.uuid
        
        # Database validation
        create_validation = await orch.validate_database_state(
            table="agent_context",
            uuid_field="context_id",
            uuid_value=context_id,
            operation="CREATE"
        )
        assert create_validation.valid, f"Database validation failed: {create_validation.errors}"
        
        # === READ CONTEXT ===
        read_result = await orch.execute_read(
            resource="agent_context",
            endpoint="/api/agent/context/{id}",
            uuid_value=context_id
        )
        
        assert read_result.success, f"Context read failed: {read_result.errors}"
        
        # === UPDATE CONTEXT ===
        update_data = {
            "context_value": {
                "updated": True,
                "version": 2,
                "data": "Updated context value"
            }
        }
        update_result = await orch.execute_update(
            resource="agent_context",
            endpoint="/api/agent/context/{id}",
            uuid_value=context_id,
            data=update_data
        )
        
        assert update_result.success, f"Context update failed: {update_result.errors}"
        
        # === DELETE CONTEXT ===
        delete_result = await orch.execute_delete(
            resource="agent_context",
            endpoint="/api/agent/context/{id}",
            uuid_value=context_id
        )
        
        assert delete_result.success, f"Context delete failed: {delete_result.errors}"
    
    async def test_case_agent_context_endpoints(self, clean_orchestrator: CRUDTestOrchestrator):
        """Test case-specific context retrieval - CRITICAL functionality"""
        orch = clean_orchestrator
        
        # Create case
        case_data, _ = orch.data_factory.generate_case()
        case_result = await orch.execute_create("cases", "/api/cases", case_data)
        assert case_result.success
        case_id = case_result.uuid
        
        # Create multiple context entries
        context_keys = ["client_preferences", "case_strategy", "document_insights"]
        
        for key in context_keys:
            context_data, _ = orch.data_factory.generate_agent_context(
                case_id, 
                context_key=key,
                context_value={"key": key, "test_data": True}
            )
            context_result = await orch.execute_create("agent_context", "/api/agent/context", context_data)
            assert context_result.success, f"Failed to create context for {key}"
        
        # Test case agent context retrieval
        response, duration = await orch.time_operation(
            "GET_CASE_AGENT_CONTEXT",
            orch.rest_client.request("GET", f"/api/agent/context/case/{case_id}/agent/CommunicationsAgent")
        )
        
        assert response.get("_success", False), f"Case agent context retrieval failed: {response}"
        
        # Test specific context key retrieval
        specific_response, duration = await orch.time_operation(
            "GET_SPECIFIC_CONTEXT_KEY",
            orch.rest_client.request("GET", f"/api/agent/context/case/{case_id}/agent/CommunicationsAgent/key/client_preferences")
        )
        
        assert specific_response.get("_success", False), f"Specific context key retrieval failed: {specific_response}"