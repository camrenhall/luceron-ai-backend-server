"""
Base CRUD Test Class
Eliminates code duplication across all resource-specific test suites
"""

import pytest
from typing import Dict, Any, Optional
from abc import ABC, abstractmethod

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.test_orchestrator import TestOrchestrator
from config.resources import get_resource_config, ResourceConfig


class BaseCRUDTest(ABC):
    """
    Abstract base class for CRUD testing
    Provides common test patterns for all resources
    """
    
    @property
    @abstractmethod
    def resource_name(self) -> str:
        """Resource name (must be defined in subclasses)"""
        pass
    
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        # Automatically add pytest markers to subclasses
        cls = pytest.mark.crud(cls)
        cls = pytest.mark.regression(cls)
    
    @pytest.fixture(autouse=True)
    def setup_resource_config(self):
        """Automatically setup resource configuration"""
        self.config = get_resource_config(self.resource_name)
        self.dependencies = {}
    
    async def create_dependencies(self, orchestrator: TestOrchestrator) -> Dict[str, str]:
        """Create required dependencies for this resource"""
        created_deps = {}
        
        for dep_name in self.config.dependencies:
            dep_config = get_resource_config(dep_name)
            factory_method = getattr(orchestrator.data_factory, dep_config.factory_method)
            
            # Handle dependencies with their own dependencies
            if dep_name == "documents" and "cases" in self.config.dependencies:
                dep_data, dep_id = factory_method(created_deps.get("cases"))
            elif dep_name == "agent_messages" and "agent_conversations" in created_deps:
                dep_data, dep_id = factory_method(created_deps["agent_conversations"], 1)
            else:
                dep_data, dep_id = factory_method()
            
            # Create the dependency
            create_result = await orchestrator.execute_create(
                resource=dep_name,
                endpoint=dep_config.endpoint, 
                data=dep_data
            )
            
            assert create_result.success, f"Failed to create dependency {dep_name}: {create_result.errors}"
            created_deps[dep_name] = create_result.uuid
            
        return created_deps
    
    def generate_test_data(self, orchestrator: TestOrchestrator, **overrides) -> tuple[Dict[str, Any], str]:
        """Generate test data for this resource"""
        factory_method = getattr(orchestrator.data_factory, self.config.factory_method)
        
        # Handle resources that need dependencies in their data
        if self.config.dependencies:
            if "cases" in self.dependencies:
                if self.config.factory_method == "generate_document":
                    return factory_method(self.dependencies["cases"], **overrides)
                elif self.config.factory_method == "generate_communication":
                    return factory_method(self.dependencies["cases"], **overrides)
                elif self.config.factory_method == "generate_agent_context":
                    return factory_method(self.dependencies["cases"], **overrides)
            elif "agent_conversations" in self.dependencies:
                return factory_method(self.dependencies["agent_conversations"], 1, **overrides)
        
        return factory_method(**overrides)
    
    async def test_full_crud_cycle(self, clean_orchestrator: TestOrchestrator):
        """
        Test complete CREATE → READ → UPDATE → DELETE cycle
        Generic implementation for any resource
        """
        orch = clean_orchestrator
        
        # Create dependencies if needed
        self.dependencies = await self.create_dependencies(orch)
        
        # Generate test data
        test_data, expected_id = self.generate_test_data(orch)
        
        # === CREATE ===
        create_result = await orch.execute_create(
            resource=self.resource_name,
            endpoint=self.config.endpoint,
            data=test_data
        )
        
        assert create_result.success, f"{self.resource_name} creation failed: {create_result.errors}"
        assert create_result.uuid, f"No UUID returned from {self.resource_name} creation"
        created_id = create_result.uuid
        
        # Validate database state after CREATE
        create_validation = await orch.validate_database_state(
            table=self.config.table,
            uuid_field=self.config.uuid_field,
            uuid_value=created_id,
            operation="CREATE"
        )
        assert create_validation.valid, f"Database validation failed after CREATE: {create_validation.errors}"
        
        # === READ ===
        read_result = await orch.execute_read(
            resource=self.resource_name,
            endpoint=f"{self.config.endpoint}/{{id}}",
            uuid_value=created_id
        )
        
        assert read_result.success, f"{self.resource_name} read failed: {read_result.errors}"
        
        # === UPDATE ===
        update_data = self.get_update_data()
        update_result = await orch.execute_update(
            resource=self.resource_name,
            endpoint=f"{self.config.endpoint}/{{id}}",
            uuid_value=created_id,
            data=update_data
        )
        
        assert update_result.success, f"{self.resource_name} update failed: {update_result.errors}"
        
        # Validate database state after UPDATE
        update_validation = await orch.validate_database_state(
            table=self.config.table,
            uuid_field=self.config.uuid_field,
            uuid_value=created_id,
            operation="UPDATE"
        )
        assert update_validation.valid, f"Database validation failed after UPDATE: {update_validation.errors}"
        
        # === DELETE ===
        delete_result = await orch.execute_delete(
            resource=self.resource_name,
            endpoint=f"{self.config.endpoint}/{{id}}",
            uuid_value=created_id
        )
        
        assert delete_result.success, f"{self.resource_name} DELETE failed: {delete_result.errors}"
        
        # Verify deletion by checking 404 response
        verify_response, _ = await orch.time_operation(
            "VERIFY_DELETE",
            orch.rest_client.request("GET", f"{self.config.endpoint}/{created_id}")
        )
        
        assert not verify_response.get("_success", True), f"{self.resource_name} should not exist after DELETE"
        assert verify_response.get("_status_code") == 404, f"Expected 404, got {verify_response.get('_status_code')}"
    
    async def test_list_operation(self, clean_orchestrator: TestOrchestrator):
        """Test list endpoint for this resource"""
        orch = clean_orchestrator
        
        # Create dependencies and test data
        self.dependencies = await self.create_dependencies(orch)
        test_data, _ = self.generate_test_data(orch)
        
        # Create a test record first
        create_result = await orch.execute_create(
            resource=self.resource_name,
            endpoint=self.config.endpoint,
            data=test_data
        )
        
        assert create_result.success, f"Failed to create test {self.resource_name} for list test"
        
        # Test list endpoint
        response, duration = await orch.time_operation(
            f"LIST {self.resource_name}",
            orch.rest_client.request("GET", self.config.endpoint, params=self.config.list_params)
        )
        
        assert response.get("_success", False), f"{self.resource_name} list failed: {response}"
        assert "data" in response or self.resource_name in response or isinstance(response, list), \
            "List response should contain data"
    
    async def test_search_operation(self, clean_orchestrator: TestOrchestrator):
        """Test search endpoint for this resource"""
        orch = clean_orchestrator
        
        # Create dependencies and test data with searchable content
        self.dependencies = await self.create_dependencies(orch)
        search_data = self.get_searchable_test_data(orch)
        test_data, _ = self.generate_test_data(orch, **search_data)
        
        # Create test record
        create_result = await orch.execute_create(
            resource=self.resource_name,
            endpoint=self.config.endpoint,
            data=test_data
        )
        
        assert create_result.success, f"Failed to create test {self.resource_name} for search test"
        
        # Test search endpoint
        search_params = self.get_search_params()
        response, duration = await orch.time_operation(
            f"SEARCH {self.resource_name}",
            orch.rest_client.request("POST", self.config.search_endpoint, data=search_params)
        )
        
        assert response.get("_success", False), f"{self.resource_name} search failed: {response}"
    
    async def test_validation_errors(self, clean_orchestrator: TestOrchestrator):
        """Test resource creation with invalid data"""
        orch = clean_orchestrator
        
        # Create dependencies if needed
        self.dependencies = await self.create_dependencies(orch)
        
        # Get invalid data for this resource
        invalid_data = self.get_invalid_test_data()
        
        create_result = await orch.execute_create(
            resource=self.resource_name,
            endpoint=self.config.endpoint,
            data=invalid_data
        )
        
        # Should fail validation
        assert not create_result.success, f"{self.resource_name} creation should fail with invalid data"
        assert create_result.errors, "Should have validation errors"
    
    async def test_performance_thresholds(self, clean_orchestrator: TestOrchestrator):
        """Test operations meet performance thresholds"""
        orch = clean_orchestrator
        
        # Create dependencies and test data
        self.dependencies = await self.create_dependencies(orch)
        test_data, _ = self.generate_test_data(orch)
        
        # Test CREATE performance
        create_result = await orch.execute_create(
            resource=self.resource_name,
            endpoint=self.config.endpoint,
            data=test_data
        )
        
        assert create_result.success, f"{self.resource_name} creation failed"
        assert create_result.duration <= orch.config.create_operation_threshold, \
            f"CREATE took {create_result.duration}s, threshold: {orch.config.create_operation_threshold}s"
        
        # Test READ performance
        read_result = await orch.execute_read(
            resource=self.resource_name,
            endpoint=f"{self.config.endpoint}/{{id}}",
            uuid_value=create_result.uuid
        )
        
        assert read_result.success, f"{self.resource_name} read failed"
        assert read_result.duration <= orch.config.read_operation_threshold, \
            f"READ took {read_result.duration}s, threshold: {orch.config.read_operation_threshold}s"
    
    # Abstract methods that subclasses should implement for resource-specific behavior
    
    def get_update_data(self) -> Dict[str, Any]:
        """Get data for UPDATE operation (default implementation)"""
        # Default update data - subclasses can override
        return {"status": "UPDATED"}
    
    def get_searchable_test_data(self, orchestrator: TestOrchestrator) -> Dict[str, Any]:
        """Get searchable data for search tests (default implementation)"""
        # Default searchable data - subclasses can override
        return {f"{orchestrator.config.test_data_prefix}_SearchTest": True}
    
    def get_search_params(self) -> Dict[str, Any]:
        """Get search parameters (default implementation)"""
        # Default search params - subclasses can override
        return {"query": "SearchTest"}
    
    def get_invalid_test_data(self) -> Dict[str, Any]:
        """Get invalid data for validation tests (default implementation)"""
        # Default invalid data - subclasses can override
        return {}