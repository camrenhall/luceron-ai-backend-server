"""
OAuth2 token endpoint for service authentication
"""

import logging
from datetime import datetime
from fastapi import APIRouter, HTTPException, Form
from typing import Dict, Any

from services.service_auth import verify_service_jwt
from services.agent_jwt_service import generate_access_token

router = APIRouter()
logger = logging.getLogger(__name__)

class OAuth2TokenResponse:
    """OAuth2 token response model"""
    
    def __init__(self, access_token: str, token_type: str = "Bearer", expires_in: int = 3600, scope: str = None):
        self.access_token = access_token
        self.token_type = token_type
        self.expires_in = expires_in
        self.scope = scope
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON response"""
        response = {
            "access_token": self.access_token,
            "token_type": self.token_type,
            "expires_in": self.expires_in
        }
        if self.scope:
            response["scope"] = self.scope
        return response


@router.post("/oauth2/token")
async def oauth2_token(
    grant_type: str = Form(...),
    client_assertion_type: str = Form(...),
    client_assertion: str = Form(...)
) -> Dict[str, Any]:
    """
    OAuth2 token endpoint using client_credentials flow with JWT assertion
    
    Request format:
    - grant_type: "client_credentials"
    - client_assertion_type: "urn:ietf:params:oauth:client-assertion-type:jwt-bearer"
    - client_assertion: Service JWT signed with private key
    
    Returns:
    - access_token: 60-minute JWT for API access
    - token_type: "Bearer"
    - expires_in: 3600 (seconds)
    - scope: Agent role scope
    """
    
    logger.info("OAuth2 token request received")
    
    try:
        # Validate grant type
        if grant_type != "client_credentials":
            logger.warning(f"Invalid grant_type: {grant_type}")
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "unsupported_grant_type",
                    "error_description": "Only client_credentials grant type is supported"
                }
            )
        
        # Validate client assertion type
        expected_assertion_type = "urn:ietf:params:oauth:client-assertion-type:jwt-bearer"
        if client_assertion_type != expected_assertion_type:
            logger.warning(f"Invalid client_assertion_type: {client_assertion_type}")
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "invalid_client",
                    "error_description": "Invalid client_assertion_type"
                }
            )
        
        # Verify service JWT
        service_identity = verify_service_jwt(client_assertion)
        if not service_identity:
            logger.warning("Service authentication failed")
            raise HTTPException(
                status_code=401,
                detail={
                    "error": "invalid_client",
                    "error_description": "Service authentication failed"
                }
            )
        
        logger.info(f"Service authenticated: {service_identity.service_id} -> {service_identity.agent_role}")
        
        # Generate access token for the service's agent role
        access_token = generate_access_token(
            agent_role=service_identity.agent_role,
            service_id=service_identity.service_id
        )
        
        
        # Create OAuth2 response
        token_response = OAuth2TokenResponse(
            access_token=access_token,
            token_type="Bearer",
            expires_in=3600,  # 60 minutes in seconds
            scope=f"agent:{service_identity.agent_role}"
        )
        
        logger.info(f"Access token issued for service: {service_identity.service_id}")
        
        return token_response.to_dict()
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Unexpected error in OAuth2 token endpoint: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "server_error",
                "error_description": "Internal server error"
            }
        )


@router.get("/oauth2/.well-known/openid_configuration")
async def openid_configuration() -> Dict[str, Any]:
    """
    OpenID Connect discovery endpoint (optional but helpful for debugging)
    """
    return {
        "issuer": "luceron-agent-system",
        "token_endpoint": "/oauth2/token",
        "grant_types_supported": ["client_credentials"],
        "token_endpoint_auth_methods_supported": ["private_key_jwt"],
        "token_endpoint_auth_signing_alg_values_supported": ["RS256"]
    }


@router.get("/oauth2/health")
async def oauth2_health() -> Dict[str, str]:
    """
    Health check endpoint for OAuth2 service
    """
    return {
        "status": "healthy",
        "service": "oauth2-token-endpoint",
        "timestamp": datetime.utcnow().isoformat()
    }