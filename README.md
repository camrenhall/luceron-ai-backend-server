# Luceron AI Backend Server

## Component Overview

The **luceron-ai-backend-server** is the central data and integration layer of the Luceron AI eDiscovery Platform. This RESTful API service acts as the backbone of the distributed system, managing all database operations, external service integrations, and providing standardized APIs for system components.

### Primary Purpose and Responsibilities

- **Data Persistence Layer**: Manages all CRUD operations for cases, documents, communications, and agent state
- **Integration Hub**: Orchestrates email/SMS communications via Resend API  
- **Agent State Management**: Persists conversation history, context, and summaries for AI agents
- **Document Pipeline Support**: Provides APIs for AWS Lambda functions during document processing
- **Audit Trail**: Maintains comprehensive logs of all system activities and communications

### Position Within System Architecture

```mermaid
graph TB
    CA[Communications Agent] --> BS[Backend Server]
    AA[Analysis Agent] --> BS
    AWS[AWS Document Pipeline] --> BS
    BS --> DB[(Supabase)]
    BS --> RS[Resend API]
    BS --> ADM[Admin Alerts]
    
    style BS fill:#f9f,stroke:#333,stroke-width:4px
```

### Key Business Problems Solved

1. **Data Consistency**: Ensures all microservices work with consistent, validated data
2. **Communication Tracking**: Maintains complete audit trail of client interactions
3. **Agent Conversation Management**: Enables stateful AI agent conversations with context persistence
4. **Scalable Document Processing**: Supports high-volume batch document operations
5. **Token Usage Tracking**: Monitors and controls LLM API costs across all agent interactions
6. **Error Recovery**: Provides resilient error handling with admin alerting

## Technical Architecture

### Technology Stack

- **Runtime**: Python 3.13
- **Framework**: FastAPI (async web framework)
- **Database Driver**: asyncpg (PostgreSQL async driver)
- **Email Service**: Resend API
- **Webhook Verification**: Svix
- **HTTP Client**: httpx (async HTTP client)
- **Data Validation**: Pydantic
- **ASGI Server**: Uvicorn with standard extras

### Design Patterns and Architectural Decisions

1. **Unified Service Layer Pattern**: All database operations go through a consistent service layer
2. **Agent Gateway Integration**: Natural language interface and REST APIs share the same data foundation
3. **Async/Await Pattern**: Fully asynchronous architecture for high concurrency
4. **Service Pattern**: Business logic abstracted through domain-specific services
5. **DTO Pattern**: Pydantic models for request/response validation
6. **Middleware Pattern**: CORS and error handling via FastAPI middleware
7. **Dependency Injection**: Authentication and database connections via FastAPI dependencies

### System Dependencies and Integration Points

```mermaid
graph LR
    BS[Backend Server] --> |PostgreSQL Protocol| SP[Supabase PostgreSQL]
    BS --> |REST API| RA[Resend API]
    BS --> |Webhook| RW[Resend Webhooks]
    LA[Lambda Functions] --> |REST API| BS
    CA[Communications Agent] --> |REST API| BS
    AA[Analysis Agent] --> |REST API| BS
```

### Unified Architecture Flow

```mermaid
sequenceDiagram
    participant NL as Natural Language
    participant AG as Agent Gateway
    participant Service as Service Layer
    participant REST as REST API
    participant DB as Database
    
    Note over NL,AG: Natural Language Interface
    NL->>AG: "Get all cases for client@example.com"
    AG->>Service: Parsed DSL → Service Call
    Service->>DB: SQL Query
    DB-->>Service: Results
    Service-->>AG: Structured Response
    AG-->>NL: Natural Language Response
    
    Note over REST,Service: REST Interface
    REST->>Service: Direct Service Call
    Service->>DB: SQL Query
    DB-->>Service: Results
    Service-->>REST: JSON Response
```

### Agent Gateway - Natural Language Interface

The backend includes a sophisticated Agent Gateway that converts natural language queries into database operations:

#### Key Components:
1. **Router**: Maps natural language to appropriate resources and operations
2. **Planner**: Converts natural language + context into structured DSL (Domain Specific Language)
3. **Validator**: Ensures DSL operations comply with security contracts and field permissions
4. **Executor**: Executes validated DSL through the unified service layer
5. **Contracts**: Define field-level permissions and operation constraints

#### Endpoint:
- `POST /agent/db` - Natural language database interface

#### Example Usage:
```json
{
  "natural_language": "Show me all open cases for client@example.com",
  "hints": {
    "resources": ["cases"],
    "intent": "READ"
  }
}
```

This provides a powerful way for AI agents to interact with the database using natural language while maintaining security and validation.

## API Documentation

### Architecture Overview

The Luceron AI Backend Server provides two primary interfaces:

1. **REST API**: Traditional HTTP endpoints for direct database operations
2. **Agent Gateway**: Natural language interface for AI agents

Both interfaces utilize the same unified service layer, ensuring consistent business logic, validation, and data access patterns.

### Authentication

All endpoints require API key authentication via the `X-API-Key` header:
```
X-API-Key: {API_KEY}
```

### Agent Gateway API

#### Natural Language Database Interface
- `POST /agent/db` - Convert natural language to database operations
- Request Schema:
```json
{
  "natural_language": "string - Natural language query",
  "hints": {
    "resources": ["cases", "documents"],
    "intent": "READ|INSERT|UPDATE",
    "filters": {"key": "value"}
  }
}
```

- Response Schema:
```json
{
  "success": true,
  "operation": "READ|INSERT|UPDATE",
  "resource": "cases",
  "data": [...],
  "count": 10,
  "page": {
    "limit": 100,
    "offset": 0
  }
}
```

### Core REST API Endpoints

#### Health Check
- `GET /` - Health check endpoint
- No authentication required
- Returns: `{"status": "healthy"}`

#### Cases Management

##### Create Case
- `POST /api/cases`
- Creates new case
- Request Schema:
```json
{
  "client_name": "string",
  "client_email": "email",
  "client_phone": "string"
}
```

##### Get Case Details
- `GET /api/cases/{case_id}`
- Returns case details

##### Search Cases
- `POST /api/cases/search`
- Advanced search with fuzzy matching support
- Supports filtering by client info, status, dates
- Request includes pagination and fuzzy match settings

##### List Cases
- `GET /api/cases`
- Paginated case listing
- Query params: `limit`, `offset`

##### Get Case Communications
- `GET /api/cases/{case_id}/communications`
- Returns communication history for a case

##### Get Analysis Summary
- `GET /api/cases/{case_id}/analysis-summary`
- Returns document analysis summary for a case


#### Documents API

##### Create Document
- `POST /api/documents`
- Creates document record (called by AWS Lambda)
- Tracks original file metadata

##### Update Document
- `PUT /api/documents/{document_id}`
- Updates document with processed file info

##### Lookup Documents by Batch
- `POST /api/documents/lookup-by-batch`
- Intelligent filename matching for batch processing
- Returns document IDs for processed files

##### Store Analysis (Single)
- `POST /api/documents/{document_id}/analysis`
- Stores OpenAI analysis results

##### Bulk Store Analysis
- `POST /api/documents/analysis/bulk`
- High-throughput batch analysis storage
- Atomic transaction with detailed error reporting

##### Get Document Analysis
- `GET /api/documents/{document_id}/analysis`
- Retrieves latest analysis for a document

##### Get All Analyses by Case
- `GET /api/documents/analysis/case/{case_id}`
- Returns all document analyses for a case
- Optional `include_content` parameter

##### Get Aggregated Analysis
- `GET /api/documents/analysis/case/{case_id}/aggregate`
- Dynamic SQL aggregation of analysis data

#### Agent State Management API

The agent state management system provides conversation persistence, message tracking, context storage, and summary generation for AI agents. This system replaces the previous workflow_states table with a more sophisticated architecture.

##### Agent Conversations

**Create Conversation**
- `POST /api/agent/conversations`
- Creates a new conversation session for an agent
- Request Schema:
```json
{
  "case_id": "uuid",
  "agent_type": "CommunicationsAgent|AnalysisAgent",
  "status": "ACTIVE|COMPLETED|FAILED|ARCHIVED"
}
```

**Get Conversation**
- `GET /api/agent/conversations/{conversation_id}`
- Returns conversation metadata including token usage

**Update Conversation**
- `PUT /api/agent/conversations/{conversation_id}`
- Updates conversation status

**Delete Conversation**
- `DELETE /api/agent/conversations/{conversation_id}`
- Deletes conversation and all associated messages/summaries

**List Conversations**
- `GET /api/agent/conversations`
- Query params: `case_id`, `agent_type`, `status`, `limit`, `offset`

**Get Full Conversation**
- `GET /api/agent/conversations/{conversation_id}/full`
- Returns conversation with all messages and summaries
- Query params: `include_summaries`, `include_function_calls`

##### Agent Messages

**Create Message**
- `POST /api/agent/messages`
- Adds a new message to a conversation
- Request Schema:
```json
{
  "conversation_id": "uuid",
  "role": "system|user|assistant|function",
  "content": {"text": "message content", "metadata": {}},
  "total_tokens": 150,
  "model_used": "gpt-4-turbo",
  "function_name": "optional_function_name",
  "function_arguments": {"param": "value"},
  "function_response": {"result": "data"}
}
```

**Get Message**
- `GET /api/agent/messages/{message_id}`
- Returns individual message with metadata

**Update Message**
- `PUT /api/agent/messages/{message_id}`
- Updates message content, tokens, or function response

**Delete Message**
- `DELETE /api/agent/messages/{message_id}`
- Removes message from conversation

**List Messages**
- `GET /api/agent/messages`
- Query params: `conversation_id`, `role`, `limit`, `offset`

**Get Conversation History**
- `GET /api/agent/messages/conversation/{conversation_id}/history`
- Returns messages in chronological order
- Query params: `limit`, `include_function_calls`

##### Agent Summaries

**Create Summary**
- `POST /api/agent/summaries`
- Creates a conversation summary
- Request Schema:
```json
{
  "conversation_id": "uuid",
  "last_message_id": "uuid",
  "summary_content": "Summary of the conversation...",
  "messages_summarized": 10
}
```

**Get Summary**
- `GET /api/agent/summaries/{summary_id}`
- Returns summary details

**Update Summary**
- `PUT /api/agent/summaries/{summary_id}`
- Updates summary content or message count

**Delete Summary**
- `DELETE /api/agent/summaries/{summary_id}`
- Removes summary

**List Summaries**
- `GET /api/agent/summaries`
- Query params: `conversation_id`, `limit`, `offset`

**Get Latest Summary**
- `GET /api/agent/summaries/conversation/{conversation_id}/latest`
- Returns most recent summary for a conversation

**Auto-Generate Summary**
- `POST /api/agent/summaries/conversation/{conversation_id}/auto-summary`
- Creates summary from recent messages
- Query params: `messages_to_summarize`

##### Agent Context

**Create/Update Context**
- `POST /api/agent/context`
- Upserts context key-value pairs
- Request Schema:
```json
{
  "case_id": "uuid",
  "agent_type": "CommunicationsAgent|AnalysisAgent",
  "context_key": "document_findings",
  "context_value": {"key": "value", "data": []},
  "expires_at": "2024-12-31T23:59:59Z"
}
```

**Get Context**
- `GET /api/agent/context/{context_id}`
- Returns context entry (excludes expired)

**Update Context**
- `PUT /api/agent/context/{context_id}`
- Updates context value or expiration

**Delete Context**
- `DELETE /api/agent/context/{context_id}`
- Removes context entry

**List Context**
- `GET /api/agent/context`
- Query params: `case_id`, `agent_type`, `context_key`, `include_expired`, `limit`, `offset`

**Get Case Agent Context**
- `GET /api/agent/context/case/{case_id}/agent/{agent_type}`
- Returns all context as key-value map for specific case/agent

**Get Specific Context Value**
- `GET /api/agent/context/case/{case_id}/agent/{agent_type}/key/{context_key}`
- Returns single context value

**Delete Case Agent Context**
- `DELETE /api/agent/context/case/{case_id}/agent/{agent_type}`
- Removes all context for case/agent combination

**Cleanup Expired Context**
- `POST /api/agent/context/cleanup-expired`
- Removes all expired context entries

#### Email API

##### Send Email
- `POST /api/send-email`
- Sends email via Resend and logs to database
- Request Schema:
```json
{
  "recipient_email": "email",
  "subject": "string",
  "body": "string",
  "html_body": "string (optional)",
  "case_id": "uuid"
}
```

#### Webhooks

##### Resend Webhook
- `POST /api/webhooks/resend`
- Handles Resend email status updates
- Updates: opened, delivered, failed, bounced
- Signature verification via Svix

#### Alerts API

##### Send Alert
- `POST /api/alert`
- Sends failure notifications to admins
- 15-minute deduplication window
- Request Schema:
```json
{
  "component": "string",
  "error_message": "string",
  "severity": "low|medium|high|critical",
  "context": {}
}
```

##### Get Error Logs
- `GET /api/logs`
- Query params: `component`, `severity`, `limit`, `offset`

##### Get Component Stats
- `GET /api/stats/{component}`
- Returns error statistics for component

### Error Handling

All endpoints return standardized error responses:
```json
{
  "detail": "Error description"
}
```

HTTP Status Codes:
- `200`: Success
- `400`: Bad Request
- `404`: Resource Not Found
- `409`: Conflict (duplicate)
- `422`: Validation Error
- `500`: Internal Server Error

### Rate Limiting

Currently no rate limiting implemented. Consider adding for production:
- Recommended: 100 requests/minute per API key
- Bulk endpoints: 10 requests/minute

## Setup and Installation

### Prerequisites

- Python 3.13+
- PostgreSQL database (via Supabase)
- Resend API account
- Docker (optional, for containerized deployment)

### Environment Variables

Required environment variables (DO NOT commit actual values):

```bash
# Database
DATABASE_URL=postgresql://user:password@host:port/database

# Authentication
API_KEY=your-api-key-here

# Email Service (Resend)
RESEND_API_KEY=re_xxxxxxxxxxxx
RESEND_WEBHOOK_SECRET=whsec_xxxxxxxxxxxx
FROM_EMAIL=notifications@yourdomain.com
ALERT_FROM_EMAIL=alerts@yourdomain.com  # Optional, defaults to FROM_EMAIL

# Admin Configuration
ADMIN_ALERT_EMAILS=admin1@company.com,admin2@company.com

# Server Configuration
PORT=8080  # Optional, defaults to 8080
```

### Local Development Setup

1. Clone the repository:
```bash
git clone <repository-url>
cd luceron-ai-backend-server
```

2. Create virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set environment variables:
```bash
export DATABASE_URL="your-database-url"
export API_KEY="your-api-key"
export RESEND_API_KEY="your-resend-key"
# ... other variables
```

5. Run the server:
```bash
python main.py
```

The server will start on `http://localhost:8080` (or configured PORT).

### Docker Configuration

Build and run with Docker:

```bash
# Build image
docker build -t luceron-backend .

# Run container
docker run -p 8080:8080 \
  -e DATABASE_URL="$DATABASE_URL" \
  -e API_KEY="$API_KEY" \
  -e RESEND_API_KEY="$RESEND_API_KEY" \
  -e FROM_EMAIL="$FROM_EMAIL" \
  -e ADMIN_ALERT_EMAILS="$ADMIN_ALERT_EMAILS" \
  luceron-backend
```

Docker image details:
- Base: `python:3.13-slim`
- Non-root user: `backend`
- Working directory: `/app`
- Exposed port: Configured via PORT env var

## Configuration

### Configuration Files

#### `src/config/settings.py`
Central configuration management. Loads environment variables and validates required settings.

Key configurations:
- Database connection pool settings
- CORS allowed origins
- Resend API configuration
- Admin email list parsing

### Environment-Specific Settings

#### Development
```bash
PORT=8080
# Use development database
DATABASE_URL=postgresql://dev_user@localhost/dev_db
```

#### Production
```bash
PORT=8080
# Use production database with SSL
DATABASE_URL=postgresql://prod_user@prod_host/prod_db?sslmode=require
```

### Feature Flags

Currently no feature flags implemented. Consider adding:
- `ENABLE_FUZZY_SEARCH`: Toggle PostgreSQL trigram search
- `ENABLE_WEBHOOK_VALIDATION`: Toggle webhook signature verification
- `ENABLE_ALERT_EMAILS`: Toggle admin email alerts

## Database Interactions

### Tables Accessed

#### Primary Tables

1. **cases**
   - Stores case metadata
   - Columns: `case_id`, `client_name`, `client_email`, `client_phone`, `status`, `created_at`
   - Status enum: `OPEN`, `CLOSED`

2. **documents**
   - Document file metadata
   - Columns: `document_id`, `case_id`, `original_file_name`, `original_s3_location`, `processed_file_name`, `processed_s3_location`, `status`, `batch_id`

3. **document_analysis**
   - OpenAI analysis results
   - Columns: `analysis_id`, `document_id`, `case_id`, `analysis_content` (JSON), `analysis_status`, `model_used`, `tokens_used`, `analysis_reasoning`

4. **client_communications**
   - Communication audit trail
   - Columns: `communication_id`, `case_id`, `channel`, `direction`, `status`, `opened_at`, `sender`, `recipient`, `subject`, `message_content`, `resend_id`

5. **Agent State Management Tables**
   
   **agent_conversations**
   - Conversation session management
   - Columns: `conversation_id`, `case_id`, `agent_type`, `status`, `total_tokens_used`, `created_at`, `updated_at`
   - Agent types: `CommunicationsAgent`, `AnalysisAgent`
   - Status: `ACTIVE`, `COMPLETED`, `FAILED`, `ARCHIVED`
   
   **agent_messages**
   - Individual message storage with sequencing
   - Columns: `message_id`, `conversation_id`, `role`, `content` (JSONB), `total_tokens`, `model_used`, `function_name`, `function_arguments` (JSONB), `function_response` (JSONB), `created_at`, `sequence_number`
   - Message roles: `system`, `user`, `assistant`, `function`
   
   **agent_summaries**
   - Rolling conversation summaries
   - Columns: `summary_id`, `conversation_id`, `last_message_id`, `summary_content`, `messages_summarized`, `created_at`, `updated_at`
   
   **agent_context**
   - Persistent key-value context storage
   - Columns: `context_id`, `case_id`, `agent_type`, `context_key`, `context_value` (JSONB), `expires_at`, `created_at`, `updated_at`
   - Unique constraint: `(case_id, agent_type, context_key)`

6. **error_logs**
   - System error tracking
   - Columns: `error_id`, `component`, `error_message`, `severity`, `context` (JSON), `email_sent`, `created_at`

### Service Layer Architecture

The backend implements a unified service layer that provides consistent data access patterns:

#### Service Components

1. **Base Service** (`services/base_service.py`)
   - Provides common CRUD operations (Create, Read, Update)
   - Handles validation through Agent Gateway contracts
   - Manages database connections and transactions

2. **Domain Services**
   - **Cases Service**: Case management operations with search capabilities
   - **Documents Service**: Document and analysis management
   - **Communications Service**: Email/SMS tracking and status updates
   - **Agent Services**: AI agent state management (conversations, messages, summaries, context)
   - **Error Logs Service**: System error tracking and monitoring

#### Service Pattern Example
```python
from services.cases_service import get_cases_service

# Get service instance
cases_service = get_cases_service()

# Perform operations
result = await cases_service.create_case(
    client_name="John Doe",
    client_email="john@example.com",
    status="OPEN"
)

# All services return consistent ServiceResult objects
if result.success:
    case_data = result.data[0]
    print(f"Created case: {case_data['case_id']}")
else:
    print(f"Error: {result.error}")
```

### Query Patterns

1. **Connection Pooling**
   - Min connections: 2
   - Max connections: 10
   - Command timeout: 60 seconds

2. **Transaction Boundaries**
   - Service layer manages transactions automatically
   - Case creation: Single transaction
   - Bulk analysis storage: Single transaction with rollback
   - Document updates: Auto-commit

3. **Optimization Strategies**
   - Batch validation queries for bulk operations
   - Index usage on `case_id`, `document_id`, `batch_id`
   - JSONB indexing for `analysis_content` queries
   - Service-level caching potential for frequently accessed data

### Database Connection Management

```python
# Connection pool initialization (src/database/connection.py)
db_pool = await asyncpg.create_pool(
    DATABASE_URL,
    min_size=2,
    max_size=10,
    command_timeout=60,
    statement_cache_size=0  # pgbouncer compatibility
)
```

## External Service Integrations

### OpenAI API Usage

While this backend doesn't directly call OpenAI, it stores and manages analysis results:
- Stores analysis in `document_analysis.analysis_content` as JSON
- Tracks token usage for cost monitoring
- Records model version used (`gpt-4-vision`, etc.)

### AWS Services

Integration points with AWS document pipeline:
- **S3**: Stores document locations but doesn't access directly
- **Lambda**: Receives API calls for document creation/updates
- **Step Functions**: Triggered by document status changes

### Supabase Operations

- **Database**: PostgreSQL via asyncpg
- **Connection**: Direct PostgreSQL protocol (not Supabase client)
- **Features Used**:
  - UUID generation
  - JSONB columns
  - Full-text search capabilities
  - Trigram extension for fuzzy matching (optional)

### Email/SMS Services

#### Resend API
- **Email Sending**: Transactional emails via REST API
- **Webhook Receipt**: Status updates (opened, delivered, failed, bounced)
- **Features**:
  - HTML and plain text support
  - Delivery tracking
  - Open tracking
  - Bounce handling

Configuration:
```python
resend.api_key = RESEND_API_KEY
```

## Event Handling and Messaging

### Events Consumed

#### Resend Webhooks
- **Endpoint**: `POST /api/webhooks/resend`
- **Events Handled**:
  - `email.opened`: Updates `opened_at` timestamp
  - `email.delivered`: Updates status to "delivered"
  - `email.failed`: Updates status to "failed"
  - `email.bounced`: Updates status to "failed"
- **Security**: Signature verification via Svix

### Events Produced

#### Database State Changes
The following state changes trigger downstream processing:

1. **Case Created**: Creates new case record
2. **Document Status Updated**: Triggers agent notifications
3. **Analysis Stored**: Enables aggregation queries

### Message Formats


#### Document Analysis Content
```json
{
  "extracted_fields": {},
  "summary": "string",
  "confidence_scores": {},
  "processing_metadata": {}
}
```

### Error Handling and Retry Logic

1. **Database Retries**: Handled by connection pool (automatic reconnection)
2. **Email Failures**: Logged but not retried (rely on Resend's retry)
3. **Webhook Processing**: Returns success even if record not found (idempotency)
4. **Bulk Operations**: Partial success with detailed failure reporting

## Testing

### Test Structure and Organization

**Note**: No test files currently exist in the repository. Recommended structure:

```
tests/
├── unit/
│   ├── test_models.py
│   ├── test_services.py
│   └── test_utils.py
├── integration/
│   ├── test_api_cases.py
│   ├── test_api_documents.py
└── conftest.py
```

### Running Tests Locally

Recommended test setup (to be implemented):

```bash
# Install test dependencies
pip install pytest pytest-asyncio pytest-cov httpx

# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test file
pytest tests/integration/test_api_cases.py
```

### Test Coverage Requirements

Recommended minimum coverage:
- Overall: 80%
- API endpoints: 90%
- Business logic: 85%
- Utilities: 70%

### Integration Test Setup

For integration tests, use TestClient:

```python
from fastapi.testclient import TestClient
from src.app import app

client = TestClient(app)

def test_health_check():
    response = client.get("/")
    assert response.status_code == 200
```

## Deployment

### Build Process

1. **Docker Build**:
```bash
docker build -t luceron-backend:latest .
```

2. **Dependency Installation**:
- Uses pip with `--no-cache-dir` flag
- Compiles with gcc for asyncpg

3. **Security Hardening**:
- Runs as non-root user `backend`
- Minimal base image (`python:3.13-slim`)

### Deployment Pipeline

Expected CI/CD flow (via GitHub Actions):

```mermaid
graph LR
    PR[Pull Request] --> TC[Test & Check]
    TC --> MG[Merge to Main]
    MG --> BD[Build Docker]
    BD --> PU[Push to Registry]
    PU --> DP[Deploy to Cloud Run]
```

### Environment Promotion

1. **Development**: Local/dev branch deployments
2. **Staging**: Pre-production testing
3. **Production**: Main branch, auto-deploy

### Rollback Procedures

1. **Cloud Run Rollback**:
```bash
gcloud run services update-traffic luceron-backend \
  --to-revisions=luceron-backend-00001=100
```

2. **Database Rollback**:
- Use Supabase point-in-time recovery
- Maximum 7 days retention

## Monitoring and Observability

### Logging Standards

#### Log Levels
- **INFO**: API requests, successful operations
- **WARNING**: Non-critical issues, retries
- **ERROR**: Failures requiring investigation
- **DEBUG**: Detailed operation traces

#### Log Format
```python
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logger.info(f"Operation completed: {details}")
```

### Metrics Collected

Currently tracked:
- Request count per endpoint
- Processing time for bulk operations
- Token usage per case
- Error counts by component

### Health Checks

- **Endpoint**: `GET /`
- **Checks**: Database connectivity on startup
- **Response Time**: < 100ms expected

### Alert Conditions

Automated alerts sent when:
- Database connection fails
- Email sending fails
- Bulk operation failures > 10%
- Any CRITICAL severity errors

Alert configuration:
- 15-minute deduplication window
- Email to `ADMIN_ALERT_EMAILS` list

## Security Considerations

### Authentication/Authorization Patterns

1. **API Key Authentication**:
   - Header-based: `X-API-Key`
   - Single shared key (consider per-agent keys)
   - Implemented via FastAPI dependency injection

2. **Webhook Security**:
   - Svix signature verification for Resend
   - Timestamp validation to prevent replay

### Data Encryption

1. **In Transit**:
   - HTTPS required for all API calls
   - TLS for database connections

2. **At Rest**:
   - Handled by Supabase (AES-256)
   - S3 encryption for documents

### Secret Management

1. **Environment Variables**:
   - Never commit secrets
   - Use Cloud Run secret manager in production

2. **API Keys**:
   - Rotate regularly
   - Monitor for exposed keys in logs

### GDPR/Compliance Considerations

1. **Data Retention**:
   - Implement case archival strategy
   - Document deletion capabilities exist

2. **Audit Trail**:
   - All communications logged
   - State changes tracked with timestamps

3. **PII Handling**:
   - Client emails/phones in database
   - Consider encryption for sensitive fields

## Performance Considerations

### Scaling Characteristics

1. **Horizontal Scaling**:
   - Stateless design enables multiple instances
   - Database connection pooling supports concurrency

2. **Vertical Scaling**:
   - Async architecture maximizes CPU utilization
   - Memory usage primarily from connection pools

### Resource Requirements

#### Minimum (Development)
- CPU: 0.5 vCPU
- Memory: 512 MB
- Database connections: 2-5

#### Recommended (Production)
- CPU: 2 vCPU
- Memory: 2 GB
- Database connections: 10-20

### Optimization Strategies

1. **Database**:
   - Connection pooling with `asyncpg`
   - Prepared statements disabled for pgbouncer
   - Batch operations for bulk inserts

2. **API**:
   - Async/await throughout
   - Streaming responses for large datasets
   - Pagination on list endpoints

3. **Caching** (Not yet implemented):
   - Consider Redis for frequently accessed data
   - Cache case details for 5 minutes
   - Cache document metadata

### Known Bottlenecks

1. **Fuzzy Search**: Requires `pg_trgm` extension
2. **Bulk Analysis**: Limited by database write throughput
3. **Email Sending**: Rate limited by Resend API

## Troubleshooting Guide

### Common Issues and Solutions

#### Database Connection Errors
**Symptom**: "Database connection failed"
**Solution**:
1. Verify `DATABASE_URL` format
2. Check network connectivity
3. Verify database credentials
4. Check connection pool exhaustion

#### Email Sending Failures
**Symptom**: HTTPException with "Email sending failed"
**Solution**:
1. Verify `RESEND_API_KEY`
2. Check Resend API status
3. Validate email addresses
4. Review Resend dashboard for bounces

#### Webhook Signature Verification Failures
**Symptom**: "Invalid webhook signature"
**Solution**:
1. Verify `RESEND_WEBHOOK_SECRET`
2. Check webhook URL configuration in Resend
3. Ensure raw body is used for verification


### Debug Procedures

1. **Enable Debug Logging**:
```python
logging.basicConfig(level=logging.DEBUG)
```

2. **Database Query Logging**:
```python
# In connection.py
db_pool = await asyncpg.create_pool(
    DATABASE_URL,
    server_settings={'log_statement': 'all'}
)
```

3. **Request/Response Logging**:
Use FastAPI middleware for full request logging

### Log Locations

- **Local Development**: Console output (stdout)
- **Docker**: `docker logs <container-id>`
- **Cloud Run**: Google Cloud Logging

### Support Contacts

- **Technical Issues**: DevOps team
- **Database Issues**: Database administrator
- **API Integration**: Backend team lead
- **Security Concerns**: Security team

## Development Guidelines

### Code Style and Conventions

1. **Python Style**:
   - Follow PEP 8
   - Use type hints for all functions
   - Maximum line length: 100 characters

2. **Naming Conventions**:
   - Snake_case for variables/functions
   - PascalCase for classes
   - UPPER_CASE for constants

3. **Async Best Practices**:
   - Always use `async with` for database connections
   - Avoid blocking I/O in async functions
   - Use `asyncio.gather()` for parallel operations

### Git Workflow

1. **Branch Naming**:
   - Feature: `feature/description`
   - Bugfix: `fix/description`
   - Hotfix: `hotfix/description`

2. **Commit Messages**:
   - Use conventional commits
   - Format: `type(scope): description`
   - Examples: `feat(cases): add fuzzy search`, `fix(emails): handle unicode`

### PR Requirements

1. **Code Review Checklist**:
   - [ ] Tests pass (when implemented)
   - [ ] No hardcoded secrets
   - [ ] API documentation updated
   - [ ] Error handling implemented
   - [ ] Logging added for operations

2. **Description Template**:
```markdown
## Changes
- What changed

## Testing
- How to test

## Rollback
- Rollback procedure if needed
```

### Documentation Standards

1. **Docstrings**: Use Google style
```python
def function(param: str) -> dict:
    """Brief description.
    
    Args:
        param: Description of param
        
    Returns:
        Description of return value
    """
```

2. **API Documentation**: Update when adding/modifying endpoints
3. **README Updates**: Required for architectural changes

## Future Enhancements

### Technical Debt Items

1. **Testing Infrastructure**:
   - Add comprehensive test suite
   - Implement integration tests
   - Add performance benchmarks

2. **Monitoring**:
   - Add APM integration (DataDog/New Relic)
   - Implement custom metrics
   - Add distributed tracing

3. **Security**:
   - Implement rate limiting
   - Add per-agent API keys
   - Enable request signing

4. **Database**:
   - Add database migrations tool (Alembic)
   - Implement soft deletes
   - Add audit table for all changes

### Planned Improvements

1. **Performance**:
   - Implement Redis caching layer
   - Add database query optimization
   - Enable HTTP/2 support

2. **Features**:
   - WebSocket support for real-time updates
   - Batch case operations
   - Advanced analytics endpoints
   - GraphQL API option

3. **Operations**:
   - Blue-green deployments
   - Automated database backups
   - Canary releases

### Known Limitations

1. **Scalability**:
   - Single database bottleneck
   - No horizontal database sharding
   - Limited to 10 concurrent DB connections

2. **Features**:
   - No real-time notifications (polling required)
   - No file upload capability (handled by AWS)
   - Limited to email channel (SMS not implemented)

3. **Integration**:
   - Tightly coupled to Resend for email
   - Requires Supabase PostgreSQL
   - No multi-region support

## Architecture Decision Records (ADRs)

### ADR-001: Async Python with FastAPI
**Decision**: Use FastAPI with async/await
**Rationale**: High concurrency needs, modern Python practices, automatic OpenAPI docs
**Consequences**: Requires Python 3.7+, careful async/await usage

### ADR-002: Direct PostgreSQL via asyncpg
**Decision**: Use asyncpg instead of ORM
**Rationale**: Maximum performance, full SQL control, native async support
**Consequences**: More verbose queries, manual SQL maintenance

### ADR-003: Pydantic for Validation
**Decision**: Use Pydantic models for all API contracts
**Rationale**: Runtime validation, automatic documentation, IDE support
**Consequences**: Additional model definitions, serialization overhead

### ADR-004: Stateless API Design
**Decision**: No session state, authentication via headers
**Rationale**: Horizontal scalability, Cloud Run compatibility
**Consequences**: No WebSocket support initially, polling for updates

### ADR-005: Unified Service Layer Architecture
**Decision**: Implement unified service layer for all database operations
**Rationale**: Consistent data access patterns, shared business logic between REST and Agent Gateway
**Consequences**: Additional abstraction layer, but improved maintainability and consistency
**Date**: December 2024

### ADR-006: Agent Gateway Integration
**Decision**: Natural language interface shares service layer with REST APIs
**Rationale**: Avoid code duplication, ensure consistent business logic, unified validation
**Consequences**: Agent Gateway operations go through service layer rather than direct SQL
**Date**: December 2024

## Contact and Support

For questions or issues related to this component:

1. **GitHub Issues**: Primary issue tracking
2. **Slack Channel**: #luceron-backend
3. **Documentation**: This README and inline code comments
4. **Runbook**: See internal wiki for operational procedures

---

## Recent Updates

### December 2024 - Unified Service Layer Migration
- ✅ **Completed MVP Migration**: Successfully migrated from direct database access to unified service layer
- ✅ **Agent Gateway Integration**: Natural language interface now uses same service foundation as REST APIs
- ✅ **Backward Compatibility**: All existing API endpoints continue working without changes
- ✅ **Architecture Unification**: Both interfaces now share consistent business logic and validation

This migration provides a solid foundation for future development while maintaining production stability.

---

*Last Updated: December 21, 2024*
*Version: 2.0.0 (Post-Service Layer Migration)*
*Maintained by: Luceron AI Backend Team*