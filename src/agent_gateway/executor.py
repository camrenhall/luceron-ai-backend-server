"""
Executor component - compiles DSL to internal CRUD operations
"""

import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
import asyncpg

from agent_gateway.contracts.base import ResourceContract
from agent_gateway.models.dsl import DSL, DSLOperation, ReadOperation, UpdateOperation, InsertOperation, WhereClause, OrderByClause
from database.connection import get_db_pool

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
    """Compiles DSL to database operations via internal CRUD"""
    
    def __init__(self):
        # Resource table mapping
        self.resource_tables = {
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
    
    async def execute(
        self,
        dsl: DSL,
        contracts: Dict[str, ResourceContract],
        role: str = "default"
    ) -> ExecutorResult:
        """
        Execute DSL against database
        
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
                return await self._execute_read(operation, contracts[operation.resource])
            elif operation.op == "UPDATE":
                return await self._execute_update(operation, contracts[operation.resource])
            elif operation.op == "INSERT":
                return await self._execute_insert(operation, contracts[operation.resource])
            else:
                raise RuntimeError(f"Unsupported operation: {operation.op}")
                
        except Exception as e:
            logger.error(f"Executor failed: {e}")
            raise RuntimeError(f"Execution failed: {str(e)}")
    
    async def _execute_read(
        self,
        operation: ReadOperation,
        contract: ResourceContract
    ) -> ExecutorResult:
        """Execute READ operation"""
        
        # Get database connection
        db_pool = get_db_pool()
        if not db_pool:
            raise RuntimeError("Database pool not initialized")
        
        async with db_pool.acquire() as conn:
            # Build SQL query from DSL
            query, params = self._build_read_query(operation, contract)
            
            logger.info(f"Executing query: {query}")
            logger.info(f"Parameters: {params}")
            
            # Execute query
            try:
                rows = await conn.fetch(query, *params)
                
                # Convert rows to dictionaries
                data = [dict(row) for row in rows]
                
                # Convert datetime objects to ISO strings for JSON serialization
                for row in data:
                    for key, value in row.items():
                        if hasattr(value, 'isoformat'):  # datetime objects
                            row[key] = value.isoformat()
                
                # Build pagination info if offset/limit used
                page_info = None
                if operation.offset > 0 or operation.limit < contract.limits.max_rows:
                    page_info = {
                        "limit": operation.limit,
                        "offset": operation.offset
                    }
                
                logger.info(f"Read operation successful - {len(data)} rows returned")
                
                return ExecutorResult(
                    operation="READ",
                    resource=operation.resource,
                    data=data,
                    count=len(data),
                    page_info=page_info
                )
                
            except asyncpg.PostgresError as e:
                logger.error(f"Database error: {e}")
                raise RuntimeError(f"Database query failed: {str(e)}")
    
    async def _execute_update(
        self,
        operation: UpdateOperation,
        contract: ResourceContract
    ) -> ExecutorResult:
        """Execute UPDATE operation with transaction safety"""
        
        db_pool = get_db_pool()
        if not db_pool:
            raise RuntimeError("Database pool not initialized")
        
        async with db_pool.acquire() as conn:
            async with conn.transaction():
                # Build UPDATE query from DSL
                query, params = self._build_update_query(operation, contract)
                
                logger.info(f"Executing UPDATE: {query}")
                logger.info(f"Parameters: {params}")
                
                try:
                    # Execute UPDATE and get affected row
                    row = await conn.fetchrow(query, *params)
                    
                    if not row:
                        # No row was updated (PK not found)
                        raise RuntimeError(f"No record found with specified ID for update")
                    
                    # Convert to dictionary and handle datetime serialization
                    data = [dict(row)]
                    for row_dict in data:
                        for key, value in row_dict.items():
                            if hasattr(value, 'isoformat'):
                                row_dict[key] = value.isoformat()
                    
                    logger.info(f"UPDATE operation successful - 1 row updated")
                    
                    return ExecutorResult(
                        operation="UPDATE",
                        resource=operation.resource,
                        data=data,  # Post-image of updated row
                        count=1
                    )
                    
                except asyncpg.UniqueViolationError as e:
                    logger.warning(f"Unique constraint violation: {e}")
                    raise RuntimeError("CONFLICT: Unique constraint violation")
                except asyncpg.PostgresError as e:
                    logger.error(f"Database error during UPDATE: {e}")
                    raise RuntimeError(f"Database UPDATE failed: {str(e)}")
    
    async def _execute_insert(
        self,
        operation: InsertOperation,
        contract: ResourceContract
    ) -> ExecutorResult:
        """Execute INSERT operation with transaction safety"""
        
        db_pool = get_db_pool()
        if not db_pool:
            raise RuntimeError("Database pool not initialized")
        
        async with db_pool.acquire() as conn:
            async with conn.transaction():
                # Build INSERT query from DSL
                query, params = self._build_insert_query(operation, contract)
                
                logger.info(f"Executing INSERT: {query}")
                logger.info(f"Parameters: {params}")
                
                try:
                    # Execute INSERT and get created row
                    row = await conn.fetchrow(query, *params)
                    
                    # Convert to dictionary and handle datetime serialization
                    data = [dict(row)]
                    for row_dict in data:
                        for key, value in row_dict.items():
                            if hasattr(value, 'isoformat'):
                                row_dict[key] = value.isoformat()
                    
                    logger.info(f"INSERT operation successful - 1 row created")
                    
                    return ExecutorResult(
                        operation="INSERT",
                        resource=operation.resource,
                        data=data,  # Post-image of created row
                        count=1
                    )
                    
                except asyncpg.UniqueViolationError as e:
                    logger.warning(f"Unique constraint violation during INSERT: {e}")
                    raise RuntimeError("CONFLICT: Unique constraint violation")
                except asyncpg.PostgresError as e:
                    logger.error(f"Database error during INSERT: {e}")
                    raise RuntimeError(f"Database INSERT failed: {str(e)}")
    
    def _build_read_query(
        self,
        operation: ReadOperation,
        contract: ResourceContract
    ) -> tuple[str, List[Any]]:
        """Build SQL query from READ operation DSL"""
        
        table_name = self.resource_tables[operation.resource]
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
    
    def _build_update_query(
        self,
        operation: UpdateOperation,
        contract: ResourceContract
    ) -> tuple[str, List[Any]]:
        """Build SQL UPDATE query from DSL"""
        
        table_name = self.resource_tables[operation.resource]
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
    
    def _build_insert_query(
        self,
        operation: InsertOperation,
        contract: ResourceContract
    ) -> tuple[str, List[Any]]:
        """Build SQL INSERT query from DSL"""
        
        table_name = self.resource_tables[operation.resource]
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
    
    def _build_where_clause(
        self,
        where_clause: WhereClause,
        param_counter: int
    ) -> tuple[str, List[Any], int]:
        """Build WHERE clause SQL from DSL where clause"""
        
        field = where_clause.field
        op = where_clause.op
        value = where_clause.value
        
        params = []
        
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
            # Handle IN operator with list of values
            if isinstance(value, list):
                placeholders = []
                for item in value:
                    placeholders.append(f"${param_counter}")
                    params.append(item)
                    param_counter += 1
                sql = f"{field} IN ({', '.join(placeholders)})"
            else:
                # Single value treated as equals
                sql = f"{field} = ${param_counter}"
                params.append(value)
                param_counter += 1
        elif op == "BETWEEN":
            # BETWEEN requires two values
            if isinstance(value, list) and len(value) == 2:
                sql = f"{field} BETWEEN ${param_counter} AND ${param_counter + 1}"
                params.extend(value)
                param_counter += 2
            else:
                raise ValueError(f"BETWEEN operator requires array of 2 values, got: {value}")
        else:
            raise ValueError(f"Unsupported WHERE operator: {op}")
        
        return sql, params, param_counter
    
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