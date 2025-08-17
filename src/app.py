"""
Production Backend API Server
Core functionality: Cases, Workflows, Email via Resend
"""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config.settings import PORT, ALLOWED_ORIGINS
from database.connection import init_database, close_database
from api.routes import health, documents, cases, emails, workflows, webhooks
from utils.error_handling import setup_error_handling

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


# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Setup centralized error handling
setup_error_handling(app)

# Include API routes
app.include_router(health.router, tags=["Health"])
app.include_router(documents.router, prefix="/api/documents", tags=["Documents"])
app.include_router(cases.router, prefix="/api/cases", tags=["Cases"])
app.include_router(emails.router, prefix="/api", tags=["Emails"])
app.include_router(workflows.router, prefix="/api/workflows", tags=["Workflows"])
app.include_router(webhooks.router, prefix="/api/webhooks", tags=["Webhooks"])

# FastAPI app instance is exported for use by uvicorn
# Server startup is handled by main.py at the project root