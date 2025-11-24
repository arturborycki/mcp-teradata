"""
Dynamic Tool Functions using Tools-as-Code Pattern

This module provides an alternative tool handling system that uses
the "tools as code" pattern. It can coexist with the traditional
fnc_tools.py module for gradual migration.
"""

import logging
from typing import Any, List
from pathlib import Path

import mcp.types as types

from .tools import ToolExecutor
from .tools.base import ToolContext
from .oauth_context import require_oauth_authorization, get_oauth_error

logger = logging.getLogger(__name__)

ResponseType = List[types.TextContent | types.ImageContent | types.EmbeddedResource]

# Global variables
_connection_manager = None
_db = ""
_tool_executor: ToolExecutor = None


def initialize_dynamic_tools(connection_manager, db: str):
    """
    Initialize the dynamic tools system.

    Args:
        connection_manager: Database connection manager
        db: Database name
    """
    global _connection_manager, _db, _tool_executor

    _connection_manager = connection_manager
    _db = db

    # Initialize tool executor
    tools_dir = Path(__file__).parent / "tools"
    _tool_executor = ToolExecutor(tools_dir)

    logger.info(f"Dynamic tools system initialized with tools directory: {tools_dir}")

    # Discover and log available tools
    tools = _tool_executor.discover_all_tools()
    logger.info(f"Discovered {len(tools)} tools:")
    for tool_meta in tools:
        logger.info(f"  - {tool_meta.name} ({tool_meta.category}): {tool_meta.description}")


async def handle_list_dynamic_tools() -> list[types.Tool]:
    """
    List available tools using the dynamic system.

    IMPORTANT: In both modes, ALL tools must be registered with MCP for execution.
    The difference between modes is in the presentation and discoverability workflow:

    - TOOLS_MODE=search_only: All tools registered, but search_tool is the entry point
      (tools are discoverable dynamically, but MCP must know about them for execution)
    - TOOLS_MODE=hybrid: All tools registered and immediately visible
      (traditional approach - all tools exposed upfront)

    The "search_only" mode provides token efficiency by encouraging discovery workflow,
    but tools must still be registered with MCP framework for execution to work.
    """
    import os

    tools_mode = os.getenv("TOOLS_MODE", "search_only").lower()

    if not _tool_executor:
        logger.warning("Tool executor not initialized")
        return []

    # Discover all tools dynamically
    tools_metadata = _tool_executor.discover_all_tools()

    # Convert to MCP tool format
    mcp_tools = []
    for meta in tools_metadata:
        # Load the tool class to get schema
        tool_class = _tool_executor.load_tool(meta.name)
        if tool_class:
            mcp_tools.append(types.Tool(
                name=meta.name,
                description=meta.description,
                inputSchema=tool_class.get_input_schema()
            ))

    if tools_mode == "search_only":
        # In search_only mode, we still register all tools with MCP (required for execution),
        # but we log that search_tool is the recommended entry point
        logger.info(f"Listing tools in search_only mode: {len(mcp_tools)} tools registered with MCP")
        logger.info("Note: Use search_tool to discover tools dynamically (tools-as-code pattern)")
    else:
        # Hybrid mode: same tool list, but presented as all tools immediately available
        logger.info(f"Listing tools in hybrid mode: {len(mcp_tools)} tools exposed")

    return mcp_tools


async def handle_dynamic_tool_call(
    name: str, arguments: dict | None
) -> List[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """
    Handle tool execution using the dynamic system.

    Args:
        name: Tool name
        arguments: Tool arguments

    Returns:
        Tool execution results
    """
    logger.info(f"Dynamic tool call: {name} with arguments: {arguments}")

    # Check OAuth authorization
    if not require_oauth_authorization(name):
        error_msg = get_oauth_error(name)
        logger.warning(f"OAuth authorization failed for tool {name}: {error_msg}")
        return [types.TextContent(type="text", text=f"Authorization Error: {error_msg}")]

    if not _tool_executor:
        logger.error("Tool executor not initialized")
        return [types.TextContent(
            type="text",
            text="Error: Tool system not initialized"
        )]

    try:
        # Create execution context
        context = ToolContext(
            connection_manager=_connection_manager,
            db_name=_db,
            oauth_token=None,  # TODO: Get from OAuth context if needed
            user_id=None
        )

        # Add tool_executor to context for search_tool
        context_dict = context.model_dump()
        context_dict['tool_executor'] = _tool_executor

        # Execute the tool
        result = await _tool_executor.execute_tool(
            tool_name=name,
            arguments=arguments or {},
            context=context
        )

        # Format response
        if result.get("success"):
            # Remove success/error fields for cleaner output
            output_data = {k: v for k, v in result.items() if k not in ["success", "error"]}
            return [types.TextContent(
                type="text",
                text=str(output_data)
            )]
        else:
            return [types.TextContent(
                type="text",
                text=f"Error: {result.get('error', 'Unknown error')}"
            )]

    except Exception as e:
        logger.error(f"Error executing dynamic tool {name}: {e}", exc_info=True)
        return [types.TextContent(
            type="text",
            text=f"Error executing tool {name}: {str(e)}"
        )]


def get_tool_executor() -> ToolExecutor:
    """Get the global tool executor instance."""
    return _tool_executor
