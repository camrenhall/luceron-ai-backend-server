# REST API Database Tests

**Standalone Tavern-based API testing suite for database operations.**

## Quick Start

### 1. Install Dependencies
```bash
cd tests/rest_db
pip install -r requirements.txt
```

### 2. Configure Environment
```bash
# Required: OAuth credentials
export TEST_OAUTH_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----
your_private_key_here
-----END PRIVATE KEY-----"

# Optional: API URL (defaults to localhost:8080)
export AGENT_DB_BASE_URL="http://localhost:8080"
```

### 3. Run Tests
```bash
# Run all API tests
python run_tests.py

# Run specific test suite
python run_tests.py --pattern cases
python run_tests.py --pattern documents

# Verbose output
python run_tests.py --verbose

# List available tests
python run_tests.py --list
```

## Test Coverage

- ✅ **Cases CRUD** - Complete create, read, update, delete operations
- ✅ **Documents CRUD** - File operations with case dependencies
- ✅ **Communications** - Client communication channels
- ✅ **Agent Conversations** - Agent interaction workflows
- ✅ **Integration Tests** - Cross-table operations and workflows

## Architecture

- **Tavern Framework** - YAML-based declarative API testing
- **OAuth2 Authentication** - Secure API access with JWT tokens
- **Environment Driven** - Easy configuration for different environments
- **Standalone** - No dependencies on other test frameworks

## CI/CD Integration

```yaml
- name: Run REST API Tests
  run: |
    cd tests/rest_db
    python run_tests.py
  env:
    TEST_OAUTH_PRIVATE_KEY: ${{ secrets.TEST_OAUTH_PRIVATE_KEY }}
    AGENT_DB_BASE_URL: "http://localhost:8080"
```