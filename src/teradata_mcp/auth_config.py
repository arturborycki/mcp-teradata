# src/teradata_mcp/auth_config.py
from dataclasses import dataclass
from typing import Optional
import os

@dataclass
class KeycloakConfig:
    """Keycloak authentication configuration"""
    # Keycloak server settings
    server_url: str = os.getenv("KEYCLOAK_SERVER_URL", "")
    realm: str = os.getenv("KEYCLOAK_REALM", "")
    client_id: str = os.getenv("KEYCLOAK_CLIENT_ID", "")
    client_secret: Optional[str] = os.getenv("KEYCLOAK_CLIENT_SECRET")
    
    # Authentication settings
    enabled: bool = os.getenv("KEYCLOAK_ENABLED", "false").lower() == "true"
    verify_ssl: bool = os.getenv("KEYCLOAK_VERIFY_SSL", "true").lower() == "true"
    
    # Token validation
    jwks_uri: Optional[str] = None
    issuer: Optional[str] = None
    audience: Optional[str] = None
    
    # Authorization settings
    required_roles: list = None
    required_scopes: list = None
    
    def __post_init__(self):
        if self.enabled:
            if not self.server_url or not self.realm or not self.client_id:
                raise ValueError("Keycloak server_url, realm, and client_id are required when enabled")
            
            # Auto-configure OIDC endpoints
            self.jwks_uri = f"{self.server_url}/realms/{self.realm}/protocol/openid-connect/certs"
            self.issuer = f"{self.server_url}/realms/{self.realm}"
            self.audience = self.client_id
            
            self.required_roles = os.getenv("KEYCLOAK_REQUIRED_ROLES", "").split(",") if os.getenv("KEYCLOAK_REQUIRED_ROLES") else []
            self.required_scopes = os.getenv("KEYCLOAK_REQUIRED_SCOPES", "").split(",") if os.getenv("KEYCLOAK_REQUIRED_SCOPES") else []