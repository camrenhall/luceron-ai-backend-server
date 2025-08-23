"""
Service authentication using RSA 2048-bit key verification
"""

import jwt
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import load_pem_public_key

from services.service_key_store import get_service, ServiceIdentity

logger = logging.getLogger(__name__)

class ServiceAuthenticator:
    """
    Service authentication using RSA signature verification
    
    Validates service JWTs signed with private keys against stored public keys
    """
    
    # Service JWT configuration
    SERVICE_JWT_ALGORITHM = "RS256"
    SERVICE_JWT_MAX_AGE_MINUTES = 15  # Service JWTs expire in 15 minutes
    EXPECTED_AUDIENCE = "luceron-auth-server"
    
    def __init__(self):
        self.algorithm = self.SERVICE_JWT_ALGORITHM
    
    def verify_service_jwt(self, service_jwt: str) -> Optional[ServiceIdentity]:
        """
        Verify service JWT and return service identity
        
        Args:
            service_jwt: JWT signed by service's private key
            
        Returns:
            ServiceIdentity if valid, None if invalid
        """
        try:
            # Decode JWT header to get key ID (service_id)
            unverified_header = jwt.get_unverified_header(service_jwt)
            unverified_payload = jwt.decode(service_jwt, options={"verify_signature": False})
            
            service_id = unverified_payload.get('iss')  # Issuer is service_id
            
            if not service_id:
                logger.warning("Service JWT missing 'iss' claim")
                return None
            
            # Get service identity and public key
            service_identity = get_service(service_id)
            if not service_identity:
                logger.warning(f"Unknown service ID: {service_id}")
                return None
            
            if not service_identity.is_active:
                logger.warning(f"Inactive service attempted authentication: {service_id}")
                return None
            
            # Load public key for verification
            try:
                public_key = load_pem_public_key(service_identity.public_key.encode())
            except Exception as e:
                logger.error(f"Invalid public key for service {service_id}: {e}")
                return None
            
            # Verify JWT signature and claims with relaxed timing validation
            # We disable built-in iat validation and handle timing in _validate_service_claims
            payload = jwt.decode(
                service_jwt,
                public_key,
                algorithms=[self.algorithm],
                audience=self.EXPECTED_AUDIENCE,
                options={"verify_iat": False}  # Disable iat validation - we handle timing manually
            )
            
            # Validate claims
            if not self._validate_service_claims(payload, service_id):
                return None
            
            logger.info(f"Service authentication successful: {service_id}")
            return service_identity
            
        except jwt.ExpiredSignatureError:
            logger.warning("Service JWT has expired")
            return None
        except jwt.InvalidAudienceError:
            logger.warning("Service JWT has invalid audience")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid service JWT: {e}")
            return None
        except Exception as e:
            logger.error(f"Service authentication error: {e}")
            return None
    
    def _validate_service_claims(self, payload: Dict[str, Any], expected_service_id: str) -> bool:
        """
        Validate service JWT claims
        
        Args:
            payload: Decoded JWT payload
            expected_service_id: Expected service ID from header
            
        Returns:
            bool: True if claims are valid
        """
        # Check required claims
        required_claims = ['iss', 'sub', 'aud', 'exp', 'iat']
        for claim in required_claims:
            if claim not in payload:
                logger.warning(f"Service JWT missing required claim: {claim}")
                return False
        
        # Validate issuer and subject match service ID
        if payload['iss'] != expected_service_id or payload['sub'] != expected_service_id:
            logger.warning("Service JWT iss/sub claims don't match service ID")
            return False
        
        # Validate audience
        if payload['aud'] != self.EXPECTED_AUDIENCE:
            logger.warning(f"Service JWT has wrong audience: {payload['aud']}")
            return False
        
        # Check token age (service JWTs should be short-lived)
        issued_at = datetime.fromtimestamp(payload['iat'])
        max_age = timedelta(minutes=self.SERVICE_JWT_MAX_AGE_MINUTES)
        
        # Use timezone-naive datetime consistently for comparison
        current_time = datetime.utcnow()
        age = current_time - issued_at
        
        logger.debug(f"JWT issued at: {issued_at}, current time: {current_time}, age: {age}, max_age: {max_age}")
        
        if age > max_age:
            logger.warning(f"Service JWT is too old: issued {age} ago, max age {max_age}")
            return False
        
        return True


class ServiceKeyGenerator:
    """
    Utility for generating RSA 2048-bit keypairs for services
    """
    
    @staticmethod
    def generate_keypair() -> tuple[str, str]:
        """
        Generate RSA 2048-bit keypair
        
        Returns:
            Tuple of (private_key_pem, public_key_pem)
        """
        try:
            # Generate private key
            private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=2048
            )
            
            # Get public key
            public_key = private_key.public_key()
            
            # Serialize private key
            private_pem = private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            ).decode()
            
            # Serialize public key
            public_pem = public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            ).decode()
            
            return private_pem, public_pem
            
        except Exception as e:
            logger.error(f"Error generating keypair: {e}")
            raise


class ServiceJWTHelper:
    """
    Helper for services to create authentication JWTs
    
    This would be used by service implementations to create JWTs for authentication
    """
    
    @staticmethod
    def create_service_jwt(service_id: str, private_key_pem: str) -> str:
        """
        Create a service authentication JWT
        
        Args:
            service_id: Service identifier
            private_key_pem: Service private key in PEM format
            
        Returns:
            Service JWT string
        """
        try:
            # Load private key
            private_key = serialization.load_pem_private_key(
                private_key_pem.encode(),
                password=None
            )
            
            # Create JWT payload
            now = datetime.utcnow()
            payload = {
                'iss': service_id,
                'sub': service_id,
                'aud': ServiceAuthenticator.EXPECTED_AUDIENCE,
                'iat': int(now.timestamp()),
                'exp': int((now + timedelta(minutes=ServiceAuthenticator.SERVICE_JWT_MAX_AGE_MINUTES)).timestamp())
            }
            
            # Sign JWT
            service_jwt = jwt.encode(
                payload,
                private_key,
                algorithm=ServiceAuthenticator.SERVICE_JWT_ALGORITHM
            )
            
            return service_jwt
            
        except Exception as e:
            logger.error(f"Error creating service JWT: {e}")
            raise


# Global service authenticator instance
service_authenticator = ServiceAuthenticator()


# Convenience functions
def verify_service_jwt(service_jwt: str) -> Optional[ServiceIdentity]:
    """Verify service JWT and return service identity"""
    return service_authenticator.verify_service_jwt(service_jwt)

def generate_service_keypair() -> tuple[str, str]:
    """Generate RSA 2048-bit keypair for service"""
    return ServiceKeyGenerator.generate_keypair()

def create_service_jwt(service_id: str, private_key_pem: str) -> str:
    """Create service authentication JWT"""
    return ServiceJWTHelper.create_service_jwt(service_id, private_key_pem)