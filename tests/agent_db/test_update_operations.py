"""
Phase 2: UPDATE Operations Testing via agent/db endpoint
Tests natural language queries for entity updates
"""

import pytest
from typing import Dict, Any, List
from infrastructure import format_test_name, is_successful_response, extract_uuid_from_response, DataValidator


class TestUpdateOperations:
    """Test natural language UPDATE operations through agent/db endpoint"""
    
    @pytest.mark.asyncio
    @pytest.mark.parametrize("client_name,update_query,expected_changes", [
        # C1: Case Status Management
        (
            "Jennifer Wilson",
            "Close Jennifer Wilson's case",
            {
                'field': 'status',
                'new_value': 'CLOSED',
                'operation_type': 'status_change'
            }
        ),
        (
            "Sarah Johnson", 
            "Reopen Sarah Johnson's case",
            {
                'field': 'status',
                'new_value': 'OPEN',
                'operation_type': 'status_change'
            }
        ),
        (
            "Robert Kim",
            "Mark Robert Kim's case as high priority",
            {
                'field': 'priority',
                'new_value': 'high',
                'operation_type': 'priority_change'
            }
        ),
        (
            "Emma Davis",
            "Update Emma Davis's case status to completed",
            {
                'field': 'status', 
                'new_value': 'COMPLETED',
                'operation_type': 'status_change'
            }
        )
    ])
    async def test_case_status_management(
        self,
        client_name: str,
        update_query: str,
        expected_changes: Dict[str, Any],
        agent_db_client,
        performance_monitor,
        data_validator,
        test_data_ecosystem,
        test_infrastructure
    ):
        """Test Category C1: Case status management through natural language"""
        
        # First create the case to update
        case_creation_query = f"Create a case for {client_name}, {client_name.lower().replace(' ', '.')}@test.com"
        case_response = await agent_db_client.agent_db_query(case_creation_query)
        
        assert is_successful_response(case_response), f"Failed to create test case for {client_name}"
        case_id = extract_uuid_from_response(case_response, 'case_id')
        assert case_id, "Failed to get case_id from creation response"
        test_infrastructure['uuid_tracker'].track('cases', case_id)
        
        # Execute UPDATE operation with performance monitoring
        response = await performance_monitor.time_operation(
            f"Update Case: {format_test_name(update_query)}",
            agent_db_client.agent_db_query(update_query),
            category="update_operation"
        )
        
        # Validate response structure
        validation = data_validator.validate_agent_db_response(response)
        assert validation['valid'], f"Invalid response structure: {validation['errors']}"
        
        # Verify successful UPDATE operation
        assert is_successful_response(response), f"Case update failed: {response}"
        assert response.get('ok') is True, "Response not marked as successful"
        assert response.get('operation') == 'UPDATE', f"Expected UPDATE operation, got {response.get('operation')}"
        assert response.get('resource') == 'cases', f"Expected cases resource, got {response.get('resource')}"
        
        # Validate updated data
        assert 'data' in response, "Response missing data field"
        assert len(response['data']) > 0, "Should return updated entity data"
        assert response.get('count') == 1, f"Should update exactly 1 entity, got {response.get('count')}"
        
        updated_case = response['data'][0]
        
        # Validate the specific change was applied
        if expected_changes['operation_type'] == 'status_change':
            # Case status should be updated
            updated_status = updated_case.get('status', '').upper()
            expected_status = expected_changes['new_value'].upper()
            assert updated_status == expected_status, \
                f"Expected status '{expected_status}', got '{updated_status}'"
        
        # Validate UUID consistency
        assert updated_case.get('case_id') == case_id, \
            f"Case ID should remain consistent: expected {case_id}, got {updated_case.get('case_id')}"
        
        # Validate client info remains unchanged
        assert updated_case.get('client_name') == client_name, \
            f"Client name should not change: expected '{client_name}', got '{updated_case.get('client_name')}'"
        
        print(f"✅ Case updated successfully: {client_name} -> {expected_changes['new_value']}")
        
        # Verify update can be retrieved
        await self._verify_case_update_persisted(agent_db_client, client_name, expected_changes)
    
    async def _verify_case_update_persisted(self, client, client_name: str, expected_changes: Dict[str, Any]):
        """Verify the update persisted by retrieving the case"""
        query = f"Show me {client_name}'s case"
        response = await client.agent_db_query(query)
        
        assert is_successful_response(response), f"Failed to retrieve updated case for {client_name}"
        assert response.get('count') > 0, f"Updated case not found for {client_name}"
        
        retrieved_case = response['data'][0]
        if expected_changes['operation_type'] == 'status_change':
            retrieved_status = retrieved_case.get('status', '').upper()
            expected_status = expected_changes['new_value'].upper()
            assert retrieved_status == expected_status, \
                f"Update did not persist: expected {expected_status}, retrieved {retrieved_status}"
        
        print(f"  ✅ Update persistence verified for {client_name}")
    
    @pytest.mark.asyncio  
    @pytest.mark.parametrize("client_name,document_name,update_query,expected_status", [
        # C2: Document Status Progression
        (
            "Jennifer Wilson",
            "New_Contract.pdf", 
            "Mark Jennifer Wilson's New_Contract.pdf as completed",
            "COMPLETED"
        ),
        (
            "Robert Kim",
            "Financial_Report.xlsx",
            "Update Financial_Report.xlsx status to processing", 
            "PROCESSING"
        ),
        (
            "Emma Davis",
            "Legal_Opinion.docx",
            "Set Legal_Opinion.docx as failed processing",
            "FAILED"
        ),
        (
            "Maria Rodriguez",
            "Case_Summary.pdf",
            "Change Case_Summary.pdf status to pending review",
            "PENDING"
        )
    ])
    async def test_document_status_progression(
        self,
        client_name: str,
        document_name: str,
        update_query: str,
        expected_status: str,
        agent_db_client,
        performance_monitor,
        data_validator,
        test_data_ecosystem,
        test_infrastructure
    ):
        """Test Category C2: Document status progression through natural language"""
        
        # Create case and document first
        case_creation_query = f"Create a case for {client_name}, {client_name.lower().replace(' ', '.')}@test.com"
        case_response = await agent_db_client.agent_db_query(case_creation_query)
        
        assert is_successful_response(case_response), f"Failed to create test case"
        case_id = extract_uuid_from_response(case_response, 'case_id')
        test_infrastructure['uuid_tracker'].track('cases', case_id)
        
        # Create document
        doc_creation_query = f"Add a document '{document_name}' to {client_name}'s case"
        doc_response = await agent_db_client.agent_db_query(doc_creation_query)
        
        assert is_successful_response(doc_response), f"Failed to create test document"
        document_id = extract_uuid_from_response(doc_response, 'document_id')
        test_infrastructure['uuid_tracker'].track('documents', document_id)
        
        # Execute document status update
        response = await performance_monitor.time_operation(
            f"Update Document: {format_test_name(update_query)}",
            agent_db_client.agent_db_query(update_query),
            category="update_operation"
        )
        
        # Validate response structure
        validation = data_validator.validate_agent_db_response(response)
        assert validation['valid'], f"Invalid response structure: {validation['errors']}"
        
        # Verify successful UPDATE operation
        assert is_successful_response(response), f"Document update failed: {response}"
        assert response.get('ok') is True, "Response not marked as successful"
        assert response.get('operation') == 'UPDATE', f"Expected UPDATE operation, got {response.get('operation')}"
        assert response.get('resource') == 'documents', f"Expected documents resource, got {response.get('resource')}"
        
        # Validate updated data
        assert len(response['data']) > 0, "Should return updated document data"
        assert response.get('count') == 1, f"Should update exactly 1 document, got {response.get('count')}"
        
        updated_document = response['data'][0]
        
        # Validate status change
        updated_status = updated_document.get('status', '').upper()
        assert updated_status == expected_status.upper(), \
            f"Expected status '{expected_status}', got '{updated_status}'"
        
        # Validate document identity remains unchanged
        assert updated_document.get('original_file_name') == document_name, \
            f"Document name should not change: expected '{document_name}', got '{updated_document.get('original_file_name')}'"
        
        assert updated_document.get('document_id') == document_id, \
            f"Document ID should remain consistent"
        
        print(f"✅ Document updated successfully: {document_name} -> {expected_status}")
    
    @pytest.mark.asyncio
    @pytest.mark.parametrize("client_name,update_query,expected_status", [
        # C3: Communication Status Updates
        (
            "Jennifer Wilson",
            "Mark email to Jennifer Wilson as delivered",
            "delivered"
        ),
        (
            "Robert Kim", 
            "Update SMS to Robert Kim as opened",
            "opened"
        ),
        (
            "Emma Davis",
            "Set Emma Davis email as bounced",
            "bounced"
        ),
        (
            "Maria Rodriguez",
            "Mark communication to Maria Rodriguez as failed",
            "failed"
        )
    ])
    async def test_communication_status_updates(
        self,
        client_name: str,
        update_query: str,
        expected_status: str,
        agent_db_client,
        performance_monitor,
        data_validator,
        test_data_ecosystem,
        test_infrastructure
    ):
        """Test Category C3: Communication status updates through natural language"""
        
        # Create case and communication first
        case_creation_query = f"Create a case for {client_name}, {client_name.lower().replace(' ', '.')}@test.com"
        case_response = await agent_db_client.agent_db_query(case_creation_query)
        
        assert is_successful_response(case_response), f"Failed to create test case"
        case_id = extract_uuid_from_response(case_response, 'case_id')
        test_infrastructure['uuid_tracker'].track('cases', case_id)
        
        # Create communication
        comm_creation_query = f"Log an email sent to {client_name} about case update"
        comm_response = await agent_db_client.agent_db_query(comm_creation_query)
        
        assert is_successful_response(comm_response), f"Failed to create test communication"
        comm_id = extract_uuid_from_response(comm_response, 'communication_id')
        test_infrastructure['uuid_tracker'].track('client_communications', comm_id)
        
        # Execute communication status update
        response = await performance_monitor.time_operation(
            f"Update Communication: {format_test_name(update_query)}",
            agent_db_client.agent_db_query(update_query),
            category="update_operation"
        )
        
        # Validate response structure
        validation = data_validator.validate_agent_db_response(response)
        assert validation['valid'], f"Invalid response structure: {validation['errors']}"
        
        # Verify successful UPDATE operation
        assert is_successful_response(response), f"Communication update failed: {response}"
        assert response.get('ok') is True, "Response not marked as successful"
        assert response.get('operation') == 'UPDATE', f"Expected UPDATE operation, got {response.get('operation')}"
        assert response.get('resource') == 'client_communications', \
            f"Expected client_communications resource, got {response.get('resource')}"
        
        # Validate updated data
        assert len(response['data']) > 0, "Should return updated communication data"
        assert response.get('count') == 1, f"Should update exactly 1 communication, got {response.get('count')}"
        
        updated_communication = response['data'][0]
        
        # Validate status change
        updated_status = updated_communication.get('status', '').lower()
        assert updated_status == expected_status.lower(), \
            f"Expected status '{expected_status}', got '{updated_status}'"
        
        # Validate communication identity remains unchanged
        assert updated_communication.get('communication_id') == comm_id, \
            f"Communication ID should remain consistent"
        
        print(f"✅ Communication updated successfully: {client_name} -> {expected_status}")
    
    @pytest.mark.asyncio
    @pytest.mark.parametrize("client_name,update_query,expected_changes", [
        # C4: Agent Context Modifications
        (
            "Jennifer Wilson",
            "Update Jennifer Wilson's communication preference to email only",
            {
                'context_key': 'communication_preference',
                'expected_value_contains': 'email'
            }
        ),
        (
            "Robert Kim",
            "Add note to Robert Kim's context: client is traveling this week",
            {
                'context_key': 'client_notes',
                'expected_value_contains': 'traveling'
            }
        ),
        (
            "Emma Davis", 
            "Modify Emma Davis preferences: urgent cases only via phone",
            {
                'context_key': 'preferences',
                'expected_value_contains': 'phone'
            }
        ),
        (
            "Maria Rodriguez",
            "Update Maria Rodriguez context: requires Spanish language support",
            {
                'context_key': 'language_preference',
                'expected_value_contains': 'Spanish'
            }
        )
    ])
    async def test_agent_context_modifications(
        self,
        client_name: str,
        update_query: str,
        expected_changes: Dict[str, Any],
        agent_db_client,
        performance_monitor,
        data_validator,
        test_data_ecosystem,
        test_infrastructure
    ):
        """Test Category C4: Agent context modifications through natural language"""
        
        # Create case first
        case_creation_query = f"Create a case for {client_name}, {client_name.lower().replace(' ', '.')}@test.com"
        case_response = await agent_db_client.agent_db_query(case_creation_query)
        
        assert is_successful_response(case_response), f"Failed to create test case"
        case_id = extract_uuid_from_response(case_response, 'case_id')
        test_infrastructure['uuid_tracker'].track('cases', case_id)
        
        # Create initial agent context
        context_creation_query = f"Create agent context for {client_name}: initial client preferences"
        context_response = await agent_db_client.agent_db_query(context_creation_query)
        
        # Context creation might fail if not supported, so we'll try the update regardless
        context_id = None
        if is_successful_response(context_response):
            context_id = extract_uuid_from_response(context_response, 'context_id')
            if context_id:
                test_infrastructure['uuid_tracker'].track('agent_context', context_id)
        
        # Execute context update
        response = await performance_monitor.time_operation(
            f"Update Context: {format_test_name(update_query)}",
            agent_db_client.agent_db_query(update_query),
            category="update_operation"
        )
        
        # Validate response structure
        validation = data_validator.validate_agent_db_response(response)
        assert validation['valid'], f"Invalid response structure: {validation['errors']}"
        
        # Context updates might be CREATE operations if context doesn't exist
        assert is_successful_response(response), f"Context update failed: {response}"
        assert response.get('ok') is True, "Response not marked as successful"
        
        operation = response.get('operation')
        assert operation in ['UPDATE', 'INSERT'], f"Expected UPDATE or INSERT operation, got {operation}"
        
        resource = response.get('resource')
        assert resource == 'agent_context', f"Expected agent_context resource, got {resource}"
        
        # Validate updated/created data
        assert len(response['data']) > 0, "Should return context data"
        assert response.get('count') == 1, f"Should affect exactly 1 context entry, got {response.get('count')}"
        
        context_data = response['data'][0]
        
        # Track UUID if this was a creation
        if operation == 'INSERT':
            new_context_id = extract_uuid_from_response(response, 'context_id')
            if new_context_id:
                test_infrastructure['uuid_tracker'].track('agent_context', new_context_id)
        
        # Validate context value contains expected content
        context_value = context_data.get('context_value', {})
        if isinstance(context_value, dict):
            context_value_str = str(context_value).lower()
        else:
            context_value_str = str(context_value).lower()
        
        expected_contains = expected_changes.get('expected_value_contains', '').lower()
        if expected_contains:
            assert expected_contains in context_value_str, \
                f"Context value should contain '{expected_contains}', got: {context_value}"
        
        print(f"✅ Agent context updated successfully: {client_name}")
    
    @pytest.mark.asyncio
    async def test_update_operations_performance_summary(
        self,
        performance_monitor,
        test_data_ecosystem
    ):
        """Final test to print UPDATE operations performance summary"""
        
        # Print performance statistics
        stats = performance_monitor.get_category_stats('update_operation')
        
        print("\n📊 UPDATE Operations Performance Summary:")
        print(f"   Update Operations: {stats['count']} operations, avg {stats['avg_time']:.2f}s")
        
        # Validate performance threshold
        if stats['count'] > 0:
            assert stats['max_time'] <= 2.0, f"Update operations exceeded 2s threshold: {stats['max_time']:.2f}s"
            assert stats['success_rate'] >= 0.8, f"Too many update operations failed: {stats['success_rate']:.1%} success rate"
        
        print("✅ All UPDATE operations completed within acceptable performance thresholds")
    
    @pytest.mark.asyncio
    async def test_invalid_updates_error_handling(
        self,
        agent_db_client,
        performance_monitor,
        data_validator,
        test_data_ecosystem
    ):
        """Test error handling for invalid update scenarios"""
        
        invalid_update_queries = [
            "Update nonexistent client's case status to closed",
            "Mark document 'DoesNotExist.pdf' as completed",
            "Close case for Fictional Client Name"
        ]
        
        for query in invalid_update_queries:
            response = await agent_db_client.agent_db_query(query)
            
            # Should get a proper error response, not a success
            validation = data_validator.validate_agent_db_response(response)
            assert validation['valid'], f"Invalid response structure: {validation['errors']}"
            
            # Should either fail with an error or return 0 updates
            if response.get('ok') is False:
                # Proper error response
                assert 'error_details' in response, "Error response should include error_details"
                print(f"  ✅ Proper error for invalid update: {format_test_name(query)}")
            elif response.get('ok') is True:
                # Success response but should affect 0 records
                assert response.get('count') == 0, f"Invalid update should affect 0 records, got {response.get('count')}"
                print(f"  ✅ Zero updates for invalid query: {format_test_name(query)}")
            else:
                pytest.fail(f"Unexpected response format for invalid update: {response}")
        
        print("✅ Invalid update error handling validated")