"""
Case management API routes
"""

import logging
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Depends, Query
import asyncpg

from models.case import CaseCreateRequest, CaseUpdateRequest, CaseSearchQuery, CaseSearchResponse, DateOperator
from models.enums import CaseStatus
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
                request.client_phone, CaseStatus.OPEN.value, datetime.utcnow())
                
                # Note: requested_documents data is now stored elsewhere
                
            
            return {
                "case_id": str(case_id),
                "client_name": request.client_name,
                "client_email": request.client_email,
                "client_phone": request.client_phone,
                "status": CaseStatus.OPEN.value
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
                "last_communication_date": last_comm['created_at'].isoformat() if last_comm else None
            }
            
    except Exception as e:
        logger.error(f"Failed to get case: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.put("/{case_id}")
async def update_case(
    case_id: str,
    request: CaseUpdateRequest,
    _: bool = Depends(AuthConfig.get_auth_dependency())
):
    """Update case details"""
    db_pool = get_db_pool()
    
    try:
        async with db_pool.acquire() as conn:
            # Check if case exists
            existing_case = await conn.fetchrow(
                "SELECT * FROM cases WHERE case_id = $1", case_id
            )
            
            if not existing_case:
                raise HTTPException(status_code=404, detail="Case not found")
            
            # Build dynamic update query based on provided fields
            update_fields = []
            update_values = []
            param_count = 1
            
            if request.client_name is not None:
                update_fields.append(f"client_name = ${param_count}")
                update_values.append(request.client_name)
                param_count += 1
                
            if request.client_email is not None:
                update_fields.append(f"client_email = ${param_count}")
                update_values.append(request.client_email)
                param_count += 1
                
            if request.client_phone is not None:
                update_fields.append(f"client_phone = ${param_count}")
                update_values.append(request.client_phone)
                param_count += 1
                
            if request.status is not None:
                update_fields.append(f"status = ${param_count}")
                update_values.append(request.status.value)
                param_count += 1
            
            if not update_fields:
                raise HTTPException(status_code=400, detail="No fields provided for update")
            
            # Always update the updated_at timestamp (assuming it exists or we add it)
            update_fields.append(f"updated_at = ${param_count}")
            update_values.append(datetime.utcnow())
            update_values.append(case_id)  # for WHERE clause
            
            query = f"""
                UPDATE cases 
                SET {', '.join(update_fields)}
                WHERE case_id = ${param_count + 1}
                RETURNING *
            """
            
            updated_case = await conn.fetchrow(query, *update_values)
            
            return {
                "case_id": str(updated_case['case_id']),
                "client_name": updated_case['client_name'],
                "client_email": updated_case['client_email'],
                "client_phone": updated_case['client_phone'],
                "status": updated_case['status'],
                "created_at": updated_case['created_at'].isoformat()
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update case: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.delete("/{case_id}")
async def delete_case(
    case_id: str,
    _: bool = Depends(AuthConfig.get_auth_dependency())
):
    """Delete a case and all associated data"""
    db_pool = get_db_pool()
    
    try:
        async with db_pool.acquire() as conn:
            async with conn.transaction():
                # Check if case exists
                existing_case = await conn.fetchrow(
                    "SELECT * FROM cases WHERE case_id = $1", case_id
                )
                
                if not existing_case:
                    raise HTTPException(status_code=404, detail="Case not found")
                
                # Delete associated communications
                await conn.execute(
                    "DELETE FROM client_communications WHERE case_id = $1", case_id
                )
                
                # Delete any documents associated with the case
                await conn.execute(
                    "DELETE FROM documents WHERE case_id = $1", case_id
                )
                
                # Delete any document analysis associated with the case
                await conn.execute(
                    "DELETE FROM document_analysis WHERE case_id = $1", case_id
                )
                
                # Finally delete the case
                await conn.execute(
                    "DELETE FROM cases WHERE case_id = $1", case_id
                )
                
                return {
                    "message": "Case and all associated data deleted successfully",
                    "deleted_case_id": case_id,
                    "client_name": existing_case['client_name']
                }
                
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete case: {e}")
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
                       da.analysis_status, da.analyzed_at, da.model_used, da.context_summary_created
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
                    "model_used": row['model_used'],
                    "context_summary_created": row['context_summary_created']
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

@router.post("/search")
async def search_cases(
    query: CaseSearchQuery,
    _: bool = Depends(AuthConfig.get_auth_dependency())
):
    """Search cases with flexible filtering"""
    db_pool = get_db_pool()
    
    try:
        async with db_pool.acquire() as conn:
            # Check if pg_trgm extension is available for fuzzy matching
            if query.use_fuzzy_matching:
                ext_check = await conn.fetchval(
                    "SELECT 1 FROM pg_extension WHERE extname = 'pg_trgm'"
                )
                if not ext_check:
                    logger.warning("pg_trgm extension not available, falling back to standard search")
                    query.use_fuzzy_matching = False
            # Build dynamic WHERE clause based on provided filters
            where_conditions = []
            query_params = []
            param_count = 1
            
            # Client name search (with optional fuzzy matching)
            if query.client_name:
                if query.use_fuzzy_matching:
                    # Use trigram similarity for fuzzy matching
                    where_conditions.append(f"similarity(c.client_name, ${param_count}) > ${param_count + 1}")
                    query_params.extend([query.client_name, query.fuzzy_threshold])
                    param_count += 2
                else:
                    # Standard LIKE search
                    where_conditions.append(f"LOWER(c.client_name) LIKE LOWER(${param_count})")
                    query_params.append(f"%{query.client_name}%")
                    param_count += 1
            
            # Client email search (with optional fuzzy matching)
            if query.client_email:
                if query.use_fuzzy_matching:
                    # Use trigram similarity for fuzzy matching
                    where_conditions.append(f"similarity(c.client_email, ${param_count}) > ${param_count + 1}")
                    query_params.extend([query.client_email, query.fuzzy_threshold])
                    param_count += 2
                else:
                    # Standard LIKE search
                    where_conditions.append(f"LOWER(c.client_email) LIKE LOWER(${param_count})")
                    query_params.append(f"%{query.client_email}%")
                    param_count += 1
            
            # Client phone search (partial match)
            if query.client_phone:
                where_conditions.append(f"c.client_phone LIKE ${param_count}")
                query_params.append(f"%{query.client_phone}%")
                param_count += 1
            
            # Status filter (exact match)
            if query.status:
                where_conditions.append(f"c.status = ${param_count}")
                query_params.append(query.status.value)
                param_count += 1
            
            # Created_at date filter
            if query.created_at:
                date_condition, date_params = _build_date_condition("c.created_at", query.created_at, param_count)
                where_conditions.append(date_condition)
                query_params.extend(date_params)
                param_count += len(date_params)
            
            # Last communication date filter - this is more complex as it requires subquery
            having_conditions = []
            if query.last_communication_date:
                date_condition, date_params = _build_date_condition("MAX(cc.created_at)", query.last_communication_date, param_count)
                having_conditions.append(date_condition)
                query_params.extend(date_params)
                param_count += len(date_params)
            
            # Build the base query with LEFT JOIN for communications
            base_query = """
                SELECT c.case_id, c.client_name, c.client_email, c.client_phone, 
                       c.status, c.created_at, MAX(cc.created_at) as last_communication_date
                FROM cases c
                LEFT JOIN client_communications cc ON c.case_id = cc.case_id
            """
            
            # Add WHERE clause if we have conditions
            if where_conditions:
                base_query += f" WHERE {' AND '.join(where_conditions)}"
            
            # Add GROUP BY (required because of LEFT JOIN and MAX)
            base_query += " GROUP BY c.case_id, c.client_name, c.client_email, c.client_phone, c.status, c.created_at"
            
            # Add HAVING clause if we have last communication date filter
            if having_conditions:
                base_query += f" HAVING {' AND '.join(having_conditions)}"
            
            # Count query for total results
            count_query = f"""
                SELECT COUNT(*) FROM (
                    {base_query}
                ) as filtered_cases
            """
            
            # Execute count query
            count_query_params = query_params.copy()
            total_count = await conn.fetchval(count_query, *count_query_params)
            
            # Add ORDER BY and LIMIT/OFFSET for main query
            # Use fuzzy matching relevance for ordering if enabled
            if query.use_fuzzy_matching and (query.client_name or query.client_email):
                order_clause = "ORDER BY "
                order_parts = []
                
                if query.client_name:
                    order_parts.append(f"similarity(c.client_name, ${param_count}) DESC")
                    query_params.append(query.client_name)
                    param_count += 1
                if query.client_email:
                    order_parts.append(f"similarity(c.client_email, ${param_count}) DESC")
                    query_params.append(query.client_email)
                    param_count += 1
                
                order_parts.append("c.created_at DESC")
                order_clause += ", ".join(order_parts)
            else:
                order_clause = "ORDER BY c.created_at DESC"
            
            main_query = base_query + f"""
                {order_clause}
                LIMIT ${param_count} OFFSET ${param_count + 1}
            """
            query_params.extend([query.limit, query.offset])
            
            # Execute main query
            rows = await conn.fetch(main_query, *query_params)
            
            # Format results
            cases = []
            for row in rows:
                cases.append({
                    "case_id": str(row['case_id']),
                    "client_name": row['client_name'],
                    "client_email": row['client_email'],
                    "client_phone": row['client_phone'],
                    "status": row['status'],
                    "created_at": row['created_at'].isoformat(),
                    "last_communication_date": row['last_communication_date'].isoformat() if row['last_communication_date'] else None
                })
            
            return CaseSearchResponse(
                total_count=total_count,
                cases=cases,
                limit=query.limit,
                offset=query.offset
            )
            
    except Exception as e:
        logger.error(f"Failed to search cases: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

def _build_date_condition(column_name: str, date_filter, param_start: int):
    """Build SQL condition for date filtering"""
    conditions = []
    params = []
    
    if date_filter.operator == DateOperator.GT:
        conditions.append(f"{column_name} > ${param_start}")
        params.append(date_filter.value)
    elif date_filter.operator == DateOperator.GTE:
        conditions.append(f"{column_name} >= ${param_start}")
        params.append(date_filter.value)
    elif date_filter.operator == DateOperator.LT:
        conditions.append(f"{column_name} < ${param_start}")
        params.append(date_filter.value)
    elif date_filter.operator == DateOperator.LTE:
        conditions.append(f"{column_name} <= ${param_start}")
        params.append(date_filter.value)
    elif date_filter.operator == DateOperator.EQ:
        # For equality, we'll use a range within the same day to handle time differences
        conditions.append(f"{column_name}::date = ${param_start}::date")
        params.append(date_filter.value)
    elif date_filter.operator == DateOperator.BETWEEN:
        if date_filter.end_value is None:
            raise HTTPException(status_code=400, detail="end_value is required for BETWEEN operator")
        conditions.append(f"{column_name} BETWEEN ${param_start} AND ${param_start + 1}")
        params.extend([date_filter.value, date_filter.end_value])
    
    return " AND ".join(conditions), params

@router.get("")
async def list_cases(
    limit: int = Query(50, ge=1, le=500, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    _: bool = Depends(AuthConfig.get_auth_dependency())
):
    """List all cases with pagination"""
    db_pool = get_db_pool()
    
    try:
        async with db_pool.acquire() as conn:
            # Count total cases
            total_count = await conn.fetchval("SELECT COUNT(*) FROM cases")
            
            # Get cases with last communication date
            rows = await conn.fetch("""
                SELECT c.case_id, c.client_name, c.client_email, c.client_phone, 
                       c.status, c.created_at, MAX(cc.created_at) as last_communication_date
                FROM cases c
                LEFT JOIN client_communications cc ON c.case_id = cc.case_id
                GROUP BY c.case_id, c.client_name, c.client_email, c.client_phone, c.status, c.created_at
                ORDER BY c.created_at DESC
                LIMIT $1 OFFSET $2
            """, limit, offset)
            
            # Format results
            cases = []
            for row in rows:
                cases.append({
                    "case_id": str(row['case_id']),
                    "client_name": row['client_name'],
                    "client_email": row['client_email'],
                    "client_phone": row['client_phone'],
                    "status": row['status'],
                    "created_at": row['created_at'].isoformat(),
                    "last_communication_date": row['last_communication_date'].isoformat() if row['last_communication_date'] else None
                })
            
            return CaseSearchResponse(
                total_count=total_count,
                cases=cases,
                limit=limit,
                offset=offset
            )
            
    except Exception as e:
        logger.error(f"Failed to list cases: {e}")
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
                WHERE c.status = $2
                GROUP BY c.case_id, c.client_email, c.client_name, c.client_phone, c.status
                HAVING MAX(cc.created_at) IS NULL OR MAX(cc.created_at) < $1
                ORDER BY MAX(cc.created_at) ASC NULLS FIRST
                LIMIT 20
            """, cutoff_date, CaseStatus.OPEN.value)
            
            cases = []
            for row in rows:
                cases.append({
                    "case_id": row['case_id'],
                    "client_email": row['client_email'],
                    "client_name": row['client_name'],
                    "client_phone": row['client_phone'],
                    "status": row['status'],
                    "last_communication_date": row['last_communication_date'].isoformat() if row['last_communication_date'] else None
                })
            
            return {"found_cases": len(cases), "cases": cases}
            
    except Exception as e:
        logger.error(f"Failed to get pending cases: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

