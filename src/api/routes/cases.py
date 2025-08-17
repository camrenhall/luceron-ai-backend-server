"""
Case management API routes
"""

import logging
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Depends
import asyncpg

from models.case import CaseCreateRequest
from database.connection import get_db_pool
from utils.auth import AuthConfig

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("")
async def create_case(
    request: CaseCreateRequest,
    _: bool = Depends(AuthConfig.get_auth_dependency())
):
    """Create a new case"""
    db_pool = get_db_pool()
    
    try:
        async with db_pool.acquire() as conn:
            async with conn.transaction():
                # Create the case and get the generated UUID
                case_id = await conn.fetchval("""
                    INSERT INTO cases (client_name, client_email, client_phone, status, created_at)
                    VALUES ($1, $2, $3, $4, $5)
                    RETURNING case_id
                """, 
                request.client_name, request.client_email, 
                request.client_phone, "awaiting_documents", datetime.utcnow())
                
                # Insert requested documents with returned UUIDs
                requested_doc_ids = []
                for doc in request.requested_documents:
                    doc_id = await conn.fetchval("""
                        INSERT INTO requested_documents (case_id, document_name, description, requested_at, updated_at)
                        VALUES ($1, $2, $3, $4, $5)
                        RETURNING requested_doc_id
                    """,
                    case_id, doc.document_name, doc.description, 
                    datetime.utcnow(), datetime.utcnow())
                    requested_doc_ids.append({
                        "requested_doc_id": str(doc_id),
                        "document_name": doc.document_name,
                        "description": doc.description
                    })
                
                # Update any existing workflows that were created without a case_id
                # and should be associated with this new case (e.g., communication workflows)
                await conn.execute("""
                    UPDATE workflow_states 
                    SET case_id = $1 
                    WHERE case_id IS NULL 
                    AND agent_type = 'CommunicationsAgent'
                    AND created_at >= NOW() - INTERVAL '1 hour'
                """, case_id)
            
            return {
                "case_id": str(case_id),
                "client_name": request.client_name,
                "client_email": request.client_email,
                "client_phone": request.client_phone,
                "status": "awaiting_documents",
                "requested_documents": requested_doc_ids
            }
            
    except asyncpg.UniqueViolationError:
        raise HTTPException(status_code=409, detail="Case ID already exists")
    except Exception as e:
        logger.error(f"Failed to create case: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.get("/{case_id}")
async def get_case(
    case_id: str,
    _: bool = Depends(AuthConfig.get_auth_dependency())
):
    """Get case details"""
    db_pool = get_db_pool()
    
    try:
        async with db_pool.acquire() as conn:
            case_row = await conn.fetchrow(
                "SELECT * FROM cases WHERE case_id = $1", case_id
            )
            
            if not case_row:
                raise HTTPException(status_code=404, detail="Case not found")
            
            # Get requested documents for this case
            requested_docs = await conn.fetch("""
                SELECT requested_doc_id, document_name, description, is_completed, completed_at, 
                       is_flagged_for_review, notes, requested_at, updated_at
                FROM requested_documents 
                WHERE case_id = $1 
                ORDER BY requested_at ASC
            """, case_id)
            
            # Get last communication date from client_communications
            last_comm = await conn.fetchrow("""
                SELECT created_at 
                FROM client_communications 
                WHERE case_id = $1 
                ORDER BY created_at DESC 
                LIMIT 1
            """, case_id)
            
            return {
                "case_id": case_row['case_id'],
                "client_name": case_row['client_name'],
                "client_email": case_row['client_email'],
                "client_phone": case_row['client_phone'],
                "status": case_row['status'],
                "created_at": case_row['created_at'].isoformat(),
                "last_communication_date": last_comm['created_at'].isoformat() if last_comm else None,
                "requested_documents": [
                    {
                        "requested_doc_id": str(doc['requested_doc_id']),
                        "document_name": doc['document_name'],
                        "description": doc['description'],
                        "is_completed": doc['is_completed'],
                        "completed_at": doc['completed_at'].isoformat() if doc['completed_at'] else None,
                        "is_flagged_for_review": doc['is_flagged_for_review'],
                        "notes": doc['notes'],
                        "requested_at": doc['requested_at'].isoformat(),
                        "updated_at": doc['updated_at'].isoformat()
                    } for doc in requested_docs
                ]
            }
            
    except Exception as e:
        logger.error(f"Failed to get case: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.get("/{case_id}/communications")
async def get_case_communications(
    case_id: str,
    _: bool = Depends(AuthConfig.get_auth_dependency())
):
    """Get communication history for a case"""
    db_pool = get_db_pool()
    
    try:
        async with db_pool.acquire() as conn:
            # Get case details
            case_row = await conn.fetchrow("SELECT * FROM cases WHERE case_id = $1", case_id)
            if not case_row:
                raise HTTPException(status_code=404, detail="Case not found")
            
            # Get requested documents for this case
            requested_docs = await conn.fetch("""
                SELECT requested_doc_id, document_name, description, is_completed, completed_at, 
                       is_flagged_for_review, notes, requested_at, updated_at
                FROM requested_documents 
                WHERE case_id = $1 
                ORDER BY requested_at ASC
            """, case_id)
            
            # Get communication history from new table
            communications = await conn.fetch("""
                SELECT communication_id, channel, direction, status, opened_at, sender, recipient, 
                       subject, message_content, created_at, sent_at, resend_id
                FROM client_communications 
                WHERE case_id = $1 
                ORDER BY created_at DESC
                LIMIT 50
            """, case_id)
            
            return {
                "case_id": case_id,
                "client_name": case_row['client_name'],
                "client_email": case_row['client_email'],
                "client_phone": case_row['client_phone'],
                "case_status": case_row['status'],
                "requested_documents": [
                    {
                        "requested_doc_id": str(doc['requested_doc_id']),
                        "document_name": doc['document_name'],
                        "description": doc['description'],
                        "is_completed": doc['is_completed'],
                        "completed_at": doc['completed_at'].isoformat() if doc['completed_at'] else None,
                        "is_flagged_for_review": doc['is_flagged_for_review'],
                        "notes": doc['notes'],
                        "requested_at": doc['requested_at'].isoformat(),
                        "updated_at": doc['updated_at'].isoformat()
                    } for doc in requested_docs
                ],
                "last_communication_date": communications[0]['created_at'].isoformat() if communications else None,
                "communication_summary": {
                    "total_communications": len(communications),
                    "last_communication_date": communications[0]['created_at'].isoformat() if communications else None
                },
                "communications": [
                    {
                        "communication_id": str(comm['communication_id']),
                        "channel": comm['channel'],
                        "direction": comm['direction'],
                        "status": comm['status'],
                        "opened_at": comm['opened_at'].isoformat() if comm['opened_at'] else None,
                        "sender": comm['sender'],
                        "recipient": comm['recipient'],
                        "subject": comm['subject'],
                        "message_content": comm['message_content'],
                        "created_at": comm['created_at'].isoformat(),
                        "sent_at": comm['sent_at'].isoformat() if comm['sent_at'] else None,
                        "resend_id": comm['resend_id']
                    } for comm in communications
                ]
            }
            
    except Exception as e:
        logger.error(f"Failed to get case communications: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.get("/{case_id}/analysis-summary")
async def get_case_analysis_summary(
    case_id: str,
    _: bool = Depends(AuthConfig.get_auth_dependency())
):
    """Get analysis summary for all documents in a case"""
    db_pool = get_db_pool()
    
    try:
        async with db_pool.acquire() as conn:
            # Get case details
            case_row = await conn.fetchrow("SELECT * FROM cases WHERE case_id = $1", case_id)
            if not case_row:
                raise HTTPException(status_code=404, detail="Case not found")
            
            # Get analysis results for all documents in the case
            analysis_rows = await conn.fetch("""
                SELECT da.analysis_id, da.document_id, d.original_file_name,
                       da.analysis_status, da.analyzed_at, da.model_used
                FROM document_analysis da
                JOIN documents d ON da.document_id = d.document_id
                WHERE da.case_id = $1
                ORDER BY da.analyzed_at DESC
            """, case_id)
            
            analysis_summary = []
            
            for row in analysis_rows:
                analysis_summary.append({
                    "analysis_id": row['analysis_id'],
                    "document_id": row['document_id'],
                    "filename": row['original_file_name'],
                    "analysis_status": row['analysis_status'],
                    "analyzed_at": row['analyzed_at'].isoformat(),
                    "model_used": row['model_used']
                })
            
            return {
                "case_id": case_id,
                "client_name": case_row['client_name'],
                "total_documents_analyzed": len(analysis_summary),
                "analysis_results": analysis_summary
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get case analysis summary: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.get("/pending-reminders")
async def get_pending_reminder_cases(
    _: bool = Depends(AuthConfig.get_auth_dependency())
):
    """Get cases that need reminder emails"""
    db_pool = get_db_pool()
    
    try:
        async with db_pool.acquire() as conn:
            cutoff_date = datetime.utcnow() - timedelta(days=3)
            
            # Get cases and their last communication date from the new table
            rows = await conn.fetch("""
                SELECT c.case_id, c.client_email, c.client_name, c.client_phone, c.status,
                       MAX(cc.created_at) as last_communication_date
                FROM cases c
                LEFT JOIN client_communications cc ON c.case_id = cc.case_id
                WHERE c.status = 'awaiting_documents'
                GROUP BY c.case_id, c.client_email, c.client_name, c.client_phone, c.status
                HAVING MAX(cc.created_at) IS NULL OR MAX(cc.created_at) < $1
                ORDER BY MAX(cc.created_at) ASC NULLS FIRST
                LIMIT 20
            """, cutoff_date)
            
            cases = []
            for row in rows:
                # Get requested documents for each case
                requested_docs = await conn.fetch("""
                    SELECT document_name, description, is_completed
                    FROM requested_documents 
                    WHERE case_id = $1 
                    ORDER BY requested_at ASC
                """, row['case_id'])
                
                cases.append({
                    "case_id": row['case_id'],
                    "client_email": row['client_email'],
                    "client_name": row['client_name'],
                    "client_phone": row['client_phone'],
                    "status": row['status'],
                    "last_communication_date": row['last_communication_date'].isoformat() if row['last_communication_date'] else None,
                    "requested_documents": [
                        {
                            "document_name": doc['document_name'],
                            "description": doc['description'],
                            "is_completed": doc['is_completed']
                        } for doc in requested_docs
                    ]
                })
            
            return {"found_cases": len(cases), "cases": cases}
            
    except Exception as e:
        logger.error(f"Failed to get pending cases: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")