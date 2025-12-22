"""
Teradata MCP Server using FastMCP
Supports all transport methods: stdio, SSE, and streamable-http
Includes OAuth 2.1 authentication with Keycloak integration
"""
import argparse
import asyncio
import logging
import os
from contextlib import asynccontextmanager
from starlette.applications import Starlette
from mcp.server.sse import SseServerTransport
from starlette.requests import Request
from starlette.routing import Mount, Route
from mcp.server import Server
import uvicorn
from urllib.parse import urlparse
from mcp.server.fastmcp import FastMCP

from .tdsql import obfuscate_password
from .connection_manager import TeradataConnectionManager
from .fnc_tools import (
    set_tools_connection,
    handle_list_tools,
    handle_tool_call
)
from .fnc_resources import (
    set_resource_connection,
    handle_list_resources,
    handle_read_resource
)
from .fnc_prompts import (
    handle_list_prompts,
    handle_get_prompt
)
from .auth import (
    OAuthConfig,
    ProtectedResourceMetadata, 
    OAuthMiddleware,
    OAuthEndpoints
)
from .oauth_context import OAuthContext, set_oauth_context

logger = logging.getLogger(__name__)

# Global variables for database connection and OAuth
_connection_manager = None
_db = ""
_oauth_config = None
_oauth_middleware = None

async def initialize_database():
    """Initialize database connection from environment or command line."""
    global _connection_manager, _db
    
    # Parse command line arguments for database URL
    parser = argparse.ArgumentParser(description="Teradata MCP Server")
    parser.add_argument("database_url", help="Database connection URL", nargs="?")
    args = parser.parse_args()
    database_url = os.environ.get("DATABASE_URI", args.database_url)
    
    if not database_url:
        logger.warning("No database URL provided. Database operations will fail.")
        return
    
    # Initialize database connection
    parsed_url = urlparse(database_url)
    _db = parsed_url.path.lstrip('/') 
    
    # Create connection manager with configurable retry settings
    max_retries = int(os.environ.get("DB_MAX_RETRIES", "3"))
    initial_backoff = float(os.environ.get("DB_INITIAL_BACKOFF", "1.0"))
    max_backoff = float(os.environ.get("DB_MAX_BACKOFF", "30.0"))

    _connection_manager = TeradataConnectionManager(
        database_url=database_url,
        db_name=_db,
        max_retries=max_retries,
        initial_backoff=initial_backoff,
        max_backoff=max_backoff
    )

    # Set the connection manager in the function modules BEFORE attempting connection
    # This ensures tools can attempt reconnection even if initial connection fails
    set_tools_connection(_connection_manager, _db)
    set_resource_connection(_connection_manager, _db)

    try:
        # Test initial connection (but don't fail if it doesn't work)
        await _connection_manager.ensure_connection()
        logger.info("Successfully connected to database and initialized connection manager")

    except Exception as e:
        logger.warning(
            f"Could not connect to database on startup: {obfuscate_password(str(e))}",
        )
        logger.warning(
            "The MCP server will start and will attempt to connect on each tool call.",
        )

async def initialize_oauth():
    """Initialize OAuth 2.1 authentication from environment variables."""
    global _oauth_config, _oauth_middleware
    
    try:
        # Load OAuth configuration from environment
        _oauth_config = OAuthConfig.from_environment()
        
        if _oauth_config.enabled:
            # Initialize OAuth components
            metadata = ProtectedResourceMetadata(_oauth_config)
            _oauth_middleware = OAuthMiddleware(_oauth_config, metadata)
            
            # Set up OAuth context for tools
            oauth_context = OAuthContext(_oauth_config, metadata)
            set_oauth_context(oauth_context)
            
            logger.info(f"OAuth 2.1 authentication enabled for realm: {_oauth_config.realm}")
            logger.info(f"Authorization server: {_oauth_config.get_issuer_url()}")
            logger.info(f"Required scopes: {_oauth_config.required_scopes}")
        else:
            logger.info("OAuth 2.1 authentication is disabled")
            # Set up empty OAuth context
            set_oauth_context(None)
            
    except Exception as e:
        logger.warning(f"OAuth initialization failed: {e}")
        logger.warning("Server will start without OAuth authentication")
        _oauth_config = OAuthConfig(enabled=False)
        _oauth_middleware = None
        set_oauth_context(None)

# Flag to track if we've initialized (for lifespan)
_initialized = False

@asynccontextmanager
async def lifespan(app):
    """Lifespan context manager for FastAPI to ensure initialization before accepting requests."""
    global _initialized

    # Startup: Initialize OAuth and database before accepting requests
    logger.info("Starting initialization sequence...")
    await initialize_oauth()
    await initialize_database()
    setup_oauth_endpoints()
    _initialized = True
    logger.info("Initialization complete, server ready to accept requests")

    yield

    # Shutdown: Clean up connections
    logger.info("Shutting down server...")
    if _connection_manager:
        try:
            await _connection_manager.close()
            logger.info("Database connections closed")
        except Exception as e:
            logger.error(f"Error closing database connections: {e}")

# Create FastMCP app
app = FastMCP("teradata-mcp")

def setup_oauth_endpoints():
    """Setup OAuth endpoints for FastMCP app."""
    global _oauth_config, _oauth_middleware
    
    if _oauth_config and _oauth_config.enabled and _oauth_middleware:
        metadata = ProtectedResourceMetadata(_oauth_config)
        oauth_endpoints = OAuthEndpoints(_oauth_config, metadata, _oauth_middleware)
        
        # Register OAuth endpoints with the FastAPI app for streamable-http transport
        # Note: For SSE transport, OAuth endpoints are handled in create_starlette_app()
        if hasattr(app, '_app') and hasattr(app._app, 'routes'):
            oauth_endpoints.register_endpoints(app._app)
            logger.info("OAuth endpoints registered with FastAPI app (streamable-http transport)")
        else:
            logger.warning("Could not register OAuth endpoints with FastAPI app")
    else:
        logger.info("OAuth endpoints not registered - OAuth is disabled")

# Set up the handlers using the internal MCP server for dynamic resources and tools
app._mcp_server.list_tools()(handle_list_tools)
app._mcp_server.call_tool(validate_input=False)(handle_tool_call)
app._mcp_server.list_resources()(handle_list_resources)
app._mcp_server.read_resource()(handle_read_resource)
app._mcp_server.list_prompts()(handle_list_prompts)
app._mcp_server.get_prompt()(handle_get_prompt)

# Note: OAuth endpoints are now set up in the lifespan context manager
# to ensure proper initialization before accepting requests

def create_starlette_app(mcp_server: Server, *, debug: bool = False) -> Starlette:
    """Create a Starlette application that can serve the provided mcp server with SSE and OAuth endpoints."""
    sse = SseServerTransport("/messages/")

    async def handle_sse(request: Request) -> None:
        async with sse.connect_sse(
                request.scope,
                request.receive,
                request._send, 
        ) as (read_stream, write_stream):
            await mcp_server.run(
                read_stream,
                write_stream,
                mcp_server.create_initialization_options(),
            )

    # Create base routes for SSE
    routes = [
        Route("/sse", endpoint=handle_sse),
        Mount("/messages/", app=sse.handle_post_message),
    ]
    
    # Add OAuth endpoints if OAuth is enabled
    if _oauth_config and _oauth_config.enabled and _oauth_middleware:
        from starlette.responses import JSONResponse
        
        # Create metadata handler for OAuth endpoints
        metadata = ProtectedResourceMetadata(_oauth_config)
        
        # Add OAuth discovery endpoints directly to Starlette routes
        async def oauth_protected_resource_metadata(request: Request):
            """OAuth Protected Resource Metadata endpoint for SSE transport."""
            try:
                metadata_dict = metadata.get_metadata()
                return JSONResponse(
                    content=metadata_dict,
                    headers={
                        "Content-Type": "application/json",
                        "Cache-Control": "max-age=3600",
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

        async def mcp_server_info(request: Request):
            """MCP Server Information endpoint for SSE transport."""
            try:
                info = {
                    "name": "teradata-mcp",
                    "version": "1.0.0", 
                    "description": "Teradata Model Context Protocol Server",
                    "transport": "sse",
                    "capabilities": {
                        "tools": True,
                        "resources": True,
                        "prompts": True,
                        "dynamic_resources": True
                    },
                    "authentication": {
                        "oauth2": {
                            "enabled": _oauth_config.enabled,
                            "authorization_server": _oauth_config.get_issuer_url() if _oauth_config.enabled else None,
                            "flows_supported": ["authorization_code", "client_credentials"] if _oauth_config.enabled else [],
                            "scopes_supported": [
                                "teradata:read", "teradata:write", "teradata:admin",
                                "teradata:query", "teradata:schema"
                            ] if _oauth_config.enabled else [],
                            "protected_resource_metadata": "/.well-known/oauth-protected-resource" if _oauth_config.enabled else None
                        }
                    },
                    "endpoints": {
                        "sse": "/sse",
                        "messages": "/messages/",
                        "health": "/health",
                        "protected_resource_metadata": "/.well-known/oauth-protected-resource" if _oauth_config.enabled else None
                    }
                }
                return JSONResponse(content=info)
            except Exception as e:
                logger.error(f"Error generating MCP server info: {e}")
                return JSONResponse(status_code=500, content={"error": "Internal server error"})

        async def health_check(request: Request):
            """Health check endpoint for SSE transport."""
            try:
                health_status = {
                    "status": "healthy",
                    "transport": "sse",
                    "oauth": {
                        "enabled": _oauth_config.enabled,
                        "configured": bool(_oauth_config.enabled and _oauth_config.keycloak_url and _oauth_config.realm)
                    },
                    "database": {
                        "status": "connected" if _connection_manager else "disconnected"
                    }
                }
                return JSONResponse(content=health_status)
            except Exception as e:
                logger.error(f"Health check error: {e}")
                return JSONResponse(status_code=503, content={"status": "unhealthy", "error": str(e)})

        async def oauth_endpoints_preflight(request: Request):
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

        # Add OAuth routes to Starlette
        routes.extend([
            Route("/.well-known/oauth-protected-resource", endpoint=oauth_protected_resource_metadata, methods=["GET"]),
            Route("/.well-known/mcp-server-info", endpoint=mcp_server_info, methods=["GET"]),
            Route("/health", endpoint=health_check, methods=["GET"]),
            # CORS preflight routes
            Route("/.well-known/oauth-protected-resource", endpoint=oauth_endpoints_preflight, methods=["OPTIONS"]),
            Route("/.well-known/mcp-server-info", endpoint=oauth_endpoints_preflight, methods=["OPTIONS"]),
            Route("/health", endpoint=oauth_endpoints_preflight, methods=["OPTIONS"]),
        ])
        
        logger.info("OAuth endpoints added to SSE Starlette app")

    return Starlette(
        debug=debug,
        routes=routes,
    )

async def main():
    """Main entry point for the server."""
    # Configure logging
    logging.basicConfig(level=logging.INFO)

    mcp_transport = os.getenv("MCP_TRANSPORT", "stdio").lower()
    logger.info(f"MCP_TRANSPORT: {mcp_transport}")

    # Start the MCP server
    if mcp_transport == "sse":
        # For SSE, initialize before starting the server (SSE handles its own startup)
        await initialize_oauth()
        await initialize_database()
        setup_oauth_endpoints()

        app.settings.host = os.getenv("MCP_HOST")
        app.settings.port = int(os.getenv("MCP_PORT"))
        logger.info(f"Starting MCP server on {app.settings.host}:{app.settings.port}")
        mcp_server = app._mcp_server
        starlette_app = create_starlette_app(mcp_server, debug=True)
        config = uvicorn.Config(starlette_app, host=app.settings.host, port=app.settings.port, log_level="info")
        server = uvicorn.Server(config)
        await server.serve()
        #await uvicorn.run(starlette_app, host=app.settings.host, port=app.settings.port)
        #await app.run_sse_async()

    elif mcp_transport == "streamable-http":
        # For streamable-http, integrate lifespan to ensure initialization before requests
        app.settings.host = os.getenv("MCP_HOST")
        app.settings.port = int(os.getenv("MCP_PORT"))
        app.settings.streamable_http_path = os.getenv("MCP_PATH", "/mcp/")
        logger.info(f"Starting MCP server on {app.settings.host}:{app.settings.port} with path {app.settings.streamable_http_path}")

        # Attach lifespan to the underlying FastAPI app
        if hasattr(app, '_app'):
            logger.info("Attaching lifespan context manager to FastAPI app")
            app._app.router.lifespan_context = lifespan
        else:
            logger.warning("Could not attach lifespan - initializing manually")
            await initialize_oauth()
            await initialize_database()
            setup_oauth_endpoints()

        await app.run_streamable_http_async()
    else:
        # For stdio, initialize before starting (stdio is synchronous)
        await initialize_oauth()
        await initialize_database()
        setup_oauth_endpoints()

        logger.info("Starting MCP server on stdin/stdout")
        await app.run_stdio_async()

if __name__ == "__main__":
    asyncio.run(main())
