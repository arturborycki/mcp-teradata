"""
Protected Resource Metadata Handler (RFC 9728)
Provides OAuth 2.1 protected resource metadata endpoint for discovery.
"""

from typing import Dict, List, Any
import logging
from .config import OAuthConfig

logger = logging.getLogger(__name__)


class ProtectedResourceMetadata:
    """Handler for OAuth Protected Resource Metadata (RFC 9728)."""
    
    def __init__(self, config: OAuthConfig):
        self.config = config
    
    def get_metadata(self) -> Dict[str, Any]:
        """
        Generate protected resource metadata per RFC 9728.
        
        Returns metadata that describes this protected resource,
        including authorization server information and scopes.
        """
        if not self.config.enabled:
            return {}
        
        metadata = {
            # RFC 9728 required fields
            "resource": self.config.resource_server_url,
            "authorization_servers": [
                self.config.get_issuer_url()
            ],
            
            # Keycloak-specific authorization server metadata
            "authorization_server_metadata_endpoints": {
                self.config.get_issuer_url(): self.config.authorization_server_metadata_url
            },
            
            # OpenID Connect Discovery (common for Keycloak)
            "openid_configuration_endpoints": {
                self.config.get_issuer_url(): self.config.openid_configuration_url
            },
            
            # Supported scopes
            "scopes_supported": [
                "teradata:read",      # Read access to database resources
                "teradata:write",     # Write access to database resources  
                "teradata:admin",     # Administrative access
                "teradata:query",     # Execute queries
                "teradata:schema",    # Schema management
                "openid",             # OpenID Connect
                "profile",            # Profile information
                "email"               # Email access
            ],
            
            # Token validation information
            "token_endpoint_auth_methods_supported": [
                "client_secret_basic",
                "client_secret_post",
                "client_secret_jwt",
                "private_key_jwt"
            ],
            
            # Supported grant types
            "grant_types_supported": [
                "authorization_code",
                "client_credentials",
                "refresh_token"
            ],
            
            # Response types supported
            "response_types_supported": [
                "code"
            ],
            
            # Token types
            "token_types_supported": [
                "Bearer"
            ],
            
            # PKCE support (required for OAuth 2.1)
            "code_challenge_methods_supported": [
                "S256"
            ],
            
            # Introspection endpoint
            "introspection_endpoint": self.config.token_validation_endpoint,
            "introspection_endpoint_auth_methods_supported": [
                "client_secret_basic",
                "client_secret_post"
            ],
            
            # JWKS endpoint for JWT validation
            "jwks_uri": self.config.jwks_endpoint,
            
            # Additional Teradata MCP specific metadata
            "mcp_server": {
                "name": "teradata-mcp",
                "version": "1.0.0",
                "capabilities": [
                    "database_query",
                    "schema_management", 
                    "workload_management",
                    "dynamic_resources"
                ]
            },
            
            # Security requirements
            "require_request_uri_registration": False,
            "require_signed_request_object": False,
            "mtls_endpoint_aliases": {},
            
            # Client registration
            "registration_endpoint": f"{self.config.get_issuer_url()}/clients-registrations/openid-connect",
            
            # Service documentation
            "service_documentation": "https://github.com/arturborycki/mcp-teradata",
            
            # RFC 9728 optional fields
            "resource_documentation": "https://github.com/arturborycki/mcp-teradata/blob/main/README.md"
        }
        
        # Add required scopes if configured
        if self.config.required_scopes:
            metadata["scopes_required"] = self.config.required_scopes
        
        # Add audience validation info
        if self.config.validate_audience:
            metadata["audience"] = self.config.resource_server_url
        
        logger.debug(f"Generated protected resource metadata for {self.config.resource_server_url}")
        return metadata
    
    def get_scopes_for_operation(self, operation_type: str) -> List[str]:
        """
        Get required scopes for different MCP operations.
        
        Args:
            operation_type: Type of operation ('read', 'write', 'admin', 'query')
            
        Returns:
            List of required scopes for the operation
        """
        scope_mapping = {
            'read': ['teradata:read'],
            'write': ['teradata:write', 'teradata:read'], 
            'admin': ['teradata:admin'],
            'query': ['teradata:query', 'teradata:read'],
            'schema': ['teradata:schema', 'teradata:admin'],
            'list': ['teradata:read'],
            'show': ['teradata:read'],
            'execute': ['teradata:query', 'teradata:read'],
            'monitor': ['teradata:read'],
            'manage': ['teradata:admin']
        }
        
        return scope_mapping.get(operation_type.lower(), ['teradata:read'])
    
    def validate_scopes_for_tool(self, tool_name: str, user_scopes: List[str]) -> bool:
        """
        Validate if user has required scopes for a specific tool.
        
        Args:
            tool_name: Name of the MCP tool being accessed
            user_scopes: Scopes present in the user's token
            
        Returns:
            True if user has sufficient scopes, False otherwise
        """
        # Map tool names to operation types
        tool_operation_mapping = {
            # Database query tools
            'mcp_teradata_query': 'query',
            'mcp_teradata_list_db': 'read',
            'mcp_teradata_list_objects': 'read',
            'mcp_teradata_show_tables': 'read',
            'mcp_teradata_list_distinct_values': 'read',
            'mcp_teradata_list_missing_values': 'read', 
            'mcp_teradata_list_negative_values': 'read',
            'mcp_teradata_standard_deviation': 'read',
            
            # TDWM tools  
            'mcp_tdwm_show_sessions': 'read',
            'mcp_tdwm_monitor_config': 'read',
            'mcp_tdwm_show_physical_resources': 'read',
            'mcp_tdwm_list_active_WD': 'read',
            'mcp_tdwm_abort_sessions_user': 'admin',
            'mcp_tdwm_create_filter_rule': 'admin',
            'mcp_tdwm_activate_rulset': 'admin',
        }
        
        operation_type = tool_operation_mapping.get(tool_name, 'read')
        required_scopes = self.get_scopes_for_operation(operation_type)
        
        # Check if user has any of the required scopes
        return any(scope in user_scopes for scope in required_scopes)
