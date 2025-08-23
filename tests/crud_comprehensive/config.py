"""
Configuration management for CRUD comprehensive testing suite
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
    """Central configuration for CRUD testing suite"""
    
    
    # Database Testing Mode
    database_mode: str = os.getenv('DB_MODE', 'qa')  # qa, production, hybrid
    
    
    # QA Database Configuration
    qa_database_url: str = os.getenv('QA_DATABASE_URL')
    
    # API Endpoints - Test API container
    api_base_url: str = os.getenv('TEST_API_BASE_URL', 'http://localhost:8080')
    
    # Environment-Isolated OAuth Configuration for QA Testing
    oauth_service_id: str = os.getenv('OAUTH_SERVICE_ID', 'qa_comprehensive_test_service')
    oauth_private_key: str = os.getenv('OAUTH_PRIVATE_KEY', '')
    oauth_audience: str = os.getenv('OAUTH_AUDIENCE', 'luceron-auth-server')  # Service auth audience
    
    # Email Service - Always use dummy key for testing
    resend_api_key: str = "dummy_resend_key_for_testing"
    
    # Performance Thresholds (seconds)
    create_operation_threshold: float = float(os.getenv('CREATE_THRESHOLD', '3.0'))
    read_operation_threshold: float = float(os.getenv('READ_THRESHOLD', '2.0'))
    update_operation_threshold: float = float(os.getenv('UPDATE_THRESHOLD', '2.0'))
    delete_operation_threshold: float = float(os.getenv('DELETE_THRESHOLD', '2.0'))
    
    # Test Behavior - Remove reporting bloat, keep essential validation
    enable_database_validation: bool = True  # Always validate database state
    enable_performance_monitoring: bool = os.getenv('ENABLE_PERF_MONITORING', 'true').lower() == 'true'
    cleanup_test_data: bool = os.getenv('CLEANUP_TEST_DATA', 'true').lower() == 'true'
    max_concurrent_tests: int = int(os.getenv('MAX_CONCURRENT_TESTS', '5'))
    
    # Test Data
    test_data_prefix: str = os.getenv('TEST_DATA_PREFIX', 'CRUD_TEST')
    
    def validate(self) -> list[str]:
        """Validate configuration and return list of errors"""
        errors = []
        
        if not self.qa_database_url:
            errors.append("QA_DATABASE_URL is required")
            
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