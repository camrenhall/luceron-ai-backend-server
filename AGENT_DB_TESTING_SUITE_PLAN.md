# Agent DB Testing Suite Development Plan

## Overview

This document outlines the development plan for a comprehensive testing suite for the `/agent/db` endpoint, based on the requirements specified in `AGENT_DB_TESTING_STRATEGY.md`. The testing suite validates natural language to database operations through a two-phase approach with deterministic test data setup followed by AI-driven testing.

## Architecture Overview

The testing suite is structured as a Python test framework using pytest with modular components for setup, execution, validation, and cleanup.

```
tests/
├── agent_db/                          # Main test suite directory
│   ├── __init__.py
│   ├── conftest.py                    # Pytest configuration & fixtures
│   ├── infrastructure/                # Core testing infrastructure
│   │   ├── __init__.py
│   │   ├── test_client.py            # HTTP client wrapper
│   │   ├── uuid_tracker.py           # UUID tracking and cleanup
│   │   ├── data_validator.py         # Data integrity validation
│   │   └── performance_monitor.py    # Response time tracking
│   ├── phase1_setup/                  # REST API test data creation
│   │   ├── __init__.py
│   │   ├── client_portfolio.py       # 4 test clients creation
│   │   ├── document_ecosystem.py     # Document states setup  
│   │   ├── communication_history.py  # Email/SMS history
│   │   ├── agent_state_setup.py      # Conversations, context
│   │   └── error_log_seeding.py      # System error simulation
│   ├── phase2_ai_testing/             # Natural language operation tests
│   │   ├── __init__.py
│   │   ├── test_read_operations.py    # Category A tests
│   │   ├── test_create_operations.py  # Category B tests  
│   │   ├── test_update_operations.py  # Category C tests
│   │   ├── test_complex_workflows.py  # Category D tests
│   │   └── test_error_handling.py     # Category E tests
│   ├── models/                        # Data models and validators
│   │   ├── __init__.py
│   │   ├── test_entities.py          # Client, case, document models
│   │   ├── expected_responses.py     # Expected AI response patterns
│   │   └── validation_schemas.py     # Response validation schemas
│   └── helpers/                       # Utility functions
│       ├── __init__.py
│       ├── natural_language.py      # NL query builders
│       ├── assertion_helpers.py     # Custom assertions
│       └── cleanup_orchestrator.py  # Database cleanup logic
```

## Development Phases

### Phase 1: Core Infrastructure Development

#### 1.1 Test Client Infrastructure (`infrastructure/test_client.py`)
- HTTP client wrapper with authentication handling
- Request/response logging for debugging
- Retry logic for flaky network conditions
- Support for both REST API and `/agent/db` endpoints

#### 1.2 UUID Tracking System (`infrastructure/uuid_tracker.py`)
- Track all generated UUIDs during test execution
- Support for different entity types (cases, documents, communications, etc.)
- Cleanup orchestration based on dependency relationships
- Verification of complete cleanup

#### 1.3 Data Validation Framework (`infrastructure/data_validator.py`)
- Schema validation for API responses
- Business logic validation helpers
- Foreign key relationship verification
- Audit trail integrity checking

#### 1.4 Performance Monitoring (`infrastructure/performance_monitor.py`)
- Response time tracking for all operations
- Performance benchmark validation
- Simple console reporting of timing metrics
- Timeout handling and alerting

### Phase 2: Test Data Creation Framework

#### 2.1 Client Portfolio Setup (`phase1_setup/client_portfolio.py`)
Create 4 diverse test clients via REST API:
- **Sarah Johnson**: Active complex case with multiple documents
- **Michael Chen**: Recently completed case  
- **Rebecca Martinez**: Problematic case with processing issues
- **David Thompson**: Minimal activity case

#### 2.2 Document Ecosystem (`phase1_setup/document_ecosystem.py`)
Create documents with various processing states:
- Sarah: 5 documents (COMPLETED, PROCESSING, FAILED, PENDING states)
- Michael: 2 documents (all COMPLETED)
- Rebecca: 2 documents (mixed FAILED/COMPLETED)
- David: 1 document (PENDING)

#### 2.3 Communication History (`phase1_setup/communication_history.py`)
Generate realistic communication patterns:
- Email delivery statuses (delivered, opened, bounced)
- SMS notifications with delivery tracking
- Inbound/outbound message flows
- Failed delivery scenarios

#### 2.4 Agent State Setup (`phase1_setup/agent_state_setup.py`)
Initialize agent conversation states:
- CommunicationsAgent conversations with message history
- AnalysisAgent conversations with summaries
- Agent context storage with client preferences
- Various conversation statuses (ACTIVE, COMPLETED, FAILED)

#### 2.5 Error Log Seeding (`phase1_setup/error_log_seeding.py`)
Create realistic error scenarios:
- Multiple severity levels (MEDIUM, HIGH, CRITICAL)
- Various component error types
- Historical error patterns

### Phase 3: AI Testing Framework

#### 3.1 READ Operations Testing (`phase2_ai_testing/test_read_operations.py`)

**Category A1: Simple Entity Queries**
- "Show me Sarah Johnson's case"
- "What documents does Michael Chen have?"
- "List all communications for Rebecca Martinez"

**Category A2: Status-Based Filtering**  
- "Show me all open cases"
- "What documents are currently processing?"
- "Find failed email communications"

**Category A3: Time-Based Queries**
- "Show me cases created in the last week"
- "What communications happened yesterday?"
- "Find documents uploaded this month"

**Category A4: Cross-Entity Relationship Queries**
- "Show me all completed analyses for Sarah Johnson"
- "What cases have failed document processing?"
- "Find clients who haven't responded to emails"

**Category A5: Aggregation and Counting**
- "How many emails were sent to each client?"
- "Count documents by processing status"

#### 3.2 CREATE Operations Testing (`phase2_ai_testing/test_create_operations.py`)

**Category B1: Case Creation**
- "Create a case for Jennifer Wilson, jennifer.wilson@email.com"
- "Add a new case for Robert Kim with phone (555) 999-8888"
- "Start a case for Emma Davis, emma@company.com, phone (555) 111-2222"

**Category B2: Document Registration**
- "Add a document 'New_Contract.pdf' to Jennifer Wilson's case"
- "Register document 'Financial_Report.xlsx' for Robert Kim"
- "Create document entry for Emma Davis: 'Legal_Opinion.docx', size 2.5MB"

**Category B3: Communication Logging**
- "Log an email sent to Jennifer Wilson about document requirements"
- "Record SMS notification sent to Robert Kim"
- "Create communication record: outbound email to Emma Davis"

**Category B4: Agent State Initialization**
- "Start a new CommunicationsAgent conversation for Jennifer Wilson's case"
- "Create agent context for Robert Kim: client prefers phone calls"
- "Begin AnalysisAgent session for Emma Davis case"

#### 3.3 UPDATE Operations Testing (`phase2_ai_testing/test_update_operations.py`)

**Category C1: Case Status Management**
- "Close Jennifer Wilson's case"
- "Reopen Sarah Johnson's case" 
- "Mark Robert Kim's case as high priority"

**Category C2: Document Status Progression**
- "Mark Jennifer Wilson's New_Contract.pdf as completed"
- "Update Financial_Report.xlsx status to processing"
- "Set Legal_Opinion.docx as failed processing"

**Category C3: Communication Status Updates**
- "Mark email to Jennifer Wilson as delivered"
- "Update SMS to Robert Kim as opened"
- "Set Emma Davis email as bounced"

**Category C4: Agent Context Modifications**
- "Update Jennifer Wilson's communication preference to email only"
- "Add note to Robert Kim's context: client is traveling this week"

#### 3.4 Complex Workflows Testing (`phase2_ai_testing/test_complex_workflows.py`)

**Category D1: Complete Case Workflow Simulation**
8-step workflow from case creation to closure:
1. Create case → 2. Add document → 3. Send email → 4. Start agent conversation → 
5. Update document status → 6. Add analysis → 7. Send notification → 8. Close case

**Category D2: Problem Resolution Workflow**
6-step problem resolution workflow:
1. Find failed cases → 2. Update document status → 3. Create context note → 
4. Send notification → 5. Update to completed → 6. Log resolution

#### 3.5 Error Handling Testing (`phase2_ai_testing/test_error_handling.py`)

**Category E1: Ambiguous Entity References**
- "Show me John's case" (multiple Johns)
- "Update the document status" (no specific document)
- "Send email to client" (no specific client)

**Category E2: Non-Existent Entity Operations**
- "Show cases for nonexistent@email.com"
- "Update document status for UnknownFile.pdf"
- "Close case for Fictional Client"

**Category E3: Invalid State Transitions**
- "Set completed document back to pending"
- "Reopen a case that's already open"
- "Mark delivered email as sent"

**Category E4: Authorization Boundary Testing**
- "Delete all error logs" (prohibited operation)
- "Modify system configuration" (unauthorized access)
- "Access restricted client information" (permission boundary)

### Phase 4: Support Components

#### 4.1 Data Models (`models/test_entities.py`)
- Pydantic models for test clients, cases, documents
- Expected response structures
- Validation schemas for AI responses

#### 4.2 Natural Language Helpers (`helpers/natural_language.py`)
- Query builders for consistent NL test cases
- Template-based query generation
- Parameterized test case creation

#### 4.3 Assertion Helpers (`helpers/assertion_helpers.py`)
- Custom assertion functions for AI responses
- Business logic validation helpers  
- Performance threshold assertions
- Data integrity checking functions

#### 4.4 Cleanup Orchestrator (`helpers/cleanup_orchestrator.py`)
- Dependency-aware cleanup sequencing
- UUID tracking integration
- Pre-test state capture
- Post-test verification

## Testing Flow

### 1. Test Session Setup
```python
@pytest.fixture(scope="session", autouse=True)
async def setup_test_environment():
    # Initialize test client and UUID tracker
    # Capture pre-test database state
    # Setup authentication
    yield
    # Execute complete cleanup
    # Verify database restoration
```

### 2. Phase 1 Execution (REST Setup)
```python
@pytest.fixture(scope="session")
async def test_data_ecosystem():
    # Create client portfolio
    # Setup document ecosystem  
    # Generate communication history
    # Initialize agent states
    # Seed error logs
    return tracked_uuids
```

### 3. Phase 2 Execution (AI Testing)
```python
@pytest.mark.parametrize("query, expected", test_cases)
async def test_ai_operation(query, expected, test_data_ecosystem):
    # Execute natural language query
    # Validate response structure
    # Check business logic compliance
    # Verify performance benchmarks
    # Assert data integrity
```

## Success Criteria & Validation

### Functional Accuracy Requirements
- **100% Entity Creation Success**: All CREATE operations must succeed with proper relationships
- **100% Data Retrieval Accuracy**: All READ operations must return correct, complete data
- **100% State Change Success**: All UPDATE operations must succeed with audit trail preservation
- **100% Error Handling**: All invalid operations must return appropriate error responses

### Performance Benchmarks
- Simple queries: < 2 seconds response time
- Complex multi-table queries: < 5 seconds response time  
- CREATE operations: < 3 seconds completion time
- UPDATE operations: < 2 seconds completion time

### AI Interpretation Accuracy
- 95% accurate entity recognition
- 98% correct operation type determination
- 100% accurate field value assignment
- 100% compliance with business logic rules

### Data Integrity Assurance
- Zero data corruption
- Complete cleanup (100% UUID tracking and removal)
- All foreign key constraints maintained
- Complete audit trail preservation

## Risk Mitigation

### Database Safety
- Transaction-based test isolation where possible
- Complete UUID tracking for cleanup guarantee
- Pre-test state capture and post-test verification
- Comprehensive cleanup orchestration with dependency handling

### Test Reliability  
- Retry logic for network-related failures
- Timeout protection for long-running operations
- Performance monitoring with threshold alerting
- Business logic validation for AI responses

### Error Handling
- Graceful handling of setup failures
- Partial cleanup capabilities for interrupted tests
- Detailed error reporting for debugging
- Test isolation to prevent cascade failures

## Reporting & Output

### Console Output Strategy
- **Test Progress**: Real-time progress indicators during execution
- **Performance Metrics**: Response time reporting for each operation category
- **Failure Details**: Comprehensive error descriptions with context
- **Summary Statistics**: Pass/fail counts, performance summaries, cleanup verification

### Test Result Categories
- **PASS**: Operation completed successfully within performance thresholds
- **FAIL**: Operation failed functionally or exceeded performance limits  
- **ERROR**: Test setup/execution error preventing proper validation
- **SKIP**: Test skipped due to dependency failure or configuration

### Cleanup Verification
- **UUID Tracking Report**: All tracked UUIDs and cleanup status
- **Database State Verification**: Pre/post test record count comparison
- **Integrity Check**: Foreign key relationship validation
- **Audit Trail Verification**: Proper logging of all operations

This development plan creates a comprehensive, robust testing framework that validates the `/agent/db` endpoint's capabilities while maintaining strict data integrity and providing clear, actionable test results through console output.