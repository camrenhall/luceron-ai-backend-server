"""
Migration Verification Test
Quick test to verify API-only migration is working
"""

import pytest
import asyncio

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from core.test_orchestrator import APITestOrchestrator
from core.data_factory import DataFactory


@pytest.mark.smoke
class TestMigrationVerification:
    """Verify the API-only migration is working correctly"""
    
    def test_data_factory_no_database(self):
        """Test that DataFactory works without database dependencies"""
        factory = DataFactory()
        
        # Test case generation
        case_data, case_id = factory.generate_case()
        assert "API_TEST_" in case_data["client_name"]
        assert case_data["status"] == "OPEN"
        assert "@crud-test.example.com" in case_data["client_email"]
        
        # Test document generation
        doc_data, doc_id = factory.generate_document(case_id)
        assert doc_data["case_id"] == case_id
        assert doc_data["status"] == "PENDING"
        
        print("✅ DataFactory working without database dependencies")
    
    async def test_orchestrator_initialization(self, clean_orchestrator: APITestOrchestrator):
        """Test that APITestOrchestrator initializes correctly"""
        orch = clean_orchestrator
        
        # Test basic properties
        assert orch.config is not None
        assert orch.rest_client is not None
        assert orch.data_factory is not None
        assert orch.results == []
        
        # Test setup/teardown (should not fail)
        await orch.setup()
        await orch.teardown()
        
        print("✅ APITestOrchestrator initializing without database dependencies")
    
    def test_config_simplified(self):
        """Test that config has been simplified correctly"""
        from config import get_config
        
        config = get_config()
        
        # Should have these essential properties
        assert hasattr(config, 'api_base_url')
        assert hasattr(config, 'oauth_service_id') 
        assert hasattr(config, 'oauth_private_key')
        assert hasattr(config, 'oauth_audience')
        
        # Should NOT have these database properties
        assert not hasattr(config, 'qa_database_url')
        assert not hasattr(config, 'test_data_prefix')
        assert not hasattr(config, 'enable_database_validation')
        
        print("✅ Configuration simplified correctly")


# Direct execution test
if __name__ == "__main__":
    def test_basic_functionality():
        """Test basic functionality without pytest"""
        print("🧪 Testing basic functionality...")
        
        # Test DataFactory
        factory = DataFactory()
        case_data, case_id = factory.generate_case()
        print(f"   DataFactory: {case_data['client_name']}")
        
        # Test Orchestrator 
        async def test_orch():
            orch = APITestOrchestrator()
            await orch.setup()
            print("   APITestOrchestrator: Initialized successfully")
            await orch.teardown()
        
        asyncio.run(test_orch())
        
        print("✅ All basic functionality working!")
    
    test_basic_functionality()