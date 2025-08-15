"""
Production Backend API Server
Core functionality: Cases, Workflows, Email via Resend
"""

import os
import logging
import uuid
import json

from datetime import datetime, timedelta
from typing import List, Optional
from contextlib import asynccontextmanager
from enum import Enum

# New enums for client communications
class CommunicationChannel(str, Enum):
    EMAIL = "email"
    SMS = "sms"

class CommunicationDirection(str, Enum):
    INCOMING = "incoming"
    OUTGOING = "outgoing"

class DeliveryStatus(str, Enum):
    SENT = "sent"
    DELIVERED = "delivered" 
    FAILED = "failed"
    OPENED = "opened"

from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
import asyncpg
import resend
import httpx
from datetime import datetime, timezone

from fastapi.middleware.cors import CORSMiddleware


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Environment configuration
DATABASE_URL = os.getenv("DATABASE_URL")
RESEND_API_KEY = os.getenv("RESEND_API_KEY")
FROM_EMAIL = os.getenv("FROM_EMAIL")
DOCUMENT_ANALYSIS_AGENT_URL = os.getenv("DOCUMENT_ANALYSIS_AGENT_URL")
PORT = int(os.getenv("PORT", 8080))

if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is required")
if not RESEND_API_KEY:
    raise ValueError("RESEND_API_KEY environment variable is required")

# Configure Resend
resend.api_key = RESEND_API_KEY

# Global database pool
db_pool = None

# Models
class WorkflowStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

class CaseData(BaseModel):
    case_id: str
    client_email: str
    client_name: str
    client_phone: Optional[str] = None
    status: str

class RequestedDocument(BaseModel):
    document_name: str
    description: Optional[str] = None

class CaseCreateRequest(BaseModel):
    case_id: str
    client_name: str
    client_email: str
    client_phone: Optional[str] = None
    requested_documents: List[RequestedDocument]

class EmailRequest(BaseModel):
    recipient_email: str
    subject: str
    body: str
    html_body: Optional[str] = None
    case_id: str
    email_type: str = "custom"
    metadata: Optional[dict] = {}

class EmailResponse(BaseModel):
    message_id: str
    status: str
    recipient: str
    case_id: str
    sent_via: str

class ClientCommunication(BaseModel):
    case_id: str
    channel: CommunicationChannel
    direction: CommunicationDirection
    status: DeliveryStatus
    sender: str
    recipient: str
    subject: Optional[str] = None
    message_content: str
    sent_at: Optional[datetime] = None
    resend_id: Optional[str] = None

class ReasoningStep(BaseModel):
    timestamp: str
    thought: str
    action: Optional[str] = None
    action_input: Optional[dict] = None
    action_output: Optional[str] = None

class WorkflowCreateRequest(BaseModel):
    workflow_id: str
    agent_type: str = "CommunicationsAgent"
    case_id: Optional[str] = None
    status: WorkflowStatus
    initial_prompt: str

class WorkflowStatusRequest(BaseModel):
    status: WorkflowStatus
    
class AnalysisResultRequest(BaseModel):
    document_id: str
    case_id: str
    workflow_id: Optional[str] = None
    analysis_content: str
    extracted_data: Optional[dict] = None
    confidence_score: Optional[int] = None
    red_flags: Optional[List[str]] = None
    recommendations: Optional[str] = None
    model_used: str = "o3"
    tokens_used: Optional[int] = None
    analysis_cost_cents: Optional[int] = None
    analysis_status: str = "completed"

class AnalysisResultResponse(BaseModel):
    analysis_id: str
    document_id: str
    case_id: str
    status: str
    analyzed_at: str

class S3UploadFile(BaseModel):
    fileName: str
    fileSize: int
    fileType: str
    s3Location: str
    s3Key: str
    s3ETag: Optional[str] = None
    uploadedAt: str
    status: str = "success"

class S3UploadWebhookRequest(BaseModel):
    event: str
    timestamp: str
    summary: dict
    files: List[S3UploadFile]
    metadata: dict

class DocumentUploadResponse(BaseModel):
    documents_created: int
    analysis_triggered: bool
    workflow_ids: List[str]
    message: str

# Database initialization
async def init_database():
    global db_pool
    db_pool = await asyncpg.create_pool(
        DATABASE_URL,
        min_size=2,
        max_size=10,
        command_timeout=60,
        statement_cache_size=0  # Fix for pgbouncer compatibility
    )
    
    # Test connection
    async with db_pool.acquire() as conn:
        await conn.fetchval("SELECT 1")
    
    logger.info("Database initialized successfully")

async def close_database():
    global db_pool
    if db_pool:
        await db_pool.close()
    logger.info("Database connections closed")
    
def parse_uploaded_timestamp(timestamp_str: str) -> datetime:
    """Parse uploaded timestamp handling timezone properly"""
    try:
        # Handle ISO format with 'Z' (UTC)
        if timestamp_str.endswith('Z'):
            timestamp_str = timestamp_str.replace('Z', '+00:00')
        
        # Parse the timestamp - FIX: Parse timestamp_str, not recursive call
        uploaded_at = datetime.fromisoformat(timestamp_str)
        
        # Convert to UTC and make timezone-naive for database storage
        if uploaded_at.tzinfo is not None:
            uploaded_at = uploaded_at.astimezone(timezone.utc).replace(tzinfo=None)
        
        return uploaded_at
        
    except Exception as e:
        logger.warning(f"Failed to parse timestamp '{timestamp_str}': {e}")
        # Return current UTC time as fallback
        return datetime.utcnow()

# Email sending function
async def send_email_via_resend(request: EmailRequest) -> EmailResponse:
    """Send email via Resend API"""
    message_id = f"msg_{uuid.uuid4().hex[:12]}"
    
    try:
        # Send email via Resend
        email_data = {
            "from": FROM_EMAIL,
            "to": [request.recipient_email],
            "subject": request.subject,
            "html": request.html_body or f"<p>{request.body.replace(chr(10), '<br>')}</p>",
            "text": request.body
        }
        
        result = resend.Emails.send(email_data)
        # Extract just the ID string from the Resend response
        if hasattr(result, 'id'):
            resend_id = result.id
        elif isinstance(result, dict) and 'id' in result:
            resend_id = result['id']
        else:
            resend_id = None
        
        # Log to database
        async with db_pool.acquire() as conn:
            # Insert into client_communications table
            await conn.execute("""
                INSERT INTO client_communications 
                (case_id, channel, direction, status, sender, recipient, subject, message_content, sent_at, resend_id)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            """,
            request.case_id, "email", "outgoing", "sent", FROM_EMAIL, 
            request.recipient_email, request.subject, request.body, datetime.utcnow(), resend_id)
        
        logger.info(f"Email sent via Resend - ID: {resend_id}, To: {request.recipient_email}")
        
        return EmailResponse(
            message_id=message_id,
            status="sent",
            recipient=request.recipient_email,
            case_id=request.case_id,
            sent_via="resend"
        )
        
    except Exception as e:
        # Log failure
        async with db_pool.acquire() as conn:
            # Insert into client_communications table
            await conn.execute("""
                INSERT INTO client_communications 
                (case_id, channel, direction, status, sender, recipient, subject, message_content, sent_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            """,
            request.case_id, "email", "outgoing", "failed", FROM_EMAIL, 
            request.recipient_email, request.subject, request.body, datetime.utcnow())
        
        logger.error(f"Email sending failed: {e}")
        raise HTTPException(status_code=500, detail=f"Email sending failed: {str(e)}")

# FastAPI app
@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_database()
    yield
    await close_database()

app = FastAPI(
    title="Legal Communications Backend",
    description="Backend API for case management and email communications", 
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://simple-s3-upload.onrender.com",  # frontend URL
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

@app.get("/")
async def health_check():
    """Health check"""
    try:
        async with db_pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        
        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "database": "connected",
            "email": "resend_configured"
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Health check failed: {str(e)}")
    
@app.post("/api/webhooks/document-uploaded", response_model=DocumentUploadResponse)
async def handle_document_upload(request: S3UploadWebhookRequest, background_tasks: BackgroundTasks):
    """Handle S3 document upload webhook and trigger analysis"""
    
    logger.info(f"📄 Document upload webhook received: {request.event}")
    logger.info(f"📄 Files uploaded: {len(request.files)}")
    
    documents_created = 0
    workflow_ids = []
    
    try:
        async with db_pool.acquire() as conn:
            for file_upload in request.files:
                if file_upload.status != "success":
                    logger.warning(f"Skipping failed upload: {file_upload.fileName}")
                    continue
                
                # Extract client email from metadata
                client_email = request.metadata.get("clientEmail")
                if not client_email:
                    logger.error("❌ No clientEmail in webhook metadata")
                    raise HTTPException(status_code=400, detail="Missing clientEmail in webhook metadata")
                
                # Find case by client email
                case_row = await conn.fetchrow(
                    "SELECT case_id FROM cases WHERE client_email = $1 AND status = 'awaiting_documents'",
                    client_email
                )
                
                if not case_row:
                    logger.error(f"❌ CRITICAL: No active case found for client email: {client_email}")
                    logger.error(f"❌ Document upload failed - client {client_email} does not have an active case")
                    raise HTTPException(
                        status_code=404, 
                        detail=f"No active case found for client email: {client_email}. Please ensure a case exists with status 'awaiting_documents'."
                    )
                
                case_id = case_row['case_id']
                
                # Generate document ID
                document_id = f"doc_{uuid.uuid4().hex[:12]}"
                
                # Classify document type based on filename
                document_type = classify_document_type(file_upload.fileName)
                
                # Parse uploaded timestamp
                uploaded_at = parse_uploaded_timestamp(file_upload.uploadedAt)
                
                # Insert document record
                await conn.execute("""
                    INSERT INTO documents 
                    (document_id, case_id, filename, file_size, file_type, 
                    s3_location, s3_key, s3_etag, document_type, status, uploaded_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                """,
                document_id, case_id, file_upload.fileName, file_upload.fileSize,
                file_upload.fileType, file_upload.s3Location, file_upload.s3Key,
                file_upload.s3ETag, document_type, "uploaded", uploaded_at)
                
                documents_created += 1
                
                logger.info(f"📄 Created document record: {document_id} for case {case_id}")
                
                # Trigger document analysis in background
                background_tasks.add_task(
                    trigger_document_analysis,
                    document_id,
                    case_id,
                    file_upload.s3Location
                )
                
                # Generate workflow ID for tracking (will be created by analysis agent)
                workflow_id = f"wf_upload_{uuid.uuid4().hex[:8]}"
                workflow_ids.append(workflow_id)
        
        return DocumentUploadResponse(
            documents_created=documents_created,
            analysis_triggered=documents_created > 0,
            workflow_ids=workflow_ids,
            message=f"Successfully processed {documents_created} document uploads"
        )
        
    except Exception as e:
        logger.error(f"Document upload webhook failed: {e}")
        raise HTTPException(status_code=500, detail=f"Webhook processing failed: {str(e)}")

def classify_document_type(filename: str) -> str:
    """Classify document type based on filename patterns"""
    filename_lower = filename.lower()
    
    if any(term in filename_lower for term in ['bank', 'statement', 'checking', 'savings']):
        return 'bank_statement'
    elif any(term in filename_lower for term in ['tax', '1040', 'w2', 'w-2']):
        return 'tax_return'
    elif any(term in filename_lower for term in ['pay', 'stub', 'payroll', 'salary']):
        return 'pay_stub'
    elif any(term in filename_lower for term in ['investment', 'brokerage', '401k', 'ira']):
        return 'investment_statement'
    elif any(term in filename_lower for term in ['financial', 'asset', 'liability']):
        return 'financial_record'
    else:
        return 'other'

async def trigger_document_analysis(document_id: str, case_id: str, s3_location: str):
    """Background task to trigger document analysis agent"""
    try:
        logger.info(f"🔄 Triggering analysis for document {document_id}")
        
        # Update document status to analyzing
        async with db_pool.acquire() as conn:
            await conn.execute(
                "UPDATE documents SET status = 'analyzing', updated_at = $1 WHERE document_id = $2",
                datetime.utcnow(), document_id
            )
        
        # Call Document Analysis Agent
        async with httpx.AsyncClient(timeout=60.0) as client:
            analysis_request = {
                "case_id": case_id,
                "document_ids": [document_id],
                "case_context": f"Single document upload analysis for document {document_id}"
            }
            
            response = await client.post(
                f"{DOCUMENT_ANALYSIS_AGENT_URL}/workflows/trigger-analysis",
                json=analysis_request
            )
            
            if response.status_code == 200:
                result = response.json()
                workflow_id = result.get("workflow_id")
                logger.info(f"✅ Analysis triggered successfully: workflow {workflow_id}")
            else:
                logger.error(f"❌ Analysis trigger failed: {response.status_code} - {response.text}")
                
                # Update document status to failed
                async with db_pool.acquire() as conn:
                    await conn.execute(
                        "UPDATE documents SET status = 'failed', updated_at = $1 WHERE document_id = $2",
                        datetime.utcnow(), document_id
                    )
                
    except Exception as e:
        logger.error(f"Background analysis trigger failed for {document_id}: {e}")
        
        # Update document status to failed
        try:
            async with db_pool.acquire() as conn:
                await conn.execute(
                    "UPDATE documents SET status = 'failed', updated_at = $1 WHERE document_id = $2",
                    datetime.utcnow(), document_id
                )
        except Exception as db_error:
            logger.error(f"Failed to update document status: {db_error}")
    
@app.post("/api/documents/{document_id}/analysis", response_model=AnalysisResultResponse)
async def store_document_analysis(document_id: str, request: AnalysisResultRequest):
    """Store document analysis results"""
    analysis_id = f"ana_{uuid.uuid4().hex[:12]}"
    
    try:
        async with db_pool.acquire() as conn:
            # Verify document exists
            doc_exists = await conn.fetchval(
                "SELECT EXISTS(SELECT 1 FROM documents WHERE document_id = $1)", 
                document_id
            )
            if not doc_exists:
                raise HTTPException(status_code=404, detail="Document not found")
            
            # Verify case exists
            case_exists = await conn.fetchval(
                "SELECT EXISTS(SELECT 1 FROM cases WHERE case_id = $1)", 
                request.case_id
            )
            if not case_exists:
                raise HTTPException(status_code=404, detail="Case not found")
            
            # Insert analysis result
            await conn.execute("""
                INSERT INTO document_analysis 
                (analysis_id, document_id, case_id, workflow_id, analysis_content, 
                 extracted_data, confidence_score, red_flags, recommendations,
                 analysis_status, model_used, tokens_used, analysis_cost_cents, analyzed_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
            """, 
            analysis_id, document_id, request.case_id, request.workflow_id,
            request.analysis_content, json.dumps(request.extracted_data) if request.extracted_data else None,
            request.confidence_score, json.dumps(request.red_flags) if request.red_flags else None,
            request.recommendations, request.analysis_status, request.model_used,
            request.tokens_used, request.analysis_cost_cents, datetime.utcnow())
            
            # Update document status to analyzed
            await conn.execute(
                "UPDATE documents SET status = 'analyzed', updated_at = $1 WHERE document_id = $2",
                datetime.utcnow(), document_id
            )
            
            logger.info(f"Stored analysis result {analysis_id} for document {document_id}")
            
            return AnalysisResultResponse(
                analysis_id=analysis_id,
                document_id=document_id,
                case_id=request.case_id,
                status="stored",
                analyzed_at=datetime.utcnow().isoformat()
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to store analysis result: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.get("/api/documents/{document_id}/analysis")
async def get_document_analysis(document_id: str):
    """Get analysis results for a document"""
    try:
        async with db_pool.acquire() as conn:
            analysis_row = await conn.fetchrow("""
                SELECT analysis_id, document_id, case_id, workflow_id, analysis_content,
                       extracted_data, confidence_score, red_flags, recommendations,
                       analysis_status, model_used, tokens_used, analysis_cost_cents,
                       analyzed_at, created_at, updated_at
                FROM document_analysis 
                WHERE document_id = $1
                ORDER BY analyzed_at DESC
                LIMIT 1
            """, document_id)
            
            if not analysis_row:
                raise HTTPException(status_code=404, detail="Analysis not found for document")
            
            result = dict(analysis_row)
            
            # Parse JSON fields
            if result['extracted_data']:
                result['extracted_data'] = json.loads(result['extracted_data'])
            if result['red_flags']:
                result['red_flags'] = json.loads(result['red_flags'])
            
            # Convert timestamps to ISO format
            for field in ['analyzed_at', 'created_at', 'updated_at']:
                if result[field]:
                    result[field] = result[field].isoformat()
            
            return result
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get analysis result: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.get("/api/cases/{case_id}/analysis-summary")
async def get_case_analysis_summary(case_id: str):
    """Get analysis summary for all documents in a case"""
    try:
        async with db_pool.acquire() as conn:
            # Get case details
            case_row = await conn.fetchrow("SELECT * FROM cases WHERE case_id = $1", case_id)
            if not case_row:
                raise HTTPException(status_code=404, detail="Case not found")
            
            # Get analysis results for all documents in the case
            analysis_rows = await conn.fetch("""
                SELECT da.analysis_id, da.document_id, d.filename, d.document_type,
                       da.confidence_score, da.analysis_status, da.analyzed_at,
                       da.red_flags, da.model_used
                FROM document_analysis da
                JOIN documents d ON da.document_id = d.document_id
                WHERE da.case_id = $1
                ORDER BY da.analyzed_at DESC
            """, case_id)
            
            analysis_summary = []
            total_red_flags = 0
            avg_confidence = 0
            
            for row in analysis_rows:
                red_flags = json.loads(row['red_flags']) if row['red_flags'] else []
                total_red_flags += len(red_flags)
                
                analysis_summary.append({
                    "analysis_id": row['analysis_id'],
                    "document_id": row['document_id'],
                    "filename": row['filename'],
                    "document_type": row['document_type'],
                    "confidence_score": row['confidence_score'],
                    "analysis_status": row['analysis_status'],
                    "analyzed_at": row['analyzed_at'].isoformat(),
                    "red_flags_count": len(red_flags),
                    "model_used": row['model_used']
                })
            
            if analysis_summary:
                avg_confidence = sum(a['confidence_score'] for a in analysis_summary if a['confidence_score']) / len(analysis_summary)
            
            return {
                "case_id": case_id,
                "client_name": case_row['client_name'],
                "total_documents_analyzed": len(analysis_summary),
                "average_confidence_score": round(avg_confidence, 1),
                "total_red_flags": total_red_flags,
                "analysis_results": analysis_summary
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get case analysis summary: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    
@app.get("/api/documents/{document_id}")
async def get_document(document_id: str):
    """Get document metadata by document ID"""
    try:
        async with db_pool.acquire() as conn:
            doc_row = await conn.fetchrow("""
                SELECT document_id, case_id, filename, file_size, file_type,
                       s3_location, s3_key, s3_etag, document_type, status,
                       uploaded_at, created_at, updated_at
                FROM documents 
                WHERE document_id = $1
            """, document_id)
            
            if not doc_row:
                raise HTTPException(status_code=404, detail="Document not found")
            
            result = dict(doc_row)
            
            # Convert timestamps to ISO format
            for field in ['uploaded_at', 'created_at', 'updated_at']:
                if result[field]:
                    result[field] = result[field].isoformat()
            
            return result
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get document: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

# Case Management
@app.post("/api/cases")
async def create_case(request: CaseCreateRequest):
    """Create a new case"""
    try:
        async with db_pool.acquire() as conn:
            async with conn.transaction():
                # Create the case
                await conn.execute("""
                    INSERT INTO cases (case_id, client_name, client_email, client_phone, status, created_at)
                    VALUES ($1, $2, $3, $4, $5, $6)
                """, 
                request.case_id, request.client_name, request.client_email, 
                request.client_phone, "awaiting_documents", datetime.utcnow())
                
                # Insert requested documents
                for doc in request.requested_documents:
                    await conn.execute("""
                        INSERT INTO requested_documents (case_id, document_name, description, requested_at, updated_at)
                        VALUES ($1, $2, $3, $4, $5)
                    """,
                    request.case_id, doc.document_name, doc.description, 
                    datetime.utcnow(), datetime.utcnow())
                
                # Update any existing workflows that were created without a case_id
                # and should be associated with this new case (e.g., communication workflows)
                await conn.execute("""
                    UPDATE workflow_states 
                    SET case_id = $1 
                    WHERE case_id IS NULL 
                    AND agent_type = 'CommunicationsAgent'
                    AND created_at >= NOW() - INTERVAL '1 hour'
                """, request.case_id)
            
            return {
                "case_id": request.case_id,
                "client_name": request.client_name,
                "client_email": request.client_email,
                "client_phone": request.client_phone,
                "status": "awaiting_documents",
                "requested_documents": [doc.model_dump() for doc in request.requested_documents]
            }
            
    except asyncpg.UniqueViolationError:
        raise HTTPException(status_code=409, detail="Case ID already exists")
    except Exception as e:
        logger.error(f"Failed to create case: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.get("/api/cases/{case_id}")
async def get_case(case_id: str):
    """Get case details"""
    try:
        async with db_pool.acquire() as conn:
            case_row = await conn.fetchrow(
                "SELECT * FROM cases WHERE case_id = $1", case_id
            )
            
            if not case_row:
                raise HTTPException(status_code=404, detail="Case not found")
            
            # Get requested documents for this case
            requested_docs = await conn.fetch("""
                SELECT id, document_name, description, is_completed, completed_at, 
                       is_flagged_for_review, notes, requested_at, updated_at
                FROM requested_documents 
                WHERE case_id = $1 
                ORDER BY requested_at ASC
            """, case_id)
            
            # Get last communication date from client_communications
            last_comm = await conn.fetchrow("""
                SELECT created_at 
                FROM client_communications 
                WHERE case_id = $1 
                ORDER BY created_at DESC 
                LIMIT 1
            """, case_id)
            
            return {
                "case_id": case_row['case_id'],
                "client_name": case_row['client_name'],
                "client_email": case_row['client_email'],
                "client_phone": case_row['client_phone'],
                "status": case_row['status'],
                "created_at": case_row['created_at'].isoformat(),
                "last_communication_date": last_comm['created_at'].isoformat() if last_comm else None,
                "requested_documents": [
                    {
                        "id": str(doc['id']),
                        "document_name": doc['document_name'],
                        "description": doc['description'],
                        "is_completed": doc['is_completed'],
                        "completed_at": doc['completed_at'].isoformat() if doc['completed_at'] else None,
                        "is_flagged_for_review": doc['is_flagged_for_review'],
                        "notes": doc['notes'],
                        "requested_at": doc['requested_at'].isoformat(),
                        "updated_at": doc['updated_at'].isoformat()
                    } for doc in requested_docs
                ]
            }
            
    except Exception as e:
        logger.error(f"Failed to get case: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.get("/api/cases/{case_id}/communications")
async def get_case_communications(case_id: str):
    """Get communication history for a case"""
    try:
        async with db_pool.acquire() as conn:
            # Get case details
            case_row = await conn.fetchrow("SELECT * FROM cases WHERE case_id = $1", case_id)
            if not case_row:
                raise HTTPException(status_code=404, detail="Case not found")
            
            # Get requested documents for this case
            requested_docs = await conn.fetch("""
                SELECT id, document_name, description, is_completed, completed_at, 
                       is_flagged_for_review, notes, requested_at, updated_at
                FROM requested_documents 
                WHERE case_id = $1 
                ORDER BY requested_at ASC
            """, case_id)
            
            # Get communication history from new table
            communications = await conn.fetch("""
                SELECT id, channel, direction, status, opened_at, sender, recipient, 
                       subject, message_content, created_at, sent_at, resend_id
                FROM client_communications 
                WHERE case_id = $1 
                ORDER BY created_at DESC
                LIMIT 50
            """, case_id)
            
            return {
                "case_id": case_id,
                "client_name": case_row['client_name'],
                "client_email": case_row['client_email'],
                "client_phone": case_row['client_phone'],
                "case_status": case_row['status'],
                "requested_documents": [
                    {
                        "id": str(doc['id']),
                        "document_name": doc['document_name'],
                        "description": doc['description'],
                        "is_completed": doc['is_completed'],
                        "completed_at": doc['completed_at'].isoformat() if doc['completed_at'] else None,
                        "is_flagged_for_review": doc['is_flagged_for_review'],
                        "notes": doc['notes'],
                        "requested_at": doc['requested_at'].isoformat(),
                        "updated_at": doc['updated_at'].isoformat()
                    } for doc in requested_docs
                ],
                "last_communication_date": communications[0]['created_at'].isoformat() if communications else None,
                "communication_summary": {
                    "total_communications": len(communications),
                    "last_communication_date": communications[0]['created_at'].isoformat() if communications else None
                },
                "communications": [
                    {
                        "id": str(comm['id']),
                        "channel": comm['channel'],
                        "direction": comm['direction'],
                        "status": comm['status'],
                        "opened_at": comm['opened_at'].isoformat() if comm['opened_at'] else None,
                        "sender": comm['sender'],
                        "recipient": comm['recipient'],
                        "subject": comm['subject'],
                        "message_content": comm['message_content'],
                        "created_at": comm['created_at'].isoformat(),
                        "sent_at": comm['sent_at'].isoformat() if comm['sent_at'] else None,
                        "resend_id": comm['resend_id']
                    } for comm in communications
                ]
            }
            
    except Exception as e:
        logger.error(f"Failed to get case communications: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.get("/api/cases/pending-reminders")
async def get_pending_reminder_cases():
    """Get cases that need reminder emails"""
    try:
        async with db_pool.acquire() as conn:
            cutoff_date = datetime.utcnow() - timedelta(days=3)
            
            # Get cases and their last communication date from the new table
            rows = await conn.fetch("""
                SELECT c.case_id, c.client_email, c.client_name, c.client_phone, c.status,
                       MAX(cc.created_at) as last_communication_date
                FROM cases c
                LEFT JOIN client_communications cc ON c.case_id = cc.case_id
                WHERE c.status = 'awaiting_documents'
                GROUP BY c.case_id, c.client_email, c.client_name, c.client_phone, c.status
                HAVING MAX(cc.created_at) IS NULL OR MAX(cc.created_at) < $1
                ORDER BY MAX(cc.created_at) ASC NULLS FIRST
                LIMIT 20
            """, cutoff_date)
            
            cases = []
            for row in rows:
                # Get requested documents for each case
                requested_docs = await conn.fetch("""
                    SELECT document_name, description, is_completed
                    FROM requested_documents 
                    WHERE case_id = $1 
                    ORDER BY requested_at ASC
                """, row['case_id'])
                
                cases.append({
                    "case_id": row['case_id'],
                    "client_email": row['client_email'],
                    "client_name": row['client_name'],
                    "client_phone": row['client_phone'],
                    "status": row['status'],
                    "last_communication_date": row['last_communication_date'].isoformat() if row['last_communication_date'] else None,
                    "requested_documents": [
                        {
                            "document_name": doc['document_name'],
                            "description": doc['description'],
                            "is_completed": doc['is_completed']
                        } for doc in requested_docs
                    ]
                })
            
            return {"found_cases": len(cases), "cases": cases}
            
    except Exception as e:
        logger.error(f"Failed to get pending cases: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

# Email Management
@app.post("/api/send-email")
async def send_email(request: EmailRequest):
    """Send email via Resend"""
    return await send_email_via_resend(request)

# Workflow Management
@app.post("/api/workflows")
async def create_workflow(request: WorkflowCreateRequest):
    """Create a new workflow"""
    try:
        async with db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO workflow_states 
                (workflow_id, agent_type, case_id, status, initial_prompt, reasoning_chain)
                VALUES ($1, $2, $3, $4, $5, $6)
            """,
            request.workflow_id, request.agent_type, request.case_id, request.status.value,
            request.initial_prompt, json.dumps([]))
            
            # Fetch the created workflow with auto-generated timestamps
            row = await conn.fetchrow(
                "SELECT * FROM workflow_states WHERE workflow_id = $1", request.workflow_id
            )
            
            return {
                "workflow_id": request.workflow_id,
                "agent_type": request.agent_type,
                "case_id": request.case_id,
                "status": request.status.value,
                "initial_prompt": request.initial_prompt,
                "reasoning_chain": [],
                "created_at": row['created_at'].isoformat() if row['created_at'] else None
            }
            
    except asyncpg.UniqueViolationError:
        raise HTTPException(status_code=409, detail="Workflow ID already exists")
    except Exception as e:
        logger.error(f"Failed to create workflow: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.get("/api/workflows/{workflow_id}")
async def get_workflow(workflow_id: str):
    """Get workflow by ID"""
    try:
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM workflow_states WHERE workflow_id = $1", workflow_id
            )
            
            if not row:
                raise HTTPException(status_code=404, detail="Workflow not found")
            
            reasoning_chain = json.loads(row['reasoning_chain']) if row['reasoning_chain'] else []
            
            return {
                "workflow_id": row['workflow_id'],
                "agent_type": row['agent_type'],
                "case_id": row['case_id'],
                "status": row['status'],
                "initial_prompt": row['initial_prompt'],
                "reasoning_chain": reasoning_chain,
                "created_at": row['created_at'].isoformat()
            }
            
    except Exception as e:
        logger.error(f"Failed to get workflow: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@app.put("/api/workflows/{workflow_id}/status")
async def update_workflow_status(workflow_id: str, request: WorkflowStatusRequest):
    """Update workflow status"""
    try:
        async with db_pool.acquire() as conn:
            result = await conn.execute(
                "UPDATE workflow_states SET status = $1 WHERE workflow_id = $2",
                request.status.value, workflow_id
            )
            
            if result == "UPDATE 0":
                raise HTTPException(status_code=404, detail="Workflow not found")
            
            return {"status": "updated", "workflow_id": workflow_id}
            
    except Exception as e:
        logger.error(f"Failed to update workflow status: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.post("/api/workflows/{workflow_id}/reasoning-step")
async def add_reasoning_step(workflow_id: str, step: ReasoningStep):
    """Add a reasoning step to workflow"""
    try:
        async with db_pool.acquire() as conn:
            # Get current reasoning chain
            current_chain = await conn.fetchval(
                "SELECT reasoning_chain FROM workflow_states WHERE workflow_id = $1",
                workflow_id
            )
            
            if current_chain is None:
                raise HTTPException(status_code=404, detail="Workflow not found")
            
            # Parse and append new step
            chain = json.loads(current_chain) if current_chain else []
            chain.append(step.model_dump())
            
            # Update database
            await conn.execute(
                "UPDATE workflow_states SET reasoning_chain = $1 WHERE workflow_id = $2",
                json.dumps(chain), workflow_id
            )
            
            return {"status": "step_added", "workflow_id": workflow_id}
            
    except Exception as e:
        logger.error(f"Failed to add reasoning step: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.get("/api/workflows/pending")
async def get_pending_workflows():
    """Get workflows that need processing"""
    try:
        async with db_pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT workflow_id FROM workflow_states 
                WHERE status = 'PENDING'
                ORDER BY created_at ASC
                LIMIT 50
            """)
            
            workflow_ids = [row['workflow_id'] for row in rows]
            return {"workflow_ids": workflow_ids}
            
    except Exception as e:
        logger.error(f"Failed to get pending workflows: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    logger.info(f"Starting backend server on port {PORT}")
    uvicorn.run(app, host="0.0.0.0", port=PORT)