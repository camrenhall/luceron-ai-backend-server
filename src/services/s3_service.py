"""
S3 upload service
"""

import logging
from config.settings import s3_client, S3_BUCKET_NAME, AWS_REGION

logger = logging.getLogger(__name__)

async def upload_to_s3(file_data: bytes, s3_key: str, content_type: str = "image/png") -> str:
    """Upload file data to S3 and return the S3 location"""
    try:
        s3_client.put_object(
            Bucket=S3_BUCKET_NAME,
            Key=s3_key,
            Body=file_data,
            ContentType=content_type
        )
        s3_location = f"https://{S3_BUCKET_NAME}.s3.{AWS_REGION}.amazonaws.com/{s3_key}"
        return s3_location
    except Exception as e:
        logger.error(f"Failed to upload to S3: {e}")
        raise