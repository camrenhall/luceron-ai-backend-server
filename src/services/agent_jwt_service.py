"""
Agent JWT service for generating and validating minimal agent tokens
"""

import jwt
import time
import logging
from typing import Dict, Any
from datetime import datetime, timedelta

from config.service_permissions import is_valid_agent_role

logger = logging.getLogger(__name__)

# JWT configuration
AGENT_JWT_SECRET = "your-agent-jwt-secret-key"  # Should be environment variable in production
AGENT_JWT_ALGORITHM = "HS256"
AGENT_JWT_EXPIRY_MINUTES = 1440  # 24-hour access tokens

class AgentJWTService:
    """Service for generating and validating minimal agent JWTs"""
    
    def __init__(self, secret_key: str = AGENT_JWT_SECRET):
        self.secret_key = secret_key
        self.algorithm = AGENT_JWT_ALGORITHM
    
    def generate_agent_jwt(self, agent_role: str) -> str:
        """
        Generate minimal JWT with just role claim
        
        Args:
            agent_role: The agent role (e.g., "communications_agent")
            
        Returns:
            JWT token string
            
        Raises:
            ValueError: If agent role is not configured
        """
        # Validate role exists in our configuration
        if not is_valid_agent_role(agent_role):
            raise ValueError(f"Unknown agent role: {agent_role}")
        
        current_time = int(time.time())
        expiry_time = current_time + (AGENT_JWT_EXPIRY_MINUTES * 60)
        
        # Minimal JWT payload - backend resolves permissions
        payload = {
            "iss": "luceron-agent-system",
            "sub": agent_role,  # This is the role/agent_type
            "iat": current_time,
            "exp": expiry_time
        }
        
        token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
        
        logger.info(f"Generated 24-hour access token for agent role: {agent_role}")
        return token
    
    def validate_and_decode_jwt(self, token: str) -> Dict[str, Any]:
        """
        Validate JWT signature and decode payload
        
        Args:
            token: JWT token string
            
        Returns:
            Decoded JWT payload
            
        Raises:
            jwt.InvalidTokenError: If token is invalid
        """
        try:
            payload = jwt.decode(
                token, 
                self.secret_key, 
                algorithms=[self.algorithm],
                options={"verify_aud": False}  # Skip audience verification for MVP
            )
            
            # Validate required fields exist
            if 'sub' not in payload:
                raise jwt.InvalidTokenError("Missing 'sub' claim")
            
            agent_role = payload['sub']
            
            # Validate role still exists in configuration
            if not is_valid_agent_role(agent_role):
                raise jwt.InvalidTokenError(f"Invalid agent role: {agent_role}")
            
            logger.debug(f"Successfully validated JWT for agent role: {agent_role}")
            return payload
            
        except jwt.ExpiredSignatureError:
            logger.warning("JWT token has expired")
            raise jwt.InvalidTokenError("Token has expired")
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid JWT token: {str(e)}")
            raise
    
    def generate_access_token(self, agent_role: str, service_id: str) -> str:
        """
        Generate access token for authenticated service
        
        Args:
            agent_role: Agent role for permissions
            service_id: Service that requested the token
            
        Returns:
            24-hour access token
        """
        if not is_valid_agent_role(agent_role):
            raise ValueError(f"Unknown agent role: {agent_role}")
        
        current_time = int(time.time())
        expiry_time = current_time + (AGENT_JWT_EXPIRY_MINUTES * 60)
        
        # Access token payload with service context
        payload = {
            "iss": "luceron-agent-system",
            "sub": agent_role,  # Agent role for permissions
            "aud": "luceron-api",
            "service_id": service_id,  # Which service requested this token
            "iat": current_time,
            "exp": expiry_time
        }
        
        token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
        
        logger.info(f"Generated access token for service {service_id} with role {agent_role}")
        return token
    
    def get_agent_role_from_token(self, token: str) -> str:
        """
        Extract agent role from JWT token
        
        Args:
            token: JWT token string
            
        Returns:
            Agent role string
        """
        payload = self.validate_and_decode_jwt(token)
        return payload['sub']


# Global service instance
agent_jwt_service = AgentJWTService()


# Convenience functions
def generate_agent_jwt(agent_role: str) -> str:
    """Generate JWT for specific agent role (legacy - use generate_access_token)"""
    return agent_jwt_service.generate_agent_jwt(agent_role)

def generate_access_token(agent_role: str, service_id: str) -> str:
    """Generate 24-hour access token for authenticated service"""
    return agent_jwt_service.generate_access_token(agent_role, service_id)

def validate_agent_jwt(token: str) -> Dict[str, Any]:
    """Validate and decode agent JWT"""
    return agent_jwt_service.validate_and_decode_jwt(token)

def get_agent_role_from_jwt(token: str) -> str:
    """Extract agent role from JWT"""
    return agent_jwt_service.get_agent_role_from_token(token)