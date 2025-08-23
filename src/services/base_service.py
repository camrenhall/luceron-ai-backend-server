"""
Base service layer for unified database operations using Agent Gateway
"""

import logging
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass

from agent_gateway.contracts.registry import get_all_contracts
from agent_gateway.validator import get_validator, ValidationError
from agent_gateway.models.dsl import DSL, ReadOperation, UpdateOperation, InsertOperation, WhereClause, OrderByClause
from database.connection import get_db_pool
import asyncpg

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
            
            # Execute operation directly
            result = await self._execute_insert_sql(dsl)
            
            return ServiceResult(
                success=True,
                data=result["data"],
                count=result["count"]
            )
            
        except Exception as e:
            # Enhanced error logging and handling
            logger.error(f"Create operation failed for {self.resource_name}: {e}", exc_info=True)
            
            error_msg = str(e).lower()
            if "runtimeerror" in error_msg and "database" in error_msg:
                # Handle database-specific errors
                if "conflict" in error_msg or "unique constraint" in error_msg:
                    return ServiceResult(
                        success=False,
                        error="Record already exists",
                        error_type="CONFLICT_ERROR"
                    )
                elif "foreign key" in error_msg:
                    return ServiceResult(
                        success=False,
                        error="Referenced record not found",
                        error_type="FOREIGN_KEY_ERROR"
                    )
                else:
                    return ServiceResult(
                        success=False,
                        error=f"Database operation failed: {e}",
                        error_type="DATABASE_ERROR"
                    )
            else:
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
            
            # Execute operation directly
            result = await self._execute_read_sql(dsl)
            
            return ServiceResult(
                success=True,
                data=result["data"],
                count=result["count"],
                page_info=result.get("page_info")
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
            
            # Execute operation directly
            result = await self._execute_update_sql(dsl)
            
            return ServiceResult(
                success=True,
                data=result["data"],
                count=result["count"]
            )
            
        except Exception as e:
            # Enhanced error logging and handling for updates
            logger.error(f"Update operation failed for {self.resource_name}: {e}", exc_info=True)
            
            error_msg = str(e).lower()
            if "not found" in error_msg or "no rows affected" in error_msg:
                return ServiceResult(
                    success=False,
                    error=f"Record with id {record_id} not found",
                    error_type="NOT_FOUND"
                )
            elif "foreign key" in error_msg:
                return ServiceResult(
                    success=False,
                    error="Referenced record not found",
                    error_type="FOREIGN_KEY_ERROR"
                )
            else:
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
    
    async def delete(self, record_id: str) -> ServiceResult:
        """
        Delete a record by primary key
        
        Args:
            record_id: Primary key value of record to delete
            
        Returns:
            ServiceResult indicating success/failure
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
            
            # Get the record before deleting (for response data)
            record_result = await self.get_by_id(record_id)
            if not record_result.success or not record_result.data:
                return ServiceResult(
                    success=False,
                    error=f"Record not found with ID: {record_id}",
                    error_type="RESOURCE_NOT_FOUND"
                )
            
            # Execute DELETE operation directly
            result = await self._execute_delete_sql(record_id, pk_field)
            
            return ServiceResult(
                success=True,
                data=record_result.data,  # Return the deleted record data
                count=result["count"]
            )
            
        except Exception as e:
            logger.error(f"Delete operation failed for {self.resource_name}: {e}")
            return ServiceResult(
                success=False,
                error=str(e),
                error_type="EXECUTION_ERROR"
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
    
    # Direct SQL execution methods (avoid circular dependency with executor)
    
    async def _execute_read_sql(self, dsl: DSL) -> Dict[str, Any]:
        """Execute READ DSL directly via SQL"""
        operation = dsl.get_primary_operation()
        
        db_pool = get_db_pool()
        if not db_pool:
            raise RuntimeError("Database pool not initialized")
        
        async with db_pool.acquire() as conn:
            query, params = self._build_read_query(operation)
            
            logger.info(f"Executing READ query: {query}")
            logger.info(f"Parameters: {params}")
            
            try:
                rows = await conn.fetch(query, *params)
                data = [dict(row) for row in rows]
                
                # Convert datetime objects to ISO strings
                for row in data:
                    for key, value in row.items():
                        if hasattr(value, 'isoformat'):
                            row[key] = value.isoformat()
                
                # Build pagination info
                page_info = None
                if operation.offset > 0 or operation.limit < 1000:  # reasonable default
                    page_info = {
                        "limit": operation.limit,
                        "offset": operation.offset
                    }
                
                return {
                    "data": data,
                    "count": len(data),
                    "page_info": page_info
                }
                
            except asyncpg.PostgresError as e:
                logger.error(f"Database error: {e}")
                raise RuntimeError(f"Database query failed: {str(e)}")
    
    async def _execute_insert_sql(self, dsl: DSL) -> Dict[str, Any]:
        """Execute INSERT DSL directly via SQL"""
        operation = dsl.get_primary_operation()
        
        db_pool = get_db_pool()
        if not db_pool:
            raise RuntimeError("Database pool not initialized")
        
        async with db_pool.acquire() as conn:
            async with conn.transaction():
                query, params = self._build_insert_query(operation)
                
                logger.info(f"Executing INSERT: {query}")
                logger.info(f"Parameters: {params}")
                
                try:
                    row = await conn.fetchrow(query, *params)
                    
                    # CRITICAL: Verify row was actually inserted
                    if not row:
                        raise RuntimeError("Insert operation failed - no data returned")
                    
                    data = [dict(row)]
                    
                    # Convert datetime objects to ISO strings
                    for row_dict in data:
                        for key, value in row_dict.items():
                            if hasattr(value, 'isoformat'):
                                row_dict[key] = value.isoformat()
                    
                    # Double-check: verify record exists in database
                    table_name = self._get_table_name(operation.resource)
                    id_field = self._get_id_field(operation.resource)
                    record_id = row[id_field]
                    
                    verify_query = f"SELECT 1 FROM {table_name} WHERE {id_field} = $1"
                    verification = await conn.fetchrow(verify_query, record_id)
                    
                    if not verification:
                        raise RuntimeError("Insert operation failed - record not found after insertion")
                    
                    return {
                        "data": data,
                        "count": 1
                    }
                    
                except asyncpg.UniqueViolationError as e:
                    logger.warning(f"Unique constraint violation: {e}")
                    raise RuntimeError("CONFLICT: Unique constraint violation")
                except asyncpg.PostgresError as e:
                    logger.error(f"Database error during INSERT: {e}")
                    raise RuntimeError(f"Database INSERT failed: {str(e)}")
    
    def _get_table_name(self, resource: str) -> str:
        """Get table name for resource"""
        resource_tables = {
            "cases": "cases",
            "client_communications": "client_communications", 
            "documents": "documents",
            "document_analysis": "document_analysis",
            "error_logs": "error_logs",
            "agent_context": "agent_context",
            "agent_conversations": "agent_conversations",
            "agent_messages": "agent_messages",
            "agent_summaries": "agent_summaries"
        }
        return resource_tables.get(resource, resource)
    
    def _get_id_field(self, resource: str) -> str:
        """Get ID field name for resource"""
        id_fields = {
            "cases": "case_id",
            "client_communications": "communication_id",
            "documents": "document_id",
            "document_analysis": "analysis_id",
            "error_logs": "error_id",
            "agent_context": "context_id",
            "agent_conversations": "conversation_id",
            "agent_messages": "message_id",
            "agent_summaries": "summary_id"
        }
        return id_fields.get(resource, "id")
    
    async def _execute_update_sql(self, dsl: DSL) -> Dict[str, Any]:
        """Execute UPDATE DSL directly via SQL"""
        operation = dsl.get_primary_operation()
        
        db_pool = get_db_pool()
        if not db_pool:
            raise RuntimeError("Database pool not initialized")
        
        async with db_pool.acquire() as conn:
            async with conn.transaction():
                query, params = self._build_update_query(operation)
                
                logger.info(f"Executing UPDATE: {query}")
                logger.info(f"Parameters: {params}")
                
                try:
                    row = await conn.fetchrow(query, *params)
                    
                    if not row:
                        raise RuntimeError(f"No record found with specified ID for update")
                    
                    data = [dict(row)]
                    
                    # Convert datetime objects to ISO strings
                    for row_dict in data:
                        for key, value in row_dict.items():
                            if hasattr(value, 'isoformat'):
                                row_dict[key] = value.isoformat()
                    
                    return {
                        "data": data,
                        "count": 1
                    }
                    
                except asyncpg.UniqueViolationError as e:
                    logger.warning(f"Unique constraint violation: {e}")
                    raise RuntimeError("CONFLICT: Unique constraint violation")
                except asyncpg.PostgresError as e:
                    logger.error(f"Database error during UPDATE: {e}")
                    raise RuntimeError(f"Database UPDATE failed: {str(e)}")
    
    async def _execute_delete_sql(self, record_id: str, pk_field: str) -> Dict[str, Any]:
        """Execute DELETE operation directly via SQL"""
        
        db_pool = get_db_pool()
        if not db_pool:
            raise RuntimeError("Database pool not initialized")
        
        # Resource table mapping
        resource_tables = {
            "cases": "cases",
            "client_communications": "client_communications", 
            "documents": "documents",
            "document_analysis": "document_analysis",
            "error_logs": "error_logs",
            "agent_context": "agent_context",
            "agent_conversations": "agent_conversations",
            "agent_messages": "agent_messages",
            "agent_summaries": "agent_summaries"
        }
        
        table_name = resource_tables[self.resource_name]
        
        async with db_pool.acquire() as conn:
            async with conn.transaction():
                query = f"DELETE FROM {table_name} WHERE {pk_field} = $1"
                
                logger.info(f"Executing DELETE: {query}")
                logger.info(f"Parameters: [{record_id}]")
                
                try:
                    result = await conn.execute(query, record_id)
                    
                    # Parse the result to get number of deleted rows
                    # asyncpg returns "DELETE N" where N is the number of rows
                    deleted_count = int(result.split()[-1]) if result else 0
                    
                    if deleted_count == 0:
                        raise RuntimeError(f"No record found with ID: {record_id}")
                    
                    return {
                        "count": deleted_count
                    }
                    
                except asyncpg.ForeignKeyViolationError as e:
                    logger.warning(f"Foreign key constraint violation: {e}")
                    raise RuntimeError("CONFLICT: Cannot delete record due to foreign key constraints")
                except asyncpg.PostgresError as e:
                    logger.error(f"Database error during DELETE: {e}")
                    raise RuntimeError(f"Database DELETE failed: {str(e)}")
    
    def _build_read_query(self, operation: ReadOperation) -> tuple[str, List[Any]]:
        """Build SQL query from READ operation DSL"""
        
        # Resource table mapping
        resource_tables = {
            "cases": "cases",
            "client_communications": "client_communications", 
            "documents": "documents",
            "document_analysis": "document_analysis",
            "error_logs": "error_logs",
            "agent_context": "agent_context",
            "agent_conversations": "agent_conversations",
            "agent_messages": "agent_messages",
            "agent_summaries": "agent_summaries"
        }
        
        table_name = resource_tables[operation.resource]
        params = []
        param_counter = 1
        
        # SELECT clause
        select_fields = ", ".join(operation.select)
        query = f"SELECT {select_fields} FROM {table_name}"
        
        # WHERE clause
        if operation.where:
            where_parts = []
            for where_clause in operation.where:
                where_sql, where_params, param_counter = self._build_where_clause(
                    where_clause, param_counter
                )
                where_parts.append(where_sql)
                params.extend(where_params)
            
            query += f" WHERE {' AND '.join(where_parts)}"
        
        # ORDER BY clause
        if operation.order_by:
            order_parts = []
            for order_clause in operation.order_by:
                direction = order_clause.dir.upper()
                order_parts.append(f"{order_clause.field} {direction}")
            
            query += f" ORDER BY {', '.join(order_parts)}"
        
        # LIMIT and OFFSET
        query += f" LIMIT ${param_counter}"
        params.append(operation.limit)
        param_counter += 1
        
        if operation.offset > 0:
            query += f" OFFSET ${param_counter}"
            params.append(operation.offset)
            param_counter += 1
        
        return query, params
    
    def _build_insert_query(self, operation: InsertOperation) -> tuple[str, List[Any]]:
        """Build SQL INSERT query from DSL"""
        
        # Resource table mapping
        resource_tables = {
            "cases": "cases",
            "client_communications": "client_communications", 
            "documents": "documents",
            "document_analysis": "document_analysis",
            "error_logs": "error_logs",
            "agent_context": "agent_context",
            "agent_conversations": "agent_conversations",
            "agent_messages": "agent_messages",
            "agent_summaries": "agent_summaries"
        }
        
        table_name = resource_tables[operation.resource]
        params = []
        param_counter = 1
        
        # Fields and values
        field_names = list(operation.values.keys())
        field_placeholders = []
        
        for value in operation.values.values():
            field_placeholders.append(f"${param_counter}")
            params.append(value)
            param_counter += 1
        
        # Add created_at if not provided (auto-managed)
        if 'created_at' not in field_names:
            field_names.append('created_at')
            field_placeholders.append('NOW()')
        
        query = f"""
            INSERT INTO {table_name} ({', '.join(field_names)})
            VALUES ({', '.join(field_placeholders)})
            RETURNING *
        """
        
        return query, params
    
    def _build_update_query(self, operation: UpdateOperation) -> tuple[str, List[Any]]:
        """Build SQL UPDATE query from DSL"""
        
        # Resource table mapping
        resource_tables = {
            "cases": "cases",
            "client_communications": "client_communications", 
            "documents": "documents",
            "document_analysis": "document_analysis",
            "error_logs": "error_logs",
            "agent_context": "agent_context",
            "agent_conversations": "agent_conversations",
            "agent_messages": "agent_messages",
            "agent_summaries": "agent_summaries"
        }
        
        table_name = resource_tables[operation.resource]
        params = []
        param_counter = 1
        
        # SET clause
        set_parts = []
        for field_name, value in operation.update.items():
            set_parts.append(f"{field_name} = ${param_counter}")
            params.append(value)
            param_counter += 1
        
        query = f"UPDATE {table_name} SET {', '.join(set_parts)}"
        
        # WHERE clause (required for UPDATE)
        where_parts = []
        for where_clause in operation.where:
            where_sql, where_params, param_counter = self._build_where_clause(
                where_clause, param_counter
            )
            where_parts.append(where_sql)
            params.extend(where_params)
        
        query += f" WHERE {' AND '.join(where_parts)}"
        
        # RETURNING clause to get post-image
        query += " RETURNING *"
        
        return query, params
    
    def _build_where_clause(self, where_clause: WhereClause, param_counter: int) -> tuple[str, List[Any], int]:
        """Build WHERE clause SQL from DSL where clause"""
        
        field = where_clause.field
        op = where_clause.op
        value = where_clause.value
        
        params = []
        
        # Convert date strings to datetime objects for date/timestamp fields
        if isinstance(value, str) and self._is_date_field(field):
            logger.info(f"Converting date field '{field}' with value '{value}'")
            converted_value = self._parse_date_string(value)
            logger.info(f"Converted '{value}' to {converted_value} (type: {type(converted_value)})")
            value = converted_value
        
        if op == "=":
            sql = f"{field} = ${param_counter}"
            params.append(value)
            param_counter += 1
        elif op == "!=":
            sql = f"{field} != ${param_counter}"
            params.append(value)
            param_counter += 1
        elif op in [">", ">=", "<", "<="]:
            sql = f"{field} {op} ${param_counter}"
            params.append(value)
            param_counter += 1
        elif op == "LIKE":
            sql = f"{field} LIKE ${param_counter}"
            params.append(value)
            param_counter += 1
        elif op == "ILIKE":
            sql = f"{field} ILIKE ${param_counter}"
            params.append(value)
            param_counter += 1
        elif op == "IN":
            if isinstance(value, list):
                placeholders = []
                for item in value:
                    placeholders.append(f"${param_counter}")
                    params.append(item)
                    param_counter += 1
                sql = f"{field} IN ({', '.join(placeholders)})"
            else:
                sql = f"{field} = ${param_counter}"
                params.append(value)
                param_counter += 1
        elif op == "BETWEEN":
            if isinstance(value, list) and len(value) == 2:
                sql = f"{field} BETWEEN ${param_counter} AND ${param_counter + 1}"
                params.extend(value)
                param_counter += 2
            else:
                raise ValueError(f"BETWEEN operator requires array of 2 values, got: {value}")
        else:
            raise ValueError(f"Unsupported WHERE operator: {op}")
        
        return sql, params, param_counter
    
    def _is_date_field(self, field_name: str) -> bool:
        """Check if a field is a date/timestamp field that needs conversion"""
        # Common date field patterns
        date_field_patterns = [
            'created_at', 'updated_at', 'date', 'timestamp', 'time',
            '_at', '_date', '_time', 'expires_at', 'opened_at'
        ]
        
        field_lower = field_name.lower()
        
        # Check if field name matches common patterns
        for pattern in date_field_patterns:
            if pattern in field_lower:
                logger.info(f"Field '{field_name}' identified as date field (matches pattern '{pattern}')")
                return True
        
        # Check field type from contract if available
        field_def = self.contract.get_field(field_name)
        if field_def:
            from agent_gateway.contracts.base import FieldType
            return field_def.type in [FieldType.DATE, FieldType.TIMESTAMP]
        
        return False
    
    def _parse_date_string(self, date_string: str):
        """Convert date string to appropriate datetime object for PostgreSQL"""
        from datetime import datetime, date
        import re
        
        try:
            # Handle various date formats
            date_string = date_string.strip()
            
            # ISO date format: YYYY-MM-DD
            if re.match(r'^\d{4}-\d{2}-\d{2}$', date_string):
                return datetime.strptime(date_string, '%Y-%m-%d').date()
            
            # ISO datetime format: YYYY-MM-DDTHH:MM:SS or YYYY-MM-DD HH:MM:SS
            if 'T' in date_string or ' ' in date_string:
                # Handle timezone info
                if date_string.endswith('Z'):
                    date_string = date_string[:-1] + '+00:00'
                
                # Try parsing as full datetime
                for fmt in ['%Y-%m-%dT%H:%M:%S%z', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M:%S']:
                    try:
                        return datetime.strptime(date_string.replace('+00:00', ''), fmt.replace('%z', ''))
                    except ValueError:
                        continue
            
            # If all else fails, try parsing as date only
            return datetime.strptime(date_string, '%Y-%m-%d').date()
            
        except (ValueError, TypeError) as e:
            logger.warning(f"Failed to parse date string '{date_string}': {e}")
            # Return the original value if parsing fails
            return date_string