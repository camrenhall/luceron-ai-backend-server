"""
Production Schema Extractor
Real-time schema extraction with change detection for immediate failure on schema drift
"""

import asyncio
import asyncpg
import json
import hashlib
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import get_config


@dataclass
class TableSchema:
    """Complete table schema definition"""
    table_name: str
    columns: List[Dict[str, Any]]
    constraints: List[Dict[str, Any]]
    indexes: List[Dict[str, Any]]
    foreign_keys: List[Dict[str, Any]]
    triggers: List[Dict[str, Any]]


@dataclass
class DatabaseSchema:
    """Complete database schema"""
    tables: Dict[str, TableSchema]
    schema_hash: str
    extracted_at: str
    version: str = "1.0"


class SchemaExtractor:
    """Extracts complete schema from production database in real-time"""
    
    def __init__(self):
        self.config = get_config()
        
    async def extract_full_schema(self) -> DatabaseSchema:
        """Extract complete database schema from production"""
        print("🔍 Extracting schema from production database...")
        
        conn = None
        try:
            # Connect to production database (READ-ONLY operations)
            print(f"   🔗 Connecting to database...")
            conn = await asyncio.wait_for(
                asyncpg.connect(
                    self.config.database_url,
                    statement_cache_size=0,  # pgbouncer compatibility
                    command_timeout=30,
                    timeout=30  # Connection timeout
                ),
                timeout=45.0  # Overall connection timeout
            )
            print(f"   ✅ Database connected successfully")
            
            # Get all table names we care about
            tables_to_extract = await asyncio.wait_for(
                self._get_tables_list(conn), 
                timeout=30.0
            )
            print(f"   📋 Found {len(tables_to_extract)} tables to extract")
            
            # Extract schema for each table with timeout protection
            table_schemas = {}
            for table_name in tables_to_extract:
                print(f"   📊 Extracting {table_name}...")
                try:
                    table_schema = await asyncio.wait_for(
                        self._extract_table_schema(conn, table_name),
                        timeout=20.0
                    )
                    table_schemas[table_name] = table_schema
                except asyncio.TimeoutError:
                    print(f"   ⚠️  Timeout extracting schema for {table_name}, skipping...")
                    continue
            
            # Create complete schema object
            schema_data = {
                "tables": {name: asdict(schema) for name, schema in table_schemas.items()},
                "extracted_at": datetime.now().isoformat(),
                "version": "1.0"
            }
            
            # Calculate schema hash for change detection
            schema_json = json.dumps(schema_data, sort_keys=True, default=str)
            schema_hash = hashlib.sha256(schema_json.encode()).hexdigest()[:16]
            
            schema = DatabaseSchema(
                tables=table_schemas,
                schema_hash=schema_hash,
                extracted_at=schema_data["extracted_at"],
                version=schema_data["version"]
            )
            
            print(f"   ✅ Schema extracted successfully (hash: {schema_hash})")
            return schema
            
        except Exception as e:
            print(f"   ❌ Schema extraction failed: {e}")
            raise RuntimeError(f"Failed to extract schema from production: {e}")
        finally:
            if conn:
                try:
                    # Close with timeout to prevent hanging
                    await asyncio.wait_for(conn.close(), timeout=10.0)
                except asyncio.TimeoutError:
                    print("   ⚠️  Database connection close timed out")
                except Exception as e:
                    print(f"   ⚠️  Error closing database connection: {e}")
    
    async def _get_tables_list(self, conn: asyncpg.Connection) -> List[str]:
        """Get list of tables to extract schema for"""
        query = """
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
          AND table_type = 'BASE TABLE'
          AND table_name NOT LIKE 'pg_%'
          AND table_name NOT LIKE 'sql_%'
        ORDER BY table_name
        """
        
        rows = await conn.fetch(query)
        return [row['table_name'] for row in rows]
    
    async def _extract_table_schema(self, conn: asyncpg.Connection, table_name: str) -> TableSchema:
        """Extract complete schema for a single table"""
        
        # Get columns
        columns = await self._extract_columns(conn, table_name)
        
        # Get constraints
        constraints = await self._extract_constraints(conn, table_name)
        
        # Get indexes
        indexes = await self._extract_indexes(conn, table_name)
        
        # Get foreign keys
        foreign_keys = await self._extract_foreign_keys(conn, table_name)
        
        # Get triggers
        triggers = await self._extract_triggers(conn, table_name)
        
        return TableSchema(
            table_name=table_name,
            columns=columns,
            constraints=constraints,
            indexes=indexes,
            foreign_keys=foreign_keys,
            triggers=triggers
        )
    
    async def _extract_columns(self, conn: asyncpg.Connection, table_name: str) -> List[Dict[str, Any]]:
        """Extract column definitions"""
        query = """
        SELECT 
            column_name,
            data_type,
            is_nullable,
            column_default,
            character_maximum_length,
            numeric_precision,
            numeric_scale,
            ordinal_position
        FROM information_schema.columns 
        WHERE table_name = $1
        ORDER BY ordinal_position
        """
        
        rows = await conn.fetch(query, table_name)
        return [dict(row) for row in rows]
    
    async def _extract_constraints(self, conn: asyncpg.Connection, table_name: str) -> List[Dict[str, Any]]:
        """Extract table constraints (CHECK, UNIQUE, PRIMARY KEY)"""
        query = """
        SELECT 
            tc.constraint_name,
            tc.constraint_type,
            kcu.column_name,
            cc.check_clause
        FROM information_schema.table_constraints tc
        LEFT JOIN information_schema.key_column_usage kcu 
            ON tc.constraint_name = kcu.constraint_name
        LEFT JOIN information_schema.check_constraints cc
            ON tc.constraint_name = cc.constraint_name
        WHERE tc.table_name = $1
        ORDER BY tc.constraint_type, tc.constraint_name
        """
        
        rows = await conn.fetch(query, table_name)
        return [dict(row) for row in rows]
    
    async def _extract_indexes(self, conn: asyncpg.Connection, table_name: str) -> List[Dict[str, Any]]:
        """Extract table indexes"""
        query = """
        SELECT 
            indexname,
            indexdef,
            indexname LIKE '%_pkey' as is_primary_key,
            indexname LIKE '%_key' as is_unique
        FROM pg_indexes 
        WHERE tablename = $1
        ORDER BY indexname
        """
        
        rows = await conn.fetch(query, table_name)
        return [dict(row) for row in rows]
    
    async def _extract_foreign_keys(self, conn: asyncpg.Connection, table_name: str) -> List[Dict[str, Any]]:
        """Extract foreign key constraints"""
        query = """
        SELECT 
            kcu.column_name,
            ccu.table_name AS foreign_table_name,
            ccu.column_name AS foreign_column_name,
            tc.constraint_name,
            rc.update_rule,
            rc.delete_rule
        FROM information_schema.table_constraints AS tc 
        JOIN information_schema.key_column_usage AS kcu
            ON tc.constraint_name = kcu.constraint_name
            AND tc.table_schema = kcu.table_schema
        JOIN information_schema.constraint_column_usage AS ccu
            ON ccu.constraint_name = tc.constraint_name
            AND ccu.table_schema = tc.table_schema
        JOIN information_schema.referential_constraints AS rc
            ON tc.constraint_name = rc.constraint_name
        WHERE tc.constraint_type = 'FOREIGN KEY' 
          AND tc.table_name = $1
        """
        
        rows = await conn.fetch(query, table_name)
        return [dict(row) for row in rows]
    
    async def _extract_triggers(self, conn: asyncpg.Connection, table_name: str) -> List[Dict[str, Any]]:
        """Extract table triggers"""
        query = """
        SELECT 
            trigger_name,
            action_timing,
            event_manipulation,
            action_statement
        FROM information_schema.triggers 
        WHERE event_object_table = $1
        ORDER BY trigger_name
        """
        
        rows = await conn.fetch(query, table_name)
        return [dict(row) for row in rows]
    
    def generate_ddl_statements(self, schema: DatabaseSchema) -> List[str]:
        """Generate DDL statements to recreate schema in test database"""
        ddl_statements = []
        
        # First pass: Create tables without foreign keys
        for table_name, table_schema in schema.tables.items():
            create_sql = self._generate_table_ddl(table_schema, include_fks=False)
            ddl_statements.append(create_sql)
        
        # Second pass: Add foreign key constraints
        for table_name, table_schema in schema.tables.items():
            fk_statements = self._generate_foreign_key_ddl(table_schema)
            ddl_statements.extend(fk_statements)
        
        # Third pass: Create indexes (except primary keys which are already created)
        for table_name, table_schema in schema.tables.items():
            index_statements = self._generate_index_ddl(table_schema)
            ddl_statements.extend(index_statements)
        
        return ddl_statements
    
    def _generate_table_ddl(self, table_schema: TableSchema, include_fks: bool = False) -> str:
        """Generate CREATE TABLE statement"""
        columns = []
        
        for col in table_schema.columns:
            col_def = f'"{col["column_name"]}" {col["data_type"]}'
            
            # Add length/precision
            if col["character_maximum_length"]:
                col_def += f'({col["character_maximum_length"]})'
            elif col["numeric_precision"] and col["numeric_scale"]:
                col_def += f'({col["numeric_precision"]},{col["numeric_scale"]})'
            elif col["numeric_precision"]:
                col_def += f'({col["numeric_precision"]})'
            
            # Add NOT NULL
            if col["is_nullable"] == "NO":
                col_def += " NOT NULL"
            
            # Add DEFAULT (clean up Supabase-specific syntax)
            if col["column_default"]:
                default_value = self._normalize_column_default(col["column_default"])
                if default_value:
                    col_def += f' DEFAULT {default_value}'
            
            columns.append(col_def)
        
        # Add primary key constraint
        pk_constraints = [c for c in table_schema.constraints if c["constraint_type"] == "PRIMARY KEY"]
        for pk in pk_constraints:
            if pk["column_name"]:
                columns.append(f'CONSTRAINT "{pk["constraint_name"]}" PRIMARY KEY ("{pk["column_name"]}")')
        
        # Add unique constraints
        unique_constraints = [c for c in table_schema.constraints if c["constraint_type"] == "UNIQUE"]
        for uc in unique_constraints:
            if uc["column_name"]:
                columns.append(f'CONSTRAINT "{uc["constraint_name"]}" UNIQUE ("{uc["column_name"]}")')
        
        # Add check constraints
        check_constraints = [c for c in table_schema.constraints if c["constraint_type"] == "CHECK"]
        for cc in check_constraints:
            if cc["check_clause"]:
                columns.append(f'CONSTRAINT "{cc["constraint_name"]}" CHECK ({cc["check_clause"]})')
        
        column_definitions = ",\n    ".join(columns)
        return f'CREATE TABLE "{table_schema.table_name}" (\n    {column_definitions}\n);'
    
    def _generate_foreign_key_ddl(self, table_schema: TableSchema) -> List[str]:
        """Generate ALTER TABLE statements for foreign keys"""
        fk_statements = []
        
        for fk in table_schema.foreign_keys:
            alter_sql = f'''ALTER TABLE "{table_schema.table_name}" 
ADD CONSTRAINT "{fk["constraint_name"]}" 
FOREIGN KEY ("{fk["column_name"]}") 
REFERENCES "{fk["foreign_table_name"]}" ("{fk["foreign_column_name"]}")'''
            
            if fk["update_rule"] and fk["update_rule"] != "NO ACTION":
                alter_sql += f' ON UPDATE {fk["update_rule"]}'
            
            if fk["delete_rule"] and fk["delete_rule"] != "NO ACTION":
                alter_sql += f' ON DELETE {fk["delete_rule"]}'
            
            alter_sql += ";"
            fk_statements.append(alter_sql)
        
        return fk_statements
    
    def _normalize_column_default(self, default_value: str) -> Optional[str]:
        """Normalize Supabase-specific column defaults for vanilla PostgreSQL"""
        if not default_value:
            return None
        
        # Handle Supabase USER() function -> current user
        if "USER" in default_value:
            return "CURRENT_USER"
        
        # Handle uuid_generate_v4() -> gen_random_uuid() for PostgreSQL 13+
        if "uuid_generate_v4()" in default_value:
            return "gen_random_uuid()"
        
        # Handle Supabase-specific timestamp functions
        if "CURRENT_TIMESTAMP" in default_value:
            return "CURRENT_TIMESTAMP"
        
        # Handle now() function
        if "now()" in default_value:
            return "CURRENT_TIMESTAMP"
        
        # Remove any quoted string indicators that might cause issues
        cleaned = default_value.replace("::text", "").strip()
        
        return cleaned if cleaned else None
    
    def _generate_index_ddl(self, table_schema: TableSchema) -> List[str]:
        """Generate CREATE INDEX statements"""
        index_statements = []
        
        for idx in table_schema.indexes:
            # Skip primary key indexes (already created with table)
            if idx["is_primary_key"]:
                continue
            
            # Use the original index definition from PostgreSQL
            index_statements.append(f'{idx["indexdef"]};')
        
        return index_statements
    
    def compare_schemas(self, schema1: DatabaseSchema, schema2: DatabaseSchema) -> Dict[str, Any]:
        """Compare two schemas and detect changes"""
        changes = {
            "schema_changed": schema1.schema_hash != schema2.schema_hash,
            "hash_old": schema2.schema_hash,
            "hash_new": schema1.schema_hash,
            "table_changes": {},
            "summary": []
        }
        
        if not changes["schema_changed"]:
            return changes
        
        # Compare each table
        all_tables = set(schema1.tables.keys()) | set(schema2.tables.keys())
        
        for table_name in all_tables:
            if table_name not in schema1.tables:
                changes["table_changes"][table_name] = {"status": "DELETED"}
                changes["summary"].append(f"Table {table_name} was DELETED")
            elif table_name not in schema2.tables:
                changes["table_changes"][table_name] = {"status": "ADDED"}
                changes["summary"].append(f"Table {table_name} was ADDED")
            else:
                # Compare table details
                table_changes = self._compare_table_schemas(
                    schema1.tables[table_name], 
                    schema2.tables[table_name]
                )
                if table_changes:
                    changes["table_changes"][table_name] = table_changes
                    changes["summary"].extend([f"Table {table_name}: {change}" for change in table_changes.get("changes", [])])
        
        return changes
    
    def _compare_table_schemas(self, table1: TableSchema, table2: TableSchema) -> Dict[str, Any]:
        """Compare two table schemas"""
        changes = {"changes": []}
        
        # Compare column counts
        if len(table1.columns) != len(table2.columns):
            changes["changes"].append(f"Column count changed ({len(table2.columns)} → {len(table1.columns)})")
        
        # Compare constraint counts
        if len(table1.constraints) != len(table2.constraints):
            changes["changes"].append(f"Constraint count changed ({len(table2.constraints)} → {len(table1.constraints)})")
        
        # Compare index counts
        if len(table1.indexes) != len(table2.indexes):
            changes["changes"].append(f"Index count changed ({len(table2.indexes)} → {len(table1.indexes)})")
        
        return changes if changes["changes"] else None