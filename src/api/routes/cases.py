"""
Case management API routes - Unified Service Layer Architecture
All database operations go through consistent service layer patterns.
No direct database access - unified with Agent Gateway architecture.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, Query

from models.case import CaseCreateRequest, CaseUpdateRequest, CaseSearchQuery, CaseSearchResponse, DateOperator
from models.enums import CaseStatus
from services.cases_service import get_cases_service
from services.communications_service import get_communications_service  
from services.documents_service import get_document_analysis_service
from utils.auth import AuthConfig

# Note: No database imports - all data access through service layer
# This ensures consistency with Agent Gateway and enables unified:
# - Caching strategies
# - Validation logic  
# - Error handling
# - Monitoring and metrics

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("")
async def create_case(
    request: CaseCreateRequest,
    _: bool = Depends(AuthConfig.get_auth_dependency())
):
    """Create a new case"""
    cases_service = get_cases_service()
    
    try:
        result = await cases_service.create_case(
            client_name=request.client_name,
            client_email=request.client_email,
            client_phone=request.client_phone,
            status=CaseStatus.OPEN.value
        )
        
        if not result.success:
            if result.error_type == "CONFLICT" or "unique" in result.error.lower():
                raise HTTPException(status_code=409, detail="Case ID already exists")
            elif result.error_type == "UNAUTHORIZED_OPERATION":
                raise HTTPException(status_code=403, detail=result.error)
            elif result.error_type == "INVALID_QUERY":
                raise HTTPException(status_code=400, detail=result.error)
            else:
                raise HTTPException(status_code=500, detail=result.error)
        
        case_data = result.data[0]
        return {
            "case_id": str(case_data['case_id']),
            "client_name": case_data['client_name'],
            "client_email": case_data['client_email'],
            "client_phone": case_data['client_phone'],
            "status": case_data['status']
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create case: {e}")
        raise HTTPException(status_code=500, detail=f"Service error: {str(e)}")

@router.get("/{case_id}")
async def get_case(
    case_id: str,
    _: bool = Depends(AuthConfig.get_auth_dependency())
):
    """Get case details"""
    cases_service = get_cases_service()
    
    try:
        # Get case data
        result = await cases_service.get_case_by_id(case_id)
        
        if not result.success or not result.data:
            raise HTTPException(status_code=404, detail="Case not found")
        
        case_data = result.data[0]
        
        # Get last communication date using communications service
        from services.communications_service import get_communications_service
        communications_service = get_communications_service()
        
        comm_result = await communications_service.read(
            filters={"case_id": case_id},
            order_by=[{"field": "created_at", "dir": "desc"}],
            limit=1
        )
        
        last_communication_date = None
        if comm_result.success and comm_result.data:
            last_comm = comm_result.data[0]
            last_comm_date = last_comm.get('created_at')
            if last_comm_date:
                if isinstance(last_comm_date, str):
                    last_communication_date = last_comm_date
                else:
                    last_communication_date = last_comm_date.isoformat()
        
        return {
            "case_id": case_data['case_id'],
            "client_name": case_data['client_name'],
            "client_email": case_data['client_email'],
            "client_phone": case_data['client_phone'],
            "status": case_data['status'],
            "created_at": case_data['created_at'].isoformat() if isinstance(case_data['created_at'], datetime) else case_data['created_at'],
            "last_communication_date": last_communication_date
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get case: {e}")
        raise HTTPException(status_code=500, detail=f"Service error: {str(e)}")

@router.put("/{case_id}")
async def update_case(
    case_id: str,
    request: CaseUpdateRequest,
    _: bool = Depends(AuthConfig.get_auth_dependency())
):
    """Update case details"""
    cases_service = get_cases_service()
    
    try:
        # Build update dictionary from request
        updates = {}
        if request.client_name is not None:
            updates["client_name"] = request.client_name
        if request.client_email is not None:
            updates["client_email"] = request.client_email
        if request.client_phone is not None:
            updates["client_phone"] = request.client_phone
        if request.status is not None:
            updates["status"] = request.status.value
        
        if not updates:
            raise HTTPException(status_code=400, detail="No fields provided for update")
        
        result = await cases_service.update_case(case_id, updates)
        
        if not result.success:
            if result.error_type == "RESOURCE_NOT_FOUND":
                raise HTTPException(status_code=404, detail="Case not found")
            elif result.error_type == "INVALID_QUERY":
                raise HTTPException(status_code=400, detail=result.error)
            else:
                raise HTTPException(status_code=500, detail=result.error)
        
        case_data = result.data[0]
        return {
            "case_id": str(case_data['case_id']),
            "client_name": case_data['client_name'],
            "client_email": case_data['client_email'],
            "client_phone": case_data['client_phone'],
            "status": case_data['status'],
            "created_at": case_data['created_at']
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update case: {e}")
        raise HTTPException(status_code=500, detail=f"Service error: {str(e)}")

@router.delete("/{case_id}")
async def delete_case(
    case_id: str,
    _: bool = Depends(AuthConfig.get_auth_dependency())
):
    """Delete a case and all associated data"""
    cases_service = get_cases_service()
    
    try:
        # Get case details first for response
        case_result = await cases_service.get_case_by_id(case_id)
        if not case_result.success:
            if case_result.error_type == "RESOURCE_NOT_FOUND":
                raise HTTPException(status_code=404, detail="Case not found")
            else:
                raise HTTPException(status_code=500, detail=case_result.error)
        
        case_data = case_result.data[0]
        client_name = case_data['client_name']
        
        # Attempt delete
        result = await cases_service.delete_case(case_id)
        
        if not result.success:
            if result.error_type == "RESOURCE_NOT_FOUND":
                raise HTTPException(status_code=404, detail="Case not found")
            elif "foreign key" in result.error.lower() or "CONFLICT" in result.error:
                raise HTTPException(status_code=409, detail="Cannot delete case: foreign key constraints exist. Delete related records first.")
            else:
                raise HTTPException(status_code=500, detail=result.error)
        
        return {
            "message": "Case and all associated data deleted successfully",
            "deleted_case_id": case_id,
            "client_name": client_name
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete case: {e}")
        raise HTTPException(status_code=500, detail=f"Service error: {str(e)}")

@router.get("/{case_id}/communications")
async def get_case_communications(
    case_id: str,
    _: bool = Depends(AuthConfig.get_auth_dependency())
):
    """Get communication history for a case"""
    cases_service = get_cases_service()
    communications_service = get_communications_service()
    
    try:
        # Get case details
        case_result = await cases_service.get_case_by_id(case_id)
        if not case_result.success:
            if case_result.error_type == "RESOURCE_NOT_FOUND":
                raise HTTPException(status_code=404, detail="Case not found")
            else:
                raise HTTPException(status_code=500, detail=case_result.error)
        
        case_data = case_result.data[0]
        
        # Get communications for this case
        comm_result = await communications_service.get_communications_by_case(case_id)
        
        if not comm_result.success:
            logger.warning(f"Failed to get communications for case {case_id}: {comm_result.error}")
            communications = []
        else:
            communications = comm_result.data
        
        # Build response with unified service data
        last_comm_date = None
        if communications:
            # Sort by created_at and get the most recent
            sorted_comms = sorted(communications, key=lambda x: x.get('created_at', ''), reverse=True)
            if sorted_comms:
                last_comm_date = sorted_comms[0].get('created_at')
        
        return {
            "case_id": case_id,
            "client_name": case_data['client_name'],
            "client_email": case_data['client_email'],
            "client_phone": case_data['client_phone'],
            "case_status": case_data['status'],
            "last_communication_date": last_comm_date,
            "communication_summary": {
                "total_communications": len(communications),
                "last_communication_date": last_comm_date
            },
            "communications": [
                {
                    "communication_id": str(comm['communication_id']),
                    "channel": comm['channel'],
                    "direction": comm['direction'],
                    "status": comm['status'],
                    "opened_at": comm.get('opened_at'),
                    "sender": comm['sender'],
                    "recipient": comm['recipient'],
                    "subject": comm['subject'],
                    "message_content": comm['message_content'],
                    "created_at": comm['created_at'],
                    "sent_at": comm.get('sent_at'),
                    "resend_id": comm.get('resend_id')
                } for comm in communications
            ]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get case communications: {e}")
        raise HTTPException(status_code=500, detail=f"Service error: {str(e)}")

@router.get("/{case_id}/analysis-summary")
async def get_case_analysis_summary(
    case_id: str,
    _: bool = Depends(AuthConfig.get_auth_dependency())
):
    """Get analysis summary for all documents in a case"""
    cases_service = get_cases_service()
    
    try:
        result = await cases_service.get_case_analysis_summary(case_id)
        
        if not result.success:
            if result.error_type == "RESOURCE_NOT_FOUND":
                raise HTTPException(status_code=404, detail="Case not found")
            else:
                raise HTTPException(status_code=500, detail=result.error)
        
        return result.data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get case analysis summary: {e}")
        raise HTTPException(status_code=500, detail=f"Service error: {str(e)}")

@router.post("/search")
async def search_cases(
    query: CaseSearchQuery,
    _: bool = Depends(AuthConfig.get_auth_dependency())
):
    """Search cases with flexible filtering"""
    cases_service = get_cases_service()
    
    try:
        # Convert date filters to simple format for service layer
        created_at_filter = None
        if query.created_at:
            created_at_filter = {
                "operator": query.created_at.operator.value,
                "value": query.created_at.value,
                "end_value": getattr(query.created_at, 'end_value', None)
            }
        
        last_communication_date_filter = None  
        if query.last_communication_date:
            last_communication_date_filter = {
                "operator": query.last_communication_date.operator.value,
                "value": query.last_communication_date.value,
                "end_value": getattr(query.last_communication_date, 'end_value', None)
            }
        
        # Call enhanced search service
        result = await cases_service.search_cases(
            client_name=query.client_name,
            client_email=query.client_email,
            client_phone=query.client_phone,
            status=query.status.value if query.status else None,
            created_at_filter=created_at_filter,
            last_communication_date_filter=last_communication_date_filter,
            use_fuzzy_matching=query.use_fuzzy_matching or False,
            fuzzy_threshold=query.fuzzy_threshold or 0.3,
            limit=query.limit,
            offset=query.offset
        )
        
        if not result.success:
            raise HTTPException(status_code=500, detail=result.error)
        
        # Format results for response
        cases = []
        for case_data in result.data:
            cases.append({
                "case_id": str(case_data['case_id']),
                "client_name": case_data['client_name'],
                "client_email": case_data['client_email'],
                "client_phone": case_data['client_phone'],
                "status": case_data['status'],
                "created_at": case_data['created_at'].isoformat() if hasattr(case_data['created_at'], 'isoformat') else case_data['created_at'],
                "last_communication_date": case_data.get('last_communication_date')
            })
        
        total_count = result.page_info.get('total_count', len(cases)) if result.page_info else len(cases)
        
        return CaseSearchResponse(
            total_count=total_count,
            cases=cases,
            limit=query.limit,
            offset=query.offset
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to search cases: {e}")
        raise HTTPException(status_code=500, detail=f"Service error: {str(e)}")

@router.get("")
async def list_cases(
    limit: int = Query(50, ge=1, le=500, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    _: bool = Depends(AuthConfig.get_auth_dependency())
):
    """List all cases with pagination"""
    cases_service = get_cases_service()
    
    try:
        # Get cases with last communication dates
        result = await cases_service.get_cases_with_last_communication(limit, offset)
        
        if not result.success:
            raise HTTPException(status_code=500, detail=result.error)
        
        # Format cases for response
        cases = []
        for case_data in result.data:
            cases.append({
                "case_id": str(case_data['case_id']),
                "client_name": case_data['client_name'],
                "client_email": case_data['client_email'],
                "client_phone": case_data['client_phone'],
                "status": case_data['status'],
                "created_at": case_data['created_at'].isoformat() if hasattr(case_data['created_at'], 'isoformat') else case_data['created_at'],
                "last_communication_date": case_data['last_communication_date']
            })
        
        # Get total count separately (since pagination affects count)
        total_count_result = await cases_service.read(limit=10000, offset=0)
        total_count = total_count_result.count if total_count_result.success else len(cases)
        
        return CaseSearchResponse(
            total_count=total_count,
            cases=cases,
            limit=limit,
            offset=offset
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list cases: {e}")
        raise HTTPException(status_code=500, detail=f"Service error: {str(e)}")

@router.get("/pending-reminders")
async def get_pending_reminder_cases(
    _: bool = Depends(AuthConfig.get_auth_dependency())
):
    """Get cases that need reminder emails"""
    cases_service = get_cases_service()
    
    try:
        result = await cases_service.get_cases_needing_reminders(days_since_last_contact=3)
        
        if not result.success:
            raise HTTPException(status_code=500, detail=result.error)
        
        cases = result.data[:20]  # Limit to 20 like the original implementation
        
        return {"found_cases": len(cases), "cases": cases}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get pending cases: {e}")
        raise HTTPException(status_code=500, detail=f"Service error: {str(e)}")

