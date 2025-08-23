"""
Core testing infrastructure for agent_db testing suite
Production-ready OAuth authentication with comprehensive testing utilities
"""

import asyncio
import time
import json
import os
import jwt
from typing import Dict, List, Any, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
import httpx
import uuid


# Load environment configuration
def load_env_config():
    """Load configuration from .env file"""
    env_path = Path(__file__).parent / '.env'
    config = {}
    
    if env_path.exists():
        with open(env_path, 'r') as f:
            content = f.read()
            
        # Handle multiline values (like private keys)
        current_key = None
        current_value = []
        
        for line in content.split('\n'):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
                
            if '=' in line and not line.startswith(' '):
                # Save previous key-value pair if exists
                if current_key:
                    value = '\n'.join(current_value).strip('"')
                    if current_key == 'OAUTH_PRIVATE_KEY':
                        value = value.replace('\\n', '\n')
                    config[current_key] = value
                
                # Start new key-value pair
                key, value = line.split('=', 1)
                current_key = key.strip()
                current_value = [value]
            else:
                # Continue multiline value
                if current_key:
                    current_value.append(line)
        
        # Don't forget the last key-value pair
        if current_key:
            value = '\n'.join(current_value).strip('"')
            if current_key == 'OAUTH_PRIVATE_KEY':
                value = value.replace('\\n', '\n')
            config[current_key] = value
    
    return config

ENV_CONFIG = load_env_config()


@dataclass
class PerformanceMetrics:
    """Performance metrics for a single operation"""
    operation: str
    duration: float
    success: bool
    category: str = ""


@dataclass
class OAuthToken:
    """OAuth token with expiration tracking"""
    access_token: str
    expires_at: datetime
    token_type: str = "Bearer"
    
    def is_expired(self, buffer_seconds: int = 60) -> bool:
        """Check if token is expired (with 1-minute buffer for 15-minute tokens)"""
        return datetime.now(timezone.utc) >= (self.expires_at - timedelta(seconds=buffer_seconds))


class OAuthTokenManager:
    """Manages OAuth token generation, caching, and refresh for production endpoint"""
    
    def __init__(self):
        self.config = ENV_CONFIG
        self.base_url = self.config.get('AGENT_DB_BASE_URL', 'http://localhost:8080')
        self.service_id = self.config.get('OAUTH_SERVICE_ID', 'camren_master')
        self.audience = self.config.get('OAUTH_AUDIENCE', 'luceron-auth-server')
        self.private_key = self.config.get('OAUTH_PRIVATE_KEY')
        self._cached_token: Optional[OAuthToken] = None
        
        if not self.private_key:
            raise ValueError("OAUTH_PRIVATE_KEY not found in .env configuration")
    
    def _generate_client_assertion(self) -> str:
        """Generate JWT client assertion for OAuth"""
        now = datetime.now(timezone.utc)
        
        payload = {
            'iss': self.service_id,
            'sub': self.service_id,
            'aud': self.audience,
            'iat': int(now.timestamp()),
            'exp': int((now + timedelta(minutes=15)).timestamp())
        }
        
        client_assertion = jwt.encode(payload, self.private_key, algorithm='RS256')
        return client_assertion
    
    async def _fetch_oauth_token(self) -> OAuthToken:
        """Fetch new OAuth token from production endpoint"""
        client_assertion = self._generate_client_assertion()
        oauth_url = f"{self.base_url}/oauth2/token"
        
        payload = {
            'grant_type': 'client_credentials',
            'client_assertion_type': 'urn:ietf:params:oauth:client-assertion-type:jwt-bearer',
            'client_assertion': client_assertion
        }
        
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(oauth_url, data=payload, headers=headers)
                
                if response.status_code == 200:
                    token_data = response.json()
                    access_token = token_data['access_token']
                    expires_in = token_data.get('expires_in', 900)  # Default 15 minutes
                    expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
                    
                    return OAuthToken(
                        access_token=access_token,
                        expires_at=expires_at
                    )
                else:
                    raise RuntimeError(f"OAuth token request failed: {response.status_code} - {response.text}")
                    
            except httpx.RequestError as e:
                raise RuntimeError(f"OAuth token request error: {e}")
    
    async def get_valid_token(self) -> str:
        """Get a valid access token, refreshing if necessary"""
        if self._cached_token is None or self._cached_token.is_expired():
            print("🔄 Refreshing OAuth token...")
            self._cached_token = await self._fetch_oauth_token()
            print(f"✅ OAuth token refreshed, expires at {self._cached_token.expires_at}")
        
        return self._cached_token.access_token


class TestClient:
    """Production-ready HTTP client with OAuth authentication for testing"""
    
    def __init__(self):
        self.config = ENV_CONFIG
        self.base_url = self.config.get('AGENT_DB_BASE_URL', 'http://localhost:8080')
        self.timeout = float(self.config.get('TEST_TIMEOUT_SECONDS', '30'))
        self.max_retries = int(self.config.get('TEST_MAX_RETRIES', '3'))
        self.oauth_manager = OAuthTokenManager()
        
        print(f"🌐 TestClient configured for production endpoint: {self.base_url}")
    
    async def _get_authenticated_headers(self) -> Dict[str, str]:
        """Get headers with OAuth authentication"""
        access_token = await self.oauth_manager.get_valid_token()
        
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {access_token}"
        }
    
    async def health_check(self) -> bool:
        """Verify backend server connectivity"""
        try:
            # Test OAuth endpoint which should be publicly accessible
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(f"{self.base_url}/oauth2/token")
                # OAuth endpoint should return 405 for GET (needs POST), which means it's accessible
                return response.status_code in [405, 400]  # 405 = Method Not Allowed is expected
        except Exception:
            return False
    
    async def rest_request(self, method: str, endpoint: str, data: Optional[Dict] = None) -> Dict[str, Any]:
        """Make REST API request with OAuth authentication"""
        url = f"{self.base_url}{endpoint}"
        headers = await self._get_authenticated_headers()
        
        for attempt in range(self.max_retries):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    if method.upper() == "GET":
                        response = await client.get(url, headers=headers)
                    elif method.upper() == "POST":
                        response = await client.post(url, headers=headers, json=data)
                    elif method.upper() == "PUT":
                        response = await client.put(url, headers=headers, json=data)
                    elif method.upper() == "DELETE":
                        response = await client.delete(url, headers=headers)
                    else:
                        raise ValueError(f"Unsupported method: {method}")
                    
                    # If we get 401/403, token might be expired - refresh and retry
                    if response.status_code in [401, 403] and attempt < self.max_retries - 1:
                        print(f"🔄 Authentication failed (attempt {attempt + 1}), refreshing token...")
                        # Force token refresh
                        self.oauth_manager._cached_token = None
                        headers = await self._get_authenticated_headers()
                        continue
                    
                    # Handle non-JSON responses gracefully
                    try:
                        result = response.json()
                    except:
                        result = {"status_code": response.status_code, "text": response.text}
                    
                    # Add status code for error handling
                    result["_status_code"] = response.status_code
                    
                    return result
                    
            except httpx.RequestError as e:
                if attempt == self.max_retries - 1:
                    raise RuntimeError(f"Request failed after {self.max_retries} attempts: {e}")
                print(f"⚠️  Request failed (attempt {attempt + 1}), retrying...")
                await asyncio.sleep(1)  # Brief delay before retry
        
        raise RuntimeError("Request failed after all retry attempts")
    
    async def agent_db_query(self, natural_language: str, hints: Optional[Dict] = None) -> Dict[str, Any]:
        """Execute natural language query via /agent/db endpoint"""
        payload = {
            "natural_language": natural_language
        }
        if hints:
            payload["hints"] = hints
        
        return await self.rest_request("POST", "/agent/db", payload)


class UUIDTracker:
    """Track all UUIDs created during testing for complete cleanup"""
    
    def __init__(self):
        # Track by entity type for proper cleanup order
        self.tracked_uuids: Dict[str, Set[str]] = {
            'agent_messages': set(),
            'agent_summaries': set(), 
            'agent_context': set(),
            'document_analysis': set(),
            'client_communications': set(),
            'documents': set(),
            'agent_conversations': set(),
            'cases': set(),
            'error_logs': set()
        }
    
    def track(self, entity_type: str, uuid_value: str) -> None:
        """Track a UUID for cleanup"""
        if entity_type in self.tracked_uuids:
            self.tracked_uuids[entity_type].add(str(uuid_value))
    
    def track_multiple(self, entity_type: str, uuid_list: List[str]) -> None:
        """Track multiple UUIDs of same type"""
        for uuid_value in uuid_list:
            self.track(entity_type, uuid_value)
    
    def get_tracked(self, entity_type: str) -> Set[str]:
        """Get tracked UUIDs for entity type"""
        return self.tracked_uuids.get(entity_type, set())
    
    def total_tracked(self) -> int:
        """Get total number of tracked UUIDs"""
        return sum(len(uuids) for uuids in self.tracked_uuids.values())
    
    def get_cleanup_order(self) -> List[str]:
        """Get entity types in proper cleanup order (dependencies first)"""
        # Order matters - child entities must be deleted before parents
        return [
            'agent_messages',      # References conversations
            'agent_summaries',     # References conversations  
            'agent_context',       # References cases
            'document_analysis',   # References documents and cases
            'client_communications', # References cases
            'documents',           # References cases
            'agent_conversations', # Standalone
            'error_logs',          # Standalone
            'cases'                # Parent entity
        ]


class DataValidator:
    """Validate API responses and data integrity"""
    
    @staticmethod
    def validate_agent_db_response(response: Dict[str, Any]) -> Dict[str, Any]:
        """Validate agent/db response structure"""
        validation_result = {
            'valid': True,
            'errors': [],
            'warnings': []
        }
        
        # Check for HTTP errors first
        if response.get('_status_code', 200) >= 400:
            validation_result['valid'] = False
            validation_result['errors'].append(f"HTTP error: {response.get('_status_code')}")
            return validation_result
        
        # Validate required fields
        required_fields = ['ok']
        for field in required_fields:
            if field not in response:
                validation_result['valid'] = False
                validation_result['errors'].append(f"Missing required field: {field}")
        
        # If successful response, validate success structure
        if response.get('ok') is True:
            if 'operation' not in response:
                validation_result['warnings'].append("Missing operation field in successful response")
            if 'data' not in response:
                validation_result['warnings'].append("Missing data field in successful response")
        
        # If error response, validate error structure
        elif response.get('ok') is False:
            if 'error_details' not in response:
                validation_result['valid'] = False
                validation_result['errors'].append("Missing error_details in error response")
            else:
                error_details = response['error_details']
                if 'type' not in error_details or 'message' not in error_details:
                    validation_result['valid'] = False
                    validation_result['errors'].append("Incomplete error_details structure")
        
        return validation_result
    
    @staticmethod
    def validate_rest_response(response: Dict[str, Any], expected_fields: Optional[List[str]] = None) -> Dict[str, Any]:
        """Validate REST API response"""
        validation_result = {
            'valid': True,
            'errors': [],
            'warnings': []
        }
        
        # Check HTTP status
        status_code = response.get('_status_code', 200)
        if status_code >= 400:
            validation_result['valid'] = False
            validation_result['errors'].append(f"HTTP error: {status_code}")
            return validation_result
        
        # Check expected fields if provided
        if expected_fields:
            for field in expected_fields:
                if field not in response:
                    validation_result['errors'].append(f"Missing expected field: {field}")
        
        return validation_result
    
    @staticmethod
    def validate_uuid(value: Any) -> bool:
        """Validate UUID format"""
        try:
            uuid.UUID(str(value))
            return True
        except (ValueError, TypeError):
            return False


class PerformanceMonitor:
    """Monitor and validate response times"""
    
    def __init__(self):
        self.config = ENV_CONFIG
        self.metrics: List[PerformanceMetrics] = []
        # Performance thresholds from environment or defaults
        self.thresholds = {
            'simple_query': float(self.config.get('PERF_THRESHOLD_SIMPLE_QUERY', '2.0')),
            'complex_query': float(self.config.get('PERF_THRESHOLD_COMPLEX_QUERY', '5.0')),
            'create_operation': float(self.config.get('PERF_THRESHOLD_CREATE_OPERATION', '3.0')),
            'update_operation': float(self.config.get('PERF_THRESHOLD_UPDATE_OPERATION', '2.0'))
        }
    
    async def time_operation(self, operation_name: str, coro, category: str = "general"):
        """Time an async operation and record metrics"""
        start_time = time.time()
        success = True
        result = None
        
        try:
            result = await coro
        except Exception as e:
            success = False
            raise
        finally:
            duration = time.time() - start_time
            
            metric = PerformanceMetrics(
                operation=operation_name,
                duration=duration,
                success=success,
                category=category
            )
            self.metrics.append(metric)
            
            # Check against thresholds
            if category in self.thresholds:
                threshold = self.thresholds[category]
                if duration > threshold:
                    print(f"⚠️  Performance warning: {operation_name} took {duration:.2f}s (threshold: {threshold}s)")
        
        return result
    
    def get_category_stats(self, category: str) -> Dict[str, Any]:
        """Get performance stats for a category"""
        category_metrics = [m for m in self.metrics if m.category == category]
        
        if not category_metrics:
            return {'count': 0, 'avg_time': 0, 'max_time': 0, 'success_rate': 0}
        
        durations = [m.duration for m in category_metrics]
        successes = sum(1 for m in category_metrics if m.success)
        
        return {
            'count': len(category_metrics),
            'avg_time': sum(durations) / len(durations),
            'max_time': max(durations),
            'success_rate': successes / len(category_metrics) if category_metrics else 0
        }
    
    def print_summary(self):
        """Print performance summary"""
        if not self.metrics:
            print("📊 No performance metrics recorded")
            return
        
        print("\n📊 Performance Summary:")
        print("-" * 40)
        
        for category in ['simple_query', 'complex_query', 'create_operation', 'update_operation']:
            stats = self.get_category_stats(category)
            if stats['count'] > 0:
                threshold = self.thresholds[category]
                status = "✅" if stats['max_time'] <= threshold else "❌"
                print(f"{status} {category}: {stats['count']} ops, avg {stats['avg_time']:.2f}s, max {stats['max_time']:.2f}s")


# Utility functions
def extract_uuid_from_response(response: Dict[str, Any], uuid_field: str) -> Optional[str]:
    """Extract UUID from API response"""
    if isinstance(response, dict):
        # Try direct field access
        if uuid_field in response:
            return str(response[uuid_field])
        
        # Try in data array (for agent/db responses)
        if 'data' in response and response['data'] and len(response['data']) > 0:
            first_item = response['data'][0]
            if isinstance(first_item, dict) and uuid_field in first_item:
                return str(first_item[uuid_field])
    
    return None


def is_successful_response(response: Dict[str, Any]) -> bool:
    """Check if response indicates success"""
    # Check HTTP status code
    if response.get('_status_code', 200) >= 400:
        return False
    
    # Check agent/db response format
    if 'ok' in response:
        return response['ok'] is True
    
    # For REST API responses, assume success if no error status
    return True


def format_test_name(natural_language_query: str) -> str:
    """Format natural language query as test name"""
    # Truncate and clean up for test display
    clean_query = natural_language_query.replace('"', '').replace("'", "")
    if len(clean_query) > 50:
        clean_query = clean_query[:47] + "..."
    return clean_query