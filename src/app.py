"""
Production Backend API Server
Core functionality: Cases, Workflows, Email via Resend
"""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from config.settings import PORT, ALLOWED_ORIGINS
from database.connection import init_database, close_database
from api.routes import health, documents, cases, emails, workflows, webhooks

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    await init_database()
    yield
    await close_database()

# FastAPI app initialization
app = FastAPI(
    title="Legal Communications Backend",
    description="Backend API for case management and email communications", 
    version="1.0.0",
    lifespan=lifespan
)

# Exception handlers for better validation error logging
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Log detailed validation errors for debugging"""
    logger.error(f"Validation error on {request.method} {request.url}")
    logger.error(f"Request headers: {dict(request.headers)}")
    
    # Try to get request body for logging
    try:
        body = await request.body()
        logger.error(f"Request body: {body.decode('utf-8')}")
    except Exception as e:
        logger.error(f"Could not read request body: {e}")
    
    logger.error(f"Validation errors: {exc.errors()}")
    
    return JSONResponse(
        status_code=422,
        content={
            "detail": exc.errors(),
            "body": f"Validation failed for {request.method} {request.url}"
        }
    )

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(health.router, tags=["Health"])
app.include_router(documents.router, prefix="/api/documents", tags=["Documents"])
app.include_router(cases.router, prefix="/api/cases", tags=["Cases"])
app.include_router(emails.router, prefix="/api", tags=["Emails"])
app.include_router(workflows.router, prefix="/api/workflows", tags=["Workflows"])
app.include_router(webhooks.router, prefix="/api/webhooks", tags=["Webhooks"])

# FastAPI app instance is exported for use by uvicorn
# Server startup is handled by main.py at the project root