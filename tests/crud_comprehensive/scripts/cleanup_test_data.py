#!/usr/bin/env python3
"""
Test Data Cleanup Job
Comprehensive cleanup for CI/CD environments and test data management
"""

import asyncio
import sys
import argparse
import time
from pathlib import Path
from typing import Dict, List, Any
from datetime import datetime, timedelta

# Add current directory to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.database_validator import DatabaseValidator
from config import get_config
from config.resources import get_cleanup_order


class TestDataCleanupJob:
    """Comprehensive test data cleanup for CI/CD environments"""
    
    def __init__(self, dry_run: bool = False, aggressive: bool = False):
        self.config = get_config()
        self.db_validator = DatabaseValidator()
        self.dry_run = dry_run
        self.aggressive = aggressive
        self.cleanup_stats = {
            "tables_processed": 0,
            "records_deleted": 0,
            "orphaned_records": 0,
            "errors": []
        }
    
    async def setup(self):
        """Initialize database connection"""
        await self.db_validator.connect()
    
    async def teardown(self):
        """Close database connection"""
        await self.db_validator.disconnect()
    
    async def cleanup_table(self, table_name: str, prefix_patterns: List[str]) -> int:
        """Clean up test records from a specific table"""
        print(f"   🧹 Cleaning {table_name}...")
        
        try:
            # Build where clause for test data patterns
            where_conditions = []
            params = []
            param_idx = 1
            
            for pattern in prefix_patterns:
                # Handle different column names that might contain test data
                if table_name == "cases":
                    where_conditions.append(f"client_name LIKE ${param_idx}")
                elif table_name == "client_communications":
                    where_conditions.append(f"sender LIKE ${param_idx} OR recipient LIKE ${param_idx}")
                    params.append(f"%{pattern}%")
                    param_idx += 1
                elif table_name == "documents":
                    where_conditions.append(f"original_file_name LIKE ${param_idx}")
                elif table_name == "error_logs":
                    where_conditions.append(f"component LIKE ${param_idx}")
                else:
                    # Generic cleanup - look for JSON fields that might contain test markers
                    where_conditions.append(f"created_at < NOW() - INTERVAL '1 hour'")
                    break
                
                params.append(f"%{pattern}%")
                param_idx += 1
            
            # Also clean up old test records (older than 1 hour in CI environments)
            if self.aggressive:
                where_conditions.append(f"created_at < ${param_idx}")
                params.append(datetime.now() - timedelta(hours=1))
            
            if not where_conditions:
                print(f"      ⚠️  No cleanup patterns for {table_name}")
                return 0
            
            # Build query
            where_clause = " OR ".join(where_conditions)
            
            if self.dry_run:
                # Count records that would be deleted
                count_query = f"SELECT COUNT(*) FROM {table_name} WHERE {where_clause}"
                async with self.db_validator.pool.acquire() as conn:
                    count = await conn.fetchval(count_query, *params)
                print(f"      🔍 Would delete {count} records (DRY RUN)")
                return count
            else:
                # Delete records
                delete_query = f"DELETE FROM {table_name} WHERE {where_clause}"
                async with self.db_validator.pool.acquire() as conn:
                    result = await conn.execute(delete_query, *params)
                    # Parse result like "DELETE 5" to get count
                    deleted_count = int(result.split()[-1]) if result.split()[-1].isdigit() else 0
                print(f"      ✅ Deleted {deleted_count} records")
                return deleted_count
        
        except Exception as e:
            error_msg = f"Error cleaning {table_name}: {e}"
            print(f"      ❌ {error_msg}")
            self.cleanup_stats["errors"].append(error_msg)
            return 0
    
    async def cleanup_orphaned_records(self) -> int:
        """Clean up orphaned records (foreign key references to deleted records)"""
        if not self.aggressive:
            return 0
            
        print("   🔍 Cleaning orphaned records...")
        
        orphaned_count = 0
        try:
            # Clean up documents without valid cases
            orphan_docs_query = """
                DELETE FROM documents 
                WHERE case_id NOT IN (SELECT case_id FROM cases)
            """
            
            # Clean up communications without valid cases
            orphan_comms_query = """
                DELETE FROM client_communications 
                WHERE case_id NOT IN (SELECT case_id FROM cases)
            """
            
            # Clean up agent messages without valid conversations
            orphan_msgs_query = """
                DELETE FROM agent_messages 
                WHERE conversation_id NOT IN (SELECT conversation_id FROM agent_conversations)
            """
            
            queries = [
                ("orphaned documents", orphan_docs_query),
                ("orphaned communications", orphan_comms_query), 
                ("orphaned messages", orphan_msgs_query)
            ]
            
            for desc, query in queries:
                try:
                    if self.dry_run:
                        count_query = query.replace("DELETE FROM", "SELECT COUNT(*) FROM").split("WHERE")[0] + " WHERE " + query.split("WHERE")[1]
                        async with self.db_validator.pool.acquire() as conn:
                            count = await conn.fetchval(count_query)
                        print(f"      🔍 Would delete {count} {desc} (DRY RUN)")
                        orphaned_count += count
                    else:
                        async with self.db_validator.pool.acquire() as conn:
                            result = await conn.execute(query)
                            deleted_count = int(result.split()[-1]) if result.split()[-1].isdigit() else 0
                        print(f"      ✅ Deleted {deleted_count} {desc}")
                        orphaned_count += deleted_count
                        
                except Exception as e:
                    error_msg = f"Error cleaning {desc}: {e}"
                    print(f"      ❌ {error_msg}")
                    self.cleanup_stats["errors"].append(error_msg)
        
        except Exception as e:
            error_msg = f"Error in orphaned record cleanup: {e}"
            print(f"   ❌ {error_msg}")
            self.cleanup_stats["errors"].append(error_msg)
        
        return orphaned_count
    
    async def vacuum_analyze(self):
        """Run VACUUM ANALYZE to reclaim space and update statistics"""
        if self.dry_run:
            print("   🔍 Would run VACUUM ANALYZE (DRY RUN)")
            return
            
        print("   🧹 Running VACUUM ANALYZE...")
        
        try:
            async with self.db_validator.pool.acquire() as conn:
                # Note: VACUUM cannot run inside a transaction
                await conn.execute("VACUUM ANALYZE")
            print("   ✅ Database maintenance completed")
        except Exception as e:
            error_msg = f"Error during VACUUM ANALYZE: {e}"
            print(f"   ❌ {error_msg}")
            self.cleanup_stats["errors"].append(error_msg)
    
    async def run_cleanup(self) -> Dict[str, Any]:
        """Execute complete cleanup process"""
        start_time = time.time()
        
        print("🧹 Starting Test Data Cleanup...")
        print(f"   Mode: {'DRY RUN' if self.dry_run else 'EXECUTE'}")
        print(f"   Aggressive: {self.aggressive}")
        
        # Test data patterns to clean up
        patterns = [
            self.config.test_data_prefix,
            "CRUD_TEST",
            "test.",
            "crud-test.example.com"
        ]
        
        print(f"   Patterns: {', '.join(patterns)}")
        
        # Clean up tables in dependency order (children first)
        cleanup_order = get_cleanup_order()
        
        for table_name in cleanup_order:
            try:
                deleted = await self.cleanup_table(table_name, patterns)
                self.cleanup_stats["records_deleted"] += deleted
                self.cleanup_stats["tables_processed"] += 1
            except Exception as e:
                error_msg = f"Failed to process {table_name}: {e}"
                self.cleanup_stats["errors"].append(error_msg)
        
        # Clean up orphaned records
        orphaned = await self.cleanup_orphaned_records()
        self.cleanup_stats["orphaned_records"] = orphaned
        
        # Database maintenance
        if not self.dry_run and self.cleanup_stats["records_deleted"] > 0:
            await self.vacuum_analyze()
        
        duration = time.time() - start_time
        
        # Final summary
        print("\n📊 Cleanup Summary:")
        print(f"   Tables Processed: {self.cleanup_stats['tables_processed']}")
        print(f"   Records Deleted: {self.cleanup_stats['records_deleted']}")
        print(f"   Orphaned Records: {self.cleanup_stats['orphaned_records']}")
        print(f"   Duration: {duration:.2f}s")
        
        if self.cleanup_stats["errors"]:
            print(f"   ⚠️  Errors: {len(self.cleanup_stats['errors'])}")
            for error in self.cleanup_stats["errors"]:
                print(f"      • {error}")
        else:
            print("   ✅ No errors")
        
        return {
            "success": len(self.cleanup_stats["errors"]) == 0,
            "stats": self.cleanup_stats,
            "duration": duration
        }


def create_argument_parser() -> argparse.ArgumentParser:
    """Create command line argument parser"""
    parser = argparse.ArgumentParser(
        description="Test Data Cleanup Job for CI/CD",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/cleanup_test_data.py                    # Normal cleanup
  python scripts/cleanup_test_data.py --dry-run          # Preview what would be cleaned
  python scripts/cleanup_test_data.py --aggressive       # Clean old records + orphans
  python scripts/cleanup_test_data.py --dry-run --aggressive  # Preview aggressive cleanup
        """
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview cleanup without making changes"
    )
    
    parser.add_argument(
        "--aggressive",
        action="store_true", 
        help="Enable aggressive cleanup (orphaned records, old data)"
    )
    
    return parser


async def main():
    """Main entry point"""
    parser = create_argument_parser()
    args = parser.parse_args()
    
    cleanup_job = TestDataCleanupJob(
        dry_run=args.dry_run,
        aggressive=args.aggressive
    )
    
    try:
        await cleanup_job.setup()
        result = await cleanup_job.run_cleanup()
        return 0 if result["success"] else 1
    except Exception as e:
        print(f"❌ Cleanup job failed: {e}")
        return 1
    finally:
        await cleanup_job.teardown()


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)