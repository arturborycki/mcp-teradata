"""
Search Tool - The primary MCP tool for discovering other tools.

This is the key tool in the "tools as code" pattern. Instead of loading all tools
upfront, the agent uses this search tool to progressively discover only the tools
it needs for the current task.
"""

from typing import List, Optional
from pydantic import Field

from .base import ToolBase, ToolInput, ToolOutput, ToolMetadata


class SearchToolInput(ToolInput):
    """Input schema for the search_tool."""
    query: Optional[str] = Field(
        default=None,
        description="Text query to search for in tool names, descriptions, and tags"
    )
    category: Optional[str] = Field(
        default=None,
        description="Filter by tool category (e.g., 'database', 'analytics')"
    )
    tags: Optional[List[str]] = Field(
        default=None,
        description="Filter by tags (returns tools matching any of the provided tags)"
    )
    detail_level: str = Field(
        default="standard",
        description="Amount of detail to return: 'minimal' (name only), 'standard' (name + description), 'full' (complete schemas)"
    )


class SearchToolOutput(ToolOutput):
    """Output schema for the search_tool."""
    tools: List[dict] = Field(
        default_factory=list,
        description="List of tools matching the search criteria"
    )
    count: int = Field(
        default=0,
        description="Number of tools found"
    )
    execution_guide: str = Field(
        default="",
        description="Instructions for executing the discovered tools"
    )


class SearchTool(ToolBase):
    """
    Tool for discovering available tools in the system.

    This is the main entry point for the "tools as code" pattern.
    Agents use this tool to:
    1. Discover what tools are available
    2. Search for specific functionality
    3. Get detailed schemas only for tools they need

    Examples:
    - Search for database tools: {"category": "database"}
    - Search for query functionality: {"query": "query"}
    - Get minimal list: {"detail_level": "minimal"}
    - Get full schema for SQL tools: {"tags": ["sql"], "detail_level": "full"}
    """

    METADATA = ToolMetadata(
        name="search_tool",
        description="Search and discover available tools. Use this to find tools for specific tasks before calling them.",
        category="system",
        tags=["search", "discovery", "tools", "meta"],
        requires_connection=False,
        requires_oauth=False
    )

    class InputSchema(SearchToolInput):
        pass

    class OutputSchema(SearchToolOutput):
        pass

    async def execute(self, input_data: SearchToolInput, context: dict) -> SearchToolOutput:
        """
        Execute the search tool to discover available tools.

        Args:
            input_data: Search parameters
            context: Execution context (contains tool_executor)

        Returns:
            List of tools matching the search criteria
        """
        from .executor import ToolExecutor

        # Get tool executor from context or create new one
        tool_executor = context.get('tool_executor')
        if not tool_executor:
            tool_executor = ToolExecutor()

        # Perform the search
        tools = tool_executor.search_tools(
            query=input_data.query,
            category=input_data.category,
            tags=input_data.tags,
            detail_level=input_data.detail_level
        )

        # Generate execution guide for tools-as-code pattern
        execution_guide = self._generate_execution_guide(tools, input_data.detail_level)

        return SearchToolOutput(
            success=True,
            tools=tools,
            count=len(tools),
            execution_guide=execution_guide
        )

    def _generate_execution_guide(self, tools: List[dict], detail_level: str) -> str:
        """
        Generate execution instructions for discovered tools.

        In tools-as-code pattern (search_only mode), tools must be executed
        via the execute_tool proxy.
        """
        if not tools:
            return "No tools found matching your criteria."

        import os
        tools_mode = os.getenv("TOOLS_MODE", "search_only").lower()

        if tools_mode == "search_only":
            # Execute proxy pattern active
            guide = [
                f"Found {len(tools)} tool(s). To execute any of these tools:",
                "",
                "Use execute_tool with:",
                "  • tool_name: Name of the tool (e.g., 'query', 'list_db')",
                "  • arguments: Tool arguments as shown in inputSchema",
                "",
                "Example:",
                "  execute_tool({",
                "    \"tool_name\": \"query\",",
                "    \"arguments\": {\"query\": \"SELECT * FROM table\"}",
                "  })",
            ]

            if detail_level == "full" and tools:
                guide.extend([
                    "",
                    f"First tool example: {tools[0]['name']}",
                    f"  execute_tool({{",
                    f"    \"tool_name\": \"{tools[0]['name']}\",",
                    f"    \"arguments\": <use inputSchema from above>",
                    f"  }})"
                ])

        else:
            # Hybrid mode - tools directly callable
            guide = [
                f"Found {len(tools)} tool(s). These tools are directly callable.",
                "",
                "You can call them directly by name:",
                ", ".join(t['name'] for t in tools[:5])
            ]
            if len(tools) > 5:
                guide.append(f"... and {len(tools) - 5} more")

        return "\n".join(guide)


# Convenience function for use in MCP handlers
async def search_tools(
    query: Optional[str] = None,
    category: Optional[str] = None,
    tags: Optional[List[str]] = None,
    detail_level: str = "standard"
) -> dict:
    """
    Convenience function to search for tools.

    Args:
        query: Text query
        category: Category filter
        tags: Tag filters
        detail_level: Detail level

    Returns:
        Search results as dictionary
    """
    tool = SearchTool()
    input_data = SearchToolInput(
        query=query,
        category=category,
        tags=tags,
        detail_level=detail_level
    )
    output = await tool.execute(input_data, {'tool_executor': None})
    return output.model_dump()
