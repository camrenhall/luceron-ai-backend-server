"""
Lightweight API Contract Test Orchestrator
Central coordination for API-only CRUD testing
Enterprise-grade contract validation without database dependencies
"""

import asyncio
import time
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.rest_client import RestClient
from core.data_factory import DataFactory
from config import get_config


@dataclass
class TestResult:
    """Simple test result container"""
    operation: str
    resource: str
    success: bool
    duration: float
    errors: List[str]
    warnings: List[str]
    uuid: Optional[str] = None


@dataclass
class CRUDCycleResult:
    """Results from complete CRUD cycle"""
    resource: str
    create_result: TestResult
    read_result: TestResult
    update_result: TestResult
    delete_result: TestResult
    total_duration: float


class APITestOrchestrator:
    """Lightweight API contract testing coordinator"""
    
    def __init__(self):
        self.config = get_config()
        self.rest_client = RestClient()
        self.data_factory = DataFactory()
        self.results: List[TestResult] = []
        
    async def setup(self):
        """Initialize components"""
        pass  # No setup needed for API-only testing
        
    async def teardown(self):
        """Cleanup components"""
        pass  # No cleanup needed - API handles data lifecycle
    
    async def time_operation(self, operation_name: str, coro) -> Tuple[Any, float]:
        """Time an operation and return result + duration"""
        start_time = time.time()
        result = await coro
        duration = time.time() - start_time
        return result, duration
    
    def _extract_uuid(self, response: Dict[str, Any]) -> Optional[str]:
        """Extract UUID from API response - handles various response formats"""
        # Common UUID field names - ordered by specificity (most specific first)
        uuid_fields = ['message_id', 'summary_id', 'context_id', 'document_id', 'communication_id', 
                      'conversation_id', 'case_id', 'error_id', 'id']
        
        # Try direct fields first
        for field in uuid_fields:
            if field in response:
                return str(response[field])
        
        # Try nested in data
        if 'data' in response and response['data']:
            for field in uuid_fields:
                if field in response['data']:
                    return str(response['data'][field])
                    
        return None
    
    def _validate_create_data(self, create_data: Dict[str, Any], read_response: Dict[str, Any]):
        """Validate that created data matches what was sent"""
        response_data = read_response.get('data', read_response)
        
        for key, expected_value in create_data.items():
            if key in response_data:
                actual_value = response_data[key]
                if str(actual_value) != str(expected_value):
                    raise AssertionError(f"CREATE validation failed: {key} = {actual_value}, expected {expected_value}")
    
    def _validate_update_data(self, update_data: Dict[str, Any], read_response: Dict[str, Any]):
        """Validate that updated data matches what was sent"""
        response_data = read_response.get('data', read_response)
        
        for key, expected_value in update_data.items():
            if key in response_data:
                actual_value = response_data[key]
                if str(actual_value) != str(expected_value):
                    raise AssertionError(f"UPDATE validation failed: {key} = {actual_value}, expected {expected_value}")
    
    async def execute_crud_cycle(self, resource: str, endpoints: Dict[str, str]) -> CRUDCycleResult:
        """Execute complete CRUD cycle with API contract validation"""
        print(f"\n🔄 Starting CRUD cycle for {resource}")
        
        # Generate test data
        if resource == "documents":
            # Documents need a case_id, so create a case first
            case_data, _ = self.data_factory.generate_case()
            case_response = await self.rest_client.request("POST", "/api/cases", case_data)
            if not case_response.get("_success", False):
                raise RuntimeError(f"Failed to create parent case for document test: {case_response}")
            case_id = self._extract_uuid(case_response)
            create_data, expected_id = self.data_factory.generate_document(case_id)
        elif resource == "communications":
            # Communications need a case_id
            case_data, _ = self.data_factory.generate_case()
            case_response = await self.rest_client.request("POST", "/api/cases", case_data)
            if not case_response.get("_success", False):
                raise RuntimeError(f"Failed to create parent case for communication test: {case_response}")
            case_id = self._extract_uuid(case_response)
            create_data, expected_id = self.data_factory.generate_communication(case_id)
        else:
            # Direct resource generation
            factory_method = getattr(self.data_factory, f"generate_{resource.rstrip('s')}")
            create_data, expected_id = factory_method()
        
        cycle_start = time.time()
        
        # === CREATE ===
        print(f"   📝 CREATE {resource}")
        create_response, create_duration = await self.time_operation(
            f"CREATE {resource}",
            self.rest_client.request("POST", endpoints["create"], create_data)
        )
        
        if not create_response.get("_success", False):
            raise AssertionError(f"CREATE failed: {create_response}")
        
        resource_id = self._extract_uuid(create_response)
        if not resource_id:
            raise AssertionError("No UUID returned from CREATE operation")
        
        create_result = TestResult("CREATE", resource, True, create_duration, [], [], resource_id)
        print(f"      ✅ Created {resource_id} in {create_duration:.3f}s")
        
        # === READ (validates CREATE worked) ===
        print(f"   📖 READ {resource}")
        read_response, read_duration = await self.time_operation(
            f"READ {resource}",
            self.rest_client.request("GET", endpoints["read"].format(id=resource_id))
        )
        
        if not read_response.get("_success", False):
            raise AssertionError(f"READ failed after CREATE: {read_response}")
        
        # Validate CREATE data integrity via API response
        self._validate_create_data(create_data, read_response)
        
        read_result = TestResult("READ", resource, True, read_duration, [], [], resource_id)
        print(f"      ✅ Read validated in {read_duration:.3f}s")
        
        # === UPDATE ===
        print(f"   ✏️  UPDATE {resource}")
        update_data = self._generate_update_data(resource)
        update_response, update_duration = await self.time_operation(
            f"UPDATE {resource}",
            self.rest_client.request("PUT", endpoints["update"].format(id=resource_id), update_data)
        )
        
        if not update_response.get("_success", False):
            raise AssertionError(f"UPDATE failed: {update_response}")
        
        update_result = TestResult("UPDATE", resource, True, update_duration, [], [], resource_id)
        print(f"      ✅ Updated in {update_duration:.3f}s")
        
        # === READ (validates UPDATE worked) ===
        print(f"   📖 READ after UPDATE")
        updated_read_response, updated_read_duration = await self.time_operation(
            f"READ after UPDATE {resource}",
            self.rest_client.request("GET", endpoints["read"].format(id=resource_id))
        )
        
        if not updated_read_response.get("_success", False):
            raise AssertionError(f"READ failed after UPDATE: {updated_read_response}")
        
        # Validate UPDATE data integrity via API response
        self._validate_update_data(update_data, updated_read_response)
        print(f"      ✅ Update validated in {updated_read_duration:.3f}s")
        
        # === DELETE ===
        print(f"   🗑️  DELETE {resource}")
        delete_response, delete_duration = await self.time_operation(
            f"DELETE {resource}",
            self.rest_client.request("DELETE", endpoints["delete"].format(id=resource_id))
        )
        
        if not delete_response.get("_success", False):
            raise AssertionError(f"DELETE failed: {delete_response}")
        
        delete_result = TestResult("DELETE", resource, True, delete_duration, [], [], resource_id)
        print(f"      ✅ Deleted in {delete_duration:.3f}s")
        
        # === READ (validates DELETE worked) ===
        print(f"   📖 READ after DELETE (should be 404)")
        final_read_response, final_read_duration = await self.time_operation(
            f"READ after DELETE {resource}",
            self.rest_client.request("GET", endpoints["read"].format(id=resource_id))
        )
        
        # DELETE validation - should return 404
        if final_read_response.get("_status_code") != 404:
            raise AssertionError(f"DELETE validation failed - resource still exists: {final_read_response}")
        
        print(f"      ✅ Delete validated (404) in {final_read_duration:.3f}s")
        
        total_duration = time.time() - cycle_start
        print(f"   🎯 CRUD cycle completed in {total_duration:.3f}s")
        
        return CRUDCycleResult(
            resource=resource,
            create_result=create_result,
            read_result=read_result,
            update_result=update_result,
            delete_result=delete_result,
            total_duration=total_duration
        )
    
    def _generate_update_data(self, resource: str) -> Dict[str, Any]:
        """Generate update data for different resource types"""
        if resource == "cases":
            return {"status": "CLOSED"}
        elif resource == "documents":
            return {"status": "PROCESSING"}
        elif resource == "communications":
            return {"direction": "outgoing"}
        elif resource == "agent_conversations":
            return {"status": "completed"}
        elif resource == "error_logs":
            return {"status": "resolved"}
        else:
            return {"status": "updated"}
    
    # Legacy methods for backward compatibility with existing tests
    async def execute_create(self, resource: str, endpoint: str, data: Dict[str, Any]) -> TestResult:
        """Execute CREATE operation - legacy compatibility"""
        response, duration = await self.time_operation(
            f"CREATE {resource}",
            self.rest_client.request("POST", endpoint, data)
        )
        
        success = response.get("_success", False)
        errors = []
        warnings = []
        uuid_value = None
        
        if not success:
            status_code = response.get('_status_code', 'Unknown')
            error_detail = response.get('detail', response.get('message', 'No error message'))
            errors.append(f"HTTP {status_code}: {error_detail}")
        else:
            uuid_value = self._extract_uuid(response)
            if not uuid_value:
                warnings.append("Could not extract UUID from response")
        
        result = TestResult("CREATE", resource, success, duration, errors, warnings, uuid_value)
        self.results.append(result)
        return result
    
    async def execute_read(self, resource: str, endpoint: str, uuid_value: str) -> TestResult:
        """Execute READ operation - legacy compatibility"""
        read_endpoint = endpoint.replace("{id}", uuid_value)
        response, duration = await self.time_operation(
            f"READ {resource}",
            self.rest_client.request("GET", read_endpoint)
        )
        
        success = response.get("_success", False)
        errors = []
        warnings = []
        
        if not success:
            status_code = response.get('_status_code', 'Unknown')
            error_detail = response.get('detail', response.get('message', 'No error message'))
            errors.append(f"HTTP {status_code}: {error_detail}")
        
        result = TestResult("READ", resource, success, duration, errors, warnings, uuid_value)
        self.results.append(result)
        return result
    
    async def execute_update(self, resource: str, endpoint: str, uuid_value: str, data: Dict[str, Any]) -> TestResult:
        """Execute UPDATE operation - legacy compatibility"""
        update_endpoint = endpoint.replace("{id}", uuid_value)
        response, duration = await self.time_operation(
            f"UPDATE {resource}",
            self.rest_client.request("PUT", update_endpoint, data)
        )
        
        success = response.get("_success", False)
        errors = []
        warnings = []
        
        if not success:
            status_code = response.get('_status_code', 'Unknown')
            error_detail = response.get('detail', response.get('message', 'No error message'))
            errors.append(f"HTTP {status_code}: {error_detail}")
        
        result = TestResult("UPDATE", resource, success, duration, errors, warnings, uuid_value)
        self.results.append(result)
        return result
    
    async def execute_delete(self, resource: str, endpoint: str, uuid_value: str) -> TestResult:
        """Execute DELETE operation - legacy compatibility"""
        delete_endpoint = endpoint.replace("{id}", uuid_value)
        response, duration = await self.time_operation(
            f"DELETE {resource}",
            self.rest_client.request("DELETE", delete_endpoint)
        )
        
        success = response.get("_success", False)
        errors = []
        warnings = []
        
        if not success:
            status_code = response.get('_status_code', 'Unknown')
            error_detail = response.get('detail', response.get('message', 'No error message'))
            errors.append(f"HTTP {status_code}: {error_detail}")
        
        result = TestResult("DELETE", resource, success, duration, errors, warnings, uuid_value)
        self.results.append(result)
        return result
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get performance summary"""
        if not self.results:
            return {"message": "No results available"}
            
        by_operation = {}
        for result in self.results:
            if result.operation not in by_operation:
                by_operation[result.operation] = []
            by_operation[result.operation].append(result.duration)
        
        summary = {}
        for operation, durations in by_operation.items():
            summary[operation] = {
                "count": len(durations),
                "avg_duration": sum(durations) / len(durations),
                "max_duration": max(durations),
                "success_rate": len([r for r in self.results if r.operation == operation and r.success]) / len(durations)
            }
        
        return summary
    
    def get_success_summary(self) -> Dict[str, Any]:
        """Get success/failure summary"""
        total = len(self.results)
        successful = len([r for r in self.results if r.success])
        
        return {
            "total_operations": total,
            "successful": successful,
            "failed": total - successful,
            "success_rate": successful / total if total > 0 else 0
        }


# Backward compatibility alias
CRUDTestOrchestrator = APITestOrchestrator