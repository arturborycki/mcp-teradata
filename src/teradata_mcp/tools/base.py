"""
Base classes and types for the tools-as-code system.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, TypeVar
from pydantic import BaseModel, Field


class ToolMetadata(BaseModel):
    """Metadata describing a tool."""
    name: str = Field(..., description="Unique identifier for the tool")
    description: str = Field(..., description="Human-readable description of what the tool does")
    category: str = Field(..., description="Category/group this tool belongs to (e.g., 'database', 'analytics')")
    tags: List[str] = Field(default_factory=list, description="Searchable tags for tool discovery")
    requires_connection: bool = Field(default=True, description="Whether tool requires database connection")
    requires_oauth: bool = Field(default=False, description="Whether tool requires OAuth authorization")
    version: str = Field(default="1.0.0", description="Tool version")


class ToolInput(BaseModel):
    """Base class for tool input schemas."""
    pass


class ToolOutput(BaseModel):
    """Base class for tool output schemas."""
    success: bool = Field(default=True, description="Whether the tool execution was successful")
    error: Optional[str] = Field(default=None, description="Error message if execution failed")


TInput = TypeVar('TInput', bound=ToolInput)
TOutput = TypeVar('TOutput', bound=ToolOutput)


class ToolBase(ABC):
    """
    Base class for all tools in the tools-as-code system with connection attachment support.

    Each tool should:
    1. Define METADATA as a class attribute
    2. Define InputSchema and OutputSchema as nested classes
    3. Implement the execute() method

    Connection Resolution:
    Tools can access connections through three mechanisms (in priority order):
    1. Attached connection (self._connection_manager) - set via attach_connection()
    2. Context parameter (context['connection_manager']) - backward compatible
    3. Connection registry - global fallback via ConnectionRegistry.get_instance()

    This design supports the "tools-as-code" pattern where connections are attached
    to tools at registration/discovery time rather than passed at execution time.
    """

    # Each tool must define these
    METADATA: ToolMetadata

    def __init__(self):
        """
        Initialize tool with connection attachment support.

        The attached connection (_connection_manager) starts as None and can be set
        via attach_connection() when the tool is registered/loaded. This allows tools
        to "know" about their connection before execution, supporting the external
        connection registry pattern.
        """
        self._connection_manager = None

    def attach_connection(self, connection_manager):
        """
        Attach a connection manager to this tool instance.

        This method allows connections to be attached to tools at registration/discovery
        time rather than passed via context at execution time. This aligns with the
        tools-as-code pattern where tools discover and attach to existing resources.

        Args:
            connection_manager: TeradataConnectionManager instance to attach

        Example:
            # At tool registration time
            tool = QueryTool()
            registry = ConnectionRegistry.get_instance()
            connection = registry.get_connection()
            tool.attach_connection(connection)

            # Later at execution time
            result = await tool.execute(input_data)  # Uses attached connection
        """
        self._connection_manager = connection_manager

    def get_connection_manager(self):
        """
        Get the attached connection manager.

        Returns:
            ConnectionManager instance or None if not attached

        Example:
            if tool.get_connection_manager():
                print("Tool has an attached connection")
        """
        return self._connection_manager

    @abstractmethod
    async def execute(self, input_data: TInput, context: Optional[Dict[str, Any]] = None) -> TOutput:
        """
        Execute the tool with given input and optional context.

        Connection Resolution Order:
        1. self._connection_manager (attached via attach_connection())
        2. context['connection_manager'] (if context provided - backward compatible)
        3. ConnectionRegistry.get_instance().get_connection() (global fallback)

        Args:
            input_data: Validated input matching InputSchema
            context: Optional execution context (for backward compatibility)
                    Contains connection_manager, db_name, oauth_token, user_id

        Returns:
            Output matching OutputSchema

        Example:
            # Modern approach (no context needed)
            tool = QueryTool()
            tool.attach_connection(connection_manager)
            result = await tool.execute(QueryInput(query="SELECT 1"))

            # Legacy approach (still supported)
            context = {"connection_manager": conn_mgr, "db_name": "demo"}
            result = await tool.execute(QueryInput(query="SELECT 1"), context)
        """
        pass

    @classmethod
    def get_input_schema(cls) -> Dict[str, Any]:
        """Get JSON Schema for tool input."""
        return cls.InputSchema.model_json_schema()

    @classmethod
    def get_output_schema(cls) -> Dict[str, Any]:
        """Get JSON Schema for tool output."""
        return cls.OutputSchema.model_json_schema()

    @classmethod
    def get_metadata(cls) -> ToolMetadata:
        """Get tool metadata."""
        return cls.METADATA

    @classmethod
    def to_mcp_tool(cls) -> Dict[str, Any]:
        """Convert to MCP tool format."""
        return {
            "name": cls.METADATA.name,
            "description": cls.METADATA.description,
            "inputSchema": cls.get_input_schema()
        }


class ToolContext(BaseModel):
    """Context passed to tool execution."""
    connection_manager: Any = Field(exclude=True)  # TeradataConnectionManager
    db_name: str
    oauth_token: Optional[str] = None
    user_id: Optional[str] = None

    class Config:
        arbitrary_types_allowed = True
