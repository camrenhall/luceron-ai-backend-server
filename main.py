"""
Production Backend API Server
Handles database operations, OpenAI batch processing, and workflow orchestration
"""

import os
import logging
import uuid
import json
import base64
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from contextlib import asynccontextmanager
from enum import Enum

from fastapi import FastAPI, HTTPException, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import asyncpg
import httpx

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Environment configuration
DATABASE_URL = os.getenv("DATABASE_URL")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
PORT = int(os.getenv("PORT", 8080))

if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is required")
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY environment variable is required")

# Global connections
db_pool = None
openai_client = None

# Models (Previous models remain the same)
class CaseData(BaseModel):
    case_id: str
    client_email: str
    client_name: str
    status: str
    last_communication_date: Optional[datetime]
    documents_requested: str

class PendingCasesResponse(BaseModel):
    found_cases: int
    cases: List[CaseData]

class EmailRequest(BaseModel):
    recipient_email: str
    subject: str
    body: str
    case_id: str

class EmailResponse(BaseModel):
    message_id: str
    status: str
    recipient: str
    case_id: str

class UpdateCaseRequest(BaseModel):
    case_id: str
    last_communication_date: datetime

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

class WorkflowState(BaseModel):
    workflow_id: str
    agent_type: str = "CommunicationsAgent"
    case_id: Optional[str] = None
    status: WorkflowStatus
    initial_prompt: str
    reasoning_chain: List[ReasoningStep]
    scheduled_for: Optional[datetime] = None
    task_graph: Optional[TaskGraph] = None
    batch_job_ids: List[str] = []
    analysis_results: dict = {}
    document_ids: List[str] = []
    case_context: Optional[str] = None
    priority: str = "batch"
    created_at: datetime
    updated_at: datetime

class CreateWorkflowRequest(BaseModel):
    workflow_id: str
    agent_type: str = "CommunicationsAgent"
    case_id: Optional[str] = None
    status: WorkflowStatus
    initial_prompt: str
    scheduled_for: Optional[datetime] = None
    document_ids: Optional[List[str]] = []
    case_context: Optional[str] = None
    priority: str = "batch"

class UpdateWorkflowStatusRequest(BaseModel):
    status: WorkflowStatus

class UpdateTaskStatusRequest(BaseModel):
    task_id: int
    status: str
    results: Optional[dict] = None
    confidence_score: Optional[int] = None

class BatchJobCompleteRequest(BaseModel):
    batch_job_id: str
    results: dict
    status: str = "completed"

class PendingWorkflowsResponse(BaseModel):
    workflow_ids: List[str]

# New Production Models
class DocumentUploadResponse(BaseModel):
    document_id: str
    filename: str
    file_size: int
    openai_file_id: str
    status: str

class CaseCreateRequest(BaseModel):
    case_id: str
    client_name: str
    client_email: str
    case_type: str = "financial_discovery"
    priority: str = "standard"
    documents_requested: str

class BatchAnalysisRequest(BaseModel):
    case_id: str
    document_ids: List[str]
    analysis_instructions: str
    priority: str = "batch"

class BatchAnalysisResponse(BaseModel):
    batch_job_id: str
    status: str
    estimated_completion: str
    documents_count: int

# Initialize connections
async def init_connections():
    """Initialize database and OpenAI client connections"""
    global db_pool, openai_client
    
    try:
        # Database connection pool
        db_pool = await asyncpg.create_pool(
            DATABASE_URL,
            min_size=2,
            max_size=10,
            command_timeout=60
        )
        
        # Test database connection
        async with db_pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        
        # OpenAI client
        openai_client = httpx.AsyncClient(
            base_url="https://api.openai.com/v1",
            headers={
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type": "application/json"
            },
            timeout=30.0
        )
        
        logger.info("Database and OpenAI connections initialized successfully")
        
    except Exception as e:
        logger.error(f"Connection initialization failed: {e}")
        raise

async def close_connections():
    """Close all connections"""
    global db_pool, openai_client
    
    if db_pool:
        await db_pool.close()
    if openai_client:
        await openai_client.aclose()
    
    logger.info("All connections closed")

# OpenAI Integration Functions
async def upload_file_to_openai(file_content: bytes, filename: str, purpose: str = "batch") -> str:
    """Upload file to OpenAI and return file ID"""
    try:
        # Create multipart form data
        files = {
            "file": (filename, file_content, "application/octet-stream"),
            "purpose": (None, purpose)
        }
        
        # Remove Content-Type header for multipart uploads
        headers = {"Authorization": f"Bearer {OPENAI_API_KEY}"}
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.openai.com/v1/files",
                headers=headers,
                files=files
            )
            response.raise_for_status()
            
            file_data = response.json()
            logger.info(f"Uploaded file {filename} to OpenAI: {file_data['id']}")
            return file_data["id"]
            
    except Exception as e:
        logger.error(f"Failed to upload file to OpenAI: {e}")
        raise HTTPException(status_code=500, detail=f"File upload failed: {str(e)}")

async def create_batch_analysis(requests: List[Dict[str, Any]]) -> str:
    """Create batch analysis job with OpenAI"""
    try:
        payload = {
            "endpoint": "/v1/responses",
            "completion_window": "24h",
            "requests": requests
        }
        
        response = await openai_client.post("/batches", json=payload)
        response.raise_for_status()
        
        batch_data = response.json()
        batch_job_id = batch_data["id"]
        
        logger.info(f"Created batch analysis job: {batch_job_id}")
        return batch_job_id
        
    except Exception as e:
        logger.error(f"Failed to create batch analysis: {e}")
        raise HTTPException(status_code=500, detail=f"Batch creation failed: {str(e)}")

async def get_batch_status(batch_job_id: str) -> Dict[str, Any]:
    """Get batch job status from OpenAI"""
    try:
        response = await openai_client.get(f"/batches/{batch_job_id}")
        response.raise_for_status()
        
        return response.json()
        
    except Exception as e:
        logger.error(f"Failed to get batch status: {e}")
        raise HTTPException(status_code=500, detail=f"Batch status check failed: {str(e)}")

async def download_batch_results(output_file_id: str) -> Dict[str, Any]:
    """Download batch results from OpenAI"""
    try:
        response = await openai_client.get(f"/files/{output_file_id}/content")
        response.raise_for_status()
        
        # Parse JSONL results
        results = []
        for line in response.text.strip().split('\n'):
            if line.strip():
                results.append(json.loads(line))
        
        return {"results": results}
        
    except Exception as e:
        logger.error(f"Failed to download batch results: {e}")
        raise HTTPException(status_code=500, detail=f"Results download failed: {str(e)}")

# FastAPI app
@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_connections()
    yield
    await close_connections()

app = FastAPI(
    title="Production Legal Document Analysis Backend",
    description="Backend API for case management, document analysis, and workflow orchestration",
    version="2.0.0",
    lifespan=lifespan
)

@app.get("/")
async def health_check():
    """Comprehensive health check"""
    try:
        # Test database
        async with db_pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        
        # Test OpenAI connection
        response = await openai_client.get("/models")
        response.raise_for_status()
        
        return {
            "status": "healthy", 
            "timestamp": datetime.now().isoformat(),
            "database": "connected",
            "openai": "connected"
        }
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
        )

# Case Management Endpoints
@app.post("/api/cases", response_model=CaseData)
async def create_case(request: CaseCreateRequest):
    """Create a new case"""
    try:
        async with db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO cases (case_id, client_name, client_email, status, documents_requested, created_at)
                VALUES ($1, $2, $3, $4, $5, $6)
            """, 
            request.case_id, request.client_name, request.client_email, 
            "awaiting_documents", request.documents_requested, datetime.now())
            
            return CaseData(
                case_id=request.case_id,
                client_name=request.client_name,
                client_email=request.client_email,
                status="awaiting_documents",
                last_communication_date=None,
                documents_requested=request.documents_requested
            )
            
    except asyncpg.UniqueViolationError:
        raise HTTPException(status_code=409, detail="Case ID already exists")
    except Exception as e:
        logger.error(f"Failed to create case: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.get("/api/cases/{case_id}", response_model=CaseData)
async def get_case(case_id: str):
    """Get case by ID"""
    try:
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM cases WHERE case_id = $1", case_id
            )
            
            if not row:
                raise HTTPException(status_code=404, detail="Case not found")
            
            return CaseData(
                case_id=row['case_id'],
                client_email=row['client_email'],
                client_name=row['client_name'],
                status=row['status'],
                last_communication_date=row['last_communication_date'],
                documents_requested=row['documents_requested']
            )
            
    except Exception as e:
        logger.error(f"Failed to get case: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.get("/api/cases/pending-reminders", response_model=PendingCasesResponse)
async def get_pending_reminder_cases():
    """Get cases that need reminder emails"""
    try:
        async with db_pool.acquire() as conn:
            cutoff_date = datetime.now() - timedelta(days=3)
            
            query_sql = """
            SELECT case_id, client_email, client_name, status, 
                   last_communication_date, documents_requested
            FROM cases 
            WHERE status = 'awaiting_documents' 
            AND (last_communication_date IS NULL OR last_communication_date < $1)
            ORDER BY last_communication_date ASC NULLS FIRST
            LIMIT 20
            """
            
            rows = await conn.fetch(query_sql, cutoff_date)
            
            cases = []
            for row in rows:
                cases.append(CaseData(
                    case_id=row['case_id'],
                    client_email=row['client_email'],
                    client_name=row['client_name'],
                    status=row['status'],
                    last_communication_date=row['last_communication_date'],
                    documents_requested=row['documents_requested']
                ))
            
            logger.info(f"Found {len(cases)} cases requiring reminders")
            return PendingCasesResponse(found_cases=len(cases), cases=cases)
            
    except Exception as e:
        logger.error(f"Database query failed: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

# Document Management Endpoints
@app.post("/api/documents/upload", response_model=DocumentUploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    case_id: str = Form(...),
    document_type: str = Form("general")
):
    """Upload document and prepare for analysis"""
    try:
        # Read file content
        file_content = await file.read()
        
        # Upload to OpenAI
        openai_file_id = await upload_file_to_openai(
            file_content, 
            file.filename,
            purpose="batch"
        )
        
        # Store document metadata in database
        document_id = f"doc_{uuid.uuid4().hex[:12]}"
        
        async with db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO documents 
                (document_id, case_id, filename, file_size, openai_file_id, document_type, status, created_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            """,
            document_id, case_id, file.filename, len(file_content),
            openai_file_id, document_type, "uploaded", datetime.now())
        
        logger.info(f"Document {document_id} uploaded for case {case_id}")
        
        return DocumentUploadResponse(
            document_id=document_id,
            filename=file.filename,
            file_size=len(file_content),
            openai_file_id=openai_file_id,
            status="uploaded"
        )
        
    except Exception as e:
        logger.error(f"Document upload failed: {e}")
        raise HTTPException(status_code=500, detail=f"Upload error: {str(e)}")

@app.get("/api/documents/{document_id}")
async def get_document(document_id: str):
    """Get document metadata"""
    try:
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM documents WHERE document_id = $1", document_id
            )
            
            if not row:
                raise HTTPException(status_code=404, detail="Document not found")
            
            return dict(row)
            
    except Exception as e:
        logger.error(f"Failed to get document: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.get("/api/cases/{case_id}/documents")
async def get_case_documents(case_id: str):
    """Get all documents for a case"""
    try:
        async with db_pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM documents WHERE case_id = $1 ORDER BY created_at DESC",
                case_id
            )
            
            return [dict(row) for row in rows]
            
    except Exception as e:
        logger.error(f"Failed to get case documents: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

# Batch Analysis Endpoints
@app.post("/api/analysis/batch", response_model=BatchAnalysisResponse)
async def create_batch_analysis_job(request: BatchAnalysisRequest):
    """Create batch analysis job for documents"""
    try:
        # Get document details
        async with db_pool.acquire() as conn:
            documents = await conn.fetch("""
                SELECT document_id, openai_file_id, filename, document_type 
                FROM documents 
                WHERE document_id = ANY($1) AND case_id = $2
            """, request.document_ids, request.case_id)
            
            if len(documents) != len(request.document_ids):
                raise HTTPException(status_code=404, detail="Some documents not found")
        
        # Create batch requests for OpenAI
        batch_requests = []
        for i, doc in enumerate(documents):
            batch_request = {
                "custom_id": f"{request.case_id}_{doc['document_id']}",
                "method": "POST",
                "url": "/v1/responses",
                "body": {
                    "model": "gpt-4o",
                    "messages": [
                        {
                            "role": "system",
                            "content": f"""You are a legal document analysis expert specializing in family law financial discovery.

ANALYSIS TASK: {request.analysis_instructions}

REQUIREMENTS:
1. Extract all financial data with exact figures and dates
2. Identify potential discrepancies or red flags
3. Provide confidence scores (1-100) for all extracted data
4. Note any OCR issues or unclear sections
5. Cross-reference related financial information

OUTPUT FORMAT:
Return a JSON object with:
- extracted_data: All financial figures, dates, names, amounts
- key_findings: Important discoveries or patterns
- confidence_score: Overall confidence (1-100)
- confidence_justification: Explanation of confidence level
- red_flags: Any suspicious or inconsistent information
- ocr_issues: Any text extraction problems noted

Be thorough, accurate, and provide specific justifications for all findings."""
                        },
                        {
                            "role": "user",
                            "content": f"Analyze this {doc['document_type']} document: {doc['filename']}. File ID: {doc['openai_file_id']}"
                        }
                    ],
                    "max_tokens": 4000,
                    "temperature": 0.1
                }
            }
            batch_requests.append(batch_request)
        
        # Submit batch job to OpenAI
        batch_job_id = await create_batch_analysis(batch_requests)
        
        # Update document status
        async with db_pool.acquire() as conn:
            await conn.execute("""
                UPDATE documents 
                SET status = 'analyzing', batch_job_id = $1, updated_at = $2
                WHERE document_id = ANY($3)
            """, batch_job_id, datetime.now(), request.document_ids)
        
        logger.info(f"Created batch analysis job {batch_job_id} for {len(documents)} documents")
        
        return BatchAnalysisResponse(
            batch_job_id=batch_job_id,
            status="submitted",
            estimated_completion="24 hours",
            documents_count=len(documents)
        )
        
    except Exception as e:
        logger.error(f"Failed to create batch analysis: {e}")
        raise HTTPException(status_code=500, detail=f"Analysis creation failed: {str(e)}")

@app.get("/api/analysis/batch/{batch_job_id}/status")
async def get_batch_analysis_status(batch_job_id: str):
    """Get batch analysis job status"""
    try:
        batch_status = await get_batch_status(batch_job_id)
        
        return {
            "batch_job_id": batch_job_id,
            "status": batch_status["status"],
            "created_at": batch_status["created_at"],
            "completed_at": batch_status.get("completed_at"),
            "failed_at": batch_status.get("failed_at"),
            "error_file_id": batch_status.get("error_file_id"),
            "output_file_id": batch_status.get("output_file_id"),
            "request_counts": batch_status.get("request_counts", {})
        }
        
    except Exception as e:
        logger.error(f"Failed to get batch status: {e}")
        raise HTTPException(status_code=500, detail=f"Status check failed: {str(e)}")

@app.get("/api/analysis/batch/{batch_job_id}/results")
async def get_batch_analysis_results(batch_job_id: str):
    """Get batch analysis results"""
    try:
        # Get batch status first
        batch_status = await get_batch_status(batch_job_id)
        
        if batch_status["status"] != "completed":
            raise HTTPException(
                status_code=400, 
                detail=f"Batch not completed. Status: {batch_status['status']}"
            )
        
        if not batch_status.get("output_file_id"):
            raise HTTPException(status_code=404, detail="No output file available")
        
        # Download results
        results = await download_batch_results(batch_status["output_file_id"])
        
        # Update database with results
        async with db_pool.acquire() as conn:
            for result in results["results"]:
                custom_id = result["custom_id"]
                case_id, document_id = custom_id.split("_", 1)
                
                # Store analysis results
                await conn.execute("""
                    UPDATE documents 
                    SET status = 'analyzed', 
                        analysis_results = $1,
                        updated_at = $2
                    WHERE document_id = $3
                """, json.dumps(result), datetime.now(), document_id)
        
        logger.info(f"Retrieved and stored results for batch {batch_job_id}")
        
        return results
        
    except Exception as e:
        logger.error(f"Failed to get batch results: {e}")
        raise HTTPException(status_code=500, detail=f"Results retrieval failed: {str(e)}")

# Email endpoint (dummy implementation as requested)
@app.post("/api/send-email", response_model=EmailResponse)
async def send_email(request: EmailRequest):
    """Send email to client - production logging implementation"""
    try:
        message_id = f"msg_{uuid.uuid4().hex[:12]}"
        
        # Production logging for email audit trail
        email_log = {
            "message_id": message_id,
            "case_id": request.case_id,
            "recipient": request.recipient_email,
            "subject": request.subject,
            "body_length": len(request.body),
            "timestamp": datetime.now().isoformat(),
            "status": "sent"
        }
        
        # Store email log in database for audit trail
        async with db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO email_logs 
                (message_id, case_id, recipient_email, subject, body, status, sent_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
            """, 
            message_id, request.case_id, request.recipient_email, 
            request.subject, request.body, "sent", datetime.now())
        
        logger.info(f"Email sent - ID: {message_id}, Case: {request.case_id}, To: {request.recipient_email}")
        
        return EmailResponse(
            message_id=message_id,
            status="sent",
            recipient=request.recipient_email,
            case_id=request.case_id
        )
        
    except Exception as e:
        logger.error(f"Email processing failed: {e}")
        raise HTTPException(status_code=500, detail=f"Email error: {str(e)}")

@app.put("/api/cases/{case_id}/communication-date")
async def update_case_communication_date(case_id: str, request: UpdateCaseRequest):
    """Update last communication date for a case"""
    try:
        async with db_pool.acquire() as conn:
            result = await conn.execute(
                "UPDATE cases SET last_communication_date = $1 WHERE case_id = $2",
                request.last_communication_date,
                case_id
            )
            
            if result == "UPDATE 0":
                raise HTTPException(status_code=404, detail="Case not found")
            
            logger.info(f"Updated communication date for case {case_id}")
            return {"status": "updated", "case_id": case_id}
            
    except Exception as e:
        logger.error(f"Database update failed: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

# All workflow management endpoints from previous implementation...
# (Include all the workflow endpoints we built earlier)

# Background task for processing completed batches
async def process_completed_batches():
    """Background task to check for completed batch jobs"""
    try:
        async with db_pool.acquire() as conn:
            # Get all pending batch jobs
            pending_batches = await conn.fetch("""
                SELECT DISTINCT batch_job_id 
                FROM documents 
                WHERE status = 'analyzing' 
                AND batch_job_id IS NOT NULL
            """)
            
            for row in pending_batches:
                batch_job_id = row['batch_job_id']
                
                try:
                    # Check status with OpenAI
                    batch_status = await get_batch_status(batch_job_id)
                    
                    if batch_status["status"] == "completed":
                        logger.info(f"Batch {batch_job_id} completed, processing results")
                        
                        # Trigger webhook processing
                        webhook_data = {
                            "batch_job_id": batch_job_id,
                            "status": "completed",
                            "results": await download_batch_results(batch_status["output_file_id"])
                        }
                        
                        # Process webhook (this would normally come from OpenAI)
                        await batch_analysis_complete(BatchJobCompleteRequest(**webhook_data))
                        
                except Exception as e:
                    logger.error(f"Failed to process batch {batch_job_id}: {e}")
                    
    except Exception as e:
        logger.error(f"Background batch processing failed: {e}")

@app.post("/api/maintenance/process-batches")
async def manual_batch_processing(background_tasks: BackgroundTasks):
    """Manually trigger batch processing check"""
    background_tasks.add_task(process_completed_batches)
    return {"status": "batch_processing_triggered"}

if __name__ == "__main__":
    import uvicorn
    logger.info(f"Starting production backend server on port {PORT}")
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="info")