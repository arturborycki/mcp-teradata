# src/teradata_mcp/auth_middleware.py
import logging
import httpx
from typing import Optional, Dict, Any
from jose import jwt, JWTError
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from .auth_config import KeycloakConfig

logger = logging.getLogger(__name__)

class KeycloakAuthMiddleware(BaseHTTPMiddleware):
    """Middleware for Keycloak JWT token validation"""
    
    def __init__(self, app, config: KeycloakConfig):
        super().__init__(app)
        self.config = config
        self.jwks_client = None
        self._jwks_cache = None
        self._jwks_cache_time = 0
        
    async def dispatch(self, request: Request, call_next):
        if not self.config.enabled:
            return await call_next(request)
            
        # Skip auth for health check endpoints
        if request.url.path in ["/health", "/ping"]:
            return await call_next(request)
            
        # Extract and validate token
        token = self._extract_token(request)
        if not token:
            return JSONResponse(
                status_code=401,
                content={"error": "Missing or invalid authorization token"}
            )
            
        try:
            # Validate JWT token
            payload = await self._validate_token(token)
            
            # Check authorization
            if not self._check_authorization(payload):
                return JSONResponse(
                    status_code=403,
                    content={"error": "Insufficient permissions"}
                )
                
            # Add user context to request
            request.state.user = payload
            
        except JWTError as e:
            logger.warning(f"JWT validation failed: {e}")
            return JSONResponse(
                status_code=401,
                content={"error": "Invalid token"}
            )
        except Exception as e:
            logger.error(f"Authentication error: {e}")
            return JSONResponse(
                status_code=500,
                content={"error": "Authentication service error"}
            )
            
        return await call_next(request)
        
    def _extract_token(self, request: Request) -> Optional[str]:
        """Extract Bearer token from Authorization header"""
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            return None
            
        if not auth_header.startswith("Bearer "):
            return None
            
        return auth_header[7:]  # Remove "Bearer " prefix
        
    async def _validate_token(self, token: str) -> Dict[str, Any]:
        """Validate JWT token against Keycloak"""
        # Get JWKS (JSON Web Key Set)
        jwks = await self._get_jwks()
        
        # Decode and validate token
        payload = jwt.decode(
            token,
            jwks,
            algorithms=["RS256"],
            audience=self.config.audience,
            issuer=self.config.issuer,
            options={"verify_exp": True}
        )
        
        return payload
        
    async def _get_jwks(self) -> Dict[str, Any]:
        """Get JWKS from Keycloak with caching"""
        import time
        current_time = time.time()
        
        # Cache JWKS for 5 minutes
        if self._jwks_cache and (current_time - self._jwks_cache_time) < 300:
            return self._jwks_cache
            
        async with httpx.AsyncClient(verify=self.config.verify_ssl) as client:
            response = await client.get(self.config.jwks_uri)
            response.raise_for_status()
            
            self._jwks_cache = response.json()
            self._jwks_cache_time = current_time
            
        return self._jwks_cache
        
    def _check_authorization(self, payload: Dict[str, Any]) -> bool:
        """Check if user has required roles and scopes"""
        # Check required roles
        if self.config.required_roles:
            user_roles = self._extract_roles(payload)
            if not any(role in user_roles for role in self.config.required_roles):
                return False
                
        # Check required scopes
        if self.config.required_scopes:
            token_scopes = payload.get("scope", "").split()
            if not any(scope in token_scopes for scope in self.config.required_scopes):
                return False
                
        return True
        
    def _extract_roles(self, payload: Dict[str, Any]) -> list:
        """Extract roles from JWT payload"""
        roles = []
        
        # Realm roles
        realm_access = payload.get("realm_access", {})
        roles.extend(realm_access.get("roles", []))
        
        # Client roles
        resource_access = payload.get("resource_access", {})
        client_access = resource_access.get(self.config.client_id, {})
        roles.extend(client_access.get("roles", []))
        
        return roles