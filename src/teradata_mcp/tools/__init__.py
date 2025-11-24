"""
Tools as Code - Dynamic Tool Loading System

This module implements the "tools as code" pattern inspired by Anthropic's approach.
Instead of registering all tools upfront, tools are discovered and loaded dynamically
based on agent queries, significantly reducing token usage.

Architecture:
- Each tool is a separate Python file with typed interfaces (Pydantic models)
- Tools are organized by category (database/, analytics/, etc.)
- The search_tool allows progressive discovery of available tools
- Tools are loaded on-demand and cached for performance
"""

from .base import ToolBase, ToolMetadata, ToolInput, ToolOutput
from .executor import ToolExecutor
from .search import search_tools

__all__ = [
    "ToolBase",
    "ToolMetadata",
    "ToolInput",
    "ToolOutput",
    "ToolExecutor",
    "search_tools"
]
