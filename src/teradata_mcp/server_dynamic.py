"""
Teradata MCP Server with Dynamic Tools Support (Experimental)

This is an experimental version of the server that supports the "tools as code" pattern.
It can run in two modes:

1. TOOLS_MODE=search_only (default): Only exposes search_tool, agents discover tools dynamically
2. TOOLS_MODE=hybrid: Exposes all tools for backward compatibility

Usage:
    # Pure tools-as-code pattern (98.7% token reduction)
    export TOOLS_MODE=search_only
    python -m teradata_mcp.server_dynamic

    # Hybrid mode (all tools exposed)
    export TOOLS_MODE=hybrid
    python -m teradata_mcp.server_dynamic

    # Use original server (unchanged)
    python -m teradata_mcp.server
"""
import argparse
import asyncio
import logging
import os
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

# Import BOTH tool systems
from .fnc_tools import (
    set_tools_connection as set_tools_connection_old,
    handle_list_tools as handle_list_tools_old,
    handle_tool_call as handle_tool_call_old
)
from .fnc_tools_dynamic import (
    initialize_dynamic_tools,
    handle_list_dynamic_tools,
    handle_dynamic_tool_call
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

# Global variables
_connection_manager = None
_db = ""
_oauth_config = None
_oauth_middleware = None
_tools_mode = "search_only"  # Default to tools-as-code pattern


async def initialize_database():
    """Initialize database connection from environment or command line."""
    global _connection_manager, _db

    parser = argparse.ArgumentParser(description="Teradata MCP Server (Dynamic Tools)")
    parser.add_argument("database_url", help="Database connection URL", nargs="?")
    args = parser.parse_args()
    database_url = os.environ.get("DATABASE_URI", args.database_url)

    if not database_url:
        logger.warning("No database URL provided. Database operations will fail.")
        return

    parsed_url = urlparse(database_url)
    _db = parsed_url.path.lstrip('/')

    try:
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

        await _connection_manager.ensure_connection()

        # Initialize BOTH tool systems
        set_tools_connection_old(_connection_manager, _db)
        initialize_dynamic_tools(_connection_manager, _db)

        set_resource_connection(_connection_manager, _db)
        logger.info("Successfully connected to database and initialized both tool systems")

    except Exception as e:
        logger.warning(
            f"Could not connect to database: {obfuscate_password(str(e))}",
        )


async def initialize_oauth():
    """Initialize OAuth 2.1 authentication from environment variables."""
    global _oauth_config, _oauth_middleware

    try:
        _oauth_config = OAuthConfig.from_environment()

        if _oauth_config.enabled:
            metadata = ProtectedResourceMetadata(_oauth_config)
            _oauth_middleware = OAuthMiddleware(_oauth_config, metadata)

            oauth_context = OAuthContext(_oauth_config, metadata)
            set_oauth_context(oauth_context)

            logger.info(f"OAuth 2.1 authentication enabled for realm: {_oauth_config.realm}")
        else:
            logger.info("OAuth 2.1 authentication is disabled")
            set_oauth_context(None)

    except Exception as e:
        logger.warning(f"OAuth initialization failed: {e}")
        _oauth_config = OAuthConfig(enabled=False)
        _oauth_middleware = None
        set_oauth_context(None)


# Create FastMCP app
app = FastMCP("teradata-mcp-dynamic")


def setup_oauth_endpoints():
    """Setup OAuth endpoints for FastMCP app."""
    global _oauth_config, _oauth_middleware

    if _oauth_config and _oauth_config.enabled and _oauth_middleware:
        metadata = ProtectedResourceMetadata(_oauth_config)
        oauth_endpoints = OAuthEndpoints(_oauth_config, metadata, _oauth_middleware)

        if hasattr(app, '_app') and hasattr(app._app, 'routes'):
            oauth_endpoints.register_endpoints(app._app)
            logger.info("OAuth endpoints registered with FastAPI app")
    else:
        logger.info("OAuth endpoints not registered - OAuth is disabled")


# Configure which tool system to use based on environment
_tools_mode = os.getenv("TOOLS_MODE", "search_only").lower()

if _tools_mode == "search_only":
    logger.info("⚡ Running in TOOLS-AS-CODE mode (search_only) - Only search_tool exposed")
    app._mcp_server.list_tools()(handle_list_dynamic_tools)
    app._mcp_server.call_tool(validate_input=False)(handle_dynamic_tool_call)
elif _tools_mode == "hybrid":
    logger.info("🔀 Running in HYBRID mode - All tools exposed via dynamic system")
    app._mcp_server.list_tools()(handle_list_dynamic_tools)
    app._mcp_server.call_tool(validate_input=False)(handle_dynamic_tool_call)
else:
    logger.info("📦 Running in LEGACY mode - Using original tool system")
    app._mcp_server.list_tools()(handle_list_tools_old)
    app._mcp_server.call_tool(validate_input=False)(handle_tool_call_old)

# Resources and prompts use same handlers
app._mcp_server.list_resources()(handle_list_resources)
app._mcp_server.read_resource()(handle_read_resource)
app._mcp_server.list_prompts()(handle_list_prompts)
app._mcp_server.get_prompt()(handle_get_prompt)

setup_oauth_endpoints()


def create_starlette_app(mcp_server: Server, *, debug: bool = False) -> Starlette:
    """Create a Starlette application for SSE transport."""
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

    routes = [
        Route("/sse", endpoint=handle_sse),
        Mount("/messages/", app=sse.handle_post_message),
    ]

    # Add OAuth endpoints if enabled (same as original server.py)
    if _oauth_config and _oauth_config.enabled and _oauth_middleware:
        from starlette.responses import JSONResponse

        metadata = ProtectedResourceMetadata(_oauth_config)

        async def oauth_protected_resource_metadata(request: Request):
            try:
                metadata_dict = metadata.get_metadata()
                return JSONResponse(
                    content=metadata_dict,
                    headers={
                        "Content-Type": "application/json",
                        "Cache-Control": "max-age=3600",
                        "Access-Control-Allow-Origin": "*"
                    }
                )
            except Exception as e:
                logger.error(f"Error generating protected resource metadata: {e}")
                return JSONResponse(status_code=500, content={"error": "Internal server error"})

        async def mcp_server_info(request: Request):
            try:
                info = {
                    "name": "teradata-mcp-dynamic",
                    "version": "1.0.0-experimental",
                    "description": "Teradata MCP Server with Tools-as-Code Pattern",
                    "transport": "sse",
                    "tools_mode": _tools_mode,
                    "capabilities": {
                        "tools": True,
                        "resources": True,
                        "prompts": True,
                        "dynamic_tools": True,
                        "search_tool": True
                    }
                }
                return JSONResponse(content=info)
            except Exception as e:
                logger.error(f"Error generating MCP server info: {e}")
                return JSONResponse(status_code=500, content={"error": "Internal server error"})

        routes.extend([
            Route("/.well-known/oauth-protected-resource", endpoint=oauth_protected_resource_metadata, methods=["GET"]),
            Route("/.well-known/mcp-server-info", endpoint=mcp_server_info, methods=["GET"]),
        ])

    return Starlette(debug=debug, routes=routes)


async def main():
    """Main entry point for the dynamic tools server."""
    logging.basicConfig(level=logging.INFO)

    logger.info("=" * 80)
    logger.info("Teradata MCP Server - Tools-as-Code Pattern (EXPERIMENTAL)")
    logger.info("=" * 80)
    logger.info(f"Tools Mode: {_tools_mode}")
    logger.info("")

    await initialize_oauth()
    await initialize_database()
    setup_oauth_endpoints()

    mcp_transport = os.getenv("MCP_TRANSPORT", "stdio").lower()
    logger.info(f"MCP_TRANSPORT: {mcp_transport}")

    if mcp_transport == "sse":
        app.settings.host = os.getenv("MCP_HOST")
        app.settings.port = int(os.getenv("MCP_PORT"))
        logger.info(f"Starting MCP server on {app.settings.host}:{app.settings.port}")
        mcp_server = app._mcp_server
        starlette_app = create_starlette_app(mcp_server, debug=True)
        config = uvicorn.Config(starlette_app, host=app.settings.host, port=app.settings.port, log_level="info")
        server = uvicorn.Server(config)
        await server.serve()
    elif mcp_transport == "streamable-http":
        app.settings.host = os.getenv("MCP_HOST")
        app.settings.port = int(os.getenv("MCP_PORT"))
        app.settings.streamable_http_path = os.getenv("MCP_PATH", "/mcp/")
        logger.info(f"Starting MCP server on {app.settings.host}:{app.settings.port}")
        await app.run_streamable_http_async()
    else:
        logger.info("Starting MCP server on stdin/stdout")
        await app.run_stdio_async()


if __name__ == "__main__":
    asyncio.run(main())
