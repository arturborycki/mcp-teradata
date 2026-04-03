"""
HTTP Endpoints for OAuth 2.1 Protected Resource Metadata
Provides the /.well-known/oauth-protected-resource endpoint per RFC 9728.
"""

import os
from typing import Dict, Any, List
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.routing import Route
from starlette.requests import Request as StarletteRequest
import logging

from .config import OAuthConfig
from .metadata import ProtectedResourceMetadata
from .middleware import OAuthMiddleware

logger = logging.getLogger(__name__)

CORS_ALLOWED_ORIGINS = os.environ.get("CORS_ALLOWED_ORIGINS", "*")


def _cors_headers(extra: dict | None = None) -> dict:
    """Build standard CORS headers."""
    headers = {
        "Access-Control-Allow-Origin": CORS_ALLOWED_ORIGINS,
        "Access-Control-Allow-Methods": "GET, OPTIONS",
        "Access-Control-Allow-Headers": "Authorization, Content-Type",
    }
    if extra:
        headers.update(extra)
    return headers


class OAuthEndpoints:
    """OAuth 2.1 HTTP endpoints for protected resource metadata."""

    def __init__(self, config: OAuthConfig, metadata: ProtectedResourceMetadata, middleware: OAuthMiddleware):
        self.config = config
        self.metadata = metadata
        self.middleware = middleware

    def _get_version(self) -> str:
        try:
            from teradata_mcp import __version__
            return __version__
        except ImportError:
            return "0.1.0"

    # --- Shared handler logic (used by both FastAPI and Starlette routes) ---

    def _handle_protected_resource_metadata(self) -> JSONResponse:
        if not self.config.enabled:
            return JSONResponse(status_code=404, content={"error": "OAuth is not enabled"})
        try:
            metadata_dict = self.metadata.get_metadata()
            return JSONResponse(
                content=metadata_dict,
                headers=_cors_headers({"Cache-Control": "max-age=3600"}),
            )
        except Exception as e:
            logger.error(f"Error generating protected resource metadata: {e}")
            return JSONResponse(status_code=500, content={"error": "Internal server error"})

    def _handle_mcp_server_info(self, transport: str = "streamable-http") -> JSONResponse:
        try:
            info = {
                "name": "teradata-mcp",
                "version": self._get_version(),
                "description": "Teradata Model Context Protocol Server",
                "transport": transport,
                "capabilities": {
                    "tools": True,
                    "resources": True,
                    "prompts": True,
                    "dynamic_resources": True
                },
                "authentication": {
                    "oauth2": {
                        "enabled": self.config.enabled,
                        "authorization_server": self.config.get_issuer_url() if self.config.enabled else None,
                        "flows_supported": ["authorization_code", "client_credentials"] if self.config.enabled else [],
                        "scopes_supported": [
                            "teradata:read", "teradata:write", "teradata:admin",
                            "teradata:query", "teradata:schema"
                        ] if self.config.enabled else [],
                        "protected_resource_metadata": "/.well-known/oauth-protected-resource" if self.config.enabled else None
                    }
                },
                "endpoints": {
                    "health": "/health",
                    "protected_resource_metadata": "/.well-known/oauth-protected-resource" if self.config.enabled else None
                }
            }
            return JSONResponse(content=info, headers=_cors_headers())
        except Exception as e:
            logger.error(f"Error generating MCP server info: {e}")
            return JSONResponse(status_code=500, content={"error": "Internal server error"})

    def _handle_health_check(self, transport: str = "streamable-http", connection_manager=None) -> JSONResponse:
        try:
            health_status = {
                "status": "healthy",
                "transport": transport,
                "oauth": {
                    "enabled": self.config.enabled,
                    "configured": bool(self.config.enabled and self.config.keycloak_url and self.config.realm)
                },
                "database": {
                    "status": "connected" if connection_manager else "disconnected"
                }
            }
            return JSONResponse(content=health_status)
        except Exception as e:
            logger.error(f"Health check error: {e}")
            return JSONResponse(status_code=503, content={"status": "unhealthy"})

    @staticmethod
    def _handle_preflight() -> JSONResponse:
        return JSONResponse(content={}, headers=_cors_headers({"Access-Control-Max-Age": "3600"}))

    # --- FastAPI registration ---

    def register_endpoints(self, app: FastAPI) -> None:
        """Register OAuth endpoints with FastAPI app."""

        @app.get("/.well-known/oauth-protected-resource")
        async def oauth_protected_resource_metadata(request: Request) -> JSONResponse:
            return self._handle_protected_resource_metadata()

        @app.get("/.well-known/mcp-server-info")
        async def mcp_server_info(request: Request) -> JSONResponse:
            return self._handle_mcp_server_info()

        @app.get("/health")
        async def health_check(request: Request) -> JSONResponse:
            return self._handle_health_check()

        @app.options("/.well-known/oauth-protected-resource")
        @app.options("/.well-known/mcp-server-info")
        @app.options("/health")
        async def oauth_endpoints_preflight(request: Request) -> JSONResponse:
            return self._handle_preflight()

        logger.info("OAuth endpoints registered successfully")

    # --- Starlette route generation (for SSE transport) ---

    def get_starlette_routes(self, transport: str = "sse", connection_manager=None) -> List[Route]:
        """Return OAuth endpoints as Starlette Route objects for SSE transport."""

        async def metadata_handler(request: StarletteRequest):
            return self._handle_protected_resource_metadata()

        async def info_handler(request: StarletteRequest):
            return self._handle_mcp_server_info(transport=transport)

        async def health_handler(request: StarletteRequest):
            return self._handle_health_check(transport=transport, connection_manager=connection_manager)

        async def preflight_handler(request: StarletteRequest):
            return self._handle_preflight()

        return [
            Route("/.well-known/oauth-protected-resource", endpoint=metadata_handler, methods=["GET"]),
            Route("/.well-known/mcp-server-info", endpoint=info_handler, methods=["GET"]),
            Route("/health", endpoint=health_handler, methods=["GET"]),
            Route("/.well-known/oauth-protected-resource", endpoint=preflight_handler, methods=["OPTIONS"]),
            Route("/.well-known/mcp-server-info", endpoint=preflight_handler, methods=["OPTIONS"]),
            Route("/health", endpoint=preflight_handler, methods=["OPTIONS"]),
        ]

    def get_endpoint_info(self) -> Dict[str, Any]:
        """Get information about registered OAuth endpoints."""
        return {
            "oauth_protected_resource": "/.well-known/oauth-protected-resource",
            "mcp_server_info": "/.well-known/mcp-server-info",
            "health": "/health",
            "enabled": self.config.enabled,
            "authorization_server": self.config.get_issuer_url() if self.config.enabled else None
        }
