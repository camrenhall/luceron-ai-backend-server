"""
Pytest configuration and fixtures for CRUD comprehensive testing
Optimized for CI/CD performance and parallel execution
"""

import pytest
import asyncio
import asyncpg
from typing import AsyncGenerator
import os
import uuid
from unittest.mock import AsyncMock, patch

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from core.test_orchestrator import CRUDTestOrchestrator
from core.rest_client import RestClient
from core.test_db_manager import TestDatabaseManager, SchemaChangeDetector

# === OAUTH MOCKING FOR TEST ENVIRONMENTS ===

@pytest.fixture(scope="session", autouse=True)
def mock_oauth_in_test_env():
    """Mock OAuth functionality when ENVIRONMENT=test"""
    if os.getenv('ENVIRONMENT') == 'test':
        # Mock the _get_access_token method to return a dummy token
        with patch.object(RestClient, '_get_access_token', new_callable=AsyncMock) as mock_token:
            mock_token.return_value = "dummy_test_token_12345"
            yield mock_token
    else:
        yield


# === SCHEMA CHANGE DETECTION ===

@pytest.fixture(scope="session", autouse=True)
async def schema_change_detector():
    """Detect schema changes and fail tests immediately if changes are found"""
    from config import get_config
    config = get_config()
    
    if not config.fail_on_schema_changes or config.database_mode == "production":
        # Skip schema change detection in production mode or if disabled
        yield
        return
    
    print("\n🔍 Checking for production schema changes...")
    
    detector = SchemaChangeDetector()
    changes = await detector.detect_schema_changes()
    
    if changes.get("schema_changed", False):
        print(f"❌ SCHEMA CHANGE DETECTED!")
        print(f"   Old hash: {changes['old_hash']}")  
        print(f"   New hash: {changes['new_hash']}")
        print("   Changes:")
        for change in changes.get("changes", {}).get("summary", []):
            print(f"     • {change}")
        
        pytest.fail(f"Production schema changed! {changes['message']}")
    else:
        print(f"✅ Schema unchanged (hash: {changes.get('schema_hash', 'unknown')[:12]})")
    
    yield


# === DATABASE ISOLATION ===

@pytest.fixture(scope="session")  
async def isolated_database():
    """Create isolated test database with production schema"""
    from config import get_config
    config = get_config()
    
    if config.database_mode != "isolated":
        # Not using isolated mode
        yield None
        return
        
    print("\n🏗️  Setting up isolated test database...")
    
    db_manager = TestDatabaseManager(engine=config.test_db_engine)
    
    try:
        # Create isolated database with current production schema
        test_db = await db_manager.create_isolated_database()
        
        # Validate schema fidelity
        validation = await db_manager.validate_schema_fidelity(test_db)
        
        if validation.get("schema_changed", False):
            print("⚠️  Schema fidelity warning - test database may not match production exactly")
        
        yield test_db
        
    finally:
        # Cleanup
        print("\n🧹 Cleaning up isolated test database...")
        await db_manager.cleanup_all_databases()


# === PERFORMANCE OPTIMIZATIONS ===

@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for entire test session"""
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def shared_rest_client() -> AsyncGenerator[RestClient, None]:
    """Shared REST client to reuse OAuth tokens across tests"""
    client = RestClient()
    # Pre-authenticate to cache token
    await client._get_access_token()
    yield client
    # Cleanup handled by garbage collection


@pytest.fixture(scope="function")
async def clean_orchestrator(shared_rest_client, isolated_database) -> AsyncGenerator[CRUDTestOrchestrator, None]:
    """Optimized test orchestrator with isolated database support"""
    from config import get_config
    config = get_config()
    
    orch = CRUDTestOrchestrator()
    orch.rest_client = shared_rest_client  # Reuse authenticated client
    
    # Configure database connection based on mode
    if config.database_mode == "isolated" and isolated_database:
        # Validate that isolated database actually has tables
        try:
            conn = await asyncpg.connect(isolated_database.connection_url)
            table_count = await conn.fetchval("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public'")
            await conn.close()
            
            if table_count > 0:
                # Use isolated test database
                orch.db_validator.config.database_url = isolated_database.connection_url  
                print(f"   🔗 Using isolated database: {isolated_database.database_name} ({table_count} tables)")
            else:
                # Fallback to production database if isolated DB is empty
                print(f"   ⚠️  Isolated database is empty, falling back to production database")
                print(f"   🔗 Using production database (fallback)")
        except Exception as e:
            print(f"   ⚠️  Cannot validate isolated database: {e}")
            print(f"   🔗 Using production database (fallback)")
    else:
        # Use production database (existing behavior)
        print(f"   🔗 Using production database")
    
    await orch.setup()
    yield orch
    
    # Fast cleanup - behavior depends on database mode
    try:
        if config.database_mode == "isolated":
            # No cleanup needed - database will be destroyed
            pass
        else:
            # Clean up test data from production database
            await orch.cleanup_test_data()
    except Exception as e:
        print(f"Warning: Cleanup failed: {e}")
    
    await orch.teardown()


@pytest.fixture(scope="session")
async def orchestrator() -> AsyncGenerator[CRUDTestOrchestrator, None]:
    """Legacy session-scoped test orchestrator for compatibility"""
    orch = CRUDTestOrchestrator()
    await orch.setup()
    yield orch
    await orch.teardown()


# === CI/CD OPTIMIZATIONS ===

def pytest_configure(config):
    """Configure pytest for CI/CD environments"""
    if os.getenv("CI"):
        # CI environment optimizations
        config.option.tb = "short"
        config.option.maxfail = 3
        
        # Enable parallel execution if not already specified
        if not hasattr(config.option, 'numprocesses') or config.option.numprocesses is None:
            config.option.numprocesses = "auto"


def pytest_collection_modifyitems(config, items):
    """Modify test collection for performance and categorization"""
    
    # Add markers based on test names and patterns
    for item in items:
        # Smoke tests - critical functionality only
        if any(name in item.name.lower() for name in ["health", "auth", "basic", "connectivity", "token", "full_crud_cycle"]):
            item.add_marker(pytest.mark.smoke)
            item.add_marker(pytest.mark.fast)
        
        # CRUD operation tests
        elif any(name in item.name.lower() for name in ["crud", "create", "read", "update", "delete", "full_crud_cycle"]):
            item.add_marker(pytest.mark.crud)
            item.add_marker(pytest.mark.regression)
        
        # Integration tests - typically slower
        elif "integration" in str(item.fspath) or any(name in item.name.lower() for name in ["workflow", "cross_table"]):
            item.add_marker(pytest.mark.integration)
            item.add_marker(pytest.mark.slow)
            item.add_marker(pytest.mark.regression)
        
        # Performance tests
        elif any(name in item.name.lower() for name in ["performance", "threshold", "benchmark"]):
            item.add_marker(pytest.mark.performance)
            item.add_marker(pytest.mark.slow)
        
        # Fast tests
        elif any(name in item.name.lower() for name in ["list", "search", "validation"]):
            item.add_marker(pytest.mark.fast)
            item.add_marker(pytest.mark.regression)
        
        # Default to regression for comprehensive coverage
        else:
            item.add_marker(pytest.mark.regression)


def pytest_addoption(parser):
    """Add custom command line options"""
    parser.addoption(
        "--fast",
        action="store_true",
        default=False,
        help="Run only fast tests"
    )
    parser.addoption(
        "--smoke-only", 
        action="store_true",
        default=False,
        help="Run only smoke tests"
    )
    parser.addoption(
        "--skip-slow",
        action="store_true",
        default=False,
        help="Skip slow running tests"
    )


def pytest_runtest_setup(item):
    """Setup optimizations per test"""
    # Skip slow tests when requested
    if item.config.getoption("--skip-slow") and item.get_closest_marker("slow"):
        pytest.skip("Skipping slow test")
    
    # Skip non-smoke tests in smoke-only mode
    if item.config.getoption("--smoke-only") and not item.get_closest_marker("smoke"):
        pytest.skip("Skipping non-smoke test")
    
    # Skip non-fast tests in fast mode
    if item.config.getoption("--fast") and not item.get_closest_marker("fast"):
        pytest.skip("Skipping non-fast test")


# === PARALLEL EXECUTION SAFETY ===

@pytest.fixture(scope="session")
def test_isolation_prefix():
    """Generate unique prefix for parallel test isolation"""
    worker_id = os.getenv("PYTEST_XDIST_WORKER", "master")
    unique_id = uuid.uuid4().hex[:8]
    return f"TEST_{worker_id}_{unique_id}"


# === ERROR HANDLING AND REPORTING ===

def pytest_runtest_logstart(nodeid, location):
    """Log test start for better CI visibility"""
    if os.getenv("CI"):
        print(f"\n🧪 Starting: {nodeid}")


def pytest_runtest_logfinish(nodeid, location):
    """Log test completion for CI visibility"""
    if os.getenv("CI"):
        print(f"✅ Completed: {nodeid}")


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Enhanced error reporting for CI/CD"""
    outcome = yield
    rep = outcome.get_result()
    
    # Add timing information to reports
    if hasattr(call, 'duration'):
        rep.duration = call.duration
    
    # Enhanced failure reporting for CI
    if rep.failed and os.getenv("CI"):
        print(f"❌ FAILED: {item.nodeid}")
        if hasattr(rep, 'longrepr'):
            print(f"   Error: {rep.longrepr}")


# === TIMEOUT MANAGEMENT ===
# Note: pytest-timeout plugin manages timeouts automatically
# Custom timeout logic handled via markers and configuration