"""
Lightweight API-only testing configuration
"""

import os
from dataclasses import dataclass
from typing import Optional
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

@dataclass
class TestConfig:
    """Lightweight API contract testing configuration"""
    
    # API Testing Only
    api_base_url: str = os.getenv('TEST_API_BASE_URL', 'http://localhost:8080')
    
    # OAuth Authentication
    oauth_service_id: str = os.getenv('OAUTH_SERVICE_ID', 'qa_comprehensive_test_service')
    oauth_private_key: str = os.getenv('TEST_OAUTH_PRIVATE_KEY', '').replace('\\n', '\n')
    oauth_audience: str = os.getenv('OAUTH_AUDIENCE', 'luceron-auth-server')
    
    # Concurrency Control
    max_concurrent_tests: int = int(os.getenv('MAX_CONCURRENT_TESTS', '5'))
    
    def validate(self) -> list[str]:
        """Validate configuration and return list of errors"""
        errors = []
        
        if not self.oauth_private_key:
            errors.append("OAUTH_PRIVATE_KEY is required for authentication")
            
        return errors


def get_config() -> TestConfig:
    """Get validated test configuration"""
    config = TestConfig()
    errors = config.validate()
    
    if errors:
        raise ValueError(f"Configuration errors: {', '.join(errors)}")
        
    return config