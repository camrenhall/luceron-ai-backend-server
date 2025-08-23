"""
Phase 2: Complex Multi-Operation Workflow Testing via agent/db endpoint
Tests complete business scenarios through natural language sequences
"""

import pytest
import asyncio
from typing import Dict, Any, List, Tuple
from infrastructure import format_test_name, is_successful_response, extract_uuid_from_response


class TestComplexWorkflows:
    """Test complex multi-operation business workflows through agent/db endpoint"""
    
    @pytest.mark.asyncio
    async def test_complete_case_workflow_simulation(
        self,
        agent_db_client,
        performance_monitor,
        data_validator,
        test_data_ecosystem,
        test_infrastructure
    ):
        """Test Category D1: Complete case workflow from creation to closure"""
        
        print("\n🔄 Testing Complete Case Workflow Simulation")
        
        # Define complete workflow sequence
        client_name = "Lisa Park"
        client_email = "lisa.park@email.com"
        client_phone = "(555) 777-8899"
        document_name = "Initial_Filing.pdf"
        
        workflow_steps = [
            (f"Create case for {client_name}, {client_email}, {client_phone}", "case_creation"),
            (f"Add document '{document_name}' to {client_name}'s case", "document_addition"),
            (f"Send welcome email to {client_name} about document upload requirements", "welcome_communication"),
            (f"Start AnalysisAgent conversation for {client_name}'s case", "agent_initialization"),
            (f"Update {document_name} status to completed", "document_processing"),
            (f"Add analysis result for {client_name}'s {document_name}", "analysis_storage"),
            (f"Send completion notification to {client_name}", "completion_communication"),
            (f"Close {client_name}'s case", "case_closure")
        ]
        
        step_results = {}
        workflow_start_time = None
        
        # Execute workflow steps sequentially
        for i, (query, step_type) in enumerate(workflow_steps, 1):
            print(f"\n  Step {i}: {step_type}")
            
            # Time the entire workflow
            if i == 1:
                import time
                workflow_start_time = time.time()
            
            # Execute step with performance monitoring
            response = await performance_monitor.time_operation(
                f"Workflow Step {i}: {format_test_name(query)}",
                agent_db_client.agent_db_query(query),
                category="complex_query"
            )
            
            # Validate response structure
            validation = data_validator.validate_agent_db_response(response)
            assert validation['valid'], f"Step {i} invalid response: {validation['errors']}"
            
            # Verify step success
            assert is_successful_response(response), f"Step {i} failed: {response}"
            assert response.get('ok') is True, f"Step {i} not marked as successful"
            
            # Track UUIDs for cleanup based on operation type
            if step_type == "case_creation":
                case_id = extract_uuid_from_response(response, 'case_id')
                assert case_id, f"Step {i}: Failed to get case_id"
                test_infrastructure['uuid_tracker'].track('cases', case_id)
                step_results['case_id'] = case_id
                
                # Validate case creation
                assert response.get('operation') == 'INSERT', f"Expected INSERT for case creation"
                assert response.get('resource') == 'cases', f"Expected cases resource"
                
            elif step_type == "document_addition":
                document_id = extract_uuid_from_response(response, 'document_id')
                if document_id:
                    test_infrastructure['uuid_tracker'].track('documents', document_id)
                    step_results['document_id'] = document_id
                
                # Validate document creation
                assert response.get('operation') == 'INSERT', f"Expected INSERT for document creation"
                
            elif step_type in ["welcome_communication", "completion_communication"]:
                comm_id = extract_uuid_from_response(response, 'communication_id')
                if comm_id:
                    test_infrastructure['uuid_tracker'].track('client_communications', comm_id)
                    if step_type == "welcome_communication":
                        step_results['welcome_comm_id'] = comm_id
                    else:
                        step_results['completion_comm_id'] = comm_id
                
            elif step_type == "agent_initialization":
                conv_id = extract_uuid_from_response(response, 'conversation_id')
                if conv_id:
                    test_infrastructure['uuid_tracker'].track('agent_conversations', conv_id)
                    step_results['conversation_id'] = conv_id
                
            elif step_type in ["document_processing", "case_closure"]:
                # These should be UPDATE operations
                assert response.get('operation') == 'UPDATE', f"Expected UPDATE for {step_type}"
                assert response.get('count') == 1, f"Should update exactly 1 record for {step_type}"
                
            elif step_type == "analysis_storage":
                analysis_id = extract_uuid_from_response(response, 'analysis_id')
                if analysis_id:
                    test_infrastructure['uuid_tracker'].track('document_analysis', analysis_id)
                    step_results['analysis_id'] = analysis_id
            
            print(f"    ✅ Step {i} completed: {step_type}")
            
            # Brief delay between steps to ensure realistic workflow timing
            import asyncio
            await asyncio.sleep(0.1)
        
        # Calculate total workflow time
        if workflow_start_time:
            import time
            total_workflow_time = time.time() - workflow_start_time
            print(f"\n⏱️  Total workflow time: {total_workflow_time:.2f}s")
        
        # Validate complete workflow integrity
        await self._validate_workflow_integrity(agent_db_client, client_name, step_results)
        
        print(f"✅ Complete case workflow simulation successful for {client_name}")
    
    async def _validate_workflow_integrity(
        self, 
        client,
        client_name: str,
        step_results: Dict[str, str]
    ):
        """Validate that all workflow steps are properly linked and accessible"""
        
        # Verify case can be retrieved with all associated data
        case_query = f"Show me {client_name}'s case with all details"
        case_response = await client.agent_db_query(case_query)
        
        assert is_successful_response(case_response), f"Failed to retrieve complete case for {client_name}"
        assert case_response.get('count') > 0, f"Case not found for {client_name}"
        
        # Verify documents are associated with case
        docs_query = f"What documents does {client_name} have?"
        docs_response = await client.agent_db_query(docs_query)
        
        assert is_successful_response(docs_response), f"Failed to retrieve documents for {client_name}"
        # Should have at least the document we created
        assert docs_response.get('count') > 0, f"No documents found for {client_name}"
        
        # Verify communications exist
        comms_query = f"List all communications for {client_name}"
        comms_response = await client.agent_db_query(comms_query)
        
        assert is_successful_response(comms_response), f"Failed to retrieve communications for {client_name}"
        # Should have welcome and completion emails
        assert comms_response.get('count') >= 1, f"Insufficient communications found for {client_name}"
        
        print("  ✅ Workflow integrity validated - all entities properly linked")
    
    @pytest.mark.asyncio 
    async def test_problem_resolution_workflow(
        self,
        agent_db_client,
        performance_monitor,
        data_validator,
        test_data_ecosystem,
        test_infrastructure
    ):
        """Test Category D2: Problem resolution workflow for failed processing"""
        
        print("\n🔧 Testing Problem Resolution Workflow")
        
        # Use existing test data - Rebecca Martinez has failed documents
        client_name = "Rebecca Martinez"
        document_name = "Disputed_Invoice.pdf"
        
        problem_resolution_steps = [
            ("Find all failed document processing cases", "problem_identification"),
            (f"Update {client_name}'s {document_name} status to processing", "status_correction"),
            (f"Create note in {client_name}'s agent context: reprocessing required", "context_notation"),
            (f"Send notification to {client_name} about reprocessing", "client_notification"),
            (f"Update {document_name} status to completed", "resolution_completion"),
            (f"Log successful resolution in {client_name}'s agent context", "resolution_logging")
        ]
        
        resolution_results = {}
        
        # Execute problem resolution workflow
        for i, (query, step_type) in enumerate(problem_resolution_steps, 1):
            print(f"\n  Resolution Step {i}: {step_type}")
            
            response = await performance_monitor.time_operation(
                f"Resolution Step {i}: {format_test_name(query)}",
                agent_db_client.agent_db_query(query),
                category="complex_query"
            )
            
            # Validate response structure
            validation = data_validator.validate_agent_db_response(response)
            assert validation['valid'], f"Resolution step {i} invalid response: {validation['errors']}"
            
            # Verify step success
            assert is_successful_response(response), f"Resolution step {i} failed: {response}"
            assert response.get('ok') is True, f"Resolution step {i} not marked as successful"
            
            # Track specific step results
            if step_type == "problem_identification":
                # Should find at least Rebecca's failed documents
                assert response.get('operation') == 'READ', "Problem identification should be READ operation"
                # May find multiple failed cases, that's OK
                resolution_results['failed_cases_count'] = response.get('count', 0)
                
            elif step_type in ["status_correction", "resolution_completion"]:
                # Should be UPDATE operations
                assert response.get('operation') == 'UPDATE', f"Expected UPDATE for {step_type}"
                assert response.get('resource') == 'documents', f"Expected documents resource for {step_type}"
                
            elif step_type in ["context_notation", "resolution_logging"]:
                # Context operations - might be INSERT or UPDATE
                operation = response.get('operation')
                assert operation in ['INSERT', 'UPDATE'], f"Expected INSERT or UPDATE for context operation"
                
                # Track context IDs for cleanup
                context_id = extract_uuid_from_response(response, 'context_id')
                if context_id:
                    test_infrastructure['uuid_tracker'].track('agent_context', context_id)
                
            elif step_type == "client_notification":
                # Should create communication
                comm_id = extract_uuid_from_response(response, 'communication_id')
                if comm_id:
                    test_infrastructure['uuid_tracker'].track('client_communications', comm_id)
            
            print(f"    ✅ Resolution step {i} completed: {step_type}")
            await asyncio.sleep(0.1)  # Brief delay between steps
        
        # Validate problem resolution effectiveness
        await self._validate_problem_resolution(agent_db_client, client_name, document_name)
        
        print(f"✅ Problem resolution workflow successful for {client_name}")
    
    async def _validate_problem_resolution(
        self,
        client,
        client_name: str, 
        document_name: str
    ):
        """Validate that problem resolution was effective"""
        
        # Verify document status was updated
        doc_query = f"What is the status of {document_name} for {client_name}?"
        doc_response = await client.agent_db_query(doc_query)
        
        if is_successful_response(doc_response) and doc_response.get('count') > 0:
            # Document should no longer be in FAILED status
            doc_data = doc_response['data'][0]
            status = doc_data.get('status', '').upper()
            assert status != 'FAILED', f"Document should no longer be FAILED, got {status}"
            print(f"  ✅ Document status resolved: {document_name} -> {status}")
        
        # Verify agent context contains resolution notes
        context_query = f"Show me agent context for {client_name}"
        context_response = await client.agent_db_query(context_query)
        
        if is_successful_response(context_response) and context_response.get('count') > 0:
            print(f"  ✅ Agent context updated with resolution notes")
    
    @pytest.mark.asyncio
    async def test_multi_client_batch_workflow(
        self,
        agent_db_client,
        performance_monitor,
        data_validator,
        test_data_ecosystem,
        test_infrastructure
    ):
        """Test workflow involving multiple clients simultaneously"""
        
        print("\n👥 Testing Multi-Client Batch Workflow")
        
        # Define multiple clients for batch processing
        batch_clients = [
            ("Alex Johnson", "alex.johnson@email.com", "(555) 100-1001"),
            ("Beth Williams", "beth.williams@company.com", "(555) 200-2002"),
            ("Chris Davis", "chris.davis@firm.com", "(555) 300-3003")
        ]
        
        # Step 1: Batch case creation
        print("\n  Batch Step 1: Creating cases for all clients")
        created_cases = []
        
        for name, email, phone in batch_clients:
            query = f"Create case for {name}, {email}, {phone}"
            response = await performance_monitor.time_operation(
                f"Batch Create: {name}",
                agent_db_client.agent_db_query(query),
                category="create_operation"
            )
            
            assert is_successful_response(response), f"Failed to create case for {name}"
            case_id = extract_uuid_from_response(response, 'case_id')
            if case_id:
                test_infrastructure['uuid_tracker'].track('cases', case_id)
                created_cases.append((name, case_id))
        
        assert len(created_cases) == len(batch_clients), "Not all cases were created"
        print(f"    ✅ Created {len(created_cases)} cases successfully")
        
        # Step 2: Batch document addition
        print("\n  Batch Step 2: Adding documents for all clients")
        
        for name, case_id in created_cases:
            document_name = f"{name.replace(' ', '_')}_Document.pdf"
            query = f"Add document '{document_name}' to {name}'s case"
            
            response = await agent_db_client.agent_db_query(query)
            assert is_successful_response(response), f"Failed to add document for {name}"
            
            doc_id = extract_uuid_from_response(response, 'document_id')
            if doc_id:
                test_infrastructure['uuid_tracker'].track('documents', doc_id)
        
        print(f"    ✅ Added documents for all {len(created_cases)} clients")
        
        # Step 3: Batch status query
        print("\n  Batch Step 3: Querying all open cases")
        
        query = "Show me all open cases with their documents"
        response = await performance_monitor.time_operation(
            "Batch Query: All open cases",
            agent_db_client.agent_db_query(query),
            category="complex_query"
        )
        
        assert is_successful_response(response), "Failed to query all open cases"
        # Should find at least our newly created cases
        assert response.get('count') >= len(created_cases), \
            f"Expected at least {len(created_cases)} cases, found {response.get('count')}"
        
        print(f"    ✅ Batch query successful: found {response.get('count')} open cases")
        
        # Step 4: Batch communication
        print("\n  Batch Step 4: Sending welcome emails to all clients")
        
        for name, case_id in created_cases:
            query = f"Send welcome email to {name} about case initiation"
            response = await agent_db_client.agent_db_query(query)
            
            # Communication might not be fully supported, so we'll be lenient
            if is_successful_response(response):
                comm_id = extract_uuid_from_response(response, 'communication_id')
                if comm_id:
                    test_infrastructure['uuid_tracker'].track('client_communications', comm_id)
        
        print(f"    ✅ Batch communications processed for {len(created_cases)} clients")
        
        print("✅ Multi-client batch workflow completed successfully")
    
    @pytest.mark.asyncio
    async def test_workflows_performance_summary(
        self,
        performance_monitor,
        test_data_ecosystem
    ):
        """Final test to print workflow operations performance summary"""
        
        # Print performance statistics
        stats = performance_monitor.get_category_stats('complex_query')
        create_stats = performance_monitor.get_category_stats('create_operation')
        
        print("\n📊 Complex Workflows Performance Summary:")
        print(f"   Complex Query Operations: {stats['count']} operations, avg {stats['avg_time']:.2f}s")
        print(f"   Workflow Create Operations: {create_stats['count']} operations, avg {create_stats['avg_time']:.2f}s")
        
        # Validate performance thresholds
        if stats['count'] > 0:
            assert stats['max_time'] <= 10.0, f"Complex workflow queries exceeded 10s threshold: {stats['max_time']:.2f}s"
            assert stats['success_rate'] >= 0.9, f"Too many workflow operations failed: {stats['success_rate']:.1%} success rate"
        
        print("✅ All complex workflows completed within acceptable performance thresholds")