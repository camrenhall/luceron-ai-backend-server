#!/usr/bin/env python3
"""
Create test cases for document integrity testing
"""

import os
import asyncio
import asyncpg
import sys
import logging

# Set environment variables FIRST
DATABASE_URL = 'postgresql://postgres.bjooglksafuxdeknpaso:SgUHEBQv5vdWG0pF@aws-0-us-east-2.pooler.supabase.com:6543/postgres'
os.environ.setdefault("DATABASE_URL", DATABASE_URL)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def create_test_cases():
    """Create test cases for document integrity testing"""
    
    test_case_ids = [
        '123e4567-e89b-12d3-a456-426614174000',
        '123e4567-e89b-12d3-a456-426614174001',
        '123e4567-e89b-12d3-a456-426614174002',
        '123e4567-e89b-12d3-a456-426614174003',
        '123e4567-e89b-12d3-a456-426614174004',
        '123e4567-e89b-12d3-a456-426614174099'  # For transaction test
    ]
    
    try:
        conn = await asyncpg.connect(DATABASE_URL, statement_cache_size=0)
        logger.info("✅ Database connection established")
        
        created_count = 0
        
        for case_id in test_case_ids:
            try:
                # Check if case already exists
                existing = await conn.fetchrow("SELECT case_id FROM cases WHERE case_id = $1", case_id)
                
                if existing:
                    logger.info(f"   Case {case_id} already exists")
                else:
                    # Create test case with correct schema
                    result = await conn.fetchrow("""
                        INSERT INTO cases (case_id, client_name, client_email, created_at, status)
                        VALUES ($1, $2, $3, NOW(), 'OPEN')
                        RETURNING case_id
                    """, case_id, 
                        f"Test Client {case_id[-4:]}",
                        f"test{case_id[-4:]}@example.com")
                    
                    if result:
                        created_count += 1
                        logger.info(f"✅ Created test case: {case_id}")
                    
            except Exception as e:
                logger.error(f"❌ Failed to create case {case_id}: {e}")
        
        logger.info(f"\n📋 Summary: Created {created_count} new test cases")
        
        await conn.close()
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to create test cases: {e}")
        return False

if __name__ == "__main__":
    success = asyncio.run(create_test_cases())
    sys.exit(0 if success else 1)