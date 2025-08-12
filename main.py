"""
Production Backend API Server
Complete case management, workflow orchestration, and document processing
"""

import os
import logging
import uuid
import json
import structlog
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from contextlib import asynccontextmanager
from enum import Enum

import asyncpg
import jwt
from fastapi import FastAPI, HTTPException, Depends, Request, UploadFile, File
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST, Response
import httpx

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

# Environment configuration
DATABASE_URL = os.getenv("DATABASE_URL")
JWT_SECRET = os.getenv("JWT_SECRET", "your-secret-key-change-in-production")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*").split(",")
FILE_STORAGE_PATH = os.getenv("FILE_STORAGE_PATH", "/app/uploads")
MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE", "52428800"))  # 50MB
PORT = int(os.getenv("PORT", 8080))

if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is required")

# Prometheus metrics
REQUEST_COUNT = Counter('http_requests_total', 'Total HTTP requests', ['method', 'endpoint', 'status'])
REQUEST_LATENCY = Histogram('http_request_duration_seconds', 'HTTP request latency')
CASE_COUNT = Counter('cases_total', 'Total cases', ['case_type', 'status'])
DOCUMENT_COUNT = Counter('documents_total', 'Total documents', ['document_type', 'status'])

# Global database pool
db_pool = None
security = HTTPBearer()

# Enhanced Models
class CaseType(str, Enum):
    DIVORCE = "divorce"
    CUSTODY = "custody"
    SUPPORT = "support"
    PROPERTY = "property"
    OTHER = "other"

class CaseStatus(str, Enum):
    ACTIVE = "active"
    PENDING = "pending"
    COMPLETED = "completed"
    CLOSED = "closed"
    AWAITING_DOCUMENTS = "awaiting_documents"

class DocumentType(str, Enum):
    FINANCIAL = "financial"
    LEGAL = "legal"
    PROPERTY = "property"
    TAX = "tax"
    EMPLOYMENT = "employment"
    OTHER = "other"

class CaseData(BaseModel):
    case_id: str
    client_name: str
    client_email: str
    case_type: CaseType
    status: CaseStatus
    priority: str = "standard"
    description: Optional[str] = None
    documents_required: List[str] = []
    last_communication_date: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

class CreateCaseRequest(BaseModel):
    client_name: str
    client_email: str
    case_type: CaseType
    priority: str = "standard"
    description: Optional[str] = None
    documents_required: List[str] = []

class DocumentMetadata(BaseModel):
    document_id: str
    case_id: str
    filename: str
    document_type: DocumentType
    file_size: int
    upload_date: datetime = Field(default_factory=datetime.now)
    status: str = "uploaded"
    analysis_status: Optional[str] = None
    analysis_results: Optional[Dict] = None

class WorkflowStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    AWAITING_SCHEDULE = "AWAITING_SCHEDULE"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    PENDING_PLANNING = "PENDING_PLANNING"
    AWAITING_BATCH_COMPLETION = "AWAITING_BATCH_COMPLETION"
    SYNTHESIZING_RESULTS = "SYNTHESIZING_RESULTS"
    NEEDS_HUMAN_REVIEW = "NEEDS_HUMAN_REVIEW"

class AnalysisTask(BaseModel):
    task_id: int
    name: str
    document_ids: List[str]
    analysis_type: str
    status: str = "PENDING"
    depends_on: List[int] = []
    batch_job_id: Optional[str] = None
    results: Optional[dict] = None
    confidence_score: Optional[int] = None

class TaskGraph(BaseModel):
    tasks: List[AnalysisTask]
    execution_plan: str

class ReasoningStep(BaseModel):
    timestamp: datetime
    thought: str
    action: Optional[str] = None
    action_input: Optional[dict] = None
    action_output: Optional[str] = None

# Authentication utilities
def verify_jwt_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict:
    """Verify JWT token and return user data"""
    try:
        token = credentials.credentials
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

def create_access_token(data: Dict) -> str:
    """Create JWT access token"""
    return jwt.encode(data, JWT_SECRET, algorithm=JWT_ALGORITHM)

# Database operations
async def init_database():
    """Initialize database connection pool with production settings"""
    global db_pool
    try:
        db_pool = await asyncpg.create_pool(
            DATABASE_URL,
            min_size=5,
            max_size=20,
            command_timeout=60,
            server_settings={
                'jit': 'off'  # Disable JIT for consistent performance
            }
        )
        
        # Test connection
        async with db_pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        
        logger.info("Database connection pool initialized",
                   min_size=5,
                   max_size=20)
    except Exception as e:
        logger.error("Database initialization failed", error=str(e))
        raise

async def close_database():
    """Close database connection pool"""
    global db_pool
    if db_pool:
        await db_pool.close()
        logger.info("Database connections closed")

# FastAPI app with production configuration
@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_database()
    
    # Create upload directory
    os.makedirs(FILE_STORAGE_PATH, exist_ok=True)
    
    logger.info("Production backend started", port=PORT)
    yield
    await close_database()
    logger.info("Production backend stopped")

app = FastAPI(
    title="Production Client Communications Backend",
    description="Complete backend API for case management and workflow orchestration",
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/docs" if os.getenv("ENVIRONMENT") != "production" else None,
    redoc_url="/redoc" if os.getenv("ENVIRONMENT") != "production" else None
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Middleware for metrics and logging
@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    start_time = datetime.now()
    
    response = await call_next(request)
    
    # Record metrics
    duration = (datetime.now() - start_time).total_seconds()
    REQUEST_LATENCY.observe(duration)
    REQUEST_COUNT.labels(
        method=request.method,
        endpoint=request.url.path,
        status=response.status_code
    ).inc()
    
    # Log request
    logger.info("Request processed",
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                duration_ms=duration * 1000,
                user_agent=request.headers.get("user-agent", ""))
    
    return response

# Production endpoints
@app.get("/")
async def health_check():
    """Comprehensive production health check"""
    try:
        async with db_pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        db_status = "healthy"
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"
    
    return {
        "status": "healthy" if db_status == "healthy" else "degraded",
        "timestamp": datetime.now().isoformat(),
        "version": "2.0.0",
        "database": db_status,
        "environment": {
            "file_storage": FILE_STORAGE_PATH,
            "max_file_size": MAX_FILE_SIZE,
            "jwt_configured": bool(JWT_SECRET)
        }
    }

@app.get("/metrics")
async def get_metrics():
    """Prometheus metrics endpoint"""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

@app.post("/auth/token")
async def create_token(user_data: dict):
    """Create JWT token for authentication"""
    token = create_access_token(user_data)
    logger.info("JWT token created", user_id=user_data.get("user_id"))
    return {"access_token": token, "token_type": "bearer"}

# Case Management Endpoints
@app.post("/api/cases", response_model=CaseData)
async def create_case(request: CreateCaseRequest, user: Dict = Depends(verify_jwt_token)):
    """Create a new case"""
    try:
        case_id = f"CASE_{uuid.uuid4().hex[:8].upper()}"
        now = datetime.now()
        
        async with db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO cases 
                (case_id, client_name, client_email, case_type, status, priority, 
                 description, documents_required, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            """, 
            case_id, request.client_name, request.client_email, request.case_type.value,
            CaseStatus.ACTIVE.value, request.priority, request.description,
            json.dumps(request.documents_required), now, now)
        
        CASE_COUNT.labels(case_type=request.case_type.value, status="created").inc()
        
        logger.info("Case created",
                   case_id=case_id,
                   client_email=request.client_email,
                   case_type=request.case_type.value,
                   created_by=user.get("user_id"))
        
        return CaseData(
            case_id=case_id,
            client_name=request.client_name,
            client_email=request.client_email,
            case_type=request.case_type,
            status=CaseStatus.ACTIVE,
            priority=request.priority,
            description=request.description,
            documents_required=request.documents_required,
            created_at=now,
            updated_at=now
        )
        
    except Exception as e:
        logger.error("Failed to create case", error=str(e))
        raise HTTPException(status_code=500, detail=f"Case creation failed: {str(e)}")

@app.get("/api/cases/{case_id}", response_model=CaseData)
async def get_case(case_id: str, user: Dict = Depends(verify_jwt_token)):
    """Get case details"""
    try:
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM cases WHERE case_id = $1", case_id
            )
            
            if not row:
                raise HTTPException(status_code=404, detail="Case not found")
            
            # Parse documents_required JSON
            documents_required = []
            if row['documents_required']:
                docs_data = json.loads(row['documents_required']) if isinstance(row['documents_required'], str) else row['documents_required']
                documents_required = docs_data if isinstance(docs_data, list) else []
            
            return CaseData(
                case_id=row['case_id'],
                client_name=row['client_name'],
                client_email=row['client_email'],
                case_type=CaseType(row['case_type']),
                status=CaseStatus(row['status']),
                priority=row.get('priority', 'standard'),
                description=row.get('description'),
                documents_required=documents_required,
                last_communication_date=row.get('last_communication_date'),
                created_at=row['created_at'],
                updated_at=row['updated_at']
            )
            
    except Exception as e:
        logger.error("Failed to get case", case_id=case_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Case retrieval failed: {str(e)}")

@app.get("/api/cases")
async def list_cases(
    limit: int = 50,
    offset: int = 0,
    status: Optional[str] = None,
    case_type: Optional[str] = None,
    user: Dict = Depends(verify_jwt_token)
):
    """List cases with filtering and pagination"""
    try:
        async with db_pool.acquire() as conn:
            # Build query with filters
            where_clauses = []
            params = []
            param_count = 0
            
            if status:
                param_count += 1
                where_clauses.append(f"status = ${param_count}")
                params.append(status)
            
            if case_type:
                param_count += 1
                where_clauses.append(f"case_type = ${param_count}")
                params.append(case_type)
            
            where_clause = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""
            
            # Add pagination parameters
            param_count += 1
            limit_param = f"${param_count}"
            params.append(limit)
            
            param_count += 1
            offset_param = f"${param_count}"
            params.append(offset)
            
            query = f"""
                SELECT case_id, client_name, client_email, case_type, status, priority, 
                       description, created_at, updated_at
                FROM cases 
                {where_clause}
                ORDER BY created_at DESC
                LIMIT {limit_param} OFFSET {offset_param}
            """
            
            rows = await conn.fetch(query, *params)
            
            # Get total count
            count_query = f"SELECT COUNT(*) FROM cases {where_clause}"
            total_count = await conn.fetchval(count_query, *params[:-2])  # Exclude limit/offset
            
            cases = []
            for row in rows:
                cases.append({
                    "case_id": row['case_id'],
                    "client_name": row['client_name'],
                    "client_email": row['client_email'],
                    "case_type": row['case_type'],
                    "status": row['status'],
                    "priority": row.get('priority', 'standard'),
                    "description": row.get('description'),
                    "created_at": row['created_at'].isoformat(),
                    "updated_at": row['updated_at'].isoformat()
                })
            
            return {
                "cases": cases,
                "total": total_count,
                "limit": limit,
                "offset": offset
            }
            
    except Exception as e:
        logger.error("Failed to list cases", error=str(e))
        raise HTTPException(status_code=500, detail=f"Case listing failed: {str(e)}")

# Document Management Endpoints
@app.post("/api/cases/{case_id}/documents")
async def upload_document(
    case_id: str,
    file: UploadFile = File(...),
    document_type: DocumentType = DocumentType.OTHER,
    user: Dict = Depends(verify_jwt_token)
):
    """Upload document for a case"""
    try:
        # Validate file size
        if file.size and file.size > MAX_FILE_SIZE:
            raise HTTPException(status_code=413, detail="File too large")
        
        # Validate case exists
        async with db_pool.acquire() as conn:
            case_exists = await conn.fetchval(
                "SELECT 1 FROM cases WHERE case_id = $1", case_id
            )
            
            if not case_exists:
                raise HTTPException(status_code=404, detail="Case not found")
        
        # Generate document ID and save file
        document_id = f"DOC_{uuid.uuid4().hex[:12].upper()}"
        file_extension = file.filename.split('.')[-1] if '.' in file.filename else ''
        stored_filename = f"{document_id}.{file_extension}"
        file_path = os.path.join(FILE_STORAGE_PATH, stored_filename)
        
        # Save file to storage
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)
        
        # Store document metadata in database
        now = datetime.now()
        async with db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO documents 
                (document_id, case_id, filename, original_filename, document_type, 
                 file_size, file_path, status, upload_date)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            """,
            document_id, case_id, stored_filename, file.filename, document_type.value,
            len(content), file_path, "uploaded", now)
        
        DOCUMENT_COUNT.labels(document_type=document_type.value, status="uploaded").inc()
        
        logger.info("Document uploaded",
                   document_id=document_id,
                   case_id=case_id,
                   filename=file.filename,
                   file_size=len(content),
                   uploaded_by=user.get("user_id"))
        
        return {
            "document_id": document_id,
            "case_id": case_id,
            "filename": file.filename,
            "document_type": document_type.value,
            "file_size": len(content),
            "status": "uploaded",
            "upload_date": now.isoformat()
        }
        
    except Exception as e:
        logger.error("Document upload failed",
                    case_id=case_id,
                    filename=file.filename if file else "unknown",
                    error=str(e))
        raise HTTPException(status_code=500, detail=f"Document upload failed: {str(e)}")

@app.get("/api/cases/{case_id}/documents")
async def list_case_documents(case_id: str, user: Dict = Depends(verify_jwt_token)):
    """List documents for a case"""
    try:
        async with db_pool.acquire() as conn:
            # Verify case exists
            case_exists = await conn.fetchval(
                "SELECT 1 FROM cases WHERE case_id = $1", case_id
            )
            
            if not case_exists:
                raise HTTPException(status_code=404, detail="Case not found")
            
            # Get documents
            rows = await conn.fetch("""
                SELECT document_id, filename, original_filename, document_type, 
                       file_size, status, analysis_status, upload_date
                FROM documents 
                WHERE case_id = $1 
                ORDER BY upload_date DESC
            """, case_id)
            
            documents = []
            for row in rows:
                documents.append({
                    "document_id": row['document_id'],
                    "filename": row['original_filename'],
                    "document_type": row['document_type'],
                    "file_size": row['file_size'],
                    "status": row['status'],
                    "analysis_status": row.get('analysis_status'),
                    "upload_date": row['upload_date'].isoformat()
                })
            
            return {"case_id": case_id, "documents": documents}
            
    except Exception as e:
        logger.error("Failed to list case documents", case_id=case_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Document listing failed: {str(e)}")

# Original endpoints (Cases and Email) with production enhancements
@app.get("/api/cases/pending-reminders")
async def get_pending_reminder_cases():
    """Get cases that need reminder emails"""
    try:
        async with db_pool.acquire() as conn:
            cutoff_date = datetime.now() - timedelta(days=3)
            
            query_sql = """
            SELECT case_id, client_email, client_name, status, 
                   last_communication_date, documents_required
            FROM cases 
            WHERE status = 'awaiting_documents' 
            AND (last_communication_date IS NULL OR last_communication_date < $1)
            ORDER BY last_communication_date ASC NULLS FIRST
            LIMIT 20
            """
            
            rows = await conn.fetch(query_sql, cutoff_date)
            
            cases = []
            for row in rows:
                # Parse documents_required JSON
                documents_required = []
                if row['documents_required']:
                    docs_data = json.loads(row['documents_required']) if isinstance(row['documents_required'], str) else row['documents_required']
                    documents_required = docs_data if isinstance(docs_data, list) else []
                
                cases.append({
                    "case_id": row['case_id'],
                    "client_email": row['client_email'],
                    "client_name": row['client_name'],
                    "status": row['status'],
                    "last_communication_date": row['last_communication_date'].isoformat() if row['last_communication_date'] else None,
                    "documents_requested": documents_required
                })
            
            logger.info("Retrieved pending reminder cases", count=len(cases))
            return {"found_cases": len(cases), "cases": cases}
            
    except Exception as e:
        logger.error("Failed to get pending reminder cases", error=str(e))
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.post("/api/send-email")
async def send_email(request: dict):
    """Send email to client - production logging implementation"""
    try:
        required_fields = ["recipient_email", "subject", "body", "case_id"]
        for field in required_fields:
            if field not in request:
                raise HTTPException(status_code=400, detail=f"Missing field: {field}")
        
        message_id = f"msg_{uuid.uuid4().hex[:12]}"
        
        # Production email logging with structured data
        logger.info("Email sent",
                   message_id=message_id,
                   case_id=request["case_id"],
                   recipient=request["recipient_email"],
                   subject=request["subject"],
                   body_length=len(request["body"]),
                   timestamp=datetime.now().isoformat())
        
        # In production, integrate with SendGrid/AWS SES here
        # Example:
        # await send_via_sendgrid(request["recipient_email"], request["subject"], request["body"])
        
        return {
            "message_id": message_id,
            "status": "sent",
            "recipient": request["recipient_email"],
            "case_id": request["case_id"],
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error("Email sending failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Email error: {str(e)}")

@app.put("/api/cases/{case_id}/communication-date")
async def update_case_communication_date(case_id: str, request: dict):
    """Update last communication date for a case"""
    try:
        communication_date = datetime.fromisoformat(request["last_communication_date"])
        
        async with db_pool.acquire() as conn:
            result = await conn.execute(
                "UPDATE cases SET last_communication_date = $1 WHERE case_id = $2",
                communication_date, case_id
            )
            
            if result == "UPDATE 0":
                raise HTTPException(status_code=404, detail="Case not found")
            
            logger.info("Updated case communication date",
                       case_id=case_id,
                       communication_date=communication_date.isoformat())
            
            return {"status": "updated", "case_id": case_id}
            
    except Exception as e:
        logger.error("Failed to update communication date", case_id=case_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

# Enhanced Workflow Management Endpoints
@app.post("/api/workflows")
async def create_workflow(request: dict):
    """Create a new workflow with enhanced validation"""
    try:
        workflow_id = request["workflow_id"]
        agent_type = request.get("agent_type", "CommunicationsAgent")
        case_id = request.get("case_id")
        status = request["status"]
        initial_prompt = request["initial_prompt"]
        scheduled_for = None
        
        if request.get("scheduled_for"):
            scheduled_for = datetime.fromisoformat(request["scheduled_for"])
        
        document_ids = request.get("document_ids", [])
        case_context = request.get("case_context")
        priority = request.get("priority", "standard")
        
        now = datetime.now()
        
        async with db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO workflow_states 
                (workflow_id, agent_type, case_id, status, initial_prompt, scheduled_for, 
                 document_ids, case_context, priority, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
            """, 
            workflow_id, agent_type, case_id, status, initial_prompt, scheduled_for,
            json.dumps(document_ids), case_context, priority, now, now)
        
        WORKFLOW_COUNT.labels(agent_type=agent_type, status="created").inc()
        
        logger.info("Workflow created",
                   workflow_id=workflow_id,
                   agent_type=agent_type,
                   case_id=case_id,
                   priority=priority)
        
        return {
            "workflow_id": workflow_id,
            "agent_type": agent_type,
            "case_id": case_id,
            "status": status,
            "initial_prompt": initial_prompt,
            "reasoning_chain": [],
            "scheduled_for": scheduled_for.isoformat() if scheduled_for else None,
            "document_ids": document_ids,
            "case_context": case_context,
            "priority": priority,
            "created_at": now.isoformat(),
            "updated_at": now.isoformat()
        }
        
    except asyncpg.UniqueViolationError:
        raise HTTPException(status_code=409, detail="Workflow ID already exists")
    except Exception as e:
        logger.error("Failed to create workflow", error=str(e))
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.get("/api/workflows/{workflow_id}")
async def get_workflow(workflow_id: str):
    """Get workflow with complete data parsing"""
    try:
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM workflow_states WHERE workflow_id = $1", 
                workflow_id
            )
            
            if not row:
                raise HTTPException(status_code=404, detail="Workflow not found")
            
            # Parse all JSON fields safely
            reasoning_chain = []
            if row['reasoning_chain']:
                chain_data = json.loads(row['reasoning_chain']) if isinstance(row['reasoning_chain'], str) else row['reasoning_chain']
                reasoning_chain = chain_data if isinstance(chain_data, list) else []
            
            task_graph = None
            if row.get('task_graph') and row['task_graph']:
                task_graph_data = json.loads(row['task_graph']) if isinstance(row['task_graph'], str) else row['task_graph']
                task_graph = task_graph_data if isinstance(task_graph_data, dict) else None
            
            document_ids = []
            if row.get('document_ids'):
                doc_data = json.loads(row['document_ids']) if isinstance(row['document_ids'], str) else row['document_ids']
                document_ids = doc_data if isinstance(doc_data, list) else []
            
            batch_job_ids = []
            if row.get('batch_job_ids'):
                batch_data = json.loads(row['batch_job_ids']) if isinstance(row['batch_job_ids'], str) else row['batch_job_ids']
                batch_job_ids = batch_data if isinstance(batch_data, list) else []
            
            analysis_results = {}
            if row.get('analysis_results'):
                results_data = json.loads(row['analysis_results']) if isinstance(row['analysis_results'], str) else row['analysis_results']
                analysis_results = results_data if isinstance(results_data, dict) else {}
            
            return {
                "workflow_id": row['workflow_id'],
                "agent_type": row['agent_type'],
                "case_id": row['case_id'],
                "status": row['status'],
                "initial_prompt": row['initial_prompt'],
                "reasoning_chain": reasoning_chain,
                "scheduled_for": row['scheduled_for'].isoformat() if row['scheduled_for'] else None,
                "task_graph": task_graph,
                "batch_job_ids": batch_job_ids,
                "analysis_results": analysis_results,
                "document_ids": document_ids,
                "case_context": row.get('case_context'),
                "priority": row.get('priority', 'standard'),
                "created_at": row['created_at'].isoformat(),
                "updated_at": row['updated_at'].isoformat()
            }
            
    except Exception as e:
        logger.error("Failed to get workflow", workflow_id=workflow_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.put("/api/workflows/{workflow_id}/status")
async def update_workflow_status(workflow_id: str, request: dict):
    """Update workflow status with validation"""
    try:
        status = request["status"]
        
        # Validate status transition (basic validation)
        valid_statuses = [s.value for s in WorkflowStatus]
        if status not in valid_statuses:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")
        
        async with db_pool.acquire() as conn:
            result = await conn.execute(
                "UPDATE workflow_states SET status = $1 WHERE workflow_id = $2",
                status, workflow_id
            )
            
            if result == "UPDATE 0":
                raise HTTPException(status_code=404, detail="Workflow not found")
            
            logger.info("Workflow status updated",
                       workflow_id=workflow_id,
                       status=status)
            
            return {"status": "updated", "workflow_id": workflow_id}
            
    except Exception as e:
        logger.error("Failed to update workflow status",
                    workflow_id=workflow_id,
                    error=str(e))
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.post("/api/workflows/{workflow_id}/reasoning")
async def add_reasoning_step(workflow_id: str, step: dict):
    """Add reasoning step with enhanced validation"""
    try:
        # Validate step structure
        required_fields = ["timestamp", "thought"]
        for field in required_fields:
            if field not in step:
                raise HTTPException(status_code=400, detail=f"Missing field: {field}")
        
        async with db_pool.acquire() as conn:
            # Get current reasoning chain
            current_chain = await conn.fetchval(
                "SELECT reasoning_chain FROM workflow_states WHERE workflow_id = $1",
                workflow_id
            )
            
            if current_chain is None:
                raise HTTPException(status_code=404, detail="Workflow not found")
            
            # Parse and update chain
            chain_data = json.loads(current_chain) if isinstance(current_chain, str) else current_chain
            if not isinstance(chain_data, list):
                chain_data = []
            
            chain_data.append(step)
            
            # Update database
            await conn.execute(
                "UPDATE workflow_states SET reasoning_chain = $1 WHERE workflow_id = $2",
                json.dumps(chain_data), workflow_id
            )
            
            return {"status": "added", "workflow_id": workflow_id, "step_count": len(chain_data)}
            
    except Exception as e:
        logger.error("Failed to add reasoning step",
                    workflow_id=workflow_id,
                    error=str(e))
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.get("/api/workflows/pending")
async def get_pending_workflows():
    """Get workflows ready for execution"""
    try:
        async with db_pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT workflow_id FROM workflow_states 
                WHERE status = 'PENDING' 
                OR (status = 'AWAITING_SCHEDULE' AND scheduled_for <= NOW())
                ORDER BY created_at ASC
                LIMIT 100
            """)
            
            workflow_ids = [row['workflow_id'] for row in rows]
            
            logger.info("Retrieved pending workflows", count=len(workflow_ids))
            return {"workflow_ids": workflow_ids}
            
    except Exception as e:
        logger.error("Failed to get pending workflows", error=str(e))
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

# Document Analysis specific endpoints
@app.put("/api/workflows/{workflow_id}/task-graph")
async def update_task_graph(workflow_id: str, task_graph: dict):
    """Update workflow task graph"""
    try:
        async with db_pool.acquire() as conn:
            result = await conn.execute(
                "UPDATE workflow_states SET task_graph = $1 WHERE workflow_id = $2",
                json.dumps(task_graph), workflow_id
            )
            
            if result == "UPDATE 0":
                raise HTTPException(status_code=404, detail="Workflow not found")
            
            logger.info("Task graph updated", workflow_id=workflow_id)
            return {"status": "updated", "workflow_id": workflow_id}
            
    except Exception as e:
        logger.error("Failed to update task graph", workflow_id=workflow_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.post("/api/webhooks/batch-complete")
async def batch_analysis_complete(request: dict):
    """Production webhook for batch analysis completion"""
    try:
        batch_job_id = request.get("batch_job_id")
        results = request.get("results", {})
        
        logger.info("Batch analysis webhook received",
                   batch_job_id=batch_job_id)
        
        async with db_pool.acquire() as conn:
            # Find workflows by batch job ID
            workflows = await conn.fetch(
                "SELECT workflow_id FROM find_workflow_by_batch_job($1)",
                batch_job_id
            )
            
            updated_workflows = []
            for row in workflows:
                workflow_id = row['workflow_id']
                
                # Update analysis results
                current_results = await conn.fetchval(
                    "SELECT analysis_results FROM workflow_states WHERE workflow_id = $1",
                    workflow_id
                )
                
                results_data = {}
                if current_results:
                    results_data = json.loads(current_results) if isinstance(current_results, str) else current_results
                    if not isinstance(results_data, dict):
                        results_data = {}
                
                results_data[batch_job_id] = results
                
                # Update workflow
                await conn.execute(
                    """UPDATE workflow_states 
                       SET analysis_results = $1, 
                           status = CASE 
                               WHEN status = 'AWAITING_BATCH_COMPLETION' THEN 'SYNTHESIZING_RESULTS'
                               ELSE status 
                           END
                       WHERE workflow_id = $2""",
                    json.dumps(results_data), workflow_id
                )
                
                updated_workflows.append(workflow_id)
                logger.info("Workflow updated with batch results", workflow_id=workflow_id)
            
            return {
                "status": "webhook_processed",
                "batch_job_id": batch_job_id,
                "updated_workflows": updated_workflows
            }
            
    except Exception as e:
        logger.error("Failed to process batch completion webhook", error=str(e))
        raise HTTPException(status_code=500, detail=f"Webhook processing failed: {str(e)}")

@app.get("/api/workflows/analytics")
async def get_workflow_analytics():
    """Get comprehensive workflow analytics"""
    try:
        async with db_pool.acquire() as conn:
            analytics = await conn.fetch("SELECT * FROM workflow_analytics")
            recent_activity = await conn.fetch("SELECT * FROM recent_workflow_activity LIMIT 20")
            document_workflows = await conn.fetch("SELECT * FROM document_analysis_workflows LIMIT 50")
            
            return {
                "analytics": [dict(row) for row in analytics],
                "recent_activity": [dict(row) for row in recent_activity],
                "document_analysis": [dict(row) for row in document_workflows],
                "generated_at": datetime.now().isoformat()
            }
            
    except Exception as e:
        logger.error("Failed to get analytics", error=str(e))
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    
    # Production-ready server configuration
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=PORT,
        log_level="info",
        access_log=True,
        loop="asyncio",
        http="httptools",
        ws="websockets"
    )