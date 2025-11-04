"""
OAuth Context Management for MCP Tools
Provides OAuth context and authorization checking for tool execution.
"""

import logging
from typing import Optional
from contextlib import asynccontextmanager
from .auth import TokenClaims, OAuthConfig, ProtectedResourceMetadata

logger = logging.getLogger(__name__)

# Global OAuth context
_oauth_context: Optional['OAuthContext'] = None


class OAuthContext:
    """OAuth context for tool execution."""
    
    def __init__(self, config: OAuthConfig, metadata: ProtectedResourceMetadata):
        self.config = config
        self.metadata = metadata
        self._current_claims: Optional[TokenClaims] = None
    
    def set_current_claims(self, claims: Optional[TokenClaims]):
        """Set the current OAuth claims for the request."""
        self._current_claims = claims
    
    def get_current_claims(self) -> Optional[TokenClaims]:
        """Get the current OAuth claims."""
        return self._current_claims
    
    def is_authorized_for_tool(self, tool_name: str) -> bool:
        """Check if current user is authorized to execute a tool."""
        if not self.config.enabled:
            return True  # OAuth disabled, allow all
        
        if not self._current_claims:
            return False  # No claims, deny access
        
        return self.metadata.validate_scopes_for_tool(tool_name, self._current_claims.scopes)
    
    def get_authorization_error(self, tool_name: str) -> str:
        """Get authorization error message for a tool."""
        if not self.config.enabled:
            return "OAuth is not enabled"
        
        if not self._current_claims:
            return "No authentication token provided"
        
        required_scopes = self.metadata.get_scopes_for_operation(
            self._get_operation_type_for_tool(tool_name)
        )
        
        return (f"Insufficient permissions for tool '{tool_name}'. "
                f"Required scopes: {required_scopes}, "
                f"Available scopes: {self._current_claims.scopes}")
    
    def _get_operation_type_for_tool(self, tool_name: str) -> str:
        """Map tool name to operation type."""
        # This maps MCP tool names to operation types for scope checking
        tool_operation_map = {
            'query': 'query',
            'list_db': 'read',
            'list_tables': 'read',
            'show_tables_details': 'read',
            'list_missing_values': 'read',
            'list_negative_values': 'read',
            'list_distinct_values': 'read',
            'standard_deviation': 'read',
            # TDWM tools
            'mcp_tdwm_show_sessions': 'read',
            'mcp_tdwm_monitor_config': 'read',
            'mcp_tdwm_show_physical_resources': 'read',
            'mcp_tdwm_list_active_WD': 'read',
            'mcp_tdwm_abort_sessions_user': 'admin',
            'mcp_tdwm_create_filter_rule': 'admin',
            'mcp_tdwm_activate_rulset': 'admin',
        }
        
        return tool_operation_map.get(tool_name, 'read')


def set_oauth_context(context: Optional[OAuthContext]):
    """Set the global OAuth context."""
    global _oauth_context
    _oauth_context = context


def get_oauth_context() -> Optional[OAuthContext]:
    """Get the global OAuth context."""
    return _oauth_context


@asynccontextmanager
async def oauth_tool_context(claims: Optional[TokenClaims]):
    """Context manager for setting OAuth claims during tool execution."""
    context = get_oauth_context()
    if context:
        old_claims = context.get_current_claims()
        try:
            context.set_current_claims(claims)
            yield context
        finally:
            context.set_current_claims(old_claims)
    else:
        yield None


def require_oauth_authorization(tool_name: str) -> bool:
    """
    Check OAuth authorization for a tool.
    
    Returns:
        True if authorized, False if not authorized
    """
    context = get_oauth_context()
    
    if not context:
        return True  # No OAuth context, allow all
    
    return context.is_authorized_for_tool(tool_name)


def get_oauth_error(tool_name: str) -> str:
    """Get OAuth authorization error message."""
    context = get_oauth_context()
    
    if not context:
        return "OAuth context not available"
    
    return context.get_authorization_error(tool_name)
