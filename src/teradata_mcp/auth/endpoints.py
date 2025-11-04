"""
HTTP Endpoints for OAuth 2.1 Protected Resource Metadata
Provides the /.well-known/oauth-protected-resource endpoint per RFC 9728.
"""

from typing import Dict, Any
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import logging

from .config import OAuthConfig
from .metadata import ProtectedResourceMetadata
from .middleware import OAuthMiddleware

logger = logging.getLogger(__name__)


class OAuthEndpoints:
    """OAuth 2.1 HTTP endpoints for protected resource metadata."""
    
    def __init__(self, config: OAuthConfig, metadata: ProtectedResourceMetadata, middleware: OAuthMiddleware):
        self.config = config
        self.metadata = metadata
        self.middleware = middleware
    
    def register_endpoints(self, app: FastAPI) -> None:
        """Register OAuth endpoints with FastAPI app."""
        
        @app.get("/.well-known/oauth-protected-resource")
        async def oauth_protected_resource_metadata(request: Request) -> JSONResponse:
            """
            OAuth Protected Resource Metadata endpoint per RFC 9728.
            
            This endpoint provides metadata about this protected resource,
            including information about the authorization servers that can
            issue tokens for this resource.
            """
            if not self.config.enabled:
                return JSONResponse(
                    status_code=404,
                    content={"error": "OAuth is not enabled"}
                )
            
            try:
                metadata = self.metadata.get_metadata()
                
                logger.debug(f"Serving protected resource metadata for {self.config.resource_server_url}")
                
                return JSONResponse(
                    content=metadata,
                    headers={
                        "Content-Type": "application/json",
                        "Cache-Control": "max-age=3600",  # Cache for 1 hour
                        "Access-Control-Allow-Origin": "*",
                        "Access-Control-Allow-Methods": "GET",
                        "Access-Control-Allow-Headers": "Authorization"
                    }
                )
                
            except Exception as e:
                logger.error(f"Error generating protected resource metadata: {e}")
                return JSONResponse(
                    status_code=500,
                    content={"error": "Internal server error"}
                )
        
        @app.get("/.well-known/mcp-server-info")
        async def mcp_server_info(request: Request) -> JSONResponse:
            """
            MCP Server Information endpoint.
            
            Provides information about MCP capabilities and OAuth configuration.
            This is not part of any RFC but useful for MCP clients.
            """
            try:
                info = {
                    "name": "teradata-mcp",
                    "version": "1.0.0",
                    "description": "Teradata Model Context Protocol Server",
                    "capabilities": {
                        "tools": True,
                        "resources": True,
                        "prompts": True,
                        "dynamic_resources": True
                    },
                    "authentication": {
                        "oauth2": {
                            "enabled": self.config.enabled,
                            "flows_supported": ["authorization_code", "client_credentials"] if self.config.enabled else [],
                            "scopes_supported": [
                                "teradata:read",
                                "teradata:write", 
                                "teradata:admin",
                                "teradata:query",
                                "teradata:schema"
                            ] if self.config.enabled else [],
                            "protected_resource_metadata": "/.well-known/oauth-protected-resource" if self.config.enabled else None
                        }
                    },
                    "endpoints": {
                        "mcp": "/mcp",
                        "health": "/health",
                        "protected_resource_metadata": "/.well-known/oauth-protected-resource" if self.config.enabled else None
                    }
                }
                
                if self.config.enabled:
                    info["authentication"]["oauth2"]["authorization_server"] = self.config.get_issuer_url()
                
                return JSONResponse(
                    content=info,
                    headers={
                        "Content-Type": "application/json",
                        "Access-Control-Allow-Origin": "*",
                        "Access-Control-Allow-Methods": "GET"
                    }
                )
                
            except Exception as e:
                logger.error(f"Error generating MCP server info: {e}")
                return JSONResponse(
                    status_code=500,
                    content={"error": "Internal server error"}
                )
        
        @app.get("/health")
        async def health_check(request: Request) -> JSONResponse:
            """
            Health check endpoint.
            
            Returns the health status of the MCP server and OAuth configuration.
            """
            try:
                health_status = {
                    "status": "healthy",
                    "timestamp": "2024-01-01T00:00:00Z",  # This would be dynamic in real implementation
                    "oauth": {
                        "enabled": self.config.enabled,
                        "configured": bool(self.config.enabled and self.config.keycloak_url and self.config.realm)
                    },
                    "database": {
                        "status": "connected"  # This would check actual DB connection
                    }
                }
                
                return JSONResponse(content=health_status)
                
            except Exception as e:
                logger.error(f"Health check error: {e}")
                return JSONResponse(
                    status_code=503,
                    content={
                        "status": "unhealthy",
                        "error": str(e)
                    }
                )
        
        # Add CORS preflight handler for OAuth endpoints
        @app.options("/.well-known/oauth-protected-resource")
        @app.options("/.well-known/mcp-server-info") 
        @app.options("/health")
        async def oauth_endpoints_preflight(request: Request) -> JSONResponse:
            """Handle CORS preflight requests for OAuth endpoints."""
            return JSONResponse(
                content={},
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "GET, OPTIONS",
                    "Access-Control-Allow-Headers": "Authorization, Content-Type",
                    "Access-Control-Max-Age": "3600"
                }
            )
        
        logger.info("OAuth endpoints registered successfully")
    
    def get_endpoint_info(self) -> Dict[str, Any]:
        """Get information about registered OAuth endpoints."""
        return {
            "oauth_protected_resource": "/.well-known/oauth-protected-resource",
            "mcp_server_info": "/.well-known/mcp-server-info", 
            "health": "/health",
            "enabled": self.config.enabled,
            "authorization_server": self.config.get_issuer_url() if self.config.enabled else None
        }
