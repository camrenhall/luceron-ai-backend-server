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
        client_name: Optional[str] = None,
        client_email: Optional[str] = None,
        client_phone: Optional[str] = None,
        status: Optional[str] = None,
        created_at_filter: Optional[Dict] = None,
        last_communication_date_filter: Optional[Dict] = None,
        use_fuzzy_matching: bool = False,
        fuzzy_threshold: float = 0.3,
        limit: int = 100,
        offset: int = 0
    ) -> ServiceResult:
        """
        Enhanced search cases with comprehensive filtering
        
        Args:
            client_name: Pattern to match client names
            client_email: Pattern to match client emails  
            client_phone: Pattern to match client phone
            status: Exact status to match
            created_at_filter: Date filter for created_at field
            last_communication_date_filter: Date filter for last communication
            use_fuzzy_matching: Enable fuzzy matching (simplified version)
            fuzzy_threshold: Similarity threshold (0.0-1.0)
            limit: Maximum number of results
            offset: Number of results to skip
            
        Returns:
            ServiceResult with matching cases and total count
        """
        logger.info(f"Enhanced search cases with filters")
        
        try:
            filters = {}
            
            # Client name search
            if client_name:
                if use_fuzzy_matching:
                    # Simplified fuzzy matching - use broader ILIKE patterns
                    # Note: True fuzzy matching requires database extensions
                    filters["client_name"] = {
                        "op": "ILIKE", 
                        "value": f"%{client_name}%"
                    }
                else:
                    filters["client_name"] = {
                        "op": "ILIKE", 
                        "value": f"%{client_name}%"
                    }
            
            # Client email search
            if client_email:
                if use_fuzzy_matching:
                    filters["client_email"] = {
                        "op": "ILIKE",
                        "value": f"%{client_email}%"
                    }
                else:
                    filters["client_email"] = {
                        "op": "ILIKE",
                        "value": f"%{client_email}%"
                    }
            
            # Client phone search
            if client_phone:
                filters["client_phone"] = {
                    "op": "ILIKE",
                    "value": f"%{client_phone}%"
                }
            
            # Status filter
            if status:
                filters["status"] = status
            
            # Date filters (simplified - exact operators only)
            if created_at_filter:
                op = created_at_filter.get('operator')
                value = created_at_filter.get('value')
                
                if op and value:
                    date_ops = {
                        'gt': '>',
                        'gte': '>=', 
                        'lt': '<',
                        'lte': '<=',
                        'eq': '='
                    }
                    
                    if op in date_ops:
                        filters["created_at"] = {
                            "op": date_ops[op].upper(),
                            "value": value
                        }
            
            # Order by created_at by default
            order_by = [{"field": "created_at", "dir": "desc"}]
            
            # Get total count first by running query without pagination
            count_result = await self.read(filters=filters, limit=10000, offset=0)
            total_count = count_result.count if count_result.success else 0
            
            # Get filtered results  
            search_result = await self.read(
                filters=filters,
                order_by=order_by,
                limit=limit,
                offset=offset
            )
            
            if not search_result.success:
                return search_result
            
            cases_data = search_result.data
            
            # If last communication date filter is requested, 
            # we need to filter post-query since it requires cross-service integration
            if last_communication_date_filter:
                logger.warning("Last communication date filtering requires cross-service integration - skipping for now")
            
            # Add last communication dates to results
            from services.communications_service import get_communications_service
            communications_service = get_communications_service()
            
            for case in cases_data:
                case_id = case['case_id']
                
                # Get last communication for this case
                comm_result = await communications_service.read(
                    filters={"case_id": case_id},
                    order_by=[{"field": "created_at", "dir": "desc"}],
                    limit=1
                )
                
                if comm_result.success and comm_result.data:
                    last_comm = comm_result.data[0]
                    last_comm_date = last_comm.get('created_at')
                    if last_comm_date:
                        if isinstance(last_comm_date, str):
                            case['last_communication_date'] = last_comm_date
                        else:
                            case['last_communication_date'] = last_comm_date.isoformat()
                    else:
                        case['last_communication_date'] = None
                else:
                    case['last_communication_date'] = None
            
            return ServiceResult(
                success=True,
                data=cases_data,
                count=len(cases_data),
                page_info={
                    "total_count": total_count,
                    "limit": limit,
                    "offset": offset
                }
            )
            
        except Exception as e:
            logger.error(f"Enhanced search cases failed: {e}")
            return ServiceResult(
                success=False,
                error=str(e),
                error_type="EXECUTION_ERROR"
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
    
    async def update_case(self, case_id: str, updates: Dict[str, Any]) -> ServiceResult:
        """
        Update case with arbitrary fields
        
        Args:
            case_id: UUID of the case
            updates: Dictionary of fields to update
            
        Returns:
            ServiceResult with updated case data
        """
        logger.info(f"Updating case {case_id} with fields: {list(updates.keys())}")
        return await self.update(case_id, updates)
    
    async def delete_case(self, case_id: str) -> ServiceResult:
        """
        Delete a case (note: this will be restricted by foreign key constraints)
        
        Args:
            case_id: UUID of the case to delete
            
        Returns:
            ServiceResult indicating success/failure
        """
        logger.info(f"Attempting to delete case {case_id}")
        
        try:
            # Use the base service delete method
            return await self.delete(case_id)
        except Exception as e:
            logger.error(f"Delete case failed for {case_id}: {e}")
            return ServiceResult(
                success=False,
                error=str(e),
                error_type="EXECUTION_ERROR"
            )
    
    async def list_cases_with_pagination(
        self,
        limit: int = 100,
        offset: int = 0
    ) -> ServiceResult:
        """
        List all cases with pagination
        
        Args:
            limit: Maximum number of cases to return
            offset: Number of cases to skip
            
        Returns:
            ServiceResult with paginated cases
        """
        order_by = [{"field": "created_at", "dir": "desc"}]
        
        return await self.read(
            order_by=order_by,
            limit=limit,
            offset=offset
        )
    
    async def get_cases_needing_reminders(self, days_since_last_contact: int = 3) -> ServiceResult:
        """
        Get cases that need reminder emails
        
        Args:
            days_since_last_contact: Days since last communication
            
        Returns:
            ServiceResult with cases needing reminders
        """
        from datetime import datetime, timedelta
        logger.info(f"Getting cases needing reminders (>{days_since_last_contact} days)")
        
        try:
            # Get all open cases first
            filters = {"status": "OPEN"}
            order_by = [{"field": "created_at", "dir": "asc"}]
            
            cases_result = await self.read(
                filters=filters,
                order_by=order_by,
                limit=100
            )
            
            if not cases_result.success:
                return cases_result
            
            # Import communications service
            from services.communications_service import get_communications_service
            communications_service = get_communications_service()
            
            cutoff_date = datetime.utcnow() - timedelta(days=days_since_last_contact)
            cases_needing_reminders = []
            
            # For each case, check if it needs a reminder
            for case in cases_result.data:
                case_id = case['case_id']
                
                # Get last communication for this case
                comm_result = await communications_service.read(
                    filters={"case_id": case_id},
                    order_by=[{"field": "created_at", "dir": "desc"}],
                    limit=1
                )
                
                needs_reminder = False
                last_communication_date = None
                
                if comm_result.success and comm_result.data:
                    last_comm = comm_result.data[0]
                    last_comm_date = last_comm.get('created_at')
                    
                    if last_comm_date:
                        if isinstance(last_comm_date, str):
                            # Parse ISO string to datetime for comparison
                            from datetime import datetime
                            last_comm_dt = datetime.fromisoformat(last_comm_date.replace('Z', '+00:00'))
                        else:
                            last_comm_dt = last_comm_date
                        
                        last_communication_date = last_comm_dt.isoformat()
                        
                        # Check if last communication is older than cutoff
                        if last_comm_dt < cutoff_date:
                            needs_reminder = True
                    else:
                        needs_reminder = True  # No communication date means no communication
                else:
                    needs_reminder = True  # No communications found
                
                if needs_reminder:
                    case_data = {
                        "case_id": case['case_id'],
                        "client_email": case['client_email'],
                        "client_name": case['client_name'],
                        "client_phone": case.get('client_phone'),
                        "status": case['status'],
                        "last_communication_date": last_communication_date
                    }
                    cases_needing_reminders.append(case_data)
            
            return ServiceResult(
                success=True,
                data=cases_needing_reminders,
                count=len(cases_needing_reminders)
            )
            
        except Exception as e:
            logger.error(f"Get cases needing reminders failed: {e}")
            return ServiceResult(
                success=False,
                error=str(e),
                error_type="EXECUTION_ERROR"
            )
    
    async def get_case_communications(self, case_id: str) -> ServiceResult:
        """
        Get communication history for a case
        
        Args:
            case_id: UUID of the case
            
        Returns:
            ServiceResult with communications data
        """
        logger.info(f"Getting communications for case {case_id}")
        
        try:
            # Verify case exists first
            case_result = await self.get_case_by_id(case_id)
            if not case_result.success:
                return case_result  # Return the same error
            
            # Note: This requires communications service integration
            # For now, return empty list - will be implemented with cross-service calls
            return ServiceResult(
                success=True,
                data=[],
                count=0,
                error="Communications integration pending - use communications service directly"
            )
            
        except Exception as e:
            logger.error(f"Get case communications failed for {case_id}: {e}")
            return ServiceResult(
                success=False,
                error=str(e),
                error_type="EXECUTION_ERROR"
            )
    
    async def get_case_analysis_summary(self, case_id: str) -> ServiceResult:
        """
        Get analysis summary for all documents in a case
        
        Args:
            case_id: UUID of the case
            
        Returns:
            ServiceResult with analysis summary data
        """
        logger.info(f"Getting analysis summary for case {case_id}")
        
        try:
            # Verify case exists first
            case_result = await self.get_case_by_id(case_id)
            if not case_result.success:
                return case_result  # Return the same error
            
            case_data = case_result.data[0]
            
            # Get aggregated analysis from documents service
            from services.documents_service import get_document_analysis_service
            documents_service = get_document_analysis_service()
            
            analysis_result = await documents_service.get_aggregated_analysis(case_id)
            if not analysis_result.success:
                logger.warning(f"Failed to get document analysis for case {case_id}: {analysis_result.error}")
                # Return case with empty analysis rather than failing completely
                return ServiceResult(
                    success=True,
                    data={
                        "case_id": case_id,
                        "client_name": case_data['client_name'],
                        "total_documents_analyzed": 0,
                        "analysis_results": []
                    }
                )
            
            # Format the response to match the route's expected structure
            return ServiceResult(
                success=True,
                data={
                    "case_id": case_id,
                    "client_name": case_data['client_name'],
                    "total_documents_analyzed": len(analysis_result.data),
                    "analysis_results": analysis_result.data
                }
            )
            
        except Exception as e:
            logger.error(f"Get case analysis summary failed for {case_id}: {e}")
            return ServiceResult(
                success=False,
                error=str(e),
                error_type="EXECUTION_ERROR"
            )
    
    async def delete_case_cascade(self, case_id: str) -> ServiceResult:
        """
        Delete a case and all associated data (CASCADE)
        
        Args:
            case_id: UUID of the case to delete
            
        Returns:
            ServiceResult indicating success/failure
        """
        logger.warning(f"Attempting cascade delete of case {case_id}")
        
        try:
            # Verify case exists first
            case_result = await self.get_case_by_id(case_id)
            if not case_result.success:
                return case_result  # Return the same error
            
            # Note: This is a complex operation that requires coordination
            # across multiple services. For production, implement proper cascade logic.
            return ServiceResult(
                success=False,
                error="CASCADE delete requires careful implementation - use database triggers or implement cross-service coordination",
                error_type="OPERATION_NOT_SUPPORTED"
            )
            
        except Exception as e:
            logger.error(f"Cascade delete failed for {case_id}: {e}")
            return ServiceResult(
                success=False,
                error=str(e),
                error_type="EXECUTION_ERROR"
            )
    
    async def get_cases_with_last_communication(
        self, 
        limit: int = 100, 
        offset: int = 0
    ) -> ServiceResult:
        """
        Get cases with their last communication date
        
        Args:
            limit: Maximum number of cases to return
            offset: Number of cases to skip
            
        Returns:
            ServiceResult with cases including last communication dates
        """
        logger.info(f"Getting cases with last communication, limit={limit}, offset={offset}")
        
        try:
            # Get basic cases first
            cases_result = await self.list_cases_with_pagination(limit, offset)
            if not cases_result.success:
                return cases_result
            
            # Import communications service
            from services.communications_service import get_communications_service
            communications_service = get_communications_service()
            
            cases_data = cases_result.data
            
            # For each case, get the last communication date
            for case in cases_data:
                case_id = case['case_id']
                
                # Get last communication for this case
                comm_result = await communications_service.read(
                    filters={"case_id": case_id},
                    order_by=[{"field": "created_at", "dir": "desc"}],
                    limit=1
                )
                
                if comm_result.success and comm_result.data:
                    last_comm = comm_result.data[0]
                    last_comm_date = last_comm.get('created_at')
                    if last_comm_date:
                        if isinstance(last_comm_date, str):
                            case['last_communication_date'] = last_comm_date
                        else:
                            case['last_communication_date'] = last_comm_date.isoformat()
                    else:
                        case['last_communication_date'] = None
                else:
                    case['last_communication_date'] = None
            
            return ServiceResult(
                success=True,
                data=cases_data,
                count=cases_result.count,
                page_info=cases_result.page_info
            )
            
        except Exception as e:
            logger.error(f"Get cases with last communication failed: {e}")
            return ServiceResult(
                success=False,
                error=str(e),
                error_type="EXECUTION_ERROR"
            )

# Global service instance
_cases_service: Optional[CasesService] = None

def get_cases_service() -> CasesService:
    """Get the global cases service instance"""
    global _cases_service
    if _cases_service is None:
        _cases_service = CasesService()
    return _cases_service