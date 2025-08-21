"""
Executor component - compiles DSL to service layer operations
"""

import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

from agent_gateway.contracts.base import ResourceContract
from agent_gateway.models.dsl import DSL, DSLOperation, ReadOperation, UpdateOperation, InsertOperation, WhereClause, OrderByClause

# Service layer imports
from services.base_service import BaseService, ServiceResult
from services.cases_service import get_cases_service
from services.documents_service import get_documents_service, get_document_analysis_service
from services.communications_service import get_communications_service
from services.error_logs_service import get_error_logs_service
from services.agent_services import (
    get_agent_context_service, 
    get_agent_conversations_service,
    get_agent_messages_service,
    get_agent_summaries_service
)

logger = logging.getLogger(__name__)

@dataclass
class ExecutorResult:
    """Result from executor operation"""
    operation: str  # "READ", "INSERT", "UPDATE"
    resource: str
    data: List[Dict[str, Any]]  # Post-image rows
    count: int  # Rows returned/affected
    page_info: Optional[Dict[str, Any]] = None  # Pagination info for reads

class Executor:
    """Compiles DSL to service layer operations"""
    
    def __init__(self):
        # Resource to service mapping
        self._service_cache = {}
        self.resource_services = {
            "cases": lambda: get_cases_service(),
            "client_communications": lambda: get_communications_service(),
            "documents": lambda: get_documents_service(),
            "document_analysis": lambda: get_document_analysis_service(),
            "error_logs": lambda: get_error_logs_service(),
            "agent_context": lambda: get_agent_context_service(),
            "agent_conversations": lambda: get_agent_conversations_service(),
            "agent_messages": lambda: get_agent_messages_service(),
            "agent_summaries": lambda: get_agent_summaries_service()
        }
    
    def _get_service(self, resource: str) -> BaseService:
        """Get service instance for resource with caching"""
        if resource not in self._service_cache:
            if resource not in self.resource_services:
                raise RuntimeError(f"No service configured for resource: {resource}")
            self._service_cache[resource] = self.resource_services[resource]()
        return self._service_cache[resource]
    
    async def execute(
        self,
        dsl: DSL,
        contracts: Dict[str, ResourceContract],
        role: str = "default"
    ) -> ExecutorResult:
        """
        Execute DSL via service layer
        
        Args:
            dsl: Validated DSL to execute
            contracts: Resource contracts for field mapping
            role: User role (for future RLS/CLS)
            
        Returns:
            ExecutorResult with operation results
            
        Raises:
            RuntimeError: If execution fails
        """
        try:
            # Phase 1: Single-step operations only
            operation = dsl.get_primary_operation()
            
            if operation.op == "READ":
                return await self._execute_read_via_service(operation, contracts[operation.resource])
            elif operation.op == "UPDATE":
                return await self._execute_update_via_service(operation, contracts[operation.resource])
            elif operation.op == "INSERT":
                return await self._execute_insert_via_service(operation, contracts[operation.resource])
            else:
                raise RuntimeError(f"Unsupported operation: {operation.op}")
                
        except Exception as e:
            logger.error(f"Executor failed: {e}")
            raise RuntimeError(f"Execution failed: {str(e)}")
    
    async def _execute_read_via_service(
        self,
        operation: ReadOperation,
        contract: ResourceContract
    ) -> ExecutorResult:
        """Execute READ operation via service layer"""
        
        # Get service for this resource
        service = self._get_service(operation.resource)
        
        # Convert DSL WHERE clauses to service filters
        filters = {}
        if operation.where:
            for where_clause in operation.where:
                if where_clause.op == "=":
                    filters[where_clause.field] = where_clause.value
                else:
                    filters[where_clause.field] = {
                        "op": where_clause.op,
                        "value": where_clause.value
                    }
        
        # Convert DSL ORDER BY clauses to service format
        order_by = []
        if operation.order_by:
            for order_clause in operation.order_by:
                order_by.append({
                    "field": order_clause.field,
                    "dir": order_clause.dir
                })
        
        # Call service read method
        result = await service.read(
            fields=operation.select,
            filters=filters if filters else None,
            order_by=order_by if order_by else None,
            limit=operation.limit,
            offset=operation.offset
        )
        
        if not result.success:
            raise RuntimeError(f"Service read failed: {result.error}")
        
        # Build pagination info if offset/limit used
        page_info = None
        if operation.offset > 0 or operation.limit < getattr(contract, 'limits', type('obj', (object,), {'max_rows': 1000})).max_rows:
            page_info = {
                "limit": operation.limit,
                "offset": operation.offset
            }
        
        logger.info(f"Read operation successful - {result.count} rows returned")
        
        return ExecutorResult(
            operation="READ",
            resource=operation.resource,
            data=result.data or [],
            count=result.count,
            page_info=page_info
        )
    
    async def _execute_update_via_service(
        self,
        operation: UpdateOperation,
        contract: ResourceContract
    ) -> ExecutorResult:
        """Execute UPDATE operation via service layer"""
        
        # Get service for this resource
        service = self._get_service(operation.resource)
        
        # Find the primary key from WHERE clauses
        record_id = None
        pk_field = None
        
        # Look for equality condition on primary key field
        for where_clause in operation.where:
            if where_clause.op == "=" and where_clause.field.endswith('_id'):
                pk_field = where_clause.field
                record_id = where_clause.value
                break
        
        if not record_id or not pk_field:
            raise RuntimeError("UPDATE operation requires primary key in WHERE clause")
        
        # Call service update method
        result = await service.update(record_id, operation.update)
        
        if not result.success:
            if "not found" in result.error.lower():
                raise RuntimeError(f"No record found with specified ID for update")
            elif "unique constraint" in result.error.lower() or "conflict" in result.error.lower():
                raise RuntimeError("CONFLICT: Unique constraint violation")
            else:
                raise RuntimeError(f"Service update failed: {result.error}")
        
        logger.info(f"UPDATE operation successful - 1 row updated")
        
        return ExecutorResult(
            operation="UPDATE",
            resource=operation.resource,
            data=result.data or [],  # Post-image of updated row
            count=result.count
        )
    
    async def _execute_insert_via_service(
        self,
        operation: InsertOperation,
        contract: ResourceContract
    ) -> ExecutorResult:
        """Execute INSERT operation via service layer"""
        
        # Get service for this resource
        service = self._get_service(operation.resource)
        
        # Call service create method
        result = await service.create(operation.values)
        
        if not result.success:
            if "unique constraint" in result.error.lower() or "conflict" in result.error.lower():
                raise RuntimeError("CONFLICT: Unique constraint violation")
            else:
                raise RuntimeError(f"Service create failed: {result.error}")
        
        logger.info(f"INSERT operation successful - 1 row created")
        
        return ExecutorResult(
            operation="INSERT",
            resource=operation.resource,
            data=result.data or [],  # Post-image of created row
            count=result.count
        )
    
    
    def get_supported_operations(self) -> List[str]:
        """Get list of supported operations for this executor"""
        return ["READ", "UPDATE", "INSERT"]  # Phase 2: READ, UPDATE, INSERT

# Global executor instance
_executor: Optional[Executor] = None

def get_executor() -> Executor:
    """Get the global executor instance"""
    global _executor
    if _executor is None:
        _executor = Executor()
    return _executor