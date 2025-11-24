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

    Three modes supported via TOOLS_MODE environment variable:

    - TOOLS_MODE=search_only: Only search_tool and execute_tool visible (TRUE tools-as-code)
      * 71-98% token reduction
      * Tools discovered via search_tool
      * Tools executed via execute_tool proxy
      * Full functionality maintained

    - TOOLS_MODE=hybrid: All tools visible immediately (traditional MCP)
      * All tools directly callable
      * No token savings
      * Backward compatible

    - TOOLS_MODE=legacy: Uses original tool system (fnc_tools.py)
      * For comparison and migration
    """
    import os

    tools_mode = os.getenv("TOOLS_MODE", "search_only").lower()

    if not _tool_executor:
        logger.warning("Tool executor not initialized")
        return []

    if tools_mode == "search_only":
        # EXECUTE PROXY PATTERN: Only expose search_tool + execute_tool
        # This achieves true tools-as-code with 71-98% token reduction
        logger.info("🎯 Listing tools in search_only mode (Execute Proxy Pattern)")
        logger.info("   Only 2 tools visible: search_tool + execute_tool")
        logger.info("   Token savings: ~71-98% compared to exposing all tools")

        mcp_tools = []

        # 1. Always include search_tool
        search_tool_class = _tool_executor.load_tool('search_tool')
        if search_tool_class:
            mcp_tools.append(types.Tool(
                name=search_tool_class.METADATA.name,
                description=search_tool_class.METADATA.description,
                inputSchema=search_tool_class.get_input_schema()
            ))
            logger.info("   ✓ search_tool - Discover available tools")

        # 2. Always include execute_tool
        execute_tool_class = _tool_executor.load_tool('execute_tool')
        if execute_tool_class:
            mcp_tools.append(types.Tool(
                name=execute_tool_class.METADATA.name,
                description=execute_tool_class.METADATA.description,
                inputSchema=execute_tool_class.get_input_schema()
            ))
            logger.info("   ✓ execute_tool - Execute discovered tools")

        logger.info(f"   Total: {len(mcp_tools)} tools registered (down from {len(_tool_executor.discover_all_tools())})")
        return mcp_tools

    else:
        # HYBRID MODE: Expose all tools directly (traditional approach)
        logger.info(f"🔀 Listing tools in hybrid mode (all tools exposed)")

        # Discover all tools dynamically
        tools_metadata = _tool_executor.discover_all_tools()

        # Convert to MCP tool format
        mcp_tools = []
        for meta in tools_metadata:
            tool_class = _tool_executor.load_tool(meta.name)
            if tool_class:
                mcp_tools.append(types.Tool(
                    name=meta.name,
                    description=meta.description,
                    inputSchema=tool_class.get_input_schema()
                ))

        logger.info(f"   Total: {len(mcp_tools)} tools directly callable")
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

        # Add tool_executor to context for search_tool and execute_tool
        context_dict = context.model_dump()
        context_dict['tool_executor'] = _tool_executor

        # Execute the tool
        # IMPORTANT: Pass context_dict (with tool_executor) not context object
        result = await _tool_executor.execute_tool(
            tool_name=name,
            arguments=arguments or {},
            context=context_dict  # Pass dict, not ToolContext object
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
