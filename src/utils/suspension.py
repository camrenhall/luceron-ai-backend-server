"""
Global suspension state management for emergency kill-switch functionality
"""

import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

class SuspensionManager:
    """
    Global singleton for managing server suspension state
    
    This provides a kill-switch mechanism that suspends all operations
    while keeping the server healthy for Cloud Deploy monitoring.
    """
    
    _instance: Optional['SuspensionManager'] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):
        """Initialize suspension state"""
        self._is_suspended = False
        self._suspended_at: Optional[datetime] = None
        self._suspended_by: Optional[str] = None
        self._suspension_reason: Optional[str] = None
    
    def suspend(self, suspended_by: str, reason: str = "Emergency kill-switch activated"):
        """
        Suspend all server operations
        
        Args:
            suspended_by: Service ID that initiated suspension
            reason: Reason for suspension
        """
        self._is_suspended = True
        self._suspended_at = datetime.utcnow()
        self._suspended_by = suspended_by
        self._suspension_reason = reason
        
        logger.critical(f"🔴 SERVER SUSPENDED by {suspended_by}: {reason}")
    
    def resume(self, resumed_by: str):
        """
        Resume server operations
        
        Args:
            resumed_by: Service ID that initiated resume
        """
        was_suspended = self._is_suspended
        self._is_suspended = False
        previous_suspended_by = self._suspended_by
        
        # Clear suspension state
        self._suspended_at = None
        self._suspended_by = None
        self._suspension_reason = None
        
        if was_suspended:
            logger.warning(f"🟢 SERVER RESUMED by {resumed_by} (was suspended by {previous_suspended_by})")
        else:
            logger.info(f"Resume called by {resumed_by} (server was not suspended)")
    
    @property
    def is_suspended(self) -> bool:
        """Check if server is currently suspended"""
        return self._is_suspended
    
    def get_suspension_info(self) -> dict:
        """Get current suspension information"""
        return {
            "is_suspended": self._is_suspended,
            "suspended_at": self._suspended_at.isoformat() if self._suspended_at else None,
            "suspended_by": self._suspended_by,
            "reason": self._suspension_reason
        }

# Global singleton instance
suspension_manager = SuspensionManager()