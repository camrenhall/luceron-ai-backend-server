"""
Phase 2: READ Operations Testing via agent/db endpoint
Tests natural language queries for data retrieval and filtering
"""

import pytest
from typing import Dict, Any, List
from infrastructure import format_test_name, is_successful_response


class TestReadOperations:
    """Test natural language READ operations through agent/db endpoint"""
    
    @pytest.mark.asyncio
    @pytest.mark.parametrize("query,expected_operation,validation_checks", [
        # A1: Simple Entity Queries
        (
            "Show me Sarah Johnson's case",
            "READ",
            {
                'should_contain_data': True,
                'expected_resource': 'cases',
                'should_have_client': 'Sarah Johnson'
            }
        ),
        (
            "What documents does Michael Chen have?",
            "READ", 
            {
                'should_contain_data': True,
                'expected_resource': 'documents',
                'should_reference_client': 'Michael Chen'
            }
        ),
        (
            "List all communications for Rebecca Martinez",
            "READ",
            {
                'should_contain_data': True,
                'expected_resource': 'client_communications',
                'should_reference_client': 'Rebecca Martinez'
            }
        ),
        (
            "Show me David Thompson's case details",
            "READ",
            {
                'should_contain_data': True,
                'expected_resource': 'cases',
                'should_have_client': 'David Thompson'
            }
        )
    ])
    async def test_simple_entity_queries(
        self, 
        query: str, 
        expected_operation: str, 
        validation_checks: Dict[str, Any],
        agent_db_client,
        performance_monitor,
        data_validator,
        test_data_ecosystem
    ):
        """Test Category A1: Simple entity queries"""
        
        # Execute query with performance monitoring
        response = await performance_monitor.time_operation(
            f"Simple Query: {format_test_name(query)}",
            agent_db_client.agent_db_query(query),
            category="simple_query"
        )
        
        # Validate response structure
        validation = data_validator.validate_agent_db_response(response)
        assert validation['valid'], f"Invalid response structure: {validation['errors']}"
        
        # Verify successful operation
        assert is_successful_response(response), f"Query failed: {response}"
        assert response.get('ok') is True, "Response not marked as successful"
        
        # Validate operation type
        assert response.get('operation') == expected_operation, f"Expected {expected_operation}, got {response.get('operation')}"
        
        # Validate resource targeting
        if validation_checks.get('expected_resource'):
            assert response.get('resource') == validation_checks['expected_resource'], \
                f"Expected resource {validation_checks['expected_resource']}, got {response.get('resource')}"
        
        # Validate data presence
        if validation_checks.get('should_contain_data'):
            assert 'data' in response, "Response missing data field"
            assert isinstance(response['data'], list), "Data field should be a list"
            if validation_checks.get('should_contain_data') is True:
                assert len(response['data']) > 0, f"Expected data but got empty result for: {query}"
        
        # Validate count field
        assert 'count' in response, "Response missing count field"
        assert isinstance(response['count'], int), "Count should be an integer"
        assert response['count'] >= 0, "Count should be non-negative"
        
        print(f"✅ Simple query successful: {format_test_name(query)} -> {response['count']} results")
    
    @pytest.mark.asyncio
    @pytest.mark.parametrize("query,expected_results", [
        # A2: Status-Based Filtering
        (
            "Show me all open cases",
            {'should_find_cases': True, 'status_filter': 'OPEN'}
        ),
        (
            "What documents are currently processing?",
            {'should_find_documents': True, 'status_filter': 'PROCESSING'}
        ),
        (
            "Find failed email communications",
            {'should_find_communications': True, 'status_filter': 'failed'}
        ),
        (
            "Show me completed documents",
            {'should_find_documents': True, 'status_filter': 'COMPLETED'}
        ),
        (
            "List all delivered emails",
            {'should_find_communications': True, 'status_filter': 'delivered'}
        )
    ])
    async def test_status_based_filtering(
        self,
        query: str,
        expected_results: Dict[str, Any],
        agent_db_client,
        performance_monitor,
        data_validator,
        test_data_ecosystem
    ):
        """Test Category A2: Status-based filtering queries"""
        
        # Execute query with performance monitoring
        response = await performance_monitor.time_operation(
            f"Status Filter: {format_test_name(query)}",
            agent_db_client.agent_db_query(query),
            category="simple_query"
        )
        
        # Validate response structure
        validation = data_validator.validate_agent_db_response(response)
        assert validation['valid'], f"Invalid response structure: {validation['errors']}"
        
        # Verify successful operation
        assert is_successful_response(response), f"Status filter query failed: {response}"
        assert response.get('ok') is True, "Response not marked as successful"
        assert response.get('operation') == 'READ', f"Expected READ operation, got {response.get('operation')}"
        
        # Validate that results are filtered (may be empty, which is valid)
        assert 'data' in response, "Response missing data field"
        assert 'count' in response, "Response missing count field"
        assert response['count'] >= 0, "Count should be non-negative"
        
        # If we expect to find results based on our test data, validate
        if expected_results.get('should_find_cases') and 'open' in query.lower():
            # We know from test data setup that we have open cases
            assert response['count'] > 0, f"Expected to find open cases but got {response['count']}"
        
        if expected_results.get('should_find_documents') and 'processing' in query.lower():
            # We know from test data that Sarah has processing documents
            assert response['count'] > 0, f"Expected to find processing documents but got {response['count']}"
        
        print(f"✅ Status filter successful: {format_test_name(query)} -> {response['count']} results")
    
    @pytest.mark.asyncio
    @pytest.mark.parametrize("query,time_expectation", [
        # A3: Time-Based Queries
        (
            "Show me cases created in the last week",
            {'should_find_recent': True, 'time_range': 'week'}
        ),
        (
            "What communications happened today?",
            {'should_find_recent': True, 'time_range': 'day'}
        ),
        (
            "Find documents uploaded this month",
            {'should_find_recent': True, 'time_range': 'month'}
        ),
        (
            "Show me recent email communications",
            {'should_find_recent': True, 'time_range': 'recent'}
        )
    ])
    async def test_time_based_queries(
        self,
        query: str,
        time_expectation: Dict[str, Any],
        agent_db_client,
        performance_monitor,
        data_validator,
        test_data_ecosystem
    ):
        """Test Category A3: Time-based queries with date calculations"""
        
        # Execute query with performance monitoring
        response = await performance_monitor.time_operation(
            f"Time Query: {format_test_name(query)}",
            agent_db_client.agent_db_query(query),
            category="simple_query"
        )
        
        # Validate response structure
        validation = data_validator.validate_agent_db_response(response)
        assert validation['valid'], f"Invalid response structure: {validation['errors']}"
        
        # Verify successful operation
        assert is_successful_response(response), f"Time-based query failed: {response}"
        assert response.get('ok') is True, "Response not marked as successful"
        assert response.get('operation') == 'READ', f"Expected READ operation, got {response.get('operation')}"
        
        # Validate response structure
        assert 'data' in response, "Response missing data field"
        assert 'count' in response, "Response missing count field"
        
        # Since our test data was just created, time-based queries should find recent data
        if time_expectation.get('should_find_recent'):
            # We expect to find recently created test data
            assert response['count'] >= 0, "Count should be non-negative"
            
            # For "last week" or "today" queries, we should find our just-created test data
            if 'week' in query.lower() or 'today' in query.lower() or 'recent' in query.lower():
                assert response['count'] > 0, f"Expected to find recent data but got {response['count']} for: {query}"
        
        print(f"✅ Time query successful: {format_test_name(query)} -> {response['count']} results")
    
    @pytest.mark.asyncio
    @pytest.mark.parametrize("query,relationship_checks", [
        # A4: Cross-Entity Relationship Queries
        (
            "Show me all completed analyses for Sarah Johnson",
            {
                'involves_multiple_tables': True,
                'should_join': ['cases', 'document_analysis'],
                'client_filter': 'Sarah Johnson',
                'status_filter': 'completed'
            }
        ),
        (
            "What cases have failed document processing?",
            {
                'involves_multiple_tables': True,
                'should_join': ['cases', 'documents'],
                'status_filter': 'failed'
            }
        ),
        (
            "Find clients who haven't responded to emails",
            {
                'involves_multiple_tables': True,
                'should_join': ['cases', 'client_communications'],
                'complex_logic': True
            }
        ),
        (
            "Show me all documents and their analysis status for Michael Chen",
            {
                'involves_multiple_tables': True,
                'should_join': ['cases', 'documents', 'document_analysis'],
                'client_filter': 'Michael Chen'
            }
        )
    ])
    async def test_cross_entity_relationships(
        self,
        query: str,
        relationship_checks: Dict[str, Any],
        agent_db_client,
        performance_monitor,
        data_validator,
        test_data_ecosystem
    ):
        """Test Category A4: Cross-entity relationship queries with JOINs"""
        
        # Execute query with performance monitoring  
        response = await performance_monitor.time_operation(
            f"Relationship Query: {format_test_name(query)}",
            agent_db_client.agent_db_query(query),
            category="complex_query"
        )
        
        # Validate response structure
        validation = data_validator.validate_agent_db_response(response)
        assert validation['valid'], f"Invalid response structure: {validation['errors']}"
        
        # Verify successful operation
        assert is_successful_response(response), f"Relationship query failed: {response}"
        assert response.get('ok') is True, "Response not marked as successful"
        assert response.get('operation') == 'READ', f"Expected READ operation, got {response.get('operation')}"
        
        # Validate response structure
        assert 'data' in response, "Response missing data field"
        assert 'count' in response, "Response missing count field"
        assert response['count'] >= 0, "Count should be non-negative"
        
        # For specific client queries, we should find data based on our test setup
        if relationship_checks.get('client_filter') == 'Sarah Johnson' and 'analyses' in query.lower():
            # Sarah has completed document analyses in test data
            assert response['count'] > 0, f"Expected to find analyses for Sarah Johnson but got {response['count']}"
        
        if relationship_checks.get('client_filter') == 'Michael Chen' and 'documents' in query.lower():
            # Michael has documents in test data
            assert response['count'] > 0, f"Expected to find documents for Michael Chen but got {response['count']}"
        
        if 'failed' in query.lower() and 'processing' in query.lower():
            # We have failed documents in test data (Rebecca's and Sarah's)
            assert response['count'] > 0, f"Expected to find failed processing cases but got {response['count']}"
        
        print(f"✅ Relationship query successful: {format_test_name(query)} -> {response['count']} results")
    
    @pytest.mark.asyncio
    @pytest.mark.parametrize("query,aggregation_checks", [
        # A5: Aggregation and Counting
        (
            "How many emails were sent to each client?",
            {
                'aggregation_type': 'count',
                'group_by': 'client',
                'filter_by': 'email'
            }
        ),
        (
            "Count documents by processing status",
            {
                'aggregation_type': 'count',
                'group_by': 'status',
                'resource': 'documents'
            }
        ),
        (
            "How many cases does each client have?",
            {
                'aggregation_type': 'count',
                'group_by': 'client',
                'resource': 'cases'
            }
        ),
        (
            "Show me communication counts by channel type",
            {
                'aggregation_type': 'count',
                'group_by': 'channel',
                'resource': 'communications'
            }
        )
    ])
    async def test_aggregation_and_counting(
        self,
        query: str,
        aggregation_checks: Dict[str, Any],
        agent_db_client,
        performance_monitor,
        data_validator,
        test_data_ecosystem
    ):
        """Test Category A5: Aggregation and counting operations"""
        
        # Execute query with performance monitoring
        response = await performance_monitor.time_operation(
            f"Aggregation Query: {format_test_name(query)}",
            agent_db_client.agent_db_query(query),
            category="complex_query"
        )
        
        # Validate response structure
        validation = data_validator.validate_agent_db_response(response)
        assert validation['valid'], f"Invalid response structure: {validation['errors']}"
        
        # Verify successful operation
        assert is_successful_response(response), f"Aggregation query failed: {response}"
        assert response.get('ok') is True, "Response not marked as successful"
        assert response.get('operation') == 'READ', f"Expected READ operation, got {response.get('operation')}"
        
        # Validate response structure
        assert 'data' in response, "Response missing data field"
        assert 'count' in response, "Response missing count field"
        assert response['count'] >= 0, "Count should be non-negative"
        
        # For counting/aggregation queries, we should get some results from our test data
        if 'count' in query.lower() or 'how many' in query.lower():
            # Aggregation queries should return groupings, so we expect results
            assert response['count'] > 0, f"Expected aggregation results but got {response['count']} for: {query}"
        
        # Validate that data contains aggregated results
        if response['count'] > 0 and response['data']:
            # Each item should represent an aggregated group
            first_item = response['data'][0]
            assert isinstance(first_item, dict), "Aggregation results should be dictionaries"
            
            # Should have some kind of grouping or count information
            has_aggregation_fields = any(
                key in first_item for key in ['count', 'total', 'sum', 'avg', 'client_name', 'status', 'channel']
            )
            assert has_aggregation_fields, f"Aggregation result should contain relevant fields: {first_item}"
        
        print(f"✅ Aggregation query successful: {format_test_name(query)} -> {response['count']} groups")
    
    @pytest.mark.asyncio
    async def test_read_operations_performance_summary(
        self,
        performance_monitor,
        test_data_ecosystem
    ):
        """Final test to print READ operations performance summary"""
        
        # Print performance statistics
        stats = performance_monitor.get_category_stats('simple_query')
        complex_stats = performance_monitor.get_category_stats('complex_query')
        
        print("\n📊 READ Operations Performance Summary:")
        print(f"   Simple Queries: {stats['count']} operations, avg {stats['avg_time']:.2f}s")
        print(f"   Complex Queries: {complex_stats['count']} operations, avg {complex_stats['avg_time']:.2f}s")
        
        # Validate performance thresholds
        if stats['count'] > 0:
            assert stats['max_time'] <= 2.0, f"Simple queries exceeded 2s threshold: {stats['max_time']:.2f}s"
        
        if complex_stats['count'] > 0:
            assert complex_stats['max_time'] <= 5.0, f"Complex queries exceeded 5s threshold: {complex_stats['max_time']:.2f}s"
        
        print("✅ All READ operations completed within performance thresholds")