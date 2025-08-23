#!/usr/bin/env python3
"""
Database Schema Investigation
Investigate documents table constraints and valid values
"""

import os
import asyncio
import asyncpg
import sys
import logging
from pathlib import Path

# Set environment variables FIRST
DATABASE_URL = 'postgresql://postgres.bjooglksafuxdeknpaso:SgUHEBQv5vdWG0pF@aws-0-us-east-2.pooler.supabase.com:6543/postgres'
os.environ.setdefault("DATABASE_URL", DATABASE_URL)
os.environ.setdefault("RESEND_API_KEY", "dummy_key")

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def investigate_documents_schema():
    """Investigate documents table schema and constraints"""
    
    logger.info("🔍 Investigating Documents Table Schema & Constraints")
    logger.info("=" * 70)
    
    try:
        # Connect with pgbouncer compatibility
        conn = await asyncpg.connect(DATABASE_URL, statement_cache_size=0)
        logger.info("✅ Database connection established")
        
        # 1. Get table schema
        logger.info("\n1️⃣ Documents Table Schema:")
        schema_query = """
        SELECT column_name, data_type, is_nullable, column_default
        FROM information_schema.columns 
        WHERE table_name = 'documents'
        ORDER BY ordinal_position;
        """
        
        schema_results = await conn.fetch(schema_query)
        for row in schema_results:
            nullable = "NULL" if row['is_nullable'] == 'YES' else "NOT NULL"
            default = f" DEFAULT {row['column_default']}" if row['column_default'] else ""
            logger.info(f"   {row['column_name']}: {row['data_type']} {nullable}{default}")
        
        # 2. Get check constraints
        logger.info("\n2️⃣ Check Constraints:")
        constraints_query = """
        SELECT 
            tc.constraint_name,
            cc.check_clause
        FROM information_schema.table_constraints tc
        JOIN information_schema.check_constraints cc 
            ON tc.constraint_name = cc.constraint_name
        WHERE tc.table_name = 'documents'
            AND tc.constraint_type = 'CHECK';
        """
        
        constraint_results = await conn.fetch(constraints_query)
        for row in constraint_results:
            logger.info(f"   Constraint: {row['constraint_name']}")
            logger.info(f"   Check:      {row['check_clause']}")
            logger.info("")
        
        # 3. Get foreign key constraints
        logger.info("3️⃣ Foreign Key Constraints:")
        fk_query = """
        SELECT 
            tc.constraint_name,
            kcu.column_name,
            ccu.table_name AS foreign_table_name,
            ccu.column_name AS foreign_column_name 
        FROM information_schema.table_constraints AS tc 
        JOIN information_schema.key_column_usage AS kcu
            ON tc.constraint_name = kcu.constraint_name
        JOIN information_schema.constraint_column_usage AS ccu
            ON ccu.constraint_name = tc.constraint_name
        WHERE tc.constraint_type = 'FOREIGN KEY' 
            AND tc.table_name = 'documents';
        """
        
        fk_results = await conn.fetch(fk_query)
        for row in fk_results:
            logger.info(f"   {row['column_name']} -> {row['foreign_table_name']}.{row['foreign_column_name']}")
        
        # 4. Sample existing data to understand valid values
        logger.info("\n4️⃣ Sample Existing Documents (to understand valid status values):")
        sample_query = """
        SELECT status, COUNT(*) as count
        FROM documents 
        GROUP BY status
        ORDER BY count DESC
        LIMIT 10;
        """
        
        try:
            sample_results = await conn.fetch(sample_query)
            if sample_results:
                logger.info("   Existing status values:")
                for row in sample_results:
                    logger.info(f"   - '{row['status']}': {row['count']} records")
            else:
                logger.info("   No existing documents found")
        except Exception as e:
            logger.info(f"   No existing documents or error: {e}")
        
        # 5. Test what status values are actually allowed
        logger.info("\n5️⃣ Testing Valid Status Values:")
        
        # Common document status values to test
        test_statuses = [
            "pending", "uploaded", "processing", "processed", "failed", "error",
            "new", "ready", "complete", "draft", "active", "inactive"
        ]
        
        valid_statuses = []
        
        for status in test_statuses:
            try:
                # Test with a minimal insert (will rollback)
                async with conn.transaction():
                    test_query = """
                    INSERT INTO documents (
                        case_id, original_file_name, original_file_size, 
                        original_file_type, original_s3_location, original_s3_key, status
                    ) 
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                    RETURNING document_id;
                    """
                    
                    result = await conn.fetchrow(test_query,
                        '123e4567-e89b-12d3-a456-426614174000',  # Valid UUID 
                        'test.pdf',
                        1000,
                        'application/pdf',
                        's3://test/test.pdf',
                        'test/test.pdf',
                        status
                    )
                    
                    if result:
                        valid_statuses.append(status)
                        logger.info(f"   ✅ '{status}' is VALID")
                        # Rollback the transaction to avoid creating test data
                        raise Exception("Rollback test insert")
                        
            except asyncpg.CheckViolationError as e:
                logger.info(f"   ❌ '{status}' is INVALID: {str(e).split('DETAIL')[0].strip()}")
            except Exception as e:
                if "Rollback test insert" in str(e):
                    # This is our intentional rollback for successful tests
                    pass
                else:
                    logger.info(f"   ⚠️ '{status}' test failed: {e}")
        
        logger.info(f"\n📋 Summary:")
        logger.info(f"   Valid status values found: {valid_statuses}")
        
        await conn.close()
        
        return {
            "valid_statuses": valid_statuses,
            "schema": [dict(row) for row in schema_results],
            "constraints": [dict(row) for row in constraint_results],
            "foreign_keys": [dict(row) for row in fk_results]
        }
        
    except Exception as e:
        logger.error(f"❌ Schema investigation failed: {e}")
        return None

async def investigate_cases_table():
    """Check if the case IDs we're using exist"""
    
    logger.info("\n🔍 Investigating Cases Table for Foreign Key Issues")
    logger.info("=" * 70)
    
    try:
        conn = await asyncpg.connect(DATABASE_URL, statement_cache_size=0)
        
        # Check if our test case IDs exist
        test_case_ids = [
            '123e4567-e89b-12d3-a456-426614174000',
            '123e4567-e89b-12d3-a456-426614174001'
        ]
        
        for case_id in test_case_ids:
            result = await conn.fetchrow("SELECT case_id FROM cases WHERE case_id = $1", case_id)
            if result:
                logger.info(f"   ✅ Case {case_id} exists")
            else:
                logger.info(f"   ❌ Case {case_id} does NOT exist - this will cause foreign key errors")
        
        # Show some existing case IDs for reference
        logger.info("\n📋 Sample existing case IDs:")
        existing_cases = await conn.fetch("SELECT case_id FROM cases LIMIT 5")
        for row in existing_cases:
            logger.info(f"   - {row['case_id']}")
        
        await conn.close()
        
    except Exception as e:
        logger.error(f"❌ Cases investigation failed: {e}")

async def main():
    """Run comprehensive database schema investigation"""
    
    schema_info = await investigate_documents_schema()
    await investigate_cases_table()
    
    if schema_info and schema_info.get("valid_statuses"):
        logger.info("\n✅ Investigation complete!")
        logger.info(f"   Use these valid status values: {schema_info['valid_statuses']}")
        return schema_info
    else:
        logger.error("\n❌ Investigation failed - could not determine valid status values")
        return None

if __name__ == "__main__":
    result = asyncio.run(main())
    sys.exit(0 if result else 1)