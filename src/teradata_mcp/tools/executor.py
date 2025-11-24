"""
Dynamic Tool Executor - Loads and executes tools on demand.
"""

import importlib
import inspect
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Type
from functools import lru_cache

from .base import ToolBase, ToolContext, ToolMetadata

logger = logging.getLogger(__name__)


class ToolExecutor:
    """
    Manages dynamic loading and execution of tools.

    Features:
    - Discovers tools from filesystem
    - Loads tools on-demand
    - Caches loaded tools for performance
    - Validates tool implementations
    """

    def __init__(self, tools_dir: Optional[Path] = None):
        """
        Initialize the tool executor.

        Args:
            tools_dir: Directory containing tool modules (defaults to ./tools/)
        """
        if tools_dir is None:
            tools_dir = Path(__file__).parent
        self.tools_dir = tools_dir
        self._tool_cache: Dict[str, Type[ToolBase]] = {}
        self._metadata_cache: Dict[str, ToolMetadata] = {}

    def discover_all_tools(self) -> List[ToolMetadata]:
        """
        Discover all available tools by scanning the tools directory.

        Returns:
            List of tool metadata for all discovered tools
        """
        tools = []

        # Scan all Python files in tools directory (excluding __init__.py and base files)
        for py_file in self.tools_dir.rglob("*.py"):
            if py_file.name.startswith("_") or py_file.name in ["base.py", "executor.py"]:
                continue

            # Get relative module path from teradata_mcp package root
            # Find the teradata_mcp directory
            package_root = self.tools_dir.parent  # This is teradata_mcp/
            rel_path = py_file.relative_to(package_root.parent)  # Relative to src/
            module_path = str(rel_path.with_suffix("")).replace("/", ".")

            try:
                # Try to load metadata without fully importing the tool
                metadata = self._load_tool_metadata(module_path)
                if metadata:
                    tools.append(metadata)
                    logger.debug(f"Discovered tool: {metadata.name} from {module_path}")
            except Exception as e:
                logger.warning(f"Could not load tool from {module_path}: {e}")

        return tools

    def _load_tool_metadata(self, module_path: str) -> Optional[ToolMetadata]:
        """
        Load just the metadata for a tool without fully loading it.

        Args:
            module_path: Python module path (e.g., 'tools.database.query')

        Returns:
            Tool metadata or None if not a valid tool
        """
        # Check cache first
        if module_path in self._metadata_cache:
            return self._metadata_cache[module_path]

        try:
            module = importlib.import_module(module_path)

            # Find ToolBase subclass in module
            for name, obj in inspect.getmembers(module, inspect.isclass):
                if (issubclass(obj, ToolBase) and
                    obj is not ToolBase and
                    hasattr(obj, 'METADATA')):
                    metadata = obj.METADATA
                    self._metadata_cache[module_path] = metadata
                    return metadata

            return None
        except Exception as e:
            logger.error(f"Error loading metadata from {module_path}: {e}")
            return None

    def load_tool(self, tool_name: str) -> Optional[Type[ToolBase]]:
        """
        Dynamically load a tool by name.

        Args:
            tool_name: Name of the tool to load

        Returns:
            Tool class or None if not found
        """
        # Check cache first
        if tool_name in self._tool_cache:
            return self._tool_cache[tool_name]

        # Search for tool in all modules
        for py_file in self.tools_dir.rglob("*.py"):
            if py_file.name.startswith("_") or py_file.name in ["base.py", "executor.py"]:
                continue

            package_root = self.tools_dir.parent  # This is teradata_mcp/
            rel_path = py_file.relative_to(package_root.parent)  # Relative to src/
            module_path = str(rel_path.with_suffix("")).replace("/", ".")

            try:
                module = importlib.import_module(module_path)

                # Find ToolBase subclass matching the tool name
                for name, obj in inspect.getmembers(module, inspect.isclass):
                    if (issubclass(obj, ToolBase) and
                        obj is not ToolBase and
                        hasattr(obj, 'METADATA') and
                        obj.METADATA.name == tool_name):

                        # Cache and return
                        self._tool_cache[tool_name] = obj
                        logger.info(f"Loaded tool: {tool_name} from {module_path}")
                        return obj

            except Exception as e:
                logger.error(f"Error loading tool from {module_path}: {e}")

        logger.warning(f"Tool not found: {tool_name}")
        return None

    async def execute_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        context: ToolContext
    ) -> Dict[str, Any]:
        """
        Load and execute a tool with given arguments.

        Args:
            tool_name: Name of the tool to execute
            arguments: Tool input arguments
            context: Execution context

        Returns:
            Tool output as dictionary
        """
        # Load the tool
        tool_class = self.load_tool(tool_name)
        if not tool_class:
            return {
                "success": False,
                "error": f"Tool not found: {tool_name}"
            }

        try:
            # Instantiate the tool
            tool_instance = tool_class()

            # Validate and parse input
            input_data = tool_class.InputSchema(**arguments)

            # Execute the tool
            output = await tool_instance.execute(input_data, context.model_dump())

            # Return as dict
            return output.model_dump()

        except Exception as e:
            logger.error(f"Error executing tool {tool_name}: {e}")
            return {
                "success": False,
                "error": f"Tool execution error: {str(e)}"
            }

    def search_tools(
        self,
        query: Optional[str] = None,
        category: Optional[str] = None,
        tags: Optional[List[str]] = None,
        detail_level: str = "standard"
    ) -> List[Dict[str, Any]]:
        """
        Search for tools matching criteria.

        Args:
            query: Text query to match against name/description
            category: Filter by category
            tags: Filter by tags (any match)
            detail_level: Amount of detail to return ('minimal', 'standard', 'full')

        Returns:
            List of tool information matching criteria
        """
        all_tools = self.discover_all_tools()
        results = []

        for metadata in all_tools:
            # Apply filters
            if category and metadata.category != category:
                continue

            if tags and not any(tag in metadata.tags for tag in tags):
                continue

            if query:
                query_lower = query.lower()
                if not (query_lower in metadata.name.lower() or
                        query_lower in metadata.description.lower() or
                        any(query_lower in tag.lower() for tag in metadata.tags)):
                    continue

            # Format based on detail level
            if detail_level == "minimal":
                results.append({
                    "name": metadata.name,
                    "category": metadata.category
                })
            elif detail_level == "standard":
                results.append({
                    "name": metadata.name,
                    "description": metadata.description,
                    "category": metadata.category,
                    "tags": metadata.tags
                })
            else:  # full
                # Load full schema
                tool_class = self.load_tool(metadata.name)
                if tool_class:
                    results.append({
                        "name": metadata.name,
                        "description": metadata.description,
                        "category": metadata.category,
                        "tags": metadata.tags,
                        "requires_connection": metadata.requires_connection,
                        "requires_oauth": metadata.requires_oauth,
                        "version": metadata.version,
                        "inputSchema": tool_class.get_input_schema(),
                        "outputSchema": tool_class.get_output_schema()
                    })

        return results

    def clear_cache(self):
        """Clear the tool cache (useful for development/hot reload)."""
        self._tool_cache.clear()
        self._metadata_cache.clear()
        logger.info("Tool cache cleared")
