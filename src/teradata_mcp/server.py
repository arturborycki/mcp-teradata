import argparse
import asyncio
import logging
import os
import signal
from urllib.parse import urlparse
from pydantic import AnyUrl

from mcp.server import NotificationOptions, Server
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server
from mcp.server.sse import SseServerTransport

from .tdsql import obfuscate_password, TDConn
from .fnc_tools import (
    handle_list_tools,
    handle_tool_call,
    set_tools_connection
)
from .fnc_resources import (
    handle_list_resources,
    handle_read_resource,
    set_resource_connection
)
from .fnc_prompts import (
    handle_list_prompts,
    handle_get_prompt,
)

logger = logging.getLogger(__name__)

# --- CLI/stdio entrypoint ---
async def main():
    logger.info("Starting Teradata MCP Server")
    
    # Set up proper shutdown handling
    try:
        loop = asyncio.get_running_loop()
        signals = (signal.SIGTERM, signal.SIGINT)
        for s in signals:
            logger.info(f"Registering signal handler for {s.name}")
            loop.add_signal_handler(s, lambda s=s: logger.info(f"Received shutdown signal: {s.name}"))
    except NotImplementedError:
        # Windows doesn't support signals properly
        logger.warning("Signal handling not supported on Windows")
        pass
    
    # Get transport type from environment
    mcp_transport = os.getenv("MCP_TRANSPORT", "stdio").lower()
    logger.info(f"MCP_TRANSPORT: {mcp_transport}")
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Teradata MCP Server")
    parser.add_argument("database_url", help="Database connection URL", nargs="?")
    args = parser.parse_args()
    database_url = os.environ.get("DATABASE_URI", args.database_url)
    
    if not database_url:
        raise ValueError(
            "Error: No database URL provided. Please specify via 'DATABASE_URI' environment variable or command-line argument.",
        )
    
    # Initialize database connection
    parsed_url = urlparse(database_url)
    db = parsed_url.path.lstrip('/') 
    try:
        tdconn = TDConn(database_url)
        # Set the connection in the fnc_tools module
        set_tools_connection(tdconn, db)
        set_resource_connection(tdconn, db)
        logger.info("Successfully connected to database and initialized connection")
    except Exception as e:
        logger.warning(
            f"Could not connect to database: {obfuscate_password(str(e))}",
        )
        logger.warning(
            "The MCP server will start but database operations will fail until a valid connection is established.",
        )

    # Create MCP server
    server = Server("teradata-mcp")
    
    # Register handlers with decorators
    @server.list_prompts()
    async def _handle_list_prompts():
        return await handle_list_prompts()

    @server.get_prompt()
    async def _handle_get_prompt(name: str, arguments: dict[str, str] | None):
        return await handle_get_prompt(name, arguments)

    @server.list_resources()
    async def _handle_list_resources():
        return await handle_list_resources()

    @server.read_resource()
    async def _handle_read_resource(uri: AnyUrl):
        return await handle_read_resource(uri)

    @server.list_tools()
    async def _handle_list_tools():
        return await handle_list_tools()

    @server.call_tool()
    async def _handle_tool_call(name: str, arguments: dict | None):
        return await handle_tool_call(name, arguments)

    # Initialize server capabilities
    init_options = InitializationOptions(
        server_name="teradata-mcp",
        server_version="0.1.0",
        capabilities=server.get_capabilities(
            notification_options=NotificationOptions(),
            experimental_capabilities={},
        ),
    )

    # Start server based on transport type
    if mcp_transport == "stdio":
        logger.info("Starting server with stdio transport")
        async with stdio_server() as (read_stream, write_stream):
            await server.run(read_stream, write_stream, init_options)
            
    elif mcp_transport == "sse":
        logger.info("Starting server with SSE transport")
        
        try:
            # Import locally to access in function scope
            from starlette.applications import Starlette
            from starlette.routing import Route, Mount
            from starlette.responses import Response
            import uvicorn
        except ImportError:
            raise ImportError("SSE transport requires starlette and uvicorn. Install with: pip install starlette uvicorn")
        
        # Create SSE transport
        host = os.getenv("MCP_HOST", "0.0.0.0")
        port = int(os.getenv("MCP_PORT", "8000"))
        sse_path = os.getenv("MCP_PATH", "/sse")
        message_path = "/messages/"
        
        sse_transport = SseServerTransport(message_path)
        
        async def handle_sse(request):
            """Handle SSE GET requests"""
            async with sse_transport.connect_sse(
                request.scope, request.receive, request._send
            ) as streams:
                await server.run(
                    streams[0], streams[1], init_options
                )
            return Response()
        
        # Create Starlette app with proper routing
        routes = [
            Route(sse_path, endpoint=handle_sse, methods=["GET"]),
            Mount(message_path, app=sse_transport.handle_post_message),
        ]
        
        app = Starlette(routes=routes)
        
        # Run with uvicorn
        config = uvicorn.Config(app, host=host, port=port, log_level="info")
        server_instance = uvicorn.Server(config)
        
        logger.info(f"SSE server starting on {host}:{port}")
        logger.info(f"SSE endpoint: {host}:{port}{sse_path}")
        logger.info(f"Message endpoint: {host}:{port}{message_path}")
        
        await server_instance.serve()
            
    elif mcp_transport == "streamable-http":
        logger.info("Starting server with streamable-http transport")
        
        try:
            # Import locally to access in function scope
            import uvicorn
            from starlette.applications import Starlette
            from starlette.routing import Mount, Route
            from starlette.responses import Response
            from contextlib import asynccontextmanager
        except ImportError:
            raise ImportError("Streamable HTTP transport requires starlette and uvicorn. Install with: pip install starlette uvicorn")
        
        # Create StreamableHTTP transport
        host = os.getenv("MCP_HOST", "0.0.0.0")
        port = int(os.getenv("MCP_PORT", "8000"))
        mcp_path = os.getenv("MCP_PATH", "/mcp/")
        
        try:
            from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
            streamable_http_available = True
        except ImportError:
            logger.warning("StreamableHTTPSessionManager not available in current MCP version")
            logger.info("Falling back to basic HTTP implementation - use SSE transport for full MCP functionality")
            streamable_http_available = False
        
        if not streamable_http_available:
            # Fallback to basic HTTP handling with proper MCP-like responses
            async def basic_http_handler(request):
                if request.method == "GET":
                    return Response(
                        content='{"jsonrpc": "2.0", "result": {"name": "teradata-mcp", "version": "0.1.0", "capabilities": {}}}',
                        media_type="application/json",
                        status_code=200
                    )
                elif request.method == "POST":
                    return Response(
                        content='{"jsonrpc": "2.0", "error": {"code": -32601, "message": "Streamable HTTP not available - use SSE transport"}}',
                        media_type="application/json", 
                        status_code=200
                    )
                else:
                    return Response("Method not allowed", status_code=405)
            
            app = Starlette(routes=[
                Route(mcp_path, endpoint=basic_http_handler, methods=["GET", "POST"])
            ])
            
            config = uvicorn.Config(app, host=host, port=port, log_level="info")
            server_instance = uvicorn.Server(config)
            
            logger.info(f"Basic HTTP server starting on {host}:{port}{mcp_path}")
            logger.info("Note: Use MCP_TRANSPORT=sse for full MCP functionality")
            await server_instance.serve()
            return
        
        # Generate session ID for streamable HTTP
        import uuid
        session_id = str(uuid.uuid4())
        
        # Create session manager
        session_manager = StreamableHTTPSessionManager(
            app=server,
            event_store=None,  # Could add event store for resumability
            json_response=False,
            stateless=False,
        )
        
        # Create a proper ASGI lifespan manager
        @asynccontextmanager
        async def lifespan(app):
            # Startup
            logger.info("Starting streamable HTTP session manager")
            async with session_manager.run():
                logger.info("StreamableHTTP session manager started successfully")
                try:
                    yield
                finally:
                    logger.info("Shutting down streamable HTTP session manager")
        
        # Create handler that handles HTTP requests through SessionManager
        async def streamable_http_handler(scope, receive, send):
            """ASGI handler for streamable HTTP requests"""
            await session_manager.handle_request(scope, receive, send)
        
        # Create Starlette app with MCP path and lifespan
        routes = [
            Mount(mcp_path, app=streamable_http_handler)
        ]
        
        app = Starlette(routes=routes, lifespan=lifespan)
        
        # Run with uvicorn
        config = uvicorn.Config(app, host=host, port=port, log_level="info")
        server_instance = uvicorn.Server(config)
        
        logger.info(f"Streamable HTTP server starting on {host}:{port}{mcp_path}")
        logger.info(f"Session ID: {session_id}")
        
        await server_instance.serve()
                
    else:
        raise ValueError(f"Unsupported transport: {mcp_transport}. Supported: stdio, sse, streamable-http")

if __name__ == "__main__":
    asyncio.run(main())
