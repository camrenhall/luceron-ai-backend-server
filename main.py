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

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import asyncpg
import resend

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Environment configuration
DATABASE_URL = os.getenv("DATABASE_URL")
RESEND_API_KEY = os.getenv("RESEND_API_KEY")
FROM_EMAIL = os.getenv("FROM_EMAIL", "legal@blueprintsw.com")
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
    status: str
    last_communication_date: Optional[datetime]
    documents_requested: str

class CaseCreateRequest(BaseModel):
    case_id: str
    client_name: str
    client_email: str
    documents_requested: str

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

# Database initialization
async def init_database():
    global db_pool
    db_pool = await asyncpg.create_pool(
        DATABASE_URL,
        min_size=2,
        max_size=10,
        command_timeout=60
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
        resend_id = result.id if hasattr(result, 'id') else str(result)
        
        # Log to database
        async with db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO email_logs 
                (message_id, case_id, recipient_email, subject, body, html_body, 
                 email_type, status, sent_via, resend_id, metadata, sent_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
            """, 
            message_id, request.case_id, request.recipient_email, 
            request.subject, request.body, request.html_body,
            request.email_type, "sent", "resend", resend_id,
            json.dumps(request.metadata), datetime.now())
            
            # Update case communication date
            await conn.execute(
                "UPDATE cases SET last_communication_date = $1 WHERE case_id = $2",
                datetime.now(), request.case_id
            )
        
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
            await conn.execute("""
                INSERT INTO email_logs 
                (message_id, case_id, recipient_email, subject, body, 
                 email_type, status, sent_via, error_message, sent_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            """, 
            message_id, request.case_id, request.recipient_email, 
            request.subject, request.body, request.email_type,
            "failed", "resend_error", str(e), datetime.now())
        
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

@app.get("/")
async def health_check():
    """Health check"""
    try:
        async with db_pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        
        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "database": "connected",
            "email": "resend_configured"
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Health check failed: {str(e)}")

# Case Management
@app.post("/api/cases")
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
            
            return {
                "case_id": request.case_id,
                "client_name": request.client_name,
                "client_email": request.client_email,
                "status": "awaiting_documents",
                "documents_requested": request.documents_requested
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
            
            return {
                "case_id": case_row['case_id'],
                "client_name": case_row['client_name'],
                "client_email": case_row['client_email'],
                "status": case_row['status'],
                "documents_requested": case_row['documents_requested'],
                "created_at": case_row['created_at'].isoformat(),
                "last_communication_date": case_row['last_communication_date'].isoformat() if case_row['last_communication_date'] else None
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
            
            # Get email history
            email_logs = await conn.fetch("""
                SELECT message_id, recipient_email, subject, email_type, 
                       status, sent_via, sent_at, metadata
                FROM email_logs 
                WHERE case_id = $1 
                ORDER BY sent_at DESC
                LIMIT 50
            """, case_id)
            
            return {
                "case_id": case_id,
                "client_name": case_row['client_name'],
                "client_email": case_row['client_email'],
                "case_status": case_row['status'],
                "documents_requested": case_row['documents_requested'],
                "last_communication_date": case_row['last_communication_date'].isoformat() if case_row['last_communication_date'] else None,
                "communication_summary": {
                    "total_emails": len(email_logs),
                    "last_email_date": email_logs[0]['sent_at'].isoformat() if email_logs else None
                },
                "email_history": [dict(log) for log in email_logs]
            }
            
    except Exception as e:
        logger.error(f"Failed to get case communications: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.get("/api/cases/pending-reminders")
async def get_pending_reminder_cases():
    """Get cases that need reminder emails"""
    try:
        async with db_pool.acquire() as conn:
            cutoff_date = datetime.now() - timedelta(days=3)
            
            rows = await conn.fetch("""
                SELECT case_id, client_email, client_name, status, 
                       last_communication_date, documents_requested
                FROM cases 
                WHERE status = 'awaiting_documents' 
                AND (last_communication_date IS NULL OR last_communication_date < $1)
                ORDER BY last_communication_date ASC NULLS FIRST
                LIMIT 20
            """, cutoff_date)
            
            cases = []
            for row in rows:
                cases.append({
                    "case_id": row['case_id'],
                    "client_email": row['client_email'],
                    "client_name": row['client_name'],
                    "status": row['status'],
                    "last_communication_date": row['last_communication_date'].isoformat() if row['last_communication_date'] else None,
                    "documents_requested": row['documents_requested']
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
                (workflow_id, agent_type, case_id, status, initial_prompt, reasoning_chain, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            """,
            request.workflow_id, request.agent_type, request.case_id, request.status.value,
            request.initial_prompt, json.dumps([]), datetime.now(), datetime.now())
            
            return {
                "workflow_id": request.workflow_id,
                "agent_type": request.agent_type,
                "case_id": request.case_id,
                "status": request.status.value,
                "initial_prompt": request.initial_prompt,
                "reasoning_chain": [],
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
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
                "created_at": row['created_at'].isoformat(),
                "updated_at": row['updated_at'].isoformat()
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
                "UPDATE workflow_states SET status = $1, updated_at = $2 WHERE workflow_id = $3",
                request.status.value, datetime.now(), workflow_id
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
            chain.append(step.dict())
            
            # Update database
            await conn.execute(
                "UPDATE workflow_states SET reasoning_chain = $1, updated_at = $2 WHERE workflow_id = $3",
                json.dumps(chain), datetime.now(), workflow_id
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