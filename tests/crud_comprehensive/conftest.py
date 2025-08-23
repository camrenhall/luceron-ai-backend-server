"""
Pytest configuration for CRUD comprehensive testing suite
"""

import pytest
import asyncio
from typing import AsyncGenerator

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from core.test_orchestrator import TestOrchestrator


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def orchestrator() -> AsyncGenerator[TestOrchestrator, None]:
    """Session-scoped test orchestrator"""
    orch = TestOrchestrator()
    await orch.setup()
    yield orch
    await orch.teardown()


@pytest.fixture(scope="function")
async def clean_orchestrator() -> AsyncGenerator[TestOrchestrator, None]:
    """Function-scoped orchestrator for isolated tests"""
    orch = TestOrchestrator()
    await orch.setup()
    yield orch
    await orch.teardown()