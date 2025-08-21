"""
Cases service - business logic for case management
"""

import logging
from typing import Dict, Any, List, Optional
from services.base_service import BaseService, ServiceResult

logger = logging.getLogger(__name__)

class CasesService(BaseService):
    """Service for case management operations"""
    
    def __init__(self, role: str = "api"):
        super().__init__("cases", role)
    
    async def create_case(
        self,
        client_name: str,
        client_email: str,
        client_phone: Optional[str] = None,
        status: str = "OPEN"
    ) -> ServiceResult:
        """
        Create a new case
        
        Args:
            client_name: Name of the client
            client_email: Email address of the client
            client_phone: Phone number of the client (optional)
            status: Initial case status (default: OPEN)
            
        Returns:
            ServiceResult with created case data
        """
        case_data = {
            "client_name": client_name,
            "client_email": client_email,
            "status": status
        }
        
        if client_phone:
            case_data["client_phone"] = client_phone
        
        logger.info(f"Creating new case for client: {client_email}")
        return await self.create(case_data)
    
    async def get_case_by_id(self, case_id: str) -> ServiceResult:
        """
        Get a case by its ID
        
        Args:
            case_id: UUID of the case
            
        Returns:
            ServiceResult with case data
        """
        return await self.get_by_id(case_id)
    
    async def get_cases_by_client_email(self, client_email: str) -> ServiceResult:
        """
        Get all cases for a specific client email
        
        Args:
            client_email: Email address of the client
            
        Returns:
            ServiceResult with list of cases
        """
        return await self.get_by_field("client_email", client_email)
    
    async def get_cases_by_status(self, status: str, limit: int = 100) -> ServiceResult:
        """
        Get cases by status
        
        Args:
            status: Case status to filter by
            limit: Maximum number of cases to return
            
        Returns:
            ServiceResult with filtered cases
        """
        return await self.get_by_field("status", status, limit)
    
    async def update_case_status(self, case_id: str, status: str) -> ServiceResult:
        """
        Update the status of a case
        
        Args:
            case_id: UUID of the case
            status: New status value
            
        Returns:
            ServiceResult with updated case data
        """
        logger.info(f"Updating case {case_id} status to: {status}")
        return await self.update(case_id, {"status": status})
    
    async def update_client_info(
        self,
        case_id: str,
        client_name: Optional[str] = None,
        client_email: Optional[str] = None,
        client_phone: Optional[str] = None
    ) -> ServiceResult:
        """
        Update client information for a case
        
        Args:
            case_id: UUID of the case
            client_name: New client name (optional)
            client_email: New client email (optional)
            client_phone: New client phone (optional)
            
        Returns:
            ServiceResult with updated case data
        """
        update_data = {}
        
        if client_name is not None:
            update_data["client_name"] = client_name
        if client_email is not None:
            update_data["client_email"] = client_email
        if client_phone is not None:
            update_data["client_phone"] = client_phone
        
        if not update_data:
            return ServiceResult(
                success=False,
                error="No client information provided to update",
                error_type="INVALID_REQUEST"
            )
        
        logger.info(f"Updating client info for case {case_id}")
        return await self.update(case_id, update_data)
    
    async def search_cases(
        self,
        client_name_pattern: Optional[str] = None,
        client_email_pattern: Optional[str] = None,
        status_list: Optional[List[str]] = None,
        limit: int = 100,
        offset: int = 0
    ) -> ServiceResult:
        """
        Search cases with various filters
        
        Args:
            client_name_pattern: Pattern to match client names (ILIKE)
            client_email_pattern: Pattern to match client emails (ILIKE)
            status_list: List of statuses to filter by (IN)
            limit: Maximum number of results
            offset: Number of results to skip
            
        Returns:
            ServiceResult with matching cases
        """
        filters = {}
        
        if client_name_pattern:
            filters["client_name"] = {
                "op": "ILIKE", 
                "value": f"%{client_name_pattern}%"
            }
        
        if client_email_pattern:
            filters["client_email"] = {
                "op": "ILIKE",
                "value": f"%{client_email_pattern}%"
            }
        
        if status_list:
            filters["status"] = {
                "op": "IN",
                "value": status_list
            }
        
        order_by = [{"field": "created_at", "dir": "desc"}]
        
        logger.info(f"Searching cases with filters: {filters}")
        return await self.read(
            filters=filters,
            order_by=order_by,
            limit=limit,
            offset=offset
        )
    
    async def get_recent_cases(self, limit: int = 50) -> ServiceResult:
        """
        Get most recently created cases
        
        Args:
            limit: Maximum number of cases to return
            
        Returns:
            ServiceResult with recent cases
        """
        order_by = [{"field": "created_at", "dir": "desc"}]
        
        return await self.read(
            order_by=order_by,
            limit=limit
        )

# Global service instance
_cases_service: Optional[CasesService] = None

def get_cases_service() -> CasesService:
    """Get the global cases service instance"""
    global _cases_service
    if _cases_service is None:
        _cases_service = CasesService()
    return _cases_service