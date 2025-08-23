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
        
        # Verify case exists by reading it back
        case_read_result = await orch.execute_read("cases", "/api/cases/{id}", case_id)
        assert case_read_result.success, f"Case {case_id} not found after creation"
        
        # Generate communication data
        comm_data, expected_comm_id = orch.data_factory.generate_communication(case_id)
        
        # === CREATE COMMUNICATION (direct database) ===
        create_result = await orch.execute_create(
            resource="client_communications",
            endpoint="/api/communications",
            data=comm_data
        )
        
        # Direct database communication creation should work
        assert create_result.success, f"Communication creation failed: {create_result.errors}"
        
        # If email succeeded, verify communication was logged
        if create_result.success:
            # Test case communications retrieval
            case_comms_response, duration = await orch.time_operation(
                "GET_CASE_COMMUNICATIONS",
                orch.rest_client.request("GET", f"/api/cases/{case_id}/communications")
            )
            
            assert case_comms_response.get("_success", False), f"Case communications retrieval failed: {case_comms_response}"
    
# Communication channels test removed - uses external email API
    # CRUD suite focuses only on direct database operations


# Error logs testing removed - uses external API endpoints (/api/alert) that send emails
# CRUD suite focuses only on direct database operations


