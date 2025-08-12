"""
Backend API Server for Client Communications Agent
Handles database operations and email sending
"""

import os
import logging
import uuid
from datetime import datetime, timedelta
from typing import List, Optional
from contextlib import asynccontextmanager

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

# Models
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
    version="1.0.0",
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
        # Generate dummy message ID
        message_id = f"msg_{uuid.uuid4().hex[:12]}"
        
        # Log email details (replace with actual email service)
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

if __name__ == "__main__":
    import uvicorn
    logger.info(f"Starting backend server on port {PORT}")
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="info")