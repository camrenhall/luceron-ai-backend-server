"""
Lightweight OAuth-enabled REST client for CRUD testing
Reuses OAuth logic from existing agent_db infrastructure
"""

import asyncio
import time
import jwt
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional
import httpx
from dataclasses import dataclass

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import get_config


@dataclass
class OAuthToken:
    """Simple OAuth token container with expiration"""
    access_token: str
    expires_at: datetime
    
    def is_expired(self, buffer_seconds: int = 60) -> bool:
        return datetime.utcnow() >= (self.expires_at - timedelta(seconds=buffer_seconds))


class RestClient:
    """Lightweight REST client with OAuth authentication"""
    
    def __init__(self):
        self.config = get_config()
        self._cached_token: Optional[OAuthToken] = None
        
    async def _get_access_token(self) -> str:
        """Get valid OAuth access token - matches get_auth_token.py pattern exactly"""
        if self._cached_token is None or self._cached_token.is_expired():
            # Generate JWT client assertion - EXACT pattern from get_auth_token.py
            # Use timezone-naive datetime to match server expectations
            now = datetime.utcnow()
            payload = {
                'iss': self.config.oauth_service_id,
                'sub': self.config.oauth_service_id,
                'aud': self.config.oauth_audience,
                'iat': int(now.timestamp()),
                'exp': int((now + timedelta(minutes=15)).timestamp())
            }
            
            client_assertion = jwt.encode(payload, self.config.oauth_private_key, algorithm='RS256')
            
            # Exchange for access token
            oauth_data = {
                'grant_type': 'client_credentials',
                'client_assertion_type': 'urn:ietf:params:oauth:client-assertion-type:jwt-bearer',
                'client_assertion': client_assertion
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.config.api_base_url}/oauth2/token",
                    data=oauth_data,
                    headers={'Content-Type': 'application/x-www-form-urlencoded'}
                )
                
                if response.status_code != 200:
                    raise RuntimeError(f"OAuth failed: {response.status_code} - {response.text}")
                
                token_data = response.json()
                expires_at = datetime.utcnow() + timedelta(seconds=token_data.get('expires_in', 900))
                self._cached_token = OAuthToken(token_data['access_token'], expires_at)
        
        return self._cached_token.access_token
    
    async def request(self, method: str, endpoint: str, data: Optional[Dict] = None, params: Optional[Dict] = None) -> Dict[str, Any]:
        """Make REST request (authenticated or not based on environment)"""
        import os
        
        headers = {"Content-Type": "application/json"}
        
        # Always authenticate with proper JWT tokens
        access_token = await self._get_access_token()
        headers["Authorization"] = f"Bearer {access_token}"
        
        url = f"{self.config.api_base_url}{endpoint}"
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            if method.upper() == "GET":
                response = await client.get(url, headers=headers, params=params)
            elif method.upper() == "POST":
                response = await client.post(url, headers=headers, json=data)
            elif method.upper() == "PUT":
                response = await client.put(url, headers=headers, json=data)
            elif method.upper() == "DELETE":
                response = await client.delete(url, headers=headers)
            else:
                raise ValueError(f"Unsupported method: {method}")
            
            # Parse response
            try:
                parsed_response = response.json()
            except:
                parsed_response = {"raw_response": response.text}
            
            # Handle both dict and list responses by wrapping in consistent format
            if isinstance(parsed_response, list):
                result = {
                    "data": parsed_response,
                    "_status_code": response.status_code,
                    "_success": response.status_code < 400
                }
            else:
                result = parsed_response
                result["_status_code"] = response.status_code
                result["_success"] = response.status_code < 400
            
            return result