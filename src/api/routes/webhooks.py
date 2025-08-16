"""
Webhook API routes
"""

import uuid
import logging
from fastapi import APIRouter, HTTPException, BackgroundTasks

from models.webhook import S3UploadWebhookRequest, ResendWebhook
from models.document import DocumentUploadResponse
from services.document_analysis import trigger_document_analysis
from utils.helpers import parse_uploaded_timestamp
from database.connection import get_db_pool

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/document-uploaded", response_model=DocumentUploadResponse)
async def handle_document_upload(request: S3UploadWebhookRequest, background_tasks: BackgroundTasks):
    """Handle S3 document upload webhook and trigger analysis"""
    db_pool = get_db_pool()
    
    logger.info(f"📄 Document upload webhook received: {request.event}")
    logger.info(f"📄 Files uploaded: {len(request.files)}")
    
    documents_created = 0
    workflow_ids = []
    
    try:
        async with db_pool.acquire() as conn:
            for file_upload in request.files:
                if file_upload.status != "success":
                    logger.warning(f"Skipping failed upload: {file_upload.fileName}")
                    continue
                
                # Extract client email from metadata
                client_email = request.metadata.get("clientEmail")
                if not client_email:
                    logger.error("❌ No clientEmail in webhook metadata")
                    raise HTTPException(status_code=400, detail="Missing clientEmail in webhook metadata")
                
                # Find case by client email
                case_row = await conn.fetchrow(
                    "SELECT case_id FROM cases WHERE client_email = $1 AND status = 'awaiting_documents'",
                    client_email
                )
                
                if not case_row:
                    logger.error(f"❌ CRITICAL: No active case found for client email: {client_email}")
                    logger.error(f"❌ Document upload failed - client {client_email} does not have an active case")
                    raise HTTPException(
                        status_code=404, 
                        detail=f"No active case found for client email: {client_email}. Please ensure a case exists with status 'awaiting_documents'."
                    )
                
                case_id = case_row['case_id']
                
                # Generate document ID
                document_id = f"doc_{uuid.uuid4().hex[:12]}"
                
                # Insert document record
                await conn.execute("""
                    INSERT INTO documents 
                    (document_id, case_id, filename, file_size, file_type, 
                    s3_location, s3_key, s3_etag, status)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                """,
                document_id, case_id, file_upload.fileName, file_upload.fileSize,
                file_upload.fileType, file_upload.s3Location, file_upload.s3Key,
                file_upload.s3ETag, "uploaded")
                
                documents_created += 1
                
                logger.info(f"📄 Created document record: {document_id} for case {case_id}")
                
                # Generate workflow ID for tracking
                workflow_id = f"wf_upload_{uuid.uuid4().hex[:8]}"
                workflow_ids.append(workflow_id)
                
                # Trigger document analysis in background
                background_tasks.add_task(
                    trigger_document_analysis,
                    document_id,
                    case_id,
                    file_upload.s3Location,
                    workflow_id
                )
        
        return DocumentUploadResponse(
            documents_created=documents_created,
            analysis_triggered=documents_created > 0,
            workflow_ids=workflow_ids,
            message=f"Successfully processed {documents_created} document uploads"
        )
        
    except Exception as e:
        logger.error(f"Document upload webhook failed: {e}")
        raise HTTPException(status_code=500, detail=f"Webhook processing failed: {str(e)}")

@router.post("/resend")
async def handle_resend_webhook(webhook: ResendWebhook):
    """Handle Resend webhooks (email.opened, email.delivered, email.failed, email.bounced)"""
    db_pool = get_db_pool()
    
    logger.info(f"📧 Resend webhook received: type={webhook.type}, email_id={webhook.data.email_id}")
    
    try:
        async with db_pool.acquire() as conn:
            if webhook.type == "email.opened":
                # Parse the opened timestamp (top-level created_at is when email was opened)
                opened_at = parse_uploaded_timestamp(webhook.created_at)
                
                # Update opened_at timestamp AND set status to "opened"
                result = await conn.execute("""
                    UPDATE client_communications 
                    SET opened_at = $1, status = 'opened'
                    WHERE resend_id = $2
                """, opened_at, webhook.data.email_id)
                
                action = "opened"
                
            elif webhook.type == "email.failed":
                # Only update status to "failed" (no timestamp update)
                result = await conn.execute("""
                    UPDATE client_communications 
                    SET status = 'failed'
                    WHERE resend_id = $1
                """, webhook.data.email_id)
                
                failure_reason = webhook.data.failed.reason if webhook.data.failed else "unknown"
                logger.info(f"❌ Email failed: reason={failure_reason}")
                action = f"failed (reason: {failure_reason})"
                
            elif webhook.type == "email.bounced":
                # Only update status to "failed" (no timestamp update)
                result = await conn.execute("""
                    UPDATE client_communications 
                    SET status = 'failed'
                    WHERE resend_id = $1
                """, webhook.data.email_id)
                
                bounce_info = ""
                if webhook.data.bounce:
                    bounce_info = f"{webhook.data.bounce.type}/{webhook.data.bounce.subType}: {webhook.data.bounce.message}"
                
                logger.info(f"🔄 Email bounced: {bounce_info}")
                action = f"bounced ({bounce_info})"
                
            elif webhook.type == "email.delivered":
                # Only update status to "delivered" (no timestamp update)
                result = await conn.execute("""
                    UPDATE client_communications 
                    SET status = 'delivered'
                    WHERE resend_id = $1
                """, webhook.data.email_id)
                
                action = "delivered"
                
            else:
                logger.warning(f"⚠️ Unsupported webhook type: {webhook.type}")
                return {"status": "unsupported", "type": webhook.type, "message": "Webhook type not supported"}
            
            # Check if any row was updated
            rows_updated = int(result.split()[-1]) if result.startswith("UPDATE") else 0
            
            if rows_updated > 0:
                logger.info(f"✅ Email {action}: Updated {rows_updated} record(s) for email_id={webhook.data.email_id}")
                return {"status": "updated", "email_id": webhook.data.email_id, "rows_updated": rows_updated, "action": action}
            else:
                # Email ID not found - log but don't fail (as per requirements)
                logger.info(f"ℹ️ Resend webhook: email_id={webhook.data.email_id} not found in database (likely from another system)")
                return {"status": "not_found", "email_id": webhook.data.email_id, "message": "Email ID not found in database"}
        
    except Exception as e:
        logger.error(f"Resend webhook processing failed: {e}")
        raise HTTPException(status_code=500, detail=f"Webhook processing failed: {str(e)}")