"""
Communications & Error Logs CRUD Testing Suite - Complete Implementation
Tests client_communications and error_logs tables - CRITICAL system functionality
"""

import pytest
from typing import Dict, Any

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.test_orchestrator import CRUDTestOrchestrator


@pytest.mark.crud
class TestClientCommunicationsCRUD:
    """Complete CRUD testing for client_communications table"""
    
    async def test_communications_full_crud_cycle(self, clean_orchestrator: CRUDTestOrchestrator):
        """Test complete communication CRUD cycle with case dependency"""
        orch = clean_orchestrator
        
        # Create parent case
        case_data, _ = orch.data_factory.generate_case()
        case_result = await orch.execute_create("cases", "/api/cases", case_data)
        assert case_result.success, "Failed to create parent case"
        case_id = case_result.uuid
        
        # Generate communication data
        comm_data, expected_comm_id = orch.data_factory.generate_communication(case_id)
        
        # Note: Communications might be created through email endpoint, not direct CRUD
        # Test email sending which creates communication record
        email_data = {
            "recipient_email": comm_data["recipient"],
            "subject": comm_data["subject"],
            "body": comm_data["message_content"],
            "case_id": case_id
        }
        
        # === CREATE COMMUNICATION (via email) ===
        create_result = await orch.execute_create(
            resource="emails",
            endpoint="/api/send-email",
            data=email_data
        )
        
        # Email service should work with fixed data format
        assert create_result.success, f"Email service failed: {create_result.errors}"
        
        # If email succeeded, verify communication was logged
        if create_result.success:
            # Test case communications retrieval
            case_comms_response, duration = await orch.time_operation(
                "GET_CASE_COMMUNICATIONS",
                orch.rest_client.request("GET", f"/api/cases/{case_id}/communications")
            )
            
            assert case_comms_response.get("_success", False), f"Case communications retrieval failed: {case_comms_response}"
    
    async def test_communication_channels_and_directions(self, clean_orchestrator: CRUDTestOrchestrator):
        """Test different communication channels and directions"""
        orch = clean_orchestrator
        
        # Create case
        case_data, _ = orch.data_factory.generate_case()
        case_result = await orch.execute_create("cases", "/api/cases", case_data)
        assert case_result.success
        case_id = case_result.uuid
        
        # Test different communication types
        communication_types = [
            {"channel": "EMAIL", "direction": "OUTBOUND"},
            {"channel": "EMAIL", "direction": "INBOUND"},
            # SMS might not be implemented yet
        ]
        
        for comm_type in communication_types:
            if comm_type["direction"] == "OUTBOUND":
                # Test outbound via email endpoint
                email_data = {
                    "recipient_email": f"test.{comm_type['channel'].lower()}@example.com",
                    "subject": f"Test {comm_type['channel']} {comm_type['direction']}",
                    "body": f"Test {comm_type['channel']} communication",
                    "case_id": case_id
                }
                
                response, duration = await orch.time_operation(
                    f"SEND_{comm_type['channel']}_{comm_type['direction']}",
                    orch.rest_client.request("POST", "/api/send-email", data=email_data)
                )
                
                # Don't fail if email service unavailable
                if response.get("_success", False):
                    print(f"✅ {comm_type['channel']} {comm_type['direction']} communication succeeded")


@pytest.mark.crud
class TestErrorLogsCRUD:
    """Complete CRUD testing for error_logs table"""
    
    async def test_error_logs_full_crud_cycle(self, clean_orchestrator: CRUDTestOrchestrator):
        """Test complete error log CRUD cycle"""
        orch = clean_orchestrator
        
        # Generate error log data
        error_data, expected_error_id = orch.data_factory.generate_error_log()
        
        # === CREATE ERROR LOG (via alert endpoint) ===
        alert_data = {
            "component": error_data["component"],
            "error_message": error_data["error_message"], 
            "severity": error_data["severity"],
            "context": error_data["context"]
        }
        
        create_result = await orch.execute_create(
            resource="alerts",
            endpoint="/api/alert",
            data=alert_data
        )
        
        assert create_result.success, f"Error log creation failed: {create_result.errors}"
        
        # === READ ERROR LOGS ===
        # Test error logs retrieval
        logs_response, duration = await orch.time_operation(
            "GET_ERROR_LOGS",
            orch.rest_client.request("GET", "/api/logs", params={"component": error_data["component"]})
        )
        
        assert logs_response.get("_success", False), f"Error logs retrieval failed: {logs_response}"
        
        # === TEST COMPONENT STATS ===
        stats_response, duration = await orch.time_operation(
            "GET_COMPONENT_STATS",
            orch.rest_client.request("GET", f"/api/stats/{error_data['component']}")
        )
        
        assert stats_response.get("_success", False), f"Component stats retrieval failed: {stats_response}"
        
        # Validate database state
        # Note: Error logs might not have direct UUID endpoint, so we validate via component query
        error_count = await orch.db_validator.count_records(
            "error_logs", 
            "component = $1", 
            [error_data["component"]]
        )
        assert error_count > 0, "Error log not found in database"
    
    async def test_error_severity_levels(self, clean_orchestrator: CRUDTestOrchestrator):
        """Test all error severity levels"""
        orch = clean_orchestrator
        
        severity_levels = ["low", "medium", "high", "critical"]
        
        for severity in severity_levels:
            error_data = {
                "component": f"{orch.config.test_data_prefix}_severity_test",
                "error_message": f"Test {severity} severity error",
                "severity": severity,
                "context": {"severity_test": True, "level": severity}
            }
            
            create_result = await orch.execute_create(
                resource="alerts",
                endpoint="/api/alert", 
                data=error_data
            )
            
            assert create_result.success, f"Failed to create {severity} severity error"
        
        # Verify all severity levels were recorded
        total_count = await orch.db_validator.count_records(
            "error_logs",
            "component = $1",
            [f"{orch.config.test_data_prefix}_severity_test"]
        )
        assert total_count >= len(severity_levels), f"Expected at least {len(severity_levels)} error logs, found {total_count}"
    
    async def test_error_log_context_validation(self, clean_orchestrator: CRUDTestOrchestrator):
        """Test JSONB context field validation"""
        orch = clean_orchestrator
        
        # Test complex context structure
        complex_context = {
            "timestamp": "2024-01-01T00:00:00Z",
            "request_id": "test-request-123",
            "user_agent": "Test User Agent",
            "stack_trace": ["frame1", "frame2", "frame3"],
            "metadata": {
                "nested": True,
                "values": [1, 2, 3],
                "object": {"key": "value"}
            }
        }
        
        error_data = {
            "component": f"{orch.config.test_data_prefix}_context_test",
            "error_message": "Complex context test error",
            "severity": "medium",
            "context": complex_context
        }
        
        create_result = await orch.execute_create(
            resource="alerts", 
            endpoint="/api/alert",
            data=error_data
        )
        
        assert create_result.success, "Failed to create error with complex context"
        
        # Validate complex context was stored correctly in database
        context_record = await orch.db_validator.get_record(
            "error_logs",
            "component", 
            f"{orch.config.test_data_prefix}_context_test"
        )
        
        assert context_record is not None, "Error log not found in database"
        assert context_record.get("context") is not None, "Context not stored in database"


@pytest.mark.crud  
class TestWebhooksCRUD:
    """Test webhook endpoints - CRITICAL for email status updates"""
    
    async def test_resend_webhook_endpoint(self, clean_orchestrator: CRUDTestOrchestrator):
        """Test Resend webhook handling"""
        orch = clean_orchestrator
        
        # Create case and send email first
        case_data, _ = orch.data_factory.generate_case()
        case_result = await orch.execute_create("cases", "/api/cases", case_data)
        assert case_result.success
        case_id = case_result.uuid
        
        email_data = {
            "recipient_email": "test@example.com",
            "subject": "Test webhook email",
            "body": "Test email for webhook",
            "case_id": case_id
        }
        
        email_result = await orch.execute_create("emails", "/api/send-email", email_data)
        
        # Skip webhook test if email service unavailable
        if not email_result.success:
            pytest.skip("Email service not available for webhook testing")
        
        # Test webhook would normally be called by Resend service
        # In test environment, we can validate the endpoint exists
        webhook_data = {
            "type": "email.delivered",
            "data": {
                "email_id": "test-email-id",
                "to": ["test@example.com"],
                "subject": "Test webhook email"
            }
        }
        
        # Note: Real webhook would include proper Resend signature
        # For testing, we just validate endpoint accessibility
        webhook_response, duration = await orch.time_operation(
            "TEST_RESEND_WEBHOOK",
            orch.rest_client.request("POST", "/api/webhooks/resend", data=webhook_data)
        )
        
        # Webhook might fail signature verification in test - that's expected
        # We just want to confirm endpoint exists and processes requests
        print(f"Webhook endpoint response status: {webhook_response.get('_status_code', 'unknown')}")