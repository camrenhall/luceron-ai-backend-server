# CRUD Comprehensive Testing Suite

**Lightweight but functionally complete testing of all database CRUD operations with dual-layer validation (REST API + Direct Database).**

## Quick Start

### 1. Install Dependencies
```bash
cd tests/crud_comprehensive
pip install -r requirements.txt
```

### 2. Configuration
Set environment variables for testing your local container:
```bash
# Required: OAuth credentials (same as original Python tests)
export OAUTH_SERVICE_ID="qa_comprehensive_test_service"
export TEST_OAUTH_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----
your_private_key_here
-----END PRIVATE KEY-----"

# Optional: API base URL (defaults to localhost:8080 for local container)
export AGENT_DB_BASE_URL="http://localhost:8080"

# Optional: Performance thresholds
export CREATE_THRESHOLD="3.0"
export READ_THRESHOLD="2.0"
```

**For CI/CD Integration:**
```bash
# Point to deployed service instead of localhost
export AGENT_DB_BASE_URL="https://your-deployed-api.com"
```

### 3. Run Tests

**🚀 TAVERN TESTS (Default - Replaces Python tests):**
```bash
# Run all integration tests (equivalent to python run_tests.py)
python run_tavern_tests.py

# Run specific test suite
python run_tavern_tests.py --pattern cases      # Cases CRUD
python run_tavern_tests.py --pattern documents  # Documents CRUD
python run_tavern_tests.py --pattern agent      # Agent tests

# Verbose output for debugging
python run_tavern_tests.py --verbose

# List available test files
python run_tavern_tests.py --list-tests

# Direct pytest execution
pytest tavern_tests/ -v --no-cov
```

**📚 Original Python Tests (Available for comparison):**
```bash
# Legacy Python implementation
python run_tests.py
pytest suites/ integration/ -v
```

**🔄 Migration Status:**
- ✅ **Tavern tests** - Lightweight YAML-based, ready for CI/CD
- 📦 **Python tests** - Original implementation, more complex but fully featured

## Architecture

### 🆕 Tavern-Based Testing (MVP Focus)
```
YAML Test Definition → Tavern Engine → API Validation
         ↓                    ↓              ↓
   Declarative Tests    HTTP Requests    Response Validation
   Static Test Data     OAuth Tokens     Status Code Checks
   Clear Test Stages    JSON Payloads    Field Validation
```

**Key Components:**
- **tavern_config.yaml** - Global configuration and environment variables
- **tavern_helpers.py** - OAuth token generation and utility functions
- **Static Test Data** - Predictable, maintainable test scenarios
- **YAML Test Files** - Declarative test definitions

### Legacy Python Testing (Advanced)
```
REST API Test → Database Validation
      ↓                    ↓
   HTTP 200           Record EXISTS
   UUID Returned     Foreign Keys Valid
   Data Correct      Constraints Met
```

**Core Components:**
- **TestOrchestrator** - Central coordination and timing
- **RestClient** - OAuth-authenticated HTTP client  
- **DatabaseValidator** - Direct Supabase connectivity
- **DataFactory** - Realistic test data generation

### Test Coverage

**All Critical Tables - COMPLETE:**
- ✅ `cases` - Full CRUD + search + validation + performance
- ✅ `documents` - Full CRUD + batch operations + analysis + foreign keys
- ✅ `client_communications` - Communication channels + email integration
- ✅ `agent_conversations` - Full CRUD + status transitions + database validation
- ✅ `agent_messages` - Full CRUD + conversation history + sequence validation
- ✅ `agent_summaries` - Full CRUD + latest summary + auto-generation
- ✅ `agent_context` - Full CRUD + case-specific context + key validation
- ✅ `error_logs` - Alert creation + severity levels + component stats

**All Critical Endpoints - COMPLETE:**
- ✅ **40+ REST endpoints** from OpenAPI specification
- ✅ **Agent Gateway** natural language interface (`/api/agent/db`)
- ✅ **Email system** + webhook handlers
- ✅ **OAuth2** authentication + discovery
- ✅ **Health checks** and system monitoring

**Integration Tests:**
- ✅ Case → Document workflow
- ✅ Agent conversation → messages → summaries
- ✅ Foreign key integrity validation

## Key Features

### 🚀 **Ultra-Lightweight MVP**
- **5 core files** - Essential functionality only
- **~800 lines total** - Minimal overhead
- **Zero external dependencies** - Uses existing OAuth infrastructure

### 🔒 **Production Authentication** 
- OAuth2 client credentials flow
- RSA-signed JWT tokens
- Automatic token refresh

### 🔍 **Comprehensive Validation**
- REST endpoint testing
- Direct database verification  
- Foreign key relationship validation
- Performance threshold monitoring

### 🧹 **Complete Cleanup**
- UUID tracking for all created records
- Dependency-aware deletion order
- Test data isolation with prefixes

## Performance Monitoring

**Default Thresholds:**
- CREATE: < 3.0 seconds
- READ: < 2.0 seconds  
- UPDATE: < 2.0 seconds
- DELETE: < 2.0 seconds

**Customize via environment:**
```bash
CREATE_THRESHOLD=2.0
READ_THRESHOLD=1.5
UPDATE_THRESHOLD=1.5
DELETE_THRESHOLD=1.5
```

## Configuration Options

```python
# config.py settings
enable_database_validation = True    # Direct DB verification
enable_performance_monitoring = True # Timing validation
cleanup_test_data = True            # Auto cleanup
max_concurrent_tests = 5            # Parallel execution limit
generate_html_report = True         # HTML reporting
```

## Example Test Flow

```python
async def test_complete_crud_cycle():
    # 1. CREATE via REST API
    case_data = {"client_name": "Test Client", ...}
    create_result = await orch.execute_create("cases", "/api/cases", case_data)
    
    # 2. VALIDATE in database
    validation = await orch.validate_database_state(
        "cases", "case_id", create_result.uuid, "CREATE"
    )
    assert validation.valid
    
    # 3. READ via REST API
    read_result = await orch.execute_read("cases", "/api/cases/{id}", create_result.uuid)
    
    # 4. UPDATE via REST API
    update_result = await orch.execute_update("cases", "/api/cases/{id}", 
                                             create_result.uuid, {"status": "CLOSED"})
    
    # 5. VALIDATE update in database
    update_validation = await orch.validate_database_state(
        "cases", "case_id", create_result.uuid, "UPDATE"
    )
    assert update_validation.valid
```

## Results & Reporting

**Console Output:**
```
🔍 Testing Connectivity & Authentication...
   ✅ OAuth token obtained: eyJhbGciOiJSUzI1Ni...
   ✅ API health check passed (0.23s)  
   ✅ Database connected, found 42 existing cases

🧪 Running Basic CRUD Test...
   ✅ CREATE case succeeded (1.34s)
   ✅ READ case succeeded (0.18s)
   ✅ Database validation passed

📊 Performance Summary:
   CREATE Operations: 3 total
   Average Duration: 1.28s
   Max Duration: 1.45s  
   Success Rate: 100.0%
   ✅ Performance within threshold (3.0s)
```

**Pytest Output:**
```
tests/crud_comprehensive/suites/test_cases_crud.py::TestCasesCRUD::test_cases_full_crud_cycle PASSED
tests/crud_comprehensive/suites/test_cases_crud.py::TestCasesCRUD::test_cases_list_operation PASSED
tests/crud_comprehensive/suites/test_documents_crud.py::TestDocumentsCRUD::test_documents_full_crud_cycle PASSED
tests/crud_comprehensive/integration/test_cross_table_operations.py::TestCrossTableOperations::test_case_document_workflow PASSED
```

## Development Notes

### Adding New Test Suites

1. **Create test file** in `suites/test_[table]_crud.py`
2. **Use TestOrchestrator** for all operations
3. **Follow naming pattern** - `test_[table]_[operation]_[scenario]`
4. **Include database validation** for all CRUD operations

### Extending Data Factory

```python
def generate_new_resource(self, parent_id: str, **overrides):
    """Generate test data for new resource"""
    resource_id = str(uuid.uuid4())
    self.track_uuid('new_resource', resource_id)
    
    data = {
        "parent_id": parent_id,
        "name": f"{self.config.test_data_prefix}_ResourceName",
        # ... other fields
    }
    data.update(overrides)
    return data, resource_id
```

## Troubleshooting

**OAuth Issues:**
```bash
# Verify private key format
head -1 your_private_key_file  # Should be: -----BEGIN PRIVATE KEY-----

# Test token generation manually  
python -c "from core.rest_client import RestClient; import asyncio; client = RestClient(); print(asyncio.run(client._get_access_token()))"
```

**Database Connection Issues:**
```bash
# Test direct connection
python -c "from core.database_validator import DatabaseValidator; import asyncio; db = DatabaseValidator(); asyncio.run(db.connect()); print('Connected')"
```

**Performance Issues:**
```bash  
# Adjust thresholds
export CREATE_THRESHOLD=5.0
export READ_THRESHOLD=3.0
```

---

## Summary

This lightweight testing suite provides **comprehensive CRUD validation** with **minimal implementation overhead**. The dual-layer approach (REST + Database) ensures complete confidence in data integrity while maintaining practical execution speed.

**Key Benefits:**
- **5-minute setup** with existing OAuth infrastructure
- **Complete CRUD coverage** for all major tables  
- **Production-ready authentication** with automatic token management
- **Database integrity validation** with foreign key checking
- **Performance monitoring** with configurable thresholds
- **Zero test data leakage** with comprehensive cleanup

Perfect for **MVP validation** while building toward comprehensive test coverage.