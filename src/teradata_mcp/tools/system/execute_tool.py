"""
Execute Tool - Universal proxy for executing discovered tools.

This tool implements the "execute proxy" pattern for true tools-as-code:
- Only 2 tools visible to Claude initially (search_tool + execute_tool)
- search_tool discovers available tools
- execute_tool routes execution to discovered tools
- Achieves 71-98% token reduction while maintaining full functionality
"""

from typing import Any, Dict, Optional
from pydantic import Field
import logging

from ..base import ToolBase, ToolInput, ToolOutput, ToolMetadata

logger = logging.getLogger(__name__)


class ExecuteToolInput(ToolInput):
    """Input schema for execute_tool."""
    tool_name: str = Field(
        ...,
        description="Name of the tool to execute (discover tools first with search_tool)"
    )
    arguments: Dict[str, Any] = Field(
        default_factory=dict,
        description="Arguments to pass to the tool (use schema from search_tool results)"
    )


class ExecuteToolOutput(ToolOutput):
    """Output schema for execute_tool."""
    tool_executed: str = Field(
        default="",
        description="Name of the tool that was executed"
    )
    result: Dict[str, Any] = Field(
        default_factory=dict,
        description="Result from the executed tool"
    )


class ExecuteTool(ToolBase):
    """
    Universal executor for discovered tools.

    This tool acts as a proxy/router that:
    1. Receives a tool name and arguments
    2. Loads the requested tool dynamically
    3. Attaches the connection from registry (if needed)
    4. Executes the tool
    5. Returns the result

    This enables the tools-as-code pattern where only 2 tools are visible
    to the LLM initially (search_tool + execute_tool), but all tools are
    executable after discovery.

    Example Workflow:
    ```python
    # Step 1: Discover tools
    search_result = search_tool({"query": "database", "detail_level": "full"})
    # Returns: {"tools": [{"name": "query", "inputSchema": {...}}, ...]}

    # Step 2: Execute discovered tool
    query_result = execute_tool({
        "tool_name": "query",
        "arguments": {"query": "SELECT * FROM table"}
    })
    # Returns: {"success": true, "results": [[...]], "row_count": 10}
    ```

    Connection Management:
    The execute_tool automatically handles connection attachment:
    - Gets tool_executor from context
    - Loads the target tool
    - Tool attaches to connection from ConnectionRegistry
    - No manual connection passing needed!
    """

    METADATA = ToolMetadata(
        name="execute_tool",
        description=(
            "Execute a tool discovered via search_tool. "
            "Use search_tool first to discover available tools, "
            "then use execute_tool with the tool name and arguments. "
            "This is the universal entry point for all discovered tools."
        ),
        category="system",
        tags=["execution", "proxy", "meta", "tools-as-code"],
        requires_connection=False,  # Proxy itself doesn't need connection
        requires_oauth=False
    )

    class InputSchema(ExecuteToolInput):
        pass

    class OutputSchema(ExecuteToolOutput):
        pass

    async def execute(
        self,
        input_data: ExecuteToolInput,
        context: Optional[Dict[str, Any]] = None
    ) -> ExecuteToolOutput:
        """
        Execute a discovered tool by routing to its implementation.

        Args:
            input_data: Tool name and arguments
            context: Execution context with tool_executor

        Returns:
            Result from the executed tool
        """
        tool_name = input_data.tool_name
        arguments = input_data.arguments

        logger.info(f"execute_tool routing to: {tool_name} with args: {arguments}")

        # Get tool executor from context
        if not context or 'tool_executor' not in context:
            return ExecuteToolOutput(
                success=False,
                error="Tool executor not available in context",
                tool_executed=tool_name
            )

        tool_executor = context['tool_executor']

        try:
            # Execute the target tool
            # The executor will:
            # 1. Load the tool class dynamically
            # 2. Attach connection from registry (if tool needs it)
            # 3. Execute the tool with provided arguments
            # 4. Return the result
            result = await tool_executor.execute_tool(
                tool_name=tool_name,
                arguments=arguments,
                context=context  # Pass full context (includes connection_manager)
            )

            # Check if tool was found
            if not result.get('success') and 'not found' in result.get('error', '').lower():
                return ExecuteToolOutput(
                    success=False,
                    error=(
                        f"Tool '{tool_name}' not found. "
                        "Use search_tool to discover available tools first."
                    ),
                    tool_executed=tool_name
                )

            # Return the result wrapped in ExecuteToolOutput
            return ExecuteToolOutput(
                success=result.get('success', True),
                error=result.get('error'),
                tool_executed=tool_name,
                result={k: v for k, v in result.items() if k not in ['success', 'error']}
            )

        except Exception as e:
            logger.error(f"Error executing tool '{tool_name}' via execute_tool: {e}", exc_info=True)
            return ExecuteToolOutput(
                success=False,
                error=f"Error executing tool '{tool_name}': {str(e)}",
                tool_executed=tool_name
            )
