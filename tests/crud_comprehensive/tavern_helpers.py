"""
Tavern Helper Functions
OAuth token generation and custom validation functions for Tavern tests
"""

import os
import jwt
import time
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any


def generate_jwt_token() -> str:
    """Generate JWT token for OAuth authentication"""
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


def generate_test_data(resource_type: str, **overrides) -> Dict[str, Any]:
    """Generate test data for various resource types"""
    test_prefix = os.getenv('TEST_DATA_PREFIX', 'TAVERN_TEST')
    timestamp = int(time.time())
    
    # Parse any special formatting from overrides (e.g., case_id from variable)
    processed_overrides = {}
    for key, value in overrides.items():
        if isinstance(value, str) and value.startswith('{') and value.endswith('}'):
            # This is a variable reference, keep as-is for Tavern to resolve
            processed_overrides[key] = value
        else:
            processed_overrides[key] = value
    
    data_generators = {
        'case': {
            'client_name': f"{test_prefix}_Client_{timestamp}",
            'client_email': f"{test_prefix.lower()}_client_{timestamp}@example.com",
            'case_type': 'GENERAL_INQUIRY',
            'priority': 'MEDIUM',
            'status': 'OPEN'
        },
        'document': {
            'file_name': f"{test_prefix}_Document_{timestamp}.txt",
            'file_type': 'TEXT',
            'file_size': 1024,
            'content_hash': f"hash_{timestamp}",
            'is_analyzed': False
        },
        'communication': {
            'communication_type': 'EMAIL',
            'direction': 'INBOUND',
            'subject': f"{test_prefix} Test Communication {timestamp}",
            'content': f"Test communication content generated at {timestamp}",
            'sender_email': f"{test_prefix.lower()}_{timestamp}@example.com"
        },
        'agent_conversation': {
            'status': 'ACTIVE',
            'conversation_type': 'GENERAL'
        },
        'agent_message': {
            'sender': 'USER',
            'content': f"{test_prefix} test message content {timestamp}",
            'message_type': 'TEXT'
        },
        'agent_context': {
            'context_type': 'CASE_BACKGROUND',
            'content': f"{test_prefix} context content {timestamp}",
            'priority': 1
        },
        'error_log': {
            'component': 'TAVERN_TESTING',
            'error_type': 'TEST_ERROR',
            'severity': 'LOW',
            'message': f"{test_prefix} test error {timestamp}",
            'details': {'test': True, 'timestamp': timestamp}
        }
    }
    
    base_data = data_generators.get(resource_type, {})
    base_data.update(processed_overrides)
    return base_data


def generate_test_data_with_overrides(resource_type: str, overrides_str: str = "") -> Dict[str, Any]:
    """
    Generate test data with string-based overrides for Tavern function calls
    Format: "key1=value1:key2=value2"
    """
    overrides = {}
    if overrides_str:
        for pair in overrides_str.split(':'):
            if '=' in pair:
                key, value = pair.split('=', 1)
                # Try to parse as different types
                if value.lower() in ('true', 'false'):
                    overrides[key] = value.lower() == 'true'
                elif value.isdigit():
                    overrides[key] = int(value)
                elif value.replace('.', '').isdigit():
                    overrides[key] = float(value)
                else:
                    overrides[key] = value
    
    return generate_test_data(resource_type, **overrides)


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


def validate_response_structure(response: Dict[str, Any], expected_fields: list) -> bool:
    """Validate that response contains expected fields"""
    return all(field in response for field in expected_fields)