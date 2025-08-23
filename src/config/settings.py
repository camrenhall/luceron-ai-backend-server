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
ENV = os.getenv("ENV", "PROD")  # PROD or QA
DATABASE_URL = os.getenv("DATABASE_URL")
RESEND_API_KEY = os.getenv("RESEND_API_KEY")
FROM_EMAIL = os.getenv("FROM_EMAIL")
ALERT_FROM_EMAIL = os.getenv("ALERT_FROM_EMAIL", FROM_EMAIL)  # Defaults to FROM_EMAIL if not set
PORT = int(os.getenv("PORT", 8080))
RESEND_WEBHOOK_SECRET = os.getenv("RESEND_WEBHOOK_SECRET")
ADMIN_ALERT_EMAILS = [email.strip() for email in os.getenv("ADMIN_ALERT_EMAILS", "admin@company.com").split(",")]

# Agent gateway configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Environment-specific JWT configuration for secure token isolation
class JWTEnvironmentConfig:
    """Environment-isolated JWT configuration to prevent cross-environment token reuse"""
    
    QA_CONFIG = {
        "secret": os.getenv("QA_JWT_SECRET", "qa-default-secret-for-development"),
        "issuer": "luceron-qa-auth",
        "audience": "luceron-qa-api", 
        "allowed_algorithms": ["HS256"],
        "max_token_age": 3600  # 1 hour for testing workflows
    }
    
    PROD_CONFIG = {
        "secret": os.getenv("PROD_JWT_SECRET", "prod-default-secret-change-in-production"),
        "issuer": "luceron-prod-auth",
        "audience": "luceron-prod-api",
        "allowed_algorithms": ["HS256"], 
        "max_token_age": 900  # 15 minutes for production security
    }
    
    @classmethod
    def get_config(cls):
        """Get JWT configuration for current environment"""
        return cls.QA_CONFIG if ENV == "QA" else cls.PROD_CONFIG

logger.info(f"Environment: {ENV}")
jwt_config = JWTEnvironmentConfig.get_config()
logger.info(f"JWT Config - Issuer: {jwt_config['issuer']}, Audience: {jwt_config['audience']}")

# Validate required environment variables
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is required")
if not RESEND_API_KEY:
    raise ValueError("RESEND_API_KEY environment variable is required")
if not OPENAI_API_KEY:
    logger.warning("OPENAI_API_KEY not set - agent gateway will not be available")

# Configure Resend
resend.api_key = RESEND_API_KEY

# CORS settings
ALLOWED_ORIGINS = [
    "https://simple-s3-upload.onrender.com",  # frontend URL
]