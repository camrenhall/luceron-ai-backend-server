"""
Configuration settings for the Legal Communications Backend
"""

import os
import resend
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Environment configuration
DATABASE_URL = os.getenv("DATABASE_URL")
RESEND_API_KEY = os.getenv("RESEND_API_KEY")
FROM_EMAIL = os.getenv("FROM_EMAIL")
ALERT_FROM_EMAIL = os.getenv("ALERT_FROM_EMAIL", FROM_EMAIL)  # Defaults to FROM_EMAIL if not set
PORT = int(os.getenv("PORT", 8080))
API_KEY = os.getenv("API_KEY")
RESEND_WEBHOOK_SECRET = os.getenv("RESEND_WEBHOOK_SECRET")
ADMIN_ALERT_EMAILS = [email.strip() for email in os.getenv("ADMIN_ALERT_EMAILS", "admin@company.com").split(",")]

# Agent gateway configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Validate required environment variables
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is required")
if not RESEND_API_KEY:
    raise ValueError("RESEND_API_KEY environment variable is required")
if not API_KEY:
    raise ValueError("API_KEY environment variable is required for authentication")
if not OPENAI_API_KEY:
    logger.warning("OPENAI_API_KEY not set - agent gateway will not be available")

# Configure Resend
resend.api_key = RESEND_API_KEY

# CORS settings
ALLOWED_ORIGINS = [
    "https://simple-s3-upload.onrender.com",  # frontend URL
]