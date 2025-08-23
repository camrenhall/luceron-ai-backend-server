"""
Test Database Manager
Creates and manages isolated PostgreSQL databases for testing
"""

import asyncio
import asyncpg
import docker
import time
import uuid
import subprocess
import tempfile
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from pathlib import Path
import json

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.schema_extractor import DatabaseSchema, SchemaExtractor
from config import get_config


@dataclass
class TestDatabase:
    """Test database instance information"""
    connection_url: str
    container_id: Optional[str] = None
    database_name: str = "test_db"
    port: int = 5432
    cleanup_required: bool = True


class TestDatabaseManager:
    """Manages isolated test databases with real-time schema replication"""
    
    def __init__(self, engine: str = "docker"):
        self.config = get_config()
        self.engine = engine
        self.schema_extractor = SchemaExtractor()
        self.active_databases: List[TestDatabase] = []
        
    async def create_isolated_database(self) -> TestDatabase:
        """Create isolated test database with current production schema"""
        print("🏗️  Creating isolated test database...")
        
        # Step 1: Extract current production schema
        print("   📋 Extracting production schema...")
        schema = await self.schema_extractor.extract_full_schema()
        
        # Step 2: Create test database instance
        if self.engine == "docker":
            test_db = await self._create_docker_database()
        elif self.engine == "embedded":
            test_db = await self._create_embedded_database()
        else:
            raise ValueError(f"Unsupported database engine: {self.engine}")
        
        # Step 3: Wait for database to be ready
        await self._wait_for_database_ready(test_db)
        
        # Step 4: Replicate production schema
        await self._replicate_schema(test_db, schema)
        
        # Track for cleanup
        self.active_databases.append(test_db)
        
        print(f"   ✅ Test database ready: {test_db.database_name}")
        print(f"   🔗 Connection: localhost:{test_db.port}")
        print(f"   📊 Schema hash: {schema.schema_hash}")
        
        return test_db
    
    async def _create_docker_database(self) -> TestDatabase:
        """Create PostgreSQL database using Docker"""
        try:
            client = docker.from_env()
            
            # Generate unique database identifiers
            db_uuid = uuid.uuid4().hex[:8]
            container_name = f"crud_test_db_{db_uuid}"
            database_name = f"test_db_{db_uuid}"
            
            # Find available port
            port = await self._find_available_port()
            
            # Docker run command - use tmpfs for speed
            container = client.containers.run(
                "postgres:15",
                name=container_name,
                environment={
                    "POSTGRES_DB": database_name,
                    "POSTGRES_USER": "test_user",
                    "POSTGRES_PASSWORD": "test_pass",
                    "POSTGRES_HOST_AUTH_METHOD": "trust"  # For testing only
                },
                ports={'5432/tcp': port},
                tmpfs={'/var/lib/postgresql/data': 'rw,noexec,nosuid,size=256m'},  # In-memory for speed
                detach=True,
                remove=True,  # Auto-remove when stopped
                auto_remove=True
            )
            
            connection_url = f"postgresql://test_user:test_pass@localhost:{port}/{database_name}"
            
            return TestDatabase(
                connection_url=connection_url,
                container_id=container.id,
                database_name=database_name,
                port=port
            )
            
        except Exception as e:
            raise RuntimeError(f"Failed to create Docker database: {e}")
    
    async def _create_embedded_database(self) -> TestDatabase:
        """Create embedded PostgreSQL database (for environments without Docker)"""
        try:
            # Use testing.postgresql if available
            import testing.postgresql
            
            db_uuid = uuid.uuid4().hex[:8]
            database_name = f"test_db_{db_uuid}"
            
            # Create temporary PostgreSQL instance
            postgresql = testing.postgresql.Postgresql()
            
            return TestDatabase(
                connection_url=postgresql.url(),
                container_id=None,
                database_name=database_name,
                port=postgresql.settings['port'],
                cleanup_required=True
            )
            
        except ImportError:
            raise RuntimeError("Embedded PostgreSQL requires 'testing.postgresql' package")
        except Exception as e:
            raise RuntimeError(f"Failed to create embedded database: {e}")
    
    async def _find_available_port(self) -> int:
        """Find an available port for the test database"""
        import socket
        
        # Start from 5433 and find first available
        for port in range(5433, 5533):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                try:
                    s.bind(('localhost', port))
                    return port
                except OSError:
                    continue
        
        raise RuntimeError("No available ports found for test database")
    
    async def _wait_for_database_ready(self, test_db: TestDatabase, max_wait: int = 30):
        """Wait for database to be ready for connections"""
        print(f"   ⏳ Waiting for database to be ready...")
        
        start_time = time.time()
        while time.time() - start_time < max_wait:
            try:
                conn = await asyncpg.connect(
                    test_db.connection_url,
                    command_timeout=5
                )
                await conn.fetchval("SELECT 1")
                await conn.close()
                print(f"   ✅ Database ready in {time.time() - start_time:.1f}s")
                return
            except Exception:
                await asyncio.sleep(0.5)
                continue
        
        raise RuntimeError(f"Database not ready after {max_wait}s")
    
    async def _replicate_schema(self, test_db: TestDatabase, schema: DatabaseSchema):
        """Replicate production schema in test database"""
        print(f"   🔄 Replicating schema ({len(schema.tables)} tables)...")
        
        try:
            conn = await asyncpg.connect(test_db.connection_url)
            
            # Step 1: Create required extensions
            await self._setup_postgres_extensions(conn)
            
            # Step 2: Generate DDL statements
            ddl_statements = self.schema_extractor.generate_ddl_statements(schema)
            
            # Execute DDL statements with better categorization
            enum_count = len(schema.enums)
            table_count = len(schema.tables)
            total_statements = len(ddl_statements)
            
            print(f"   🔧 Executing {total_statements} DDL statements...")
            print(f"      • {enum_count} enum types")
            print(f"      • {table_count} tables")
            print(f"      • ~{total_statements - enum_count - table_count} constraints/indexes")
            
            success_count = 0
            for i, statement in enumerate(ddl_statements):
                try:
                    await conn.execute(statement)
                    success_count += 1
                    
                    # Log successful table creations specifically
                    if statement.strip().startswith("CREATE TABLE"):
                        table_match = statement.split('"')[1] if '"' in statement else "unknown"
                        print(f"   ✅ Created table: {table_match}")
                        
                except Exception as e:
                    error_type = "ENUM" if i < enum_count else "TABLE" if i < enum_count + table_count else "CONSTRAINT/INDEX"
                    print(f"   ❌ {error_type} statement {i+1} failed: {e}")
                    
                    # Always print full statement for table creation failures
                    if error_type == "TABLE":
                        print(f"      FULL STATEMENT: {statement}")
                    elif "syntax error" in str(e) or "does not exist" in str(e):
                        print(f"      Statement: {statement[:200]}...")
                    else:
                        print(f"      Statement: {statement[:100]}...")
            
            print(f"   📊 DDL Results: {success_count}/{total_statements} statements successful")
            
            await conn.close()
            print(f"   ✅ Schema replication complete")
            
        except Exception as e:
            raise RuntimeError(f"Failed to replicate schema: {e}")
    
    async def _setup_postgres_extensions(self, conn: asyncpg.Connection):
        """Setup PostgreSQL extensions required for Supabase compatibility"""
        extensions = [
            "CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\";",
            "CREATE EXTENSION IF NOT EXISTS \"pgcrypto\";"
        ]
        
        for ext in extensions:
            try:
                await conn.execute(ext)
            except Exception as e:
                print(f"   ⚠️  Extension setup warning: {e}")
    
    async def validate_schema_fidelity(self, test_db: TestDatabase) -> Dict[str, Any]:
        """Validate that test database schema matches production"""
        print("   🔍 Validating schema fidelity...")
        
        try:
            # Extract schema from test database
            original_db_url = self.config.database_url
            
            # Temporarily point to test database
            self.schema_extractor.config.database_url = test_db.connection_url
            test_schema = await self.schema_extractor.extract_full_schema()
            
            # Restore original database URL
            self.schema_extractor.config.database_url = original_db_url
            
            # Extract current production schema
            prod_schema = await self.schema_extractor.extract_full_schema()
            
            # Compare schemas
            comparison = self.schema_extractor.compare_schemas(test_schema, prod_schema)
            
            if comparison["schema_changed"]:
                print(f"   ⚠️  Schema fidelity warning: Differences detected")
                for change in comparison["summary"]:
                    print(f"      • {change}")
            else:
                print(f"   ✅ Schema fidelity confirmed")
            
            return comparison
            
        except Exception as e:
            print(f"   ❌ Schema validation failed: {e}")
            return {"error": str(e)}
    
    async def cleanup_database(self, test_db: TestDatabase):
        """Clean up test database"""
        if not test_db.cleanup_required:
            return
        
        try:
            if test_db.container_id:
                # Stop Docker container
                client = docker.from_env()
                container = client.containers.get(test_db.container_id)
                container.stop(timeout=5)
                print(f"   🧹 Docker container {test_db.container_id[:12]} stopped")
            else:
                # For embedded databases, connection closure handles cleanup
                print(f"   🧹 Embedded database cleaned up")
                
        except Exception as e:
            print(f"   ⚠️  Cleanup warning: {e}")
    
    async def cleanup_all_databases(self):
        """Clean up all active test databases"""
        if not self.active_databases:
            return
        
        print(f"🧹 Cleaning up {len(self.active_databases)} test databases...")
        
        cleanup_tasks = [
            self.cleanup_database(db) for db in self.active_databases
        ]
        
        await asyncio.gather(*cleanup_tasks, return_exceptions=True)
        self.active_databases.clear()
        print("   ✅ All test databases cleaned up")
    
    async def health_check(self, test_db: TestDatabase) -> bool:
        """Check if test database is healthy"""
        try:
            conn = await asyncpg.connect(test_db.connection_url, command_timeout=5)
            result = await conn.fetchval("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public'")
            await conn.close()
            return result > 0
        except Exception:
            return False
    
    def get_database_stats(self, test_db: TestDatabase) -> Dict[str, Any]:
        """Get statistics about the test database"""
        return {
            "connection_url": test_db.connection_url,
            "database_name": test_db.database_name,
            "port": test_db.port,
            "engine": self.engine,
            "container_id": test_db.container_id[:12] if test_db.container_id else None
        }


class SchemaChangeDetector:
    """Detects schema changes and fails tests immediately"""
    
    def __init__(self):
        self.config = get_config()
        self.last_known_schema: Optional[DatabaseSchema] = None
    
    async def detect_schema_changes(self) -> Dict[str, Any]:
        """Check for schema changes since last run"""
        extractor = SchemaExtractor()
        current_schema = await extractor.extract_full_schema()
        
        if self.last_known_schema is None:
            # First run - establish baseline
            self.last_known_schema = current_schema
            return {
                "first_run": True,
                "schema_hash": current_schema.schema_hash,
                "message": "Baseline schema established"
            }
        
        # Compare with previous schema
        comparison = extractor.compare_schemas(current_schema, self.last_known_schema)
        
        if comparison["schema_changed"]:
            # Schema changed - this should fail tests
            return {
                "schema_changed": True,
                "changes": comparison,
                "old_hash": self.last_known_schema.schema_hash,
                "new_hash": current_schema.schema_hash,
                "message": "SCHEMA CHANGE DETECTED - Tests should fail"
            }
        
        return {
            "schema_changed": False,
            "schema_hash": current_schema.schema_hash,
            "message": "Schema unchanged"
        }