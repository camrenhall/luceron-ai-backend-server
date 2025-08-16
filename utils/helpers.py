"""
Utility functions and helpers
"""

import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

def parse_uploaded_timestamp(timestamp_str: str) -> datetime:
    """Parse uploaded timestamp handling timezone properly"""
    try:
        # Handle ISO format with 'Z' (UTC)
        if timestamp_str.endswith('Z'):
            timestamp_str = timestamp_str.replace('Z', '+00:00')
        
        # Parse the timestamp - FIX: Parse timestamp_str, not recursive call
        uploaded_at = datetime.fromisoformat(timestamp_str)
        
        # Convert to UTC and make timezone-naive for database storage
        if uploaded_at.tzinfo is not None:
            uploaded_at = uploaded_at.astimezone(timezone.utc).replace(tzinfo=None)
        
        return uploaded_at
        
    except Exception as e:
        logger.warning(f"Failed to parse timestamp '{timestamp_str}': {e}")
        # Return current UTC time as fallback
        return datetime.utcnow()