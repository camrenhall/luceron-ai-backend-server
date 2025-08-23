"""
Environment-isolated Agent JWT service for secure token generation and validation
Prevents cross-environment token reuse through environment-specific signing and validation
"""

import jwt
import time
import logging
from typing import Dict, Any
from datetime import datetime, timedelta

from config.service_permissions import is_valid_agent_role, get_service_permissions
from config.settings import JWTEnvironmentConfig, ENV

logger = logging.getLogger(__name__)

class AgentJWTService:
    """Environment-isolated service for generating and validating agent JWTs"""
    
    def __init__(self):
        self.jwt_config = JWTEnvironmentConfig.get_config()
        self.secret_key = self.jwt_config["secret"]
        self.algorithm = self.jwt_config["allowed_algorithms"][0]  # Use first allowed algorithm
        self.issuer = self.jwt_config["issuer"]
        self.audience = self.jwt_config["audience"]
    
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
        expiry_time = current_time + (self.jwt_config["max_token_age"])
        
        # Environment-aware JWT payload with security claims
        payload = {
            "iss": self.issuer,  # Environment-specific issuer
            "sub": agent_role,   # Agent role for permissions
            "aud": self.audience,  # Environment-specific audience
            "environment": ENV,    # Explicit environment claim for validation
            "iat": current_time,
            "exp": expiry_time
        }
        
        token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
        
        logger.info(f"Generated 15-minute access token for agent role: {agent_role}")
        return token
    
    def validate_and_decode_jwt(self, token: str) -> Dict[str, Any]:
        """
        Validate JWT with comprehensive security checks against tampering
        
        Args:
            token: JWT token string
            
        Returns:
            Decoded JWT payload
            
        Raises:
            jwt.InvalidTokenError: If token is invalid, tampered, or from wrong environment
        """
        try:
            # Hardened JWT validation with strict security controls
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=self.jwt_config["allowed_algorithms"],  # Strict algorithm allowlist
                audience=self.audience,  # Environment-specific audience validation
                issuer=self.issuer,      # Environment-specific issuer validation
                options={
                    "require_exp": True,     # Expiration required
                    "require_iat": True,     # Issued-at required  
                    "require_sub": True,     # Subject required
                    "require_aud": True,     # Audience required
                    "require_iss": True,     # Issuer required
                    "verify_signature": True # Signature verification mandatory
                }
            )
            
            # Validate environment claim matches current environment
            token_env = payload.get('environment')
            if not token_env:
                raise jwt.InvalidTokenError("Missing environment claim")
            if token_env != ENV:
                raise jwt.InvalidTokenError(f"Environment mismatch: token='{token_env}', server='{ENV}'")
            
            # Validate required claims are present
            required_claims = ["sub", "environment", "iss", "aud", "exp", "iat"]
            for claim in required_claims:
                if claim not in payload:
                    raise jwt.InvalidTokenError(f"Missing required claim: {claim}")
            
            agent_role = payload['sub']
            
            # Validate role exists and is authorized for current environment
            if not is_valid_agent_role(agent_role):
                raise jwt.InvalidTokenError(f"Invalid agent role: {agent_role}")
                
            # Validate agent role is authorized for current environment
            permissions = get_service_permissions(agent_role)
            if permissions and "environments" in permissions:
                if ENV not in permissions["environments"]:
                    raise jwt.InvalidTokenError(f"Agent '{agent_role}' not authorized for environment '{ENV}'")
            
            logger.debug(f"Successfully validated environment-isolated JWT for agent role: {agent_role} in {ENV}")
            return payload
            
        except jwt.ExpiredSignatureError:
            logger.warning("JWT token has expired")
            raise jwt.InvalidTokenError("Token has expired")
        except jwt.InvalidAudienceError:
            logger.warning(f"JWT audience validation failed - expected: {self.audience}")
            raise jwt.InvalidTokenError("Invalid audience")
        except jwt.InvalidIssuerError:
            logger.warning(f"JWT issuer validation failed - expected: {self.issuer}")
            raise jwt.InvalidTokenError("Invalid issuer")
        except jwt.InvalidTokenError as e:
            logger.warning(f"JWT validation failed: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"JWT validation error: {str(e)}")
            raise jwt.InvalidTokenError("Token validation failed")
    
    def generate_access_token(self, agent_role: str, service_id: str) -> str:
        """
        Generate access token for authenticated service
        
        Args:
            agent_role: Agent role for permissions
            service_id: Service that requested the token
            
        Returns:
            15-minute access token
        """
        if not is_valid_agent_role(agent_role):
            raise ValueError(f"Unknown agent role: {agent_role}")
        
        current_time = int(time.time())
        expiry_time = current_time + (self.jwt_config["max_token_age"])
        
        # Environment-aware access token payload with service context
        payload = {
            "iss": self.issuer,       # Environment-specific issuer
            "sub": agent_role,        # Agent role for permissions
            "aud": self.audience,     # Environment-specific audience
            "environment": ENV,       # Explicit environment claim
            "service_id": service_id, # Which service requested this token
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
    """Generate 15-minute access token for authenticated service"""
    return agent_jwt_service.generate_access_token(agent_role, service_id)

def validate_agent_jwt(token: str) -> Dict[str, Any]:
    """Validate and decode agent JWT"""
    return agent_jwt_service.validate_and_decode_jwt(token)

def get_agent_role_from_jwt(token: str) -> str:
    """Extract agent role from JWT"""
    return agent_jwt_service.get_agent_role_from_token(token)