"""
Phase 2: CREATE Operations Testing via agent/db endpoint
Tests natural language queries for entity creation
"""

import pytest
from typing import Dict, Any, List
from infrastructure import format_test_name, is_successful_response, extract_uuid_from_response, DataValidator


class TestCreateOperations:
    """Test natural language CREATE operations through agent/db endpoint"""
    
    @pytest.mark.asyncio
    @pytest.mark.parametrize("query,expected_entity,validation_checks", [
        # B1: Case Creation Scenarios
        (
            "Create a case for Jennifer Wilson, jennifer.wilson@email.com",
            "cases",
            {
                'should_create_case': True,
                'client_name': 'Jennifer Wilson',
                'client_email': 'jennifer.wilson@email.com',
                'expected_fields': ['case_id', 'client_name', 'client_email', 'status']
            }
        ),
        (
            "Add a new case for Robert Kim with phone (555) 999-8888",
            "cases", 
            {
                'should_create_case': True,
                'client_name': 'Robert Kim',
                'client_phone': '(555) 999-8888',
                'expected_fields': ['case_id', 'client_name', 'client_phone']
            }
        ),
        (
            "Start a case for Emma Davis, emma@company.com, phone (555) 111-2222",
            "cases",
            {
                'should_create_case': True,
                'client_name': 'Emma Davis',
                'client_email': 'emma@company.com',
                'client_phone': '(555) 111-2222',
                'expected_fields': ['case_id', 'client_name', 'client_email', 'client_phone']
            }
        ),
        (
            "Create case for Maria Rodriguez, maria.rodriguez@law.com, phone (555) 333-4444",
            "cases",
            {
                'should_create_case': True,
                'client_name': 'Maria Rodriguez',
                'client_email': 'maria.rodriguez@law.com',
                'client_phone': '(555) 333-4444',
                'expected_fields': ['case_id', 'client_name', 'client_email', 'client_phone']
            }
        )
    ])
    async def test_case_creation(
        self,
        query: str,
        expected_entity: str,
        validation_checks: Dict[str, Any],
        agent_db_client,
        performance_monitor,
        data_validator,
        test_data_ecosystem,
        test_infrastructure
    ):
        """Test Category B1: Case creation through natural language"""
        
        # Execute CREATE operation with performance monitoring
        response = await performance_monitor.time_operation(
            f"Create Case: {format_test_name(query)}",
            agent_db_client.agent_db_query(query),
            category="create_operation"
        )
        
        # Validate response structure
        validation = data_validator.validate_agent_db_response(response)
        assert validation['valid'], f"Invalid response structure: {validation['errors']}"
        
        # Verify successful CREATE operation
        assert is_successful_response(response), f"Case creation failed: {response}"
        assert response.get('ok') is True, "Response not marked as successful"
        assert response.get('operation') == 'INSERT', f"Expected INSERT operation, got {response.get('operation')}"
        assert response.get('resource') == expected_entity, f"Expected {expected_entity}, got {response.get('resource')}"
        
        # Validate created data
        assert 'data' in response, "Response missing data field"
        assert isinstance(response['data'], list), "Data should be a list"
        assert len(response['data']) > 0, "Should return created entity data"
        assert response.get('count') == 1, f"Should create exactly 1 entity, got {response.get('count')}"
        
        created_entity = response['data'][0]
        assert isinstance(created_entity, dict), "Created entity should be a dictionary"
        
        # Track UUID for cleanup
        case_id = extract_uuid_from_response(response, 'case_id')
        if case_id:
            test_infrastructure['uuid_tracker'].track('cases', case_id)
            print(f"🔑 Tracking case UUID: {case_id}")
        else:
            pytest.fail("Failed to extract case_id from create response")
        
        # Validate expected fields are present
        for field in validation_checks.get('expected_fields', []):
            assert field in created_entity, f"Missing expected field: {field}"
        
        # Validate specific field values if provided
        if validation_checks.get('client_name'):
            assert created_entity.get('client_name') == validation_checks['client_name'], \
                f"Expected client_name '{validation_checks['client_name']}', got '{created_entity.get('client_name')}'"
        
        if validation_checks.get('client_email'):
            assert created_entity.get('client_email') == validation_checks['client_email'], \
                f"Expected client_email '{validation_checks['client_email']}', got '{created_entity.get('client_email')}'"
        
        if validation_checks.get('client_phone'):
            assert created_entity.get('client_phone') == validation_checks['client_phone'], \
                f"Expected client_phone '{validation_checks['client_phone']}', got '{created_entity.get('client_phone')}'"
        
        # Validate UUID format
        assert data_validator.validate_uuid(created_entity.get('case_id')), \
            f"Invalid UUID format for case_id: {created_entity.get('case_id')}"
        
        # Validate default status is set
        assert created_entity.get('status') in ['OPEN', 'open'], \
            f"Expected default status 'OPEN', got '{created_entity.get('status')}'"
        
        print(f"✅ Case created successfully: {validation_checks.get('client_name', 'Unknown')} -> {case_id}")
        
        # Verify case can be retrieved (integration test)
        await self._verify_created_case_retrieval(agent_db_client, validation_checks.get('client_name'))
    
    async def _verify_created_case_retrieval(self, client, client_name: str):
        """Verify created case can be retrieved via natural language query"""
        if client_name:
            query = f"Show me {client_name}'s case"
            response = await client.agent_db_query(query)
            
            assert is_successful_response(response), f"Failed to retrieve created case for {client_name}"
            assert response.get('count') > 0, f"Created case for {client_name} not found in retrieval test"
            print(f"  ✅ Case retrieval verified for {client_name}")
    
    @pytest.mark.asyncio
    @pytest.mark.parametrize("query,parent_client,validation_checks", [
        # B2: Document Registration (requires existing cases)
        (
            "Add a document 'New_Contract.pdf' to Jennifer Wilson's case",
            "Jennifer Wilson",
            {
                'document_name': 'New_Contract.pdf',
                'expected_fields': ['document_id', 'original_file_name', 'status']
            }
        ),
        (
            "Register document 'Financial_Report.xlsx' for Robert Kim, mark as priority",
            "Robert Kim",
            {
                'document_name': 'Financial_Report.xlsx',
                'expected_fields': ['document_id', 'original_file_name', 'case_id']
            }
        ),
        (
            "Create document entry for Emma Davis: 'Legal_Opinion.docx', size 2.5MB",
            "Emma Davis",
            {
                'document_name': 'Legal_Opinion.docx',
                'expected_size': '2.5MB',
                'expected_fields': ['document_id', 'original_file_name', 'original_file_size']
            }
        )
    ])
    async def test_document_registration(
        self,
        query: str,
        parent_client: str,
        validation_checks: Dict[str, Any],
        agent_db_client,
        performance_monitor,
        data_validator,
        test_data_ecosystem,
        test_infrastructure
    ):
        """Test Category B2: Document registration through natural language"""
        
        # First ensure the parent case exists by creating it
        case_creation_query = f"Create a case for {parent_client}, {parent_client.lower().replace(' ', '.')}@test.com"
        case_response = await agent_db_client.agent_db_query(case_creation_query)
        
        if is_successful_response(case_response):
            case_id = extract_uuid_from_response(case_response, 'case_id') 
            if case_id:
                test_infrastructure['uuid_tracker'].track('cases', case_id)
        
        # Now execute document creation with performance monitoring
        response = await performance_monitor.time_operation(
            f"Create Document: {format_test_name(query)}",
            agent_db_client.agent_db_query(query),
            category="create_operation"
        )
        
        # Validate response structure
        validation = data_validator.validate_agent_db_response(response)
        assert validation['valid'], f"Invalid response structure: {validation['errors']}"
        
        # Verify successful CREATE operation
        assert is_successful_response(response), f"Document creation failed: {response}"
        assert response.get('ok') is True, "Response not marked as successful"
        assert response.get('operation') == 'INSERT', f"Expected INSERT operation, got {response.get('operation')}"
        assert response.get('resource') == 'documents', f"Expected documents resource, got {response.get('resource')}"
        
        # Validate created data
        assert 'data' in response, "Response missing data field"
        assert len(response['data']) > 0, "Should return created document data"
        assert response.get('count') == 1, f"Should create exactly 1 document, got {response.get('count')}"
        
        created_document = response['data'][0]
        
        # Track UUID for cleanup
        document_id = extract_uuid_from_response(response, 'document_id')
        if document_id:
            test_infrastructure['uuid_tracker'].track('documents', document_id)
            print(f"🔑 Tracking document UUID: {document_id}")
        
        # Validate expected fields
        for field in validation_checks.get('expected_fields', []):
            assert field in created_document, f"Missing expected field: {field}"
        
        # Validate document name
        if validation_checks.get('document_name'):
            assert created_document.get('original_file_name') == validation_checks['document_name'], \
                f"Expected filename '{validation_checks['document_name']}', got '{created_document.get('original_file_name')}'"
        
        # Validate UUID format
        assert data_validator.validate_uuid(created_document.get('document_id')), \
            f"Invalid UUID format for document_id: {created_document.get('document_id')}"
        
        # Validate case association
        assert data_validator.validate_uuid(created_document.get('case_id')), \
            f"Invalid UUID format for case_id: {created_document.get('case_id')}"
        
        # Default status should be set
        assert created_document.get('status') in ['PENDING', 'pending'], \
            f"Expected default status 'PENDING', got '{created_document.get('status')}'"
        
        print(f"✅ Document created successfully: {validation_checks.get('document_name')} for {parent_client}")
    
    @pytest.mark.asyncio
    @pytest.mark.parametrize("query,parent_client,validation_checks", [
        # B3: Communication Logging
        (
            "Log an email sent to Jennifer Wilson about document requirements",
            "Jennifer Wilson",
            {
                'channel': 'email',
                'direction': 'outbound',
                'subject_contains': 'document requirements',
                'expected_fields': ['communication_id', 'channel', 'direction', 'status']
            }
        ),
        (
            "Record SMS notification sent to Robert Kim",
            "Robert Kim",
            {
                'channel': 'sms', 
                'direction': 'outbound',
                'expected_fields': ['communication_id', 'channel', 'direction', 'recipient']
            }
        ),
        (
            "Create communication record: outbound email to Emma Davis, subject 'Case Update'",
            "Emma Davis",
            {
                'channel': 'email',
                'direction': 'outbound',
                'subject': 'Case Update',
                'expected_fields': ['communication_id', 'subject', 'message_content']
            }
        )
    ])
    async def test_communication_logging(
        self,
        query: str,
        parent_client: str,
        validation_checks: Dict[str, Any],
        agent_db_client,
        performance_monitor,
        data_validator,
        test_data_ecosystem,
        test_infrastructure
    ):
        """Test Category B3: Communication logging through natural language"""
        
        # Ensure parent case exists
        case_creation_query = f"Create a case for {parent_client}, {parent_client.lower().replace(' ', '.')}@test.com"
        case_response = await agent_db_client.agent_db_query(case_creation_query)
        
        if is_successful_response(case_response):
            case_id = extract_uuid_from_response(case_response, 'case_id')
            if case_id:
                test_infrastructure['uuid_tracker'].track('cases', case_id)
        
        # Execute communication creation
        response = await performance_monitor.time_operation(
            f"Create Communication: {format_test_name(query)}",
            agent_db_client.agent_db_query(query),
            category="create_operation"
        )
        
        # Validate response structure
        validation = data_validator.validate_agent_db_response(response)
        assert validation['valid'], f"Invalid response structure: {validation['errors']}"
        
        # Verify successful CREATE operation
        assert is_successful_response(response), f"Communication creation failed: {response}"
        assert response.get('ok') is True, "Response not marked as successful"
        assert response.get('operation') == 'INSERT', f"Expected INSERT operation, got {response.get('operation')}"
        assert response.get('resource') == 'client_communications', \
            f"Expected client_communications resource, got {response.get('resource')}"
        
        # Validate created data
        assert len(response['data']) > 0, "Should return created communication data"
        assert response.get('count') == 1, f"Should create exactly 1 communication, got {response.get('count')}"
        
        created_comm = response['data'][0]
        
        # Track UUID for cleanup
        comm_id = extract_uuid_from_response(response, 'communication_id')
        if comm_id:
            test_infrastructure['uuid_tracker'].track('client_communications', comm_id)
            print(f"🔑 Tracking communication UUID: {comm_id}")
        
        # Validate expected fields
        for field in validation_checks.get('expected_fields', []):
            assert field in created_comm, f"Missing expected field: {field}"
        
        # Validate channel type
        if validation_checks.get('channel'):
            assert created_comm.get('channel') == validation_checks['channel'], \
                f"Expected channel '{validation_checks['channel']}', got '{created_comm.get('channel')}'"
        
        # Validate direction
        if validation_checks.get('direction'):
            assert created_comm.get('direction') == validation_checks['direction'], \
                f"Expected direction '{validation_checks['direction']}', got '{created_comm.get('direction')}'"
        
        # Validate subject if specified
        if validation_checks.get('subject'):
            assert created_comm.get('subject') == validation_checks['subject'], \
                f"Expected subject '{validation_checks['subject']}', got '{created_comm.get('subject')}'"
        
        # Validate UUID formats
        assert data_validator.validate_uuid(created_comm.get('communication_id')), \
            f"Invalid communication_id UUID: {created_comm.get('communication_id')}"
        assert data_validator.validate_uuid(created_comm.get('case_id')), \
            f"Invalid case_id UUID: {created_comm.get('case_id')}"
        
        print(f"✅ Communication created: {validation_checks.get('channel', 'unknown')} for {parent_client}")
    
    @pytest.mark.asyncio
    @pytest.mark.parametrize("query,parent_client,validation_checks", [
        # B4: Agent State Initialization
        (
            "Start a new CommunicationsAgent conversation for Jennifer Wilson's case",
            "Jennifer Wilson",
            {
                'agent_type': 'CommunicationsAgent',
                'expected_fields': ['conversation_id', 'agent_type', 'status']
            }
        ),
        (
            "Create agent context for Robert Kim: client prefers phone calls",
            "Robert Kim",
            {
                'context_key': 'client_preferences',
                'context_value_contains': 'phone',
                'expected_fields': ['context_id', 'context_key', 'context_value']
            }
        ),
        (
            "Begin AnalysisAgent session for Emma Davis case",
            "Emma Davis",
            {
                'agent_type': 'AnalysisAgent',
                'expected_fields': ['conversation_id', 'agent_type']
            }
        )
    ])
    async def test_agent_state_initialization(
        self,
        query: str,
        parent_client: str,
        validation_checks: Dict[str, Any],
        agent_db_client,
        performance_monitor,
        data_validator,
        test_data_ecosystem,
        test_infrastructure
    ):
        """Test Category B4: Agent state initialization through natural language"""
        
        # Ensure parent case exists
        case_creation_query = f"Create a case for {parent_client}, {parent_client.lower().replace(' ', '.')}@test.com"
        case_response = await agent_db_client.agent_db_query(case_creation_query)
        
        if is_successful_response(case_response):
            case_id = extract_uuid_from_response(case_response, 'case_id')
            if case_id:
                test_infrastructure['uuid_tracker'].track('cases', case_id)
        
        # Execute agent state creation
        response = await performance_monitor.time_operation(
            f"Create Agent State: {format_test_name(query)}",
            agent_db_client.agent_db_query(query),
            category="create_operation"
        )
        
        # Validate response structure
        validation = data_validator.validate_agent_db_response(response)
        assert validation['valid'], f"Invalid response structure: {validation['errors']}"
        
        # Verify successful CREATE operation
        assert is_successful_response(response), f"Agent state creation failed: {response}"
        assert response.get('ok') is True, "Response not marked as successful"
        assert response.get('operation') == 'INSERT', f"Expected INSERT operation, got {response.get('operation')}"
        
        # Resource should be agent-related
        resource = response.get('resource')
        assert resource in ['agent_conversations', 'agent_context'], \
            f"Expected agent resource, got {resource}"
        
        # Validate created data
        assert len(response['data']) > 0, "Should return created agent state data"
        assert response.get('count') == 1, f"Should create exactly 1 entity, got {response.get('count')}"
        
        created_state = response['data'][0]
        
        # Track UUID for cleanup based on resource type
        if resource == 'agent_conversations':
            conv_id = extract_uuid_from_response(response, 'conversation_id')
            if conv_id:
                test_infrastructure['uuid_tracker'].track('agent_conversations', conv_id)
        elif resource == 'agent_context':
            context_id = extract_uuid_from_response(response, 'context_id')
            if context_id:
                test_infrastructure['uuid_tracker'].track('agent_context', context_id)
        
        # Validate expected fields
        for field in validation_checks.get('expected_fields', []):
            assert field in created_state, f"Missing expected field: {field}"
        
        # Validate agent type if specified
        if validation_checks.get('agent_type'):
            assert created_state.get('agent_type') == validation_checks['agent_type'], \
                f"Expected agent_type '{validation_checks['agent_type']}', got '{created_state.get('agent_type')}'"
        
        print(f"✅ Agent state created for {parent_client}: {resource}")
    
    @pytest.mark.asyncio
    async def test_create_operations_performance_summary(
        self,
        performance_monitor,
        test_data_ecosystem
    ):
        """Final test to print CREATE operations performance summary"""
        
        # Print performance statistics
        stats = performance_monitor.get_category_stats('create_operation')
        
        print("\n📊 CREATE Operations Performance Summary:")
        print(f"   Create Operations: {stats['count']} operations, avg {stats['avg_time']:.2f}s")
        
        # Validate performance threshold
        if stats['count'] > 0:
            assert stats['max_time'] <= 3.0, f"Create operations exceeded 3s threshold: {stats['max_time']:.2f}s"
            assert stats['success_rate'] == 1.0, f"Some create operations failed: {stats['success_rate']:.1%} success rate"
        
        print("✅ All CREATE operations completed within performance thresholds")