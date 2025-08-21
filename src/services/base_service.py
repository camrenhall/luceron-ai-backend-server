"""
Base service layer for unified database operations using Agent Gateway
"""

import logging
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass

from agent_gateway.contracts.registry import get_all_contracts
from agent_gateway.validator import get_validator, ValidationError
from agent_gateway.executor import get_executor, ExecutorResult
from agent_gateway.models.dsl import DSL, ReadOperation, UpdateOperation, InsertOperation, WhereClause, OrderByClause

logger = logging.getLogger(__name__)

@dataclass
class ServiceResult:
    """Result from service operation"""
    success: bool
    data: Optional[List[Dict[str, Any]]] = None
    count: int = 0
    error: Optional[str] = None
    error_type: Optional[str] = None
    page_info: Optional[Dict[str, Any]] = None

class BaseService:
    """Base service that wraps Agent Gateway components for unified data access"""
    
    def __init__(self, resource_name: str, role: str = "api"):
        self.resource_name = resource_name
        self.role = role
        self.validator = get_validator()
        self.executor = get_executor()
        self.contracts = get_all_contracts(role)
        
        if resource_name not in self.contracts:
            raise ValueError(f"Resource not found in contracts: {resource_name}")
        
        self.contract = self.contracts[resource_name]
        logger.info(f"BaseService initialized for resource: {resource_name}")
    
    async def create(self, data: Dict[str, Any]) -> ServiceResult:
        """
        Create a new record using INSERT operation
        
        Args:
            data: Dictionary of field values to insert
            
        Returns:
            ServiceResult with created record data
        """
        try:
            # Build INSERT DSL
            insert_op = InsertOperation(
                resource=self.resource_name,
                values=data
            )
            dsl = DSL(steps=[insert_op])
            
            # Validate DSL
            validation_error = self.validator.validate(dsl, self.contracts, self.role)
            if validation_error:
                return ServiceResult(
                    success=False,
                    error=validation_error.message,
                    error_type=validation_error.error_type
                )
            
            # Execute operation
            result = await self.executor.execute(dsl, self.contracts, self.role)
            
            return ServiceResult(
                success=True,
                data=result.data,
                count=result.count
            )
            
        except Exception as e:
            logger.error(f"Create operation failed for {self.resource_name}: {e}")
            return ServiceResult(
                success=False,
                error=str(e),
                error_type="EXECUTION_ERROR"
            )
    
    async def read(
        self,
        fields: Optional[List[str]] = None,
        filters: Optional[Dict[str, Any]] = None,
        order_by: Optional[List[Dict[str, str]]] = None,
        limit: int = 100,
        offset: int = 0
    ) -> ServiceResult:
        """
        Read records using READ operation
        
        Args:
            fields: List of fields to select (default: all readable fields)
            filters: Dictionary of field filters {field_name: value} or {field_name: {"op": "=", "value": value}}
            order_by: List of ordering specs [{"field": "created_at", "dir": "desc"}]
            limit: Maximum number of records to return
            offset: Number of records to skip
            
        Returns:
            ServiceResult with matched records
        """
        try:
            # Default to all readable fields if none specified
            if fields is None:
                fields = [f.name for f in self.contract.fields if f.readable]
            
            # Build WHERE clauses from filters
            where_clauses = []
            if filters:
                for field_name, filter_spec in filters.items():
                    if isinstance(filter_spec, dict):
                        # Advanced filter: {"op": "=", "value": "test"}
                        op = filter_spec.get("op", "=")
                        value = filter_spec.get("value")
                    else:
                        # Simple filter: field_name: value (defaults to equality)
                        op = "="
                        value = filter_spec
                    
                    where_clauses.append(WhereClause(
                        field=field_name,
                        op=op,
                        value=value
                    ))
            
            # Build ORDER BY clauses
            order_by_clauses = []
            if order_by:
                for order_spec in order_by:
                    order_by_clauses.append(OrderByClause(
                        field=order_spec["field"],
                        dir=order_spec.get("dir", "asc")
                    ))
            
            # Build READ DSL
            read_op = ReadOperation(
                resource=self.resource_name,
                select=fields,
                where=where_clauses if where_clauses else None,
                order_by=order_by_clauses if order_by_clauses else None,
                limit=limit,
                offset=offset
            )
            dsl = DSL(steps=[read_op])
            
            # Validate DSL
            validation_error = self.validator.validate(dsl, self.contracts, self.role)
            if validation_error:
                return ServiceResult(
                    success=False,
                    error=validation_error.message,
                    error_type=validation_error.error_type
                )
            
            # Execute operation
            result = await self.executor.execute(dsl, self.contracts, self.role)
            
            return ServiceResult(
                success=True,
                data=result.data,
                count=result.count,
                page_info=result.page_info
            )
            
        except Exception as e:
            logger.error(f"Read operation failed for {self.resource_name}: {e}")
            return ServiceResult(
                success=False,
                error=str(e),
                error_type="EXECUTION_ERROR"
            )
    
    async def update(self, record_id: str, data: Dict[str, Any]) -> ServiceResult:
        """
        Update a record using UPDATE operation
        
        Args:
            record_id: Primary key value of record to update
            data: Dictionary of field values to update
            
        Returns:
            ServiceResult with updated record data
        """
        try:
            # Find primary key field name
            pk_field = self._find_primary_key_field()
            if not pk_field:
                return ServiceResult(
                    success=False,
                    error=f"Cannot identify primary key field for {self.resource_name}",
                    error_type="CONFIGURATION_ERROR"
                )
            
            # Build WHERE clause with PK equality
            where_clauses = [WhereClause(
                field=pk_field,
                op="=",
                value=record_id
            )]
            
            # Build UPDATE DSL
            update_op = UpdateOperation(
                resource=self.resource_name,
                where=where_clauses,
                update=data,
                limit=1
            )
            dsl = DSL(steps=[update_op])
            
            # Validate DSL
            validation_error = self.validator.validate(dsl, self.contracts, self.role)
            if validation_error:
                return ServiceResult(
                    success=False,
                    error=validation_error.message,
                    error_type=validation_error.error_type
                )
            
            # Execute operation
            result = await self.executor.execute(dsl, self.contracts, self.role)
            
            return ServiceResult(
                success=True,
                data=result.data,
                count=result.count
            )
            
        except Exception as e:
            logger.error(f"Update operation failed for {self.resource_name}: {e}")
            return ServiceResult(
                success=False,
                error=str(e),
                error_type="EXECUTION_ERROR"
            )
    
    async def get_by_id(self, record_id: str) -> ServiceResult:
        """
        Get a single record by primary key
        
        Args:
            record_id: Primary key value
            
        Returns:
            ServiceResult with single record or empty result
        """
        pk_field = self._find_primary_key_field()
        if not pk_field:
            return ServiceResult(
                success=False,
                error=f"Cannot identify primary key field for {self.resource_name}",
                error_type="CONFIGURATION_ERROR"
            )
        
        return await self.read(
            filters={pk_field: record_id},
            limit=1
        )
    
    async def get_by_field(self, field_name: str, value: Any, limit: int = 100) -> ServiceResult:
        """
        Get records by specific field value
        
        Args:
            field_name: Name of field to filter by
            value: Value to match
            limit: Maximum number of records to return
            
        Returns:
            ServiceResult with matching records
        """
        return await self.read(
            filters={field_name: value},
            limit=limit
        )
    
    def _find_primary_key_field(self) -> Optional[str]:
        """Find the primary key field for this resource"""
        # Look for fields ending with _id that are not writable (auto-generated)
        for field in self.contract.fields:
            if field.name.endswith('_id') and not field.writable:
                return field.name
        
        # Fallback: look for common PK names
        common_pk_names = ['id', f"{self.resource_name.rstrip('s')}_id"]
        for field in self.contract.fields:
            if field.name in common_pk_names and not field.writable:
                return field.name
        
        return None
    
    def get_readable_fields(self) -> List[str]:
        """Get list of readable field names for this resource"""
        return [f.name for f in self.contract.fields if f.readable]
    
    def get_writable_fields(self) -> List[str]:
        """Get list of writable field names for this resource"""
        return [f.name for f in self.contract.fields if f.writable]
    
    def is_field_readable(self, field_name: str) -> bool:
        """Check if a field is readable"""
        return self.contract.is_field_readable(field_name)
    
    def is_field_writable(self, field_name: str) -> bool:
        """Check if a field is writable"""
        return self.contract.is_field_writable(field_name)