"""
Pytest configuration and fixtures for API contract testing
Lightweight configuration without database dependencies
"""

import pytest
import asyncio
from typing import AsyncGenerator
import os
import uuid
from unittest.mock import AsyncMock, patch

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from core.test_orchestrator import APITestOrchestrator
from core.rest_client import RestClient

# === CRUD DATABASE TESTING SETUP ===




# === DATABASE ISOLATION ===



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
    """Shared REST client for CRUD testing (no auth required for test container)"""
    client = RestClient()
    # No pre-authentication needed - test container has ENABLE_AUTH=false
    yield client
    # Cleanup handled by garbage collection


@pytest.fixture(scope="function")
async def clean_orchestrator(shared_rest_client) -> AsyncGenerator[APITestOrchestrator, None]:
    """Lightweight API test orchestrator"""
    orch = APITestOrchestrator()
    orch.rest_client = shared_rest_client  # Reuse authenticated client
    
    print(f"   🔗 API-only testing")
    
    await orch.setup()
    yield orch
    await orch.teardown()


@pytest.fixture(scope="session")
async def orchestrator() -> AsyncGenerator[APITestOrchestrator, None]:
    """Legacy session-scoped test orchestrator for compatibility"""
    orch = APITestOrchestrator()
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