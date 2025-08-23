"""
Lightweight direct Supabase database validator
Ultra-focused on essential validation with minimal overhead
"""

import asyncio
import asyncpg
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
import uuid
import json

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import get_config


@dataclass
class ValidationResult:
    """Simple validation result container"""
    valid: bool
    errors: List[str]
    warnings: List[str]


class DatabaseValidator:
    """Lightweight direct database validator"""
    
    def __init__(self):
        self.config = get_config()
        self.pool: Optional[asyncpg.Pool] = None
        
    async def connect(self):
        """Initialize database connection pool"""
        if self.pool is None:
            self.pool = await asyncpg.create_pool(
                self.config.qa_database_url,
                min_size=2,
                max_size=5,
                command_timeout=30,
                statement_cache_size=0  # Required for pgbouncer compatibility
            )
    
    async def disconnect(self):
        """Close database connections"""
        if self.pool:
            try:
                await asyncio.wait_for(self.pool.close(), timeout=30.0)
            except asyncio.TimeoutError:
                print("Warning: Database pool close timed out, forcing close")
            finally:
                self.pool = None
    
    async def record_exists(self, table: str, uuid_field: str, uuid_value: str) -> bool:
        """Check if record exists in database"""
        await self.connect()
        
        query = f"SELECT 1 FROM {table} WHERE {uuid_field} = $1"
        async with self.pool.acquire() as conn:
            result = await conn.fetchval(query, uuid_value)
            return result is not None
    
    async def get_record(self, table: str, uuid_field: str, uuid_value: str) -> Optional[Dict[str, Any]]:
        """Get complete record from database"""
        await self.connect()
        
        query = f"SELECT * FROM {table} WHERE {uuid_field} = $1"
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, uuid_value)
            if row:
                # Convert row to dict and handle special types
                record = dict(row)
                for key, value in record.items():
                    if isinstance(value, uuid.UUID):
                        record[key] = str(value)
                return record
            return None
    
    async def validate_foreign_keys(self, table: str, uuid_field: str, uuid_value: str) -> ValidationResult:
        """Validate foreign key relationships exist - COMPREHENSIVE validation"""
        await self.connect()
        
        validation = ValidationResult(True, [], [])
        
        try:
            async with self.pool.acquire() as conn:
                # Get foreign key constraints for the table
                fk_query = """
                SELECT 
                    kcu.column_name,
                    ccu.table_name AS foreign_table_name,
                    ccu.column_name AS foreign_column_name,
                    tc.constraint_name
                FROM 
                    information_schema.table_constraints AS tc 
                    JOIN information_schema.key_column_usage AS kcu
                      ON tc.constraint_name = kcu.constraint_name
                      AND tc.table_schema = kcu.table_schema
                    JOIN information_schema.constraint_column_usage AS ccu
                      ON ccu.constraint_name = tc.constraint_name
                      AND ccu.table_schema = tc.table_schema
                WHERE tc.constraint_type = 'FOREIGN KEY' 
                  AND tc.table_name = $1
                  AND tc.table_schema = 'public';
                """
                
                constraints = await conn.fetch(fk_query, table)
                
                # Get the actual record
                record = await self.get_record(table, uuid_field, uuid_value)
                if not record:
                    validation.errors.append(f"Record not found in {table}")
                    validation.valid = False
                    return validation
                
                # Validate each foreign key constraint
                for constraint in constraints:
                    column = constraint['column_name']
                    foreign_table = constraint['foreign_table_name']
                    foreign_column = constraint['foreign_column_name']
                    constraint_name = constraint['constraint_name']
                    
                    if column in record and record[column] is not None:
                        # Check if foreign record exists
                        fk_check_query = f"SELECT 1 FROM {foreign_table} WHERE {foreign_column} = $1"
                        fk_exists = await conn.fetchval(fk_check_query, record[column])
                        
                        if not fk_exists:
                            validation.errors.append(
                                f"Foreign key violation: {table}.{column} -> {foreign_table}.{foreign_column} "
                                f"(constraint: {constraint_name}, value: {record[column]})"
                            )
                            validation.valid = False
                        else:
                            validation.warnings.append(f"✅ FK valid: {column} -> {foreign_table}")
                    elif column in record:
                        # NULL foreign key - might be valid depending on constraint
                        validation.warnings.append(f"NULL foreign key: {column} (might be valid)")
                
                # Additional validation for specific table relationships
                validation = await self._validate_table_specific_constraints(conn, table, record, validation)
                            
        except Exception as e:
            validation.errors.append(f"Foreign key validation error: {str(e)}")
            validation.valid = False
            
        return validation
    
    async def _validate_table_specific_constraints(self, conn, table: str, record: Dict[str, Any], validation: ValidationResult) -> ValidationResult:
        """Validate table-specific business logic constraints"""
        try:
            if table == "agent_messages":
                # Validate sequence_number uniqueness within conversation
                seq_check = await conn.fetchval(
                    "SELECT COUNT(*) FROM agent_messages WHERE conversation_id = $1 AND sequence_number = $2",
                    record.get('conversation_id'), record.get('sequence_number')
                )
                if seq_check > 1:
                    validation.errors.append(f"Duplicate sequence_number {record.get('sequence_number')} in conversation")
                    validation.valid = False
            
            elif table == "agent_context":
                # Validate unique constraint (case_id, agent_type, context_key)
                unique_check = await conn.fetchval(
                    "SELECT COUNT(*) FROM agent_context WHERE case_id = $1 AND agent_type = $2 AND context_key = $3",
                    record.get('case_id'), record.get('agent_type'), record.get('context_key')
                )
                if unique_check > 1:
                    validation.errors.append(f"Duplicate context key {record.get('context_key')} for case/agent")
                    validation.valid = False
            
            elif table == "documents":
                # Validate status enum
                valid_statuses = ['PENDING', 'PROCESSING', 'COMPLETED', 'FAILED']
                if record.get('status') not in valid_statuses:
                    validation.errors.append(f"Invalid document status: {record.get('status')}")
                    validation.valid = False
            
            elif table == "cases":
                # Validate status enum
                valid_statuses = ['OPEN', 'CLOSED']
                if record.get('status') not in valid_statuses:
                    validation.errors.append(f"Invalid case status: {record.get('status')}")
                    validation.valid = False
                    
            elif table == "client_communications":
                # Validate channel and direction enums
                valid_channels = ['email', 'sms']
                valid_directions = ['incoming', 'outgoing']
                if record.get('channel') not in valid_channels:
                    validation.errors.append(f"Invalid communication channel: {record.get('channel')}")
                    validation.valid = False
                if record.get('direction') not in valid_directions:
                    validation.errors.append(f"Invalid communication direction: {record.get('direction')}")
                    validation.valid = False
                    
        except Exception as e:
            validation.warnings.append(f"Table-specific validation error: {str(e)}")
            
        return validation
    
    async def count_records(self, table: str, where_clause: str = "", params: List[Any] = None) -> int:
        """Count records in table with optional where clause"""
        await self.connect()
        
        query = f"SELECT COUNT(*) FROM {table}"
        if where_clause:
            query += f" WHERE {where_clause}"
        
        async with self.pool.acquire() as conn:
            return await conn.fetchval(query, *(params or []))
    
    async def cleanup_test_data(self, test_prefix: str = "CRUD_TEST") -> int:
        """Clean up test data by prefix - returns count of cleaned records"""
        await self.connect()
        
        cleanup_count = 0
        
        # Define cleanup order (children first)
        cleanup_tables = [
            ('agent_messages', 'conversation_id', 'agent_conversations'),
            ('agent_summaries', 'conversation_id', 'agent_conversations'),
            ('agent_context', 'case_id', 'cases'),
            ('document_analysis', 'case_id', 'cases'),
            ('client_communications', 'case_id', 'cases'),
            ('documents', 'case_id', 'cases'),
            ('agent_conversations', None, None),
            ('error_logs', None, None),
            ('cases', None, None),
        ]
        
        async with self.pool.acquire() as conn:
            for table, fk_field, parent_table in cleanup_tables:
                try:
                    if parent_table:
                        # Clean based on parent table having test prefix
                        query = f"""
                        DELETE FROM {table} 
                        WHERE {fk_field} IN (
                            SELECT case_id FROM cases 
                            WHERE client_name LIKE '{test_prefix}%'
                        )
                        """
                    else:
                        # Direct cleanup
                        if table == 'cases':
                            query = f"DELETE FROM {table} WHERE client_name LIKE '{test_prefix}%'"
                        elif table == 'error_logs':
                            query = f"DELETE FROM {table} WHERE component LIKE '{test_prefix}%'"
                        elif table == 'agent_conversations':
                            query = f"DELETE FROM {table} WHERE conversation_id::text LIKE '%test%'"
                        else:
                            continue
                    
                    result = await conn.execute(query)
                    deleted = int(result.split()[-1]) if result and result.split() else 0
                    cleanup_count += deleted
                    
                except Exception as e:
                    # Continue cleanup even if one table fails
                    print(f"Cleanup error for {table}: {e}")
                    
        return cleanup_count