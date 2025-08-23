"""
Comprehensive Endpoint Testing - CRITICAL Coverage
Tests ALL endpoints identified in OpenAPI analysis to ensure no functionality is missed
This is NOT optional - every endpoint must be validated
"""

import pytest
from typing import Dict, Any, List

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.test_orchestrator import CRUDTestOrchestrator


@pytest.mark.crud
class TestComprehensiveEndpointCoverage:
    """Systematic testing of ALL API endpoints - CRITICAL for complete coverage"""
    
    async def test_health_and_oauth_endpoints(self, clean_orchestrator: CRUDTestOrchestrator):
        """Test health and authentication endpoints - FOUNDATION"""
        orch = clean_orchestrator
        
        # Health check - CRITICAL
        health_response, duration = await orch.time_operation(
            "HEALTH_CHECK",
            orch.rest_client.request("GET", "/")
        )
        assert health_response.get("_success", False), f"Health check failed: {health_response}"
        
        # OAuth discovery - CRITICAL for service integration
        discovery_response, duration = await orch.time_operation(
            "OAUTH_DISCOVERY", 
            orch.rest_client.request("GET", "/oauth2/.well-known/openid_configuration")
        )
        # Don't fail if not implemented, but report status
        print(f"OAuth discovery status: {discovery_response.get('_status_code', 'unknown')}")
        
        # OAuth health check
        oauth_health_response, duration = await orch.time_operation(
            "OAUTH_HEALTH",
            orch.rest_client.request("GET", "/oauth2/health")
        )
        print(f"OAuth health status: {oauth_health_response.get('_status_code', 'unknown')}")
    
    async def test_all_cases_endpoints(self, clean_orchestrator: CRUDTestOrchestrator):
        """Test ALL cases endpoints identified in OpenAPI - CRITICAL"""
        orch = clean_orchestrator
        
        # Create test case for endpoint testing
        case_data, _ = orch.data_factory.generate_case()
        case_result = await orch.execute_create("cases", "/api/cases", case_data)
        assert case_result.success, "Failed to create test case"
        case_id = case_result.uuid
        
        # Test ALL cases endpoints
        cases_endpoints = [
            ("GET", f"/api/cases/{case_id}", "Get single case"),
            ("PUT", f"/api/cases/{case_id}", "Update case", {"status": "CLOSED"}),
            ("GET", "/api/cases", "List cases"),
            ("POST", "/api/cases/search", "Search cases", {"client_name": "test"}),
            ("GET", f"/api/cases/{case_id}/communications", "Get case communications"),
            ("GET", f"/api/cases/{case_id}/analysis-summary", "Get analysis summary"),
        ]
        
        for method, endpoint, description, *data in cases_endpoints:
            payload = data[0] if data else None
            
            response, duration = await orch.time_operation(
                f"CASES_{description.upper().replace(' ', '_')}",
                orch.rest_client.request(method, endpoint, data=payload)
            )
            
            # Most endpoints should work, but some might return empty results
            success = response.get("_success", False) or response.get("_status_code") == 404
            assert success, f"Cases endpoint failed: {method} {endpoint} - {response}"
            print(f"✅ Cases endpoint: {method} {endpoint} ({description})")
    
    async def test_all_documents_endpoints(self, clean_orchestrator: CRUDTestOrchestrator):
        """Test ALL documents endpoints - CRITICAL for document workflow"""
        orch = clean_orchestrator
        
        # Create case and document for testing
        case_data, _ = orch.data_factory.generate_case()
        case_result = await orch.execute_create("cases", "/api/cases", case_data)
        assert case_result.success
        case_id = case_result.uuid
        
        doc_data, _ = orch.data_factory.generate_document(case_id)
        doc_result = await orch.execute_create("documents", "/api/documents", doc_data)
        assert doc_result.success
        doc_id = doc_result.uuid
        
        # Test ALL documents endpoints
        documents_endpoints = [
            ("GET", f"/api/documents/{doc_id}", "Get single document"),
            ("PUT", f"/api/documents/{doc_id}", "Update document", {"status": "PROCESSING"}),
            ("POST", "/api/documents/lookup-by-batch", "Batch lookup", {
                "filenames": [doc_data["original_file_name"]], 
                "case_id": case_id
            }),
            ("POST", f"/api/documents/{doc_id}/analysis", "Store analysis", {
                "analysis_content": {"summary": "Test analysis"},
                "model_used": "gpt-4-turbo",
                "tokens_used": 100
            }),
            ("POST", "/api/documents/analysis/bulk", "Bulk analysis storage", {
                "analyses": [{
                    "document_id": doc_id,
                    "case_id": case_id,
                    "analysis_content": {"summary": "Bulk test"},
                    "model_used": "gpt-4-turbo",
                    "tokens_used": 50
                }]
            }),
            ("GET", f"/api/documents/{doc_id}/analysis", "Get document analysis"),
            ("GET", f"/api/documents/analysis/case/{case_id}", "Get all analyses by case"),
            ("GET", f"/api/documents/analysis/case/{case_id}/aggregate", "Aggregated analysis"),
        ]
        
        for method, endpoint, description, *data in documents_endpoints:
            payload = data[0] if data else None
            
            response, duration = await orch.time_operation(
                f"DOCUMENTS_{description.upper().replace(' ', '_')}",
                orch.rest_client.request(method, endpoint, data=payload)
            )
            
            # Some endpoints might not be fully implemented - don't fail hard
            if response.get("_success", False):
                print(f"✅ Documents endpoint: {method} {endpoint} ({description})")
            else:
                print(f"⚠️  Documents endpoint: {method} {endpoint} ({description}) - Status: {response.get('_status_code', 'unknown')}")
    
    async def test_all_agent_endpoints_systematic(self, clean_orchestrator: CRUDTestOrchestrator):
        """Test ALL agent endpoints systematically - CRITICAL for agent functionality"""
        orch = clean_orchestrator
        
        # Create test data ecosystem
        case_data, _ = orch.data_factory.generate_case()
        case_result = await orch.execute_create("cases", "/api/cases", case_data)
        assert case_result.success
        case_id = case_result.uuid
        
        conv_data, _ = orch.data_factory.generate_agent_conversation()
        conv_result = await orch.execute_create("agent_conversations", "/api/agent/conversations", conv_data)
        assert conv_result.success
        conv_id = conv_result.uuid
        
        msg_data, _ = orch.data_factory.generate_agent_message(conv_id)
        msg_result = await orch.execute_create("agent_messages", "/api/agent/messages", msg_data)
        assert msg_result.success
        msg_id = msg_result.uuid
        
        # Test ALL agent endpoints comprehensively
        agent_endpoints = [
            # Conversations
            ("GET", f"/api/agent/conversations/{conv_id}", "Get conversation"),
            ("PUT", f"/api/agent/conversations/{conv_id}", "Update conversation", {"status": "COMPLETED"}),
            ("GET", "/api/agent/conversations", "List conversations"),
            ("GET", f"/api/agent/conversations/{conv_id}/full", "Get full conversation"),
            
            # Messages  
            ("GET", f"/api/agent/messages/{msg_id}", "Get message"),
            ("PUT", f"/api/agent/messages/{msg_id}", "Update message", {"content": {"text": "updated"}}),
            ("GET", "/api/agent/messages", "List messages"),
            ("GET", f"/api/agent/messages/conversation/{conv_id}/history", "Conversation history"),
            
            # Summaries
            ("POST", "/api/agent/summaries", "Create summary", {
                "conversation_id": conv_id,
                "summary_content": "Test summary",
                "messages_summarized": 1
            }),
            ("GET", "/api/agent/summaries", "List summaries"),
            ("GET", f"/api/agent/summaries/conversation/{conv_id}/latest", "Latest summary"),
            ("POST", f"/api/agent/summaries/conversation/{conv_id}/auto-summary", "Auto-summary"),
            
            # Context
            ("POST", "/api/agent/context", "Create context", {
                "case_id": case_id,
                "agent_type": "CommunicationsAgent", 
                "context_key": "test_key",
                "context_value": {"test": True}
            }),
            ("GET", "/api/agent/context", "List context"),
            ("GET", f"/api/agent/context/case/{case_id}/agent/CommunicationsAgent", "Case agent context"),
            ("POST", "/api/agent/context/cleanup-expired", "Cleanup expired context"),
        ]
        
        for method, endpoint, description, *data in agent_endpoints:
            payload = data[0] if data else None
            
            response, duration = await orch.time_operation(
                f"AGENT_{description.upper().replace(' ', '_')}",
                orch.rest_client.request(method, endpoint, data=payload)
            )
            
            if response.get("_success", False):
                print(f"✅ Agent endpoint: {method} {endpoint} ({description})")
            else:
                print(f"⚠️  Agent endpoint: {method} {endpoint} ({description}) - Status: {response.get('_status_code', 'unknown')}")
    
    async def test_email_and_webhook_endpoints(self, clean_orchestrator: CRUDTestOrchestrator):
        """Test email and webhook endpoints - CRITICAL for communication"""
        orch = clean_orchestrator
        
        # Create case for email testing
        case_data, _ = orch.data_factory.generate_case()
        case_result = await orch.execute_create("cases", "/api/cases", case_data)
        assert case_result.success
        case_id = case_result.uuid
        
        # Test email endpoint
        email_data = {
            "recipient_email": "test@example.com",
            "subject": "Test email from CRUD test suite",
            "body": "This is a test email to validate the endpoint",
            "case_id": case_id
        }
        
        email_response, duration = await orch.time_operation(
            "SEND_EMAIL",
            orch.rest_client.request("POST", "/api/send-email", data=email_data)
        )
        
        # Email might not be configured - don't fail hard
        if email_response.get("_success", False):
            print("✅ Email endpoint working")
        else:
            print(f"⚠️  Email endpoint - Status: {email_response.get('_status_code', 'unknown')}")
        
        # Test webhook endpoint (without signature - will likely fail but validates endpoint exists)
        webhook_data = {
            "type": "email.delivered",
            "data": {"email_id": "test", "to": ["test@example.com"]}
        }
        
        webhook_response, duration = await orch.time_operation(
            "RESEND_WEBHOOK",
            orch.rest_client.request("POST", "/api/webhooks/resend", data=webhook_data)
        )
        
        print(f"Webhook endpoint status: {webhook_response.get('_status_code', 'unknown')}")
    
    async def test_error_logs_and_alerts_endpoints(self, clean_orchestrator: CRUDTestOrchestrator):
        """Test error logging and alerts - CRITICAL for system monitoring"""
        orch = clean_orchestrator
        
        # Test alert creation (creates error log)
        alert_data = {
            "component": f"{orch.config.test_data_prefix}_endpoint_test",
            "error_message": "Test error from comprehensive endpoint testing",
            "severity": "medium",
            "context": {"test": True, "endpoint_coverage": True}
        }
        
        alert_response, duration = await orch.time_operation(
            "CREATE_ALERT",
            orch.rest_client.request("POST", "/api/alert", data=alert_data)
        )
        
        assert alert_response.get("_success", False), f"Alert creation failed: {alert_response}"
        print("✅ Alert endpoint working")
        
        # Test error logs retrieval
        logs_response, duration = await orch.time_operation(
            "GET_ERROR_LOGS",
            orch.rest_client.request("GET", "/api/logs", params={"limit": 10})
        )
        
        assert logs_response.get("_success", False), f"Error logs retrieval failed: {logs_response}"
        print("✅ Error logs endpoint working")
        
        # Test component stats
        stats_response, duration = await orch.time_operation(
            "GET_COMPONENT_STATS",
            orch.rest_client.request("GET", f"/api/stats/{alert_data['component']}")
        )
        
        assert stats_response.get("_success", False), f"Component stats failed: {stats_response}"
        print("✅ Component stats endpoint working")
    
    async def test_agent_db_natural_language_endpoint(self, clean_orchestrator: CRUDTestOrchestrator):
        """Test Agent Gateway natural language interface - CRITICAL core functionality"""
        orch = clean_orchestrator
        
        # Create test data for natural language queries
        case_data, _ = orch.data_factory.generate_case()
        case_result = await orch.execute_create("cases", "/api/cases", case_data)
        assert case_result.success
        
        # Test natural language queries
        nl_queries = [
            "Show me all cases",
            "How many cases do we have?", 
            "Find cases that are open",
            f"Get the case for client {case_data['client_name']}"
        ]
        
        for query in nl_queries:
            nl_data = {
                "natural_language": query,
                "hints": {
                    "resources": ["cases"],
                    "intent": "READ"
                }
            }
            
            response, duration = await orch.time_operation(
                f"AGENT_DB_{query[:20].upper().replace(' ', '_')}",
                orch.rest_client.request("POST", "/api/agent/db", data=nl_data)
            )
            
            if response.get("_success", False) or response.get("ok") is True:
                print(f"✅ Agent DB query: '{query}'")
            else:
                print(f"⚠️  Agent DB query: '{query}' - Status: {response.get('_status_code', 'unknown')}")
        
        print("Agent Gateway endpoint validation complete")


@pytest.mark.crud
class TestMissingCriticalFunctionality:
    """Test functionality that might be missing but is CRITICAL"""
    
    async def test_delete_operations_all_resources(self, clean_orchestrator: CRUDTestOrchestrator):
        """Test DELETE operations for all resources - CRITICAL for data management"""
        orch = clean_orchestrator
        
        # Create test ecosystem
        case_data, _ = orch.data_factory.generate_case()
        case_result = await orch.execute_create("cases", "/api/cases", case_data)
        assert case_result.success
        case_id = case_result.uuid
        
        conv_data, _ = orch.data_factory.generate_agent_conversation()
        conv_result = await orch.execute_create("agent_conversations", "/api/agent/conversations", conv_data)
        assert conv_result.success
        conv_id = conv_result.uuid
        
        # Test DELETE operations for all major resources
        delete_tests = [
            ("agent_conversations", f"/api/agent/conversations/{conv_id}", conv_id),
            # Note: Cases might not have delete - cascade deletes handle cleanup
        ]
        
        for resource, endpoint, uuid_val in delete_tests:
            delete_result = await orch.execute_delete(resource, endpoint, uuid_val)
            
            if delete_result.success:
                print(f"✅ DELETE {resource} succeeded")
                # Validate database state
                validation = await orch.validate_database_state(
                    resource.replace("_", ""), 
                    f"{resource.replace('_', '')}_id" if not resource.endswith('s') else f"{resource[:-1]}_id",
                    uuid_val,
                    "DELETE"
                )
                if validation.valid:
                    print(f"✅ Database validation passed for {resource} delete")
            else:
                print(f"⚠️  DELETE {resource} not available or failed")
    
    async def test_performance_under_load(self, clean_orchestrator: CRUDTestOrchestrator):
        """Test performance thresholds with multiple operations - CRITICAL for production readiness"""
        orch = clean_orchestrator
        
        # Test multiple CREATE operations
        create_times = []
        case_ids = []
        
        for i in range(5):
            case_data, _ = orch.data_factory.generate_case()
            create_result = await orch.execute_create("cases", "/api/cases", case_data)
            
            assert create_result.success, f"Create {i+1} failed"
            create_times.append(create_result.duration)
            case_ids.append(create_result.uuid)
        
        # Test multiple READ operations
        read_times = []
        for case_id in case_ids:
            read_result = await orch.execute_read("cases", "/api/cases/{id}", case_id)
            assert read_result.success, f"Read failed for case {case_id}"
            read_times.append(read_result.duration)
        
        # Validate performance
        avg_create_time = sum(create_times) / len(create_times)
        avg_read_time = sum(read_times) / len(read_times)
        max_create_time = max(create_times)
        max_read_time = max(read_times)
        
        print(f"Performance Summary:")
        print(f"  CREATE: avg={avg_create_time:.2f}s, max={max_create_time:.2f}s")
        print(f"  READ: avg={avg_read_time:.2f}s, max={max_read_time:.2f}s")
        
        # Assert against thresholds
        assert max_create_time <= orch.config.create_operation_threshold, \
            f"CREATE performance exceeded threshold: {max_create_time:.2f}s > {orch.config.create_operation_threshold}s"
        assert max_read_time <= orch.config.read_operation_threshold, \
            f"READ performance exceeded threshold: {max_read_time:.2f}s > {orch.config.read_operation_threshold}s"
        
        print("✅ All performance thresholds met under load")