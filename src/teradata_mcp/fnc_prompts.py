"""
MCP Tool Functions for Teradata Database Operations

This module contains all the tool functions that are exposed through the MCP server.
Each function implements a specific database operation and returns properly formatted responses.
"""

import logging
import yaml
from typing import Any, List
from pydantic import AnyUrl

import mcp.types as types
from .prompt import PROMPTS

logger = logging.getLogger(__name__)
ResponseType = List[types.TextContent | types.ImageContent | types.EmbeddedResource]

async def get_prompt_impl(name: str, arguments: dict[str, Any] = None) -> List[dict]:
    """Implementation of prompt getting that can be used with FastMCP decorators."""
    result = await handle_get_prompt(name, arguments or {})
    # Convert GetPromptResult to the expected format for FastMCP
    return result.messages

async def handle_list_prompts() -> list[types.Prompt]:
    logger.debug("Handling list_prompts request")
    return [
        types.Prompt(
            name="Analyze_database",
            description="A prompt demonstrate how to analyze objects in Teradata database",
            arguments=[
                types.PromptArgument(
                    name="database",
                    description="Database name to analyze",
                    required=True,
                )
            ],
        ),
        types.Prompt(
            name="Analyze_table",
            description="A prompt demonstrate how to analyze objects in Teradata database",
            arguments=[
                types.PromptArgument(
                    name="database",
                    description="Database name to analyze",
                    required=True,
                ),
                types.PromptArgument(
                    name="table",
                    description="table name to analyze",
                    required=True,
                )
            ],

        ),
        types.Prompt(
            name="glm",
            description="A prompt demonstrate how to train model with GLM in Teradata database",
            arguments=[
                types.PromptArgument(
                    name="database",
                    description="Database name to analyze",
                    required=True,
                ),
                types.PromptArgument(
                    name="table",
                    description="table name to analyze",
                    required=True,
                )
            ],

        )
    ]


async def handle_get_prompt(name: str, arguments: dict[str, str] | None) -> types.GetPromptResult:
    """Generate a prompt based on the requested type"""
    # Simple argument handling
    if arguments is None:
        arguments = {}
        
    if name == "Analyze_database":
        database = arguments.get("database", "datbase name")
        prompt_text = PROMPTS["Analyze_database"].format( database=database)
        return types.GetPromptResult(
            description=f"Analyze database focus on {database}",
            messages=[
                types.PromptMessage(
                    role="assistant", 
                    content=types.TextContent(
                        type="text",
                        text="I am Database expert specializing in performing database tasks for the user."
                    )
                ),
                types.PromptMessage(
                    role="user", 
                    content=types.TextContent(
                        type="text",
                        text=prompt_text
                    )
                )
            ]
        )
    
    elif name == "Analyze_table":
        # Get info_type with a fallback default
        database = arguments.get("database", "database name")
        table = arguments.get("table", "table name")
        prompt_text = PROMPTS["Analyze_database"].format(table=table, database=database)
        return types.GetPromptResult(
            description=f"Extracting details on {table} from database {database}",
            messages=[
                types.PromptMessage(
                    role="assistant", 
                    content=types.TextContent(
                        type="text",
                        text="I am database expert analyzing your database."
                    )
                ),
                types.PromptMessage(
                    role="user", 
                    content=types.TextContent(
                        type="text",
                        text=prompt_text
                    )
                )
            ]
        )
    elif name == "glm":
        # Get info_type with a fallback default
        database = arguments.get("database", "database name")
        table = arguments.get("table", "table name")
        prompt_text = PROMPTS["glm"].format(table=table, database=database)
        return types.GetPromptResult(
            description=f"Extracting details on {table} from database {database}",
            messages=[
                types.PromptMessage(
                    role="assistant", 
                    content=types.TextContent(
                        type="text",
                        text="I am database expert analyzing your database."
                    )
                ),
                types.PromptMessage(
                    role="user", 
                    content=types.TextContent(
                        type="text",
                        text=prompt_text
                    )
                )
            ]
        )
   
    else:
        raise ValueError(f"Unknown prompt: {name}")

