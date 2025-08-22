"""
Database connection and pool management
"""

import asyncpg
import logging
from config.settings import DATABASE_URL

logger = logging.getLogger(__name__)

# Global database pool
db_pool = None

async def init_database():
    """Initialize database connection pool"""
    global db_pool
    db_pool = await asyncpg.create_pool(
        DATABASE_URL,
        min_size=2,
        max_size=10,
        command_timeout=60,
        statement_cache_size=0  # Fix for pgbouncer compatibility
    )
    
    # Test connection
    async with db_pool.acquire() as conn:
        await conn.fetchval("SELECT 1")
    
    logger.info("Database initialized successfully")


async def close_database():
    """Close database connection pool"""
    global db_pool
    if db_pool:
        await db_pool.close()
    logger.info("Database connections closed")

def get_db_pool():
    """Get the database pool instance"""
    return db_pool