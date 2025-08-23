"""
Lightweight Test Orchestrator
Central coordination for CRUD testing with dual-layer validation
Ultra-focused MVP implementation
"""

import asyncio
import time
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.rest_client import RestClient
from core.database_validator import DatabaseValidator, ValidationResult
from core.data_factory import DataFactory
from core.performance_tracker import PerformanceTracker
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
    validation_results: List[ValidationResult]
    total_duration: float


class CRUDTestOrchestrator:
    """Lightweight central coordinator for CRUD testing"""
    
    def __init__(self):
        self.config = get_config()
        self.rest_client = RestClient()
        self.db_validator = DatabaseValidator()
        self.data_factory = DataFactory()
        self.performance_tracker = PerformanceTracker()
        self.results: List[TestResult] = []
        
    async def setup(self):
        """Initialize components"""
        await self.db_validator.connect()
        
    async def teardown(self):
        """Cleanup components"""
        await self.db_validator.disconnect()
        
        # Cleanup test data if enabled
        if self.config.cleanup_test_data:
            cleanup_count = await self.db_validator.cleanup_test_data(self.config.test_data_prefix)
            print(f"🧹 Cleaned up {cleanup_count} test records")
    
    async def time_operation(self, operation_name: str, coro) -> Tuple[Any, float]:
        """Time an operation and return result + duration"""
        start_time = time.time()
        result = await coro
        duration = time.time() - start_time
        return result, duration
    
    async def validate_database_state(self, table: str, uuid_field: str, uuid_value: str, operation: str) -> ValidationResult:
        """Validate database state after operation"""
        if not self.config.enable_database_validation:
            return ValidationResult(True, [], [])
            
        validation = ValidationResult(True, [], [])
        
        try:
            if operation == "DELETE":
                # Record should not exist
                exists = await self.db_validator.record_exists(table, uuid_field, uuid_value)
                if exists:
                    validation.errors.append(f"Record still exists after DELETE")
                    validation.valid = False
            else:
                # Record should exist
                exists = await self.db_validator.record_exists(table, uuid_field, uuid_value)
                if not exists:
                    validation.errors.append(f"Record not found after {operation}")
                    validation.valid = False
                else:
                    # Validate foreign keys
                    fk_validation = await self.db_validator.validate_foreign_keys(table, uuid_field, uuid_value)
                    if not fk_validation.valid:
                        validation.errors.extend(fk_validation.errors)
                        validation.valid = False
                    validation.warnings.extend(fk_validation.warnings)
                        
        except Exception as e:
            validation.errors.append(f"Database validation error: {str(e)}")
            validation.valid = False
            
        return validation
    
    async def execute_create(self, resource: str, endpoint: str, data: Dict[str, Any]) -> TestResult:
        """Execute CREATE operation"""
        response, duration = await self.time_operation(
            f"CREATE {resource}",
            self.rest_client.request("POST", endpoint, data)
        )
        
        success = response.get("_success", False)
        errors = []
        warnings = []
        uuid_value = None
        
        if not success:
            errors.append(f"HTTP {response.get('_status_code')}: {response.get('detail', 'Unknown error')}")
        else:
            # Extract UUID from response
            uuid_value = self._extract_uuid(response)
            if not uuid_value:
                warnings.append("Could not extract UUID from response")
                
        result = TestResult(
            operation="CREATE",
            resource=resource,
            success=success,
            duration=duration,
            errors=errors,
            warnings=warnings,
            uuid=uuid_value
        )
        
        # Track performance metrics
        self.performance_tracker.record_test_result(
            test_name=f"{resource}_crud_cycle",
            operation="CREATE",
            resource=resource,
            duration=duration,
            success=success
        )
        
        self.results.append(result)
        return result
    
    async def execute_read(self, resource: str, endpoint: str, uuid_value: str) -> TestResult:
        """Execute READ operation"""
        read_endpoint = endpoint.replace("{id}", uuid_value)
        response, duration = await self.time_operation(
            f"READ {resource}",
            self.rest_client.request("GET", read_endpoint)
        )
        
        success = response.get("_success", False)
        errors = []
        warnings = []
        
        if not success:
            errors.append(f"HTTP {response.get('_status_code')}: {response.get('detail', 'Unknown error')}")
            
        result = TestResult(
            operation="READ",
            resource=resource,
            success=success,
            duration=duration,
            errors=errors,
            warnings=warnings,
            uuid=uuid_value
        )
        
        # Track performance metrics
        self.performance_tracker.record_test_result(
            test_name=f"{resource}_crud_cycle",
            operation="READ",
            resource=resource,
            duration=duration,
            success=success
        )
        
        self.results.append(result)
        return result
    
    async def execute_update(self, resource: str, endpoint: str, uuid_value: str, data: Dict[str, Any]) -> TestResult:
        """Execute UPDATE operation"""
        update_endpoint = endpoint.replace("{id}", uuid_value)
        response, duration = await self.time_operation(
            f"UPDATE {resource}",
            self.rest_client.request("PUT", update_endpoint, data)
        )
        
        success = response.get("_success", False)
        errors = []
        warnings = []
        
        if not success:
            errors.append(f"HTTP {response.get('_status_code')}: {response.get('detail', 'Unknown error')}")
            
        result = TestResult(
            operation="UPDATE",
            resource=resource,
            success=success,
            duration=duration,
            errors=errors,
            warnings=warnings,
            uuid=uuid_value
        )
        
        # Track performance metrics
        self.performance_tracker.record_test_result(
            test_name=f"{resource}_crud_cycle",
            operation="UPDATE",
            resource=resource,
            duration=duration,
            success=success
        )
        
        self.results.append(result)
        return result
    
    async def execute_delete(self, resource: str, endpoint: str, uuid_value: str) -> TestResult:
        """Execute DELETE operation"""
        delete_endpoint = endpoint.replace("{id}", uuid_value)
        response, duration = await self.time_operation(
            f"DELETE {resource}",
            self.rest_client.request("DELETE", delete_endpoint)
        )
        
        success = response.get("_success", False)
        errors = []
        warnings = []
        
        if not success:
            errors.append(f"HTTP {response.get('_status_code')}: {response.get('detail', 'Unknown error')}")
            
        result = TestResult(
            operation="DELETE",
            resource=resource,
            success=success,
            duration=duration,
            errors=errors,
            warnings=warnings,
            uuid=uuid_value
        )
        
        # Track performance metrics
        self.performance_tracker.record_test_result(
            test_name=f"{resource}_crud_cycle",
            operation="DELETE",
            resource=resource,
            duration=duration,
            success=success
        )
        
        self.results.append(result)
        return result
    
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