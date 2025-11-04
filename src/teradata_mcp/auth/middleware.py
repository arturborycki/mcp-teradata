"""
OAuth 2.1 Token Validation Middleware
Handles JWT token validation and scope checking for MCP server endpoints.
"""

import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import aiohttp
import jwt
from jwt import PyJWKClient
from fastapi import HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi import Request

from .config import OAuthConfig
from .metadata import ProtectedResourceMetadata

logger = logging.getLogger(__name__)


@dataclass
class TokenClaims:
    """Validated token claims."""
    subject: str
    audience: List[str]
    scopes: List[str]
    issuer: str
    client_id: str
    expires_at: int
    issued_at: int
    username: Optional[str] = None
    email: Optional[str] = None
    roles: List[str] = None
    
    def __post_init__(self):
        if self.roles is None:
            self.roles = []


class TokenValidationError(Exception):
    """Token validation error."""
    
    def __init__(self, message: str, status_code: int = 401):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class OAuthMiddleware:
    """OAuth 2.1 token validation middleware."""
    
    def __init__(self, config: OAuthConfig, metadata: ProtectedResourceMetadata):
        self.config = config
        self.metadata = metadata
        self.security = HTTPBearer(auto_error=False)
        
        # JWT validation setup
        if config.enabled and config.jwks_endpoint:
            self.jwks_client = PyJWKClient(config.jwks_endpoint)
        else:
            self.jwks_client = None
            
        # Token introspection session
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def __aenter__(self):
        """Async context manager entry."""
        if self.config.enabled:
            self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()
    
    async def validate_token(self, token: str) -> TokenClaims:
        """
        Validate an OAuth 2.1 Bearer token.
        
        Args:
            token: Bearer token string
            
        Returns:
            TokenClaims object with validated claims
            
        Raises:
            TokenValidationError: If token is invalid
        """
        if not self.config.enabled:
            # OAuth is disabled, create dummy claims for development
            return TokenClaims(
                subject="dev-user",
                audience=[self.config.resource_server_url or "teradata-mcp"],
                scopes=["teradata:admin", "teradata:read", "teradata:write", "teradata:query"],
                issuer="dev",
                client_id="dev-client",
                expires_at=9999999999,  # Far future
                issued_at=1600000000,
                username="dev-user"
            )
        
        try:
            # Try JWT validation first (faster)
            if self.jwks_client:
                try:
                    return await self._validate_jwt_token(token)
                except Exception as e:
                    logger.debug(f"JWT validation failed, falling back to introspection: {e}")
            
            # Fall back to token introspection
            return await self._introspect_token(token)
            
        except TokenValidationError:
            raise
        except Exception as e:
            logger.error(f"Token validation error: {e}")
            raise TokenValidationError(f"Token validation failed: {str(e)}")
    
    async def _validate_jwt_token(self, token: str) -> TokenClaims:
        """Validate JWT token using JWKS."""
        try:
            # Get signing key from JWKS
            signing_key = self.jwks_client.get_signing_key_from_jwt(token)
            
            # Decode and validate JWT
            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256", "RS384", "RS512", "ES256", "ES384", "ES512"],
                audience=self.config.resource_server_url if self.config.validate_audience else None,
                issuer=self.config.get_issuer_url(),
                options={
                    "verify_exp": True,
                    "verify_aud": self.config.validate_audience,
                    "verify_iss": True
                }
            )
            
            return self._extract_claims_from_jwt(payload)
            
        except jwt.ExpiredSignatureError:
            raise TokenValidationError("Token has expired", 401)
        except jwt.InvalidAudienceError:
            raise TokenValidationError("Invalid token audience", 401)
        except jwt.InvalidIssuerError:
            raise TokenValidationError("Invalid token issuer", 401)
        except jwt.InvalidTokenError as e:
            raise TokenValidationError(f"Invalid JWT token: {str(e)}", 401)
    
    async def _introspect_token(self, token: str) -> TokenClaims:
        """Validate token using introspection endpoint."""
        if not self.session:
            raise TokenValidationError("OAuth session not initialized")
        
        # Prepare introspection request
        data = {
            'token': token,
            'token_type_hint': 'access_token'
        }
        
        # Add client authentication
        auth = None
        if self.config.client_secret:
            auth = aiohttp.BasicAuth(self.config.client_id, self.config.client_secret)
        else:
            data['client_id'] = self.config.client_id
        
        try:
            async with self.session.post(
                self.config.token_validation_endpoint,
                data=data,
                auth=auth,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                
                if response.status != 200:
                    raise TokenValidationError(f"Introspection failed: {response.status}", 401)
                
                result = await response.json()
                
                if not result.get('active', False):
                    raise TokenValidationError("Token is not active", 401)
                
                return self._extract_claims_from_introspection(result)
                
        except aiohttp.ClientError as e:
            raise TokenValidationError(f"Introspection request failed: {str(e)}", 503)
    
    def _extract_claims_from_jwt(self, payload: Dict[str, Any]) -> TokenClaims:
        """Extract claims from JWT payload."""
        
        # Extract scopes (can be in 'scope' or 'scopes' claim)
        scopes = []
        if 'scope' in payload:
            scopes = payload['scope'].split(' ') if isinstance(payload['scope'], str) else payload['scope']
        elif 'scopes' in payload:
            scopes = payload['scopes'] if isinstance(payload['scopes'], list) else [payload['scopes']]
        
        # Extract roles from various possible claims
        roles = []
        if 'realm_access' in payload and 'roles' in payload['realm_access']:
            roles.extend(payload['realm_access']['roles'])
        if 'resource_access' in payload:
            for resource, access in payload['resource_access'].items():
                if 'roles' in access:
                    roles.extend([f"{resource}:{role}" for role in access['roles']])
        
        return TokenClaims(
            subject=payload.get('sub', ''),
            audience=payload.get('aud', []) if isinstance(payload.get('aud'), list) else [payload.get('aud', '')],
            scopes=scopes,
            issuer=payload.get('iss', ''),
            client_id=payload.get('client_id', payload.get('azp', '')),
            expires_at=payload.get('exp', 0),
            issued_at=payload.get('iat', 0),
            username=payload.get('preferred_username', payload.get('username')),
            email=payload.get('email'),
            roles=roles
        )
    
    def _extract_claims_from_introspection(self, result: Dict[str, Any]) -> TokenClaims:
        """Extract claims from introspection response."""
        
        scopes = []
        if 'scope' in result:
            scopes = result['scope'].split(' ') if isinstance(result['scope'], str) else result['scope']
        
        return TokenClaims(
            subject=result.get('sub', ''),
            audience=result.get('aud', []) if isinstance(result.get('aud'), list) else [result.get('aud', '')],
            scopes=scopes,
            issuer=result.get('iss', ''),
            client_id=result.get('client_id', ''),
            expires_at=result.get('exp', 0),
            issued_at=result.get('iat', 0),
            username=result.get('username'),
            email=result.get('email')
        )
    
    async def authenticate_request(self, request: Request) -> Optional[TokenClaims]:
        """
        Authenticate an HTTP request.
        
        Args:
            request: FastAPI request object
            
        Returns:
            TokenClaims if authenticated, None if OAuth is disabled
            
        Raises:
            HTTPException: If authentication fails
        """
        if not self.config.enabled:
            return None
        
        # Extract token from Authorization header
        credentials: Optional[HTTPAuthorizationCredentials] = await self.security(request)
        
        if not credentials:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authorization header required",
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        if credentials.scheme.lower() != "bearer":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication scheme",
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        try:
            return await self.validate_token(credentials.credentials)
        except TokenValidationError as e:
            raise HTTPException(
                status_code=e.status_code,
                detail=e.message,
                headers={"WWW-Authenticate": "Bearer"}
            )
    
    def validate_scopes_for_operation(self, claims: Optional[TokenClaims], operation: str) -> bool:
        """
        Validate that the token has required scopes for an operation.
        
        Args:
            claims: Token claims (None if OAuth disabled)
            operation: Operation name or type
            
        Returns:
            True if authorized, False otherwise
        """
        if not self.config.enabled or not claims:
            return True  # OAuth disabled or no claims
        
        if not self.config.validate_scopes:
            return True  # Scope validation disabled
        
        required_scopes = self.metadata.get_scopes_for_operation(operation)
        
        # Check if user has any of the required scopes
        user_scopes = set(claims.scopes)
        required_scopes_set = set(required_scopes)
        
        return bool(user_scopes.intersection(required_scopes_set))
    
    def require_scopes(self, *required_scopes: str):
        """
        Decorator to require specific scopes for an endpoint.
        
        Args:
            required_scopes: Required scope names
        """
        def decorator(func):
            async def wrapper(*args, **kwargs):
                # Extract request from args/kwargs
                request = None
                for arg in args:
                    if isinstance(arg, Request):
                        request = arg
                        break
                
                if not request:
                    request = kwargs.get('request')
                
                if not request:
                    raise HTTPException(
                        status_code=500,
                        detail="Request object not found in endpoint"
                    )
                
                # Authenticate request
                claims = await self.authenticate_request(request)
                
                # Check scopes if OAuth is enabled
                if self.config.enabled and claims:
                    user_scopes = set(claims.scopes)
                    required_scopes_set = set(required_scopes)
                    
                    if not user_scopes.intersection(required_scopes_set):
                        raise HTTPException(
                            status_code=status.HTTP_403_FORBIDDEN,
                            detail=f"Insufficient scopes. Required: {list(required_scopes)}, "
                                   f"Available: {claims.scopes}"
                        )
                
                # Add claims to request state for use in handler
                if claims:
                    request.state.oauth_claims = claims
                
                return await func(*args, **kwargs)
            
            return wrapper
        return decorator
