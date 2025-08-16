"""
Document analysis service
"""

import logging
import httpx
from database.connection import get_db_pool
from config.settings import DOCUMENT_ANALYSIS_AGENT_URL

logger = logging.getLogger(__name__)

async def trigger_document_analysis(document_id: str, case_id: str, s3_location: str, workflow_id: str):
    """Background task to trigger document analysis agent"""
    db_pool = get_db_pool()
    
    try:
        logger.info(f"🔄 Triggering analysis for document {document_id} with workflow {workflow_id}")
        
        # Update document status to analyzing
        async with db_pool.acquire() as conn:
            await conn.execute(
                "UPDATE documents SET status = 'analyzing' WHERE document_id = $1",
                document_id
            )
        
        # Call Document Analysis Agent
        async with httpx.AsyncClient(timeout=60.0) as client:
            analysis_request = {
                "case_id": case_id,
                "document_ids": [document_id],
                "case_context": f"Single document upload analysis for document {document_id}",
                "workflow_id": workflow_id
            }
            
            response = await client.post(
                f"{DOCUMENT_ANALYSIS_AGENT_URL}/workflows/trigger-analysis",
                json=analysis_request
            )
            
            if response.status_code == 200:
                result = response.json()
                workflow_id = result.get("workflow_id")
                logger.info(f"✅ Analysis triggered successfully: workflow {workflow_id}")
            else:
                logger.error(f"❌ Analysis trigger failed: {response.status_code} - {response.text}")
                
                # Update document status to failed
                async with db_pool.acquire() as conn:
                    await conn.execute(
                        "UPDATE documents SET status = 'failed' WHERE document_id = $1",
                        document_id
                    )
                
    except Exception as e:
        logger.error(f"Background analysis trigger failed for {document_id}: {e}")
        
        # Update document status to failed
        try:
            async with db_pool.acquire() as conn:
                await conn.execute(
                    "UPDATE documents SET status = 'failed' WHERE document_id = $1",
                    document_id
                )
        except Exception as db_error:
            logger.error(f"Failed to update document status: {db_error}")