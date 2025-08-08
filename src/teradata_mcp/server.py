"""
Teradata MCP Server using FastMCP
Supports all transport methods: stdio, SSE, and streamable-http
"""
import argparse
import asyncio
import logging
import os
from urllib.parse import urlparse
from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.prompts.base import TextContent, UserMessage

from .tdsql import obfuscate_password, TDConn
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

logger = logging.getLogger(__name__)

# Global variables for database connection
_tdconn = None
_db = ""

async def initialize_database():
    """Initialize database connection from environment or command line."""
    global _tdconn, _db
    
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
    
    try:
        _tdconn = TDConn(database_url)
        # Set the connection in the function modules
        set_tools_connection(_tdconn, _db)
        set_resource_connection(_tdconn, _db)
        logger.info("Successfully connected to database and initialized connection")
    except Exception as e:
        logger.warning(
            f"Could not connect to database: {obfuscate_password(str(e))}",
        )
        logger.warning(
            "The MCP server will start but database operations will fail until a valid connection is established.",
        )

# Create FastMCP app
app = FastMCP("teradata-mcp")

# Set up the handlers using the internal MCP server for dynamic resources and tools
app._mcp_server.list_tools()(handle_list_tools)
app._mcp_server.call_tool(validate_input=False)(handle_tool_call)
app._mcp_server.list_resources()(handle_list_resources)
app._mcp_server.read_resource()(handle_read_resource)
app._mcp_server.list_prompts()(handle_list_prompts)
app._mcp_server.get_prompt()(handle_get_prompt)

async def main():
    """Main entry point for the server."""
    # Configure logging
    logging.basicConfig(level=logging.INFO)
    
    # Initialize database connection
    await initialize_database()
    
    mcp_transport = os.getenv("MCP_TRANSPORT", "stdio").lower()
    logger.info(f"MCP_TRANSPORT: {mcp_transport}")

    # Start the MCP server
    if mcp_transport == "sse":
        app.settings.host = os.getenv("MCP_HOST")
        app.settings.port = int(os.getenv("MCP_PORT"))
        logger.info(f"Starting MCP server on {app.settings.host}:{app.settings.port}")
        await app.run_sse_async()
    elif mcp_transport == "streamable-http":
        app.settings.host = os.getenv("MCP_HOST")
        app.settings.port = int(os.getenv("MCP_PORT"))
        app.settings.streamable_http_path = os.getenv("MCP_PATH", "/mcp/")
        logger.info(f"Starting MCP server on {app.settings.host}:{app.settings.port} with path {app.settings.streamable_http_path}")
        await app.run_streamable_http_async()
    else:
        logger.info("Starting MCP server on stdin/stdout")
        await app.run_stdio_async()

if __name__ == "__main__":
    asyncio.run(main())
