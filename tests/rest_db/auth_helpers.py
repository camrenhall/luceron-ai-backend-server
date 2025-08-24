"""
OAuth Authentication Helper for Tavern Tests
Generates JWT tokens for API authentication
"""

import os
import jwt
import uuid
from datetime import datetime, timedelta


def generate_jwt_token() -> str:
    """Generate OAuth JWT token for API authentication"""
    private_key = os.getenv('TEST_OAUTH_PRIVATE_KEY', '').replace('\\n', '\n')
    if not private_key:
        raise ValueError("TEST_OAUTH_PRIVATE_KEY environment variable is required")
    
    service_id = os.getenv('OAUTH_SERVICE_ID', 'qa_comprehensive_test_service')
    audience = os.getenv('OAUTH_AUDIENCE', 'luceron-auth-server')
    
    now = datetime.utcnow()
    payload = {
        'iss': service_id,
        'sub': service_id,
        'aud': audience,
        'iat': int(now.timestamp()),
        'exp': int((now + timedelta(minutes=5)).timestamp()),
        'jti': str(uuid.uuid4())
    }
    
    return jwt.encode(payload, private_key, algorithm='RS256')


def validate_uuid(value: str) -> bool:
    """Validate UUID format"""
    try:
        uuid.UUID(value)
        return True
    except ValueError:
        return False


def validate_timestamp(value: str) -> bool:
    """Validate ISO timestamp format"""
    try:
        datetime.fromisoformat(value.replace('Z', '+00:00'))
        return True
    except ValueError:
        return False