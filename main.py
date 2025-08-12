"""
Backend API Server for Client Communications Agent
Handles database operations, email sending, and workflow state management
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

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Environment configuration
DATABASE_URL = os.getenv("DATABASE_URL")
PORT = int(os.getenv("PORT", 8080))

if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is required")

# Global database pool
db_pool = None

# Existing Models (Cases and Email)
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

# Workflow Models
class WorkflowStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    AWAITING_SCHEDULE = "AWAITING_SCHEDULE"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

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
    created_at: datetime
    updated_at: datetime

class CreateWorkflowRequest(BaseModel):
    workflow_id: str
    agent_type: str = "CommunicationsAgent"
    case_id: Optional[str] = None
    status: WorkflowStatus
    initial_prompt: str
    scheduled_for: Optional[datetime] = None

class UpdateWorkflowStatusRequest(BaseModel):
    status: WorkflowStatus

class PendingWorkflowsResponse(BaseModel):
    workflow_ids: List[str]

# Database operations
async def init_database():
    """Initialize database connection pool"""
    global db_pool
    try:
        db_pool = await asyncpg.create_pool(
            DATABASE_URL,
            min_size=2,
            max_size=10,
            command_timeout=60
        )
        async with db_pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        logger.info("Database connection pool initialized")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise

async def close_database():
    """Close database connection pool"""
    global db_pool
    if db_pool:
        await db_pool.close()
        logger.info("Database connections closed")

# FastAPI app
@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_database()
    yield
    await close_database()

app = FastAPI(
    title="Client Communications Backend",
    description="Backend API for case management and workflow orchestration",
    version="2.0.0",
    lifespan=lifespan
)

@app.get("/")
async def health_check():
    """Health check"""
    try:
        async with db_pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        return {"status": "healthy", "timestamp": datetime.now().isoformat()}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Database unavailable: {str(e)}")

# Case Management Endpoints (Existing)
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

@app.post("/api/send-email", response_model=EmailResponse)
async def send_email(request: EmailRequest):
    """Send email to client - dummy implementation"""
    try:
        message_id = f"msg_{uuid.uuid4().hex[:12]}"
        
        logger.info(f"Sending email for case {request.case_id}")
        logger.info(f"To: {request.recipient_email}")
        logger.info(f"Subject: {request.subject}")
        logger.info(f"Body preview: {request.body[:100]}...")
        logger.info(f"Message ID: {message_id}")
        
        # Simulate email sending delay
        import asyncio
        await asyncio.sleep(0.1)
        
        return EmailResponse(
            message_id=message_id,
            status="sent",
            recipient=request.recipient_email,
            case_id=request.case_id
        )
        
    except Exception as e:
        logger.error(f"Email sending failed: {e}")
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

# Workflow Management Endpoints (New)
@app.post("/api/workflows", response_model=WorkflowState)
async def create_workflow(request: CreateWorkflowRequest):
    """Create a new workflow"""
    try:
        async with db_pool.acquire() as conn:
            now = datetime.now()
            
            await conn.execute("""
                INSERT INTO workflow_states 
                (workflow_id, agent_type, case_id, status, initial_prompt, scheduled_for, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            """, 
            request.workflow_id, request.agent_type, request.case_id, 
            request.status.value, request.initial_prompt, request.scheduled_for, now, now)
            
            # Return the created workflow
            return WorkflowState(
                workflow_id=request.workflow_id,
                agent_type=request.agent_type,
                case_id=request.case_id,
                status=request.status,
                initial_prompt=request.initial_prompt,
                reasoning_chain=[],
                scheduled_for=request.scheduled_for,
                created_at=now,
                updated_at=now
            )
            
    except asyncpg.UniqueViolationError:
        raise HTTPException(status_code=409, detail="Workflow ID already exists")
    except Exception as e:
        logger.error(f"Failed to create workflow: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.get("/api/workflows/{workflow_id}", response_model=WorkflowState)
async def get_workflow(workflow_id: str):
    """Get workflow by ID"""
    try:
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM workflow_states WHERE workflow_id = $1", 
                workflow_id
            )
            
            if not row:
                raise HTTPException(status_code=404, detail="Workflow not found")
            
            # Parse reasoning chain from JSONB
            reasoning_chain = []
            if row['reasoning_chain']:
                chain_data = json.loads(row['reasoning_chain']) if isinstance(row['reasoning_chain'], str) else row['reasoning_chain']
                reasoning_chain = [ReasoningStep(**step) for step in chain_data]
            
            return WorkflowState(
                workflow_id=row['workflow_id'],
                agent_type=row['agent_type'],
                case_id=row['case_id'],
                status=WorkflowStatus(row['status']),
                initial_prompt=row['initial_prompt'],
                reasoning_chain=reasoning_chain,
                scheduled_for=row['scheduled_for'],
                created_at=row['created_at'],
                updated_at=row['updated_at']
            )
            
    except Exception as e:
        logger.error(f"Failed to get workflow: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.put("/api/workflows/{workflow_id}/status")
async def update_workflow_status(workflow_id: str, request: UpdateWorkflowStatusRequest):
    """Update workflow status"""
    try:
        async with db_pool.acquire() as conn:
            result = await conn.execute(
                "UPDATE workflow_states SET status = $1 WHERE workflow_id = $2",
                request.status.value, workflow_id
            )
            
            if result == "UPDATE 0":
                raise HTTPException(status_code=404, detail="Workflow not found")
            
            logger.info(f"Updated workflow {workflow_id} status to {request.status.value}")
            return {"status": "updated", "workflow_id": workflow_id}
            
    except Exception as e:
        logger.error(f"Failed to update workflow status: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.post("/api/workflows/{workflow_id}/reasoning")
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
            
            # Parse existing chain
            chain_data = json.loads(current_chain) if isinstance(current_chain, str) else current_chain
            if not isinstance(chain_data, list):
                chain_data = []
            
            # Add new step
            chain_data.append(step.dict())
            
            # Update database
            await conn.execute(
                "UPDATE workflow_states SET reasoning_chain = $1 WHERE workflow_id = $2",
                json.dumps(chain_data), workflow_id
            )
            
            logger.info(f"Added reasoning step to workflow {workflow_id}")
            return {"status": "added", "workflow_id": workflow_id, "step_count": len(chain_data)}
            
    except Exception as e:
        logger.error(f"Failed to add reasoning step: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.get("/api/workflows/pending", response_model=PendingWorkflowsResponse)
async def get_pending_workflows():
    """Get workflows ready for execution"""
    try:
        async with db_pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT workflow_id FROM workflow_states 
                WHERE status = 'PENDING' 
                OR (status = 'AWAITING_SCHEDULE' AND scheduled_for <= NOW())
                ORDER BY created_at ASC
                LIMIT 50
            """)
            
            workflow_ids = [row['workflow_id'] for row in rows]
            
            logger.info(f"Found {len(workflow_ids)} pending workflows")
            return PendingWorkflowsResponse(workflow_ids=workflow_ids)
            
    except Exception as e:
        logger.error(f"Failed to get pending workflows: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

# Analytics endpoints
@app.get("/api/workflows/analytics")
async def get_workflow_analytics():
    """Get workflow analytics"""
    try:
        async with db_pool.acquire() as conn:
            analytics = await conn.fetch("SELECT * FROM workflow_analytics")
            recent_activity = await conn.fetch("SELECT * FROM recent_workflow_activity LIMIT 10")
            
            return {
                "analytics": [dict(row) for row in analytics],
                "recent_activity": [dict(row) for row in recent_activity]
            }
            
    except Exception as e:
        logger.error(f"Failed to get analytics: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    logger.info(f"Starting backend server on port {PORT}")
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="info")