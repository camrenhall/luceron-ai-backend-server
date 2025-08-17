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
PORT = int(os.getenv("PORT", 8080))
API_KEY = os.getenv("API_KEY")

# Validate required environment variables
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is required")
if not RESEND_API_KEY:
    raise ValueError("RESEND_API_KEY environment variable is required")

# Configure Resend
resend.api_key = RESEND_API_KEY

# CORS settings
ALLOWED_ORIGINS = [
    "https://simple-s3-upload.onrender.com",  # frontend URL
]