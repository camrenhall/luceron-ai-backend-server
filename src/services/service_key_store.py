"""
Service key store using lightweight key-value storage for service authentication
"""

import json
import os
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, asdict
from pathlib import Path

logger = logging.getLogger(__name__)

@dataclass
class ServiceIdentity:
    """Service identity with authentication details"""
    service_id: str           # "communications_agent_service"
    service_name: str         # "Communications Agent Service"
    agent_role: str           # "communications_agent"
    public_key: str           # RSA public key in PEM format
    is_active: bool
    created_at: str           # ISO format datetime

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ServiceIdentity":
        """Create from dictionary"""
        return cls(**data)


class ServiceKeyStore:
    """
    Lightweight key-value store for service authentication data
    
    Uses JSON file storage for MVP - can be easily replaced with Redis/DynamoDB later
    """
    
    def __init__(self, storage_path: str = "src/config/service_keys.json"):
        self.storage_path = Path(storage_path)
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_storage_exists()
    
    def _ensure_storage_exists(self):
        """Create storage file if it doesn't exist"""
        if not self.storage_path.exists():
            self._save_data({})
            logger.info(f"Created service key store at {self.storage_path}")
    
    def _load_data(self) -> Dict[str, Any]:
        """Load data from storage"""
        try:
            with open(self.storage_path, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.error(f"Error loading service key store: {e}")
            return {}
    
    def _save_data(self, data: Dict[str, Any]):
        """Save data to storage"""
        try:
            with open(self.storage_path, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving service key store: {e}")
            raise
    
    def register_service(self, service_identity: ServiceIdentity) -> bool:
        """
        Register a new service identity
        
        Args:
            service_identity: Service identity to register
            
        Returns:
            bool: True if registered successfully
        """
        try:
            data = self._load_data()
            
            # Check if service already exists
            if service_identity.service_id in data:
                logger.warning(f"Service {service_identity.service_id} already exists")
                return False
            
            # Store service identity
            data[service_identity.service_id] = service_identity.to_dict()
            self._save_data(data)
            
            logger.info(f"Registered service: {service_identity.service_id} -> {service_identity.agent_role}")
            return True
            
        except Exception as e:
            logger.error(f"Error registering service {service_identity.service_id}: {e}")
            return False
    
    def get_service(self, service_id: str) -> Optional[ServiceIdentity]:
        """
        Get service identity by ID
        
        Args:
            service_id: Service identifier
            
        Returns:
            ServiceIdentity if found, None otherwise
        """
        try:
            data = self._load_data()
            service_data = data.get(service_id)
            
            if not service_data:
                return None
            
            return ServiceIdentity.from_dict(service_data)
            
        except Exception as e:
            logger.error(f"Error retrieving service {service_id}: {e}")
            return None
    
    
    def deactivate_service(self, service_id: str) -> bool:
        """
        Deactivate a service (soft delete)
        
        Args:
            service_id: Service identifier
            
        Returns:
            bool: True if deactivated successfully
        """
        try:
            data = self._load_data()
            
            if service_id not in data:
                logger.warning(f"Service {service_id} not found")
                return False
            
            data[service_id]['is_active'] = False
            self._save_data(data)
            
            logger.info(f"Deactivated service: {service_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error deactivating service {service_id}: {e}")
            return False
    
    def list_active_services(self) -> List[ServiceIdentity]:
        """
        Get list of all active services
        
        Returns:
            List of active ServiceIdentity objects
        """
        try:
            data = self._load_data()
            active_services = []
            
            for service_data in data.values():
                if service_data.get('is_active', True):
                    active_services.append(ServiceIdentity.from_dict(service_data))
            
            return active_services
            
        except Exception as e:
            logger.error(f"Error listing active services: {e}")
            return []
    
    def service_exists(self, service_id: str) -> bool:
        """
        Check if service exists and is active
        
        Args:
            service_id: Service identifier
            
        Returns:
            bool: True if service exists and is active
        """
        service = self.get_service(service_id)
        return service is not None and service.is_active


# Global service key store instance
service_key_store = ServiceKeyStore()


# Convenience functions
def register_service(service_identity: ServiceIdentity) -> bool:
    """Register a new service"""
    return service_key_store.register_service(service_identity)

def get_service(service_id: str) -> Optional[ServiceIdentity]:
    """Get service by ID"""
    return service_key_store.get_service(service_id)


def service_exists(service_id: str) -> bool:
    """Check if service exists and is active"""
    return service_key_store.service_exists(service_id)