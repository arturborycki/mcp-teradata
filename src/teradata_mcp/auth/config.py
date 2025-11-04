"""
OAuth 2.1 Configuration Module for Teradata MCP Server
Handles authentication configuration with support for Keycloak and other OAuth providers.
"""

import os
from dataclasses import dataclass, field
from typing import List
from urllib.parse import urlparse
import logging

logger = logging.getLogger(__name__)


@dataclass
class OAuthConfig:
    """OAuth 2.1 configuration for the MCP server."""
    
    # Core OAuth settings
    enabled: bool = False
    
    # Authorization Server settings (Keycloak)
    keycloak_url: str = ""
    realm: str = ""
    client_id: str = ""
    client_secret: str = ""
    
    # Resource Server settings
    resource_server_url: str = ""
    required_scopes: List[str] = field(default_factory=list)
    
    # Token validation endpoints
    token_validation_endpoint: str = ""
    jwks_endpoint: str = ""
    
    # Discovery endpoints
    authorization_server_metadata_url: str = ""
    openid_configuration_url: str = ""
    
    # Security settings
    validate_audience: bool = True
    validate_scopes: bool = True
    require_https: bool = True
    
    @classmethod
    def from_environment(cls) -> 'OAuthConfig':
        """Create OAuth configuration from environment variables."""
        
        enabled = os.getenv('OAUTH_ENABLED', 'false').lower() == 'true'
        
        if not enabled:
            logger.info("OAuth authentication is disabled")
            return cls(enabled=False)
        
        # Required settings
        keycloak_url = os.getenv('KEYCLOAK_URL', '')
        realm = os.getenv('KEYCLOAK_REALM', '')
        client_id = os.getenv('KEYCLOAK_CLIENT_ID', '')
        resource_server_url = os.getenv('OAUTH_RESOURCE_SERVER_URL', '')
        
        # Validate required settings
        missing_settings = []
        if not keycloak_url:
            missing_settings.append('KEYCLOAK_URL')
        if not realm:
            missing_settings.append('KEYCLOAK_REALM')
        if not client_id:
            missing_settings.append('KEYCLOAK_CLIENT_ID')
        if not resource_server_url:
            missing_settings.append('OAUTH_RESOURCE_SERVER_URL')
        
        if missing_settings:
            raise ValueError(f"OAuth is enabled but missing required settings: {', '.join(missing_settings)}")
        
        # Optional settings
        client_secret = os.getenv('KEYCLOAK_CLIENT_SECRET', '')
        required_scopes = os.getenv('OAUTH_REQUIRED_SCOPES', '').split(',') if os.getenv('OAUTH_REQUIRED_SCOPES') else []
        required_scopes = [scope.strip() for scope in required_scopes if scope.strip()]
        
        # Build endpoints
        keycloak_base_url = keycloak_url.rstrip('/')
        realm_base_url = f"{keycloak_base_url}/auth/realms/{realm}"
        
        # Token validation endpoints
        token_validation_endpoint = os.getenv(
            'OAUTH_TOKEN_VALIDATION_ENDPOINT',
            f"{realm_base_url}/protocol/openid-connect/token/introspect"
        )
        
        jwks_endpoint = os.getenv(
            'OAUTH_JWKS_ENDPOINT',
            f"{realm_base_url}/protocol/openid-connect/certs"
        )
        
        # Discovery endpoints
        authorization_server_metadata_url = f"{keycloak_base_url}/.well-known/oauth-authorization-server/{realm}"
        openid_configuration_url = f"{realm_base_url}/.well-known/openid-configuration"
        
        # Security settings
        validate_audience = os.getenv('OAUTH_VALIDATE_AUDIENCE', 'true').lower() == 'true'
        validate_scopes = os.getenv('OAUTH_VALIDATE_SCOPES', 'true').lower() == 'true'
        require_https = os.getenv('OAUTH_REQUIRE_HTTPS', 'true').lower() == 'true'
        
        config = cls(
            enabled=True,
            keycloak_url=keycloak_url,
            realm=realm,
            client_id=client_id,
            client_secret=client_secret,
            resource_server_url=resource_server_url,
            required_scopes=required_scopes,
            token_validation_endpoint=token_validation_endpoint,
            jwks_endpoint=jwks_endpoint,
            authorization_server_metadata_url=authorization_server_metadata_url,
            openid_configuration_url=openid_configuration_url,
            validate_audience=validate_audience,
            validate_scopes=validate_scopes,
            require_https=require_https
        )
        
        config.validate()
        logger.info(f"OAuth configuration loaded successfully for realm: {realm}")
        return config
    
    def validate(self) -> None:
        """Validate the OAuth configuration."""
        if not self.enabled:
            return
        
        # Validate URLs
        try:
            parsed_keycloak = urlparse(self.keycloak_url)
            if not parsed_keycloak.scheme or not parsed_keycloak.netloc:
                raise ValueError("KEYCLOAK_URL must be a valid URL")
                
            parsed_resource = urlparse(self.resource_server_url)
            if not parsed_resource.scheme or not parsed_resource.netloc:
                raise ValueError("OAUTH_RESOURCE_SERVER_URL must be a valid URL")
                
            # Check HTTPS requirement
            if self.require_https:
                if parsed_keycloak.scheme != 'https':
                    raise ValueError("KEYCLOAK_URL must use HTTPS when OAUTH_REQUIRE_HTTPS is true")
                if parsed_resource.scheme != 'https':
                    raise ValueError("OAUTH_RESOURCE_SERVER_URL must use HTTPS when OAUTH_REQUIRE_HTTPS is true")
                    
        except Exception as e:
            raise ValueError(f"Invalid OAuth configuration: {e}")
    
    def get_issuer_url(self) -> str:
        """Get the OAuth issuer URL."""
        return f"{self.keycloak_url.rstrip('/')}/auth/realms/{self.realm}"
    
    def get_authorization_endpoint(self) -> str:
        """Get the authorization endpoint URL."""
        return f"{self.get_issuer_url()}/protocol/openid-connect/auth"
    
    def get_token_endpoint(self) -> str:
        """Get the token endpoint URL."""
        return f"{self.get_issuer_url()}/protocol/openid-connect/token"
    
    def get_userinfo_endpoint(self) -> str:
        """Get the userinfo endpoint URL."""
        return f"{self.get_issuer_url()}/protocol/openid-connect/userinfo"
    
    def get_logout_endpoint(self) -> str:
        """Get the logout endpoint URL."""
        return f"{self.get_issuer_url()}/protocol/openid-connect/logout"
    
    def __str__(self) -> str:
        """String representation of the config (hiding secrets)."""
        if not self.enabled:
            return "OAuthConfig(enabled=False)"
        
        return (
            f"OAuthConfig(enabled=True, keycloak_url={self.keycloak_url}, "
            f"realm={self.realm}, client_id={self.client_id}, "
            f"resource_server_url={self.resource_server_url}, "
            f"scopes={self.required_scopes})"
        )
