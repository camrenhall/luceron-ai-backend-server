"""
pytest configuration and fixtures for agent_db testing suite
Session-level setup, data creation, and cleanup orchestration
"""

import pytest
import pytest_asyncio
import asyncio
import time
from typing import Dict, List, Any

from infrastructure import TestClient, UUIDTracker, DataValidator, PerformanceMonitor
from test_data_setup import TestDataEcosystem


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def test_infrastructure():
    """Initialize core testing infrastructure"""
    print("\n🚀 Initializing Agent DB Test Suite...")
    
    # Initialize components
    client = TestClient()
    uuid_tracker = UUIDTracker()
    validator = DataValidator()
    perf_monitor = PerformanceMonitor()
    
    # Verify endpoint connectivity
    print("📡 Verifying API connectivity...")
    health_ok = await client.health_check()
    assert health_ok, "❌ Backend server not accessible"
    print("✅ Backend server connectivity verified")
    
    infrastructure = {
        'client': client,
        'uuid_tracker': uuid_tracker,
        'validator': validator,
        'perf_monitor': perf_monitor
    }
    
    yield infrastructure
    
    print("\n🧹 Test suite completed - infrastructure shutdown")


@pytest_asyncio.fixture(scope="session")
async def test_data_ecosystem(test_infrastructure):
    """Create complete test data ecosystem via REST API"""
    client = test_infrastructure['client']
    uuid_tracker = test_infrastructure['uuid_tracker']
    
    print("\n📊 Phase 1: Creating test data ecosystem via REST API...")
    
    # Initialize data setup
    ecosystem = TestDataEcosystem(client, uuid_tracker)
    
    try:
        # Execute complete setup
        setup_data = await ecosystem.create_complete_ecosystem()
        
        print(f"✅ Test ecosystem created successfully:")
        print(f"   📁 {len(setup_data['cases'])} cases created")
        print(f"   📄 {len(setup_data['documents'])} documents created") 
        print(f"   📧 {len(setup_data['communications'])} communications logged")
        print(f"   🤖 {len(setup_data['conversations'])} agent conversations started")
        print(f"   🔑 {uuid_tracker.total_tracked()} UUIDs tracked for cleanup")
        
        yield setup_data
        
    except Exception as e:
        print(f"❌ Test ecosystem setup failed: {e}")
        raise
    finally:
        # Execute complete cleanup
        print("\n🗑️ Executing complete test data cleanup...")
        cleanup_success = await ecosystem.cleanup_all_data()
        
        if cleanup_success:
            print("✅ All test data cleaned up successfully")
        else:
            print("⚠️  Some cleanup issues detected - check logs")


@pytest_asyncio.fixture(scope="function")
async def agent_db_client(test_infrastructure):
    """Function-level fixture for agent/db endpoint testing"""
    return test_infrastructure['client']


@pytest_asyncio.fixture(scope="function") 
async def performance_monitor(test_infrastructure):
    """Function-level fixture for performance monitoring"""
    return test_infrastructure['perf_monitor']


@pytest_asyncio.fixture(scope="function")
async def data_validator(test_infrastructure):
    """Function-level fixture for response validation"""
    return test_infrastructure['validator']


# Test result collection for summary reporting
@pytest.fixture(scope="session")
def test_results_collector():
    """Collect test results for summary reporting"""
    results = {
        'read_operations': {'passed': 0, 'failed': 0, 'total_time': 0},
        'create_operations': {'passed': 0, 'failed': 0, 'total_time': 0},
        'update_operations': {'passed': 0, 'failed': 0, 'total_time': 0},
        'workflows': {'passed': 0, 'failed': 0, 'total_time': 0},
        'error_handling': {'passed': 0, 'failed': 0, 'total_time': 0}
    }
    yield results
    
    # Print summary at end of session
    print("\n" + "="*60)
    print("🧪 AGENT DB TESTING SUITE SUMMARY")
    print("="*60)
    
    total_passed = sum(cat['passed'] for cat in results.values())
    total_failed = sum(cat['failed'] for cat in results.values()) 
    total_time = sum(cat['total_time'] for cat in results.values())
    
    for category, stats in results.items():
        category_name = category.replace('_', ' ').title()
        total_tests = stats['passed'] + stats['failed']
        avg_time = stats['total_time'] / total_tests if total_tests > 0 else 0
        
        status = "✅" if stats['failed'] == 0 else "❌"
        print(f"{status} {category_name}: {stats['passed']}/{total_tests} passed, avg {avg_time:.2f}s")
    
    print("-" * 60)
    print(f"📈 OVERALL: {total_passed}/{total_passed + total_failed} tests passed")
    print(f"⏱️  TOTAL TIME: {total_time:.2f} seconds")
    
    if total_failed == 0:
        print("🎉 ALL TESTS PASSED - Agent DB endpoint functioning correctly!")
    else:
        print(f"⚠️  {total_failed} tests failed - review failures above")
    print("="*60)


def pytest_runtest_makereport(item, call):
    """Hook to collect test results for summary reporting"""
    if call.when == "call":
        # Extract category from test file name
        test_file = item.fspath.basename
        if 'read_operations' in test_file:
            category = 'read_operations'
        elif 'create_operations' in test_file:
            category = 'create_operations'
        elif 'update_operations' in test_file:
            category = 'update_operations'
        elif 'workflows' in test_file:
            category = 'workflows'
        elif 'error_handling' in test_file:
            category = 'error_handling'
        else:
            return
        
        # Get results collector from session
        results_collector = item.session._test_results_collector if hasattr(item.session, '_test_results_collector') else None
        if results_collector:
            if call.excinfo is None:
                results_collector[category]['passed'] += 1
            else:
                results_collector[category]['failed'] += 1
            results_collector[category]['total_time'] += call.duration


@pytest.fixture(scope="session", autouse=True)
def setup_results_collector(test_results_collector):
    """Ensure results collector is available in session"""
    import pytest
    pytest.current_session = None
    yield