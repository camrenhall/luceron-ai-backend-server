# Agent DB Testing Suite

Comprehensive testing framework for the `/agent/db` endpoint - the natural language to database operation interface.

## Overview

This testing suite validates the AI-driven database interaction capabilities of the Luceron AI Backend Server's `/agent/db` endpoint through a two-phase approach:

1. **Phase 1**: Create comprehensive test data ecosystem via REST API
2. **Phase 2**: Validate natural language operations (CREATE, READ, UPDATE) via `/agent/db`

## Test Structure

```
tests/agent_db/
├── conftest.py              # Pytest fixtures & session setup
├── infrastructure.py       # Core testing utilities  
├── test_data_setup.py      # Phase 1: REST API data creation
├── test_read_operations.py # Phase 2: READ operation testing
├── test_create_operations.py # Phase 2: CREATE operation testing
├── test_update_operations.py # Phase 2: UPDATE operation testing
├── test_workflows.py       # Phase 2: Complex workflow testing
└── test_error_handling.py  # Phase 2: Error & edge case testing
```

## Prerequisites

1. **Backend Server Running**: Ensure the Luceron AI Backend Server is running and accessible
2. **Database Access**: Clean test database or ability to cleanup test data
3. **API Authentication**: Valid API key or OAuth2 credentials configured

## Configuration

### Environment Variables

Set these environment variables or update the test configuration:

```bash
# Backend server URL (default: http://localhost:8080)
export AGENT_DB_TEST_BASE_URL="http://localhost:8080"

# API authentication
export AGENT_DB_TEST_API_KEY="your-test-api-key"

# Or OAuth2 configuration
export AGENT_DB_TEST_OAUTH_CLIENT_ID="your-client-id"
export AGENT_DB_TEST_OAUTH_CLIENT_SECRET="your-client-secret"
```

### Test Configuration

Update `infrastructure.py` if needed to match your authentication setup:

```python
class TestClient:
    def __init__(self, base_url: str = "http://localhost:8080"):
        self.headers = {
            "Content-Type": "application/json",
            "X-API-Key": "your-api-key-here"  # Update this
        }
```

## Running Tests

### Run All Tests
```bash
cd tests/agent_db
pytest
```

### Run Specific Test Categories
```bash
# READ operations only
pytest test_read_operations.py

# CREATE operations only  
pytest test_create_operations.py

# UPDATE operations only
pytest test_update_operations.py

# Complex workflows
pytest test_workflows.py

# Error handling
pytest test_error_handling.py
```

### Run with Specific Options
```bash
# Verbose output with performance timing
pytest -v --durations=10

# Stop on first failure
pytest -x

# Run only fast tests (skip slow workflows)
pytest -m "not slow"

# Generate detailed output
pytest -v -s --tb=long
```

## Test Categories

### READ Operations (`test_read_operations.py`)
- **A1**: Simple entity queries ("Show me Sarah Johnson's case")
- **A2**: Status-based filtering ("Show me all open cases") 
- **A3**: Time-based queries ("Show me cases created in the last week")
- **A4**: Cross-entity relationships ("Show me all completed analyses for Sarah Johnson")
- **A5**: Aggregation and counting ("How many emails were sent to each client?")

### CREATE Operations (`test_create_operations.py`)
- **B1**: Case creation scenarios
- **B2**: Document registration 
- **B3**: Communication logging
- **B4**: Agent state initialization

### UPDATE Operations (`test_update_operations.py`)
- **C1**: Case status management ("Close Jennifer Wilson's case")
- **C2**: Document status progression ("Mark document as completed")
- **C3**: Communication status updates ("Mark email as delivered")
- **C4**: Agent context modifications ("Update client preferences")

### Complex Workflows (`test_workflows.py`)
- **D1**: Complete case workflow simulation (8-step end-to-end process)
- **D2**: Problem resolution workflow (6-step error recovery)
- **D3**: Multi-client batch operations

### Error Handling (`test_error_handling.py`)
- **E1**: Ambiguous entity references
- **E2**: Non-existent entity operations
- **E3**: Invalid state transitions
- **E4**: Authorization boundary testing

## Performance Benchmarks

The test suite validates these performance requirements:

- **Simple queries**: < 2 seconds response time
- **Complex multi-table queries**: < 5 seconds response time
- **CREATE operations**: < 3 seconds completion time  
- **UPDATE operations**: < 2 seconds completion time

## Test Data Management

### Automatic Cleanup
- All test data is automatically tracked and cleaned up
- UUID tracking ensures complete data removal
- Pre-test state capture and post-test verification

### Test Ecosystem
The test suite creates a realistic data ecosystem:
- **4 test clients** with diverse case types
- **10 documents** with various processing states
- **13 communications** with different delivery statuses
- **5 agent conversations** with messages and summaries
- **3 agent context entries** with client preferences
- **5 error logs** with different severity levels

## Success Criteria

### Functional Accuracy
- **100%** successful entity creation with proper relationships
- **100%** accurate data retrieval and filtering  
- **100%** successful state changes with audit trail preservation
- **100%** appropriate error responses for invalid operations

### AI Interpretation Accuracy
- **95%** accurate entity recognition
- **98%** correct operation type determination
- **100%** accurate field value assignment
- **100%** compliance with business logic rules

## Troubleshooting

### Common Issues

**Backend Server Not Accessible**
```
❌ Backend server not accessible
```
Solution: Ensure server is running on expected URL and check network connectivity.

**Authentication Failures**
```
❌ HTTP error: 401/403
```
Solution: Verify API key or OAuth2 credentials are correctly configured.

**Database Connection Issues**
```
❌ Test ecosystem setup failed
```
Solution: Check database connectivity and permissions.

**Incomplete Cleanup**
```
⚠️  Some cleanup issues detected
```
Solution: Review cleanup logs and manually clean test data if needed.

### Debug Mode

Run tests with debug logging:
```bash
pytest -v -s --log-cli-level=DEBUG
```

### Test Isolation

If tests interfere with each other:
```bash
# Run tests one at a time
pytest --maxfail=1 -x

# Run specific test function
pytest -k "test_simple_entity_queries"
```

## Expected Output

Successful test run should show:
```
🧪 AGENT DB TESTING SUITE SUMMARY
============================================================
✅ Read Operations: 20/20 passed, avg 0.45s
✅ Create Operations: 15/15 passed, avg 1.2s  
✅ Update Operations: 12/12 passed, avg 0.8s
✅ Workflows: 3/3 passed, avg 4.2s
✅ Error Handling: 25/25 passed, avg 0.3s
------------------------------------------------------------
📈 OVERALL: 75/75 tests passed
⏱️  TOTAL TIME: 123.45 seconds
🎉 ALL TESTS PASSED - Agent DB endpoint functioning correctly!
============================================================
```

## Contributing

When adding new tests:
1. Follow existing naming conventions
2. Add appropriate performance monitoring
3. Include UUID tracking for cleanup
4. Update this README with new test descriptions
5. Ensure tests validate both success and error conditions