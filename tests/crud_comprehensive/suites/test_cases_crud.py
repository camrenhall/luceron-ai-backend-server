"""
Cases CRUD Testing Suite - Refactored to use Base Class
Demonstrates resource-specific customizations on top of common patterns
"""

from typing import Dict, Any

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from suites.base_crud_test import BaseCRUDTest


class TestCasesCRUD(BaseCRUDTest):
    """Cases-specific CRUD testing using base class"""
    
    @property
    def resource_name(self) -> str:
        return "cases"
    
    def get_update_data(self) -> Dict[str, Any]:
        """Cases-specific update data"""
        return {"status": "CLOSED"}
    
    def get_searchable_test_data(self, orchestrator) -> Dict[str, Any]:
        """Cases-specific searchable data"""
        return {
            "client_name": f"{orchestrator.config.test_data_prefix}_SearchTest_Company"
        }
    
    def get_search_params(self) -> Dict[str, Any]:
        """Cases-specific search parameters"""
        return {"client_name": "SearchTest"}
    
    def get_invalid_test_data(self) -> Dict[str, Any]:
        """Cases-specific invalid data for validation tests"""
        return {
            "client_name": "",  # Empty name
            # Missing client_email
        }