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
    Base class for all tools in the tools-as-code system.

    Each tool should:
    1. Define METADATA as a class attribute
    2. Define InputSchema and OutputSchema as nested classes
    3. Implement the execute() method
    """

    # Each tool must define these
    METADATA: ToolMetadata

    @abstractmethod
    async def execute(self, input_data: TInput, context: Dict[str, Any]) -> TOutput:
        """
        Execute the tool with given input and context.

        Args:
            input_data: Validated input matching InputSchema
            context: Execution context (connection_manager, db_name, etc.)

        Returns:
            Output matching OutputSchema
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
