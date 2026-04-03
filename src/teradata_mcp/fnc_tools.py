"""
MCP Tool Functions for Teradata Database Operations

This module contains all the tool functions that are exposed through the MCP server.
Each function implements a specific database operation and returns properly formatted responses.
Includes OAuth 2.1 authorization support and connection retry logic.
"""

import asyncio
import json
import logging
import re
import yaml
from datetime import date, datetime
from decimal import Decimal
from typing import Any, List
from pydantic import AnyUrl

import mcp.types as types
from .oauth_context import require_oauth_authorization, get_oauth_error
from .retry_utils import with_connection_retry
from .sql_constants import COLUMN_TYPE_CASE_SQL
from .queryband import build_queryband

logger = logging.getLogger(__name__)

# Input validation for SQL identifiers (table/column names)
_IDENTIFIER_PATTERN = re.compile(r'^[A-Za-z_][A-Za-z0-9_.]*$')


def validate_identifier(name: str, label: str = "identifier") -> str:
    """Validate that a name is a safe SQL identifier (alphanumeric, underscores, dots only)."""
    if not name or not _IDENTIFIER_PATTERN.match(name):
        raise ValueError(
            f"Invalid {label}: {name!r}. "
            "Only alphanumeric characters, underscores, and dots are allowed."
        )
    return name

ResponseType = List[types.TextContent | types.ImageContent | types.EmbeddedResource]

# Global connection and database variables
_connection_manager = None
_db = ""
_transport = "stdio"


def set_tools_connection(connection_manager, db: str):
    """Set the global database connection manager and database name."""
    global _connection_manager, _db
    _connection_manager = connection_manager
    _db = db


def set_transport(transport: str):
    """Set the transport type for QueryBand."""
    global _transport
    _transport = transport


def _set_queryband(tdconn, tool_name: str):
    """Set QueryBand on connection for a tool call. Fails silently."""
    try:
        qb = build_queryband(
            application="Teradata_MCP",
            tool_name=tool_name,
            transport=_transport,
        )
        cur = tdconn.cursor()
        cur.execute(f"SET QUERY_BAND = '{qb}' FOR TRANSACTION")
        cur.close()
    except Exception:
        pass  # QueryBand is best-effort


async def call_tool_impl(name: str, arguments: dict[str, Any]) -> ResponseType:
    """Implementation of tool calling that can be used with FastMCP decorators."""
    return await handle_tool_call(name, arguments)


def format_text_response(text: Any) -> ResponseType:
    """Format a text response."""
    return [types.TextContent(type="text", text=str(text))]


def format_error_response(error: str) -> ResponseType:
    """Format an error response."""
    return format_text_response(f"Error: {error}")


def _serialize_value(val: Any) -> Any:
    """Convert Teradata-specific types to JSON-serializable values."""
    if val is None:
        return None
    if isinstance(val, Decimal):
        return float(val)
    if isinstance(val, (datetime, date)):
        return str(val)
    if isinstance(val, bytes):
        return val.hex()
    return val


async def get_connection():
    """Get a healthy database connection, initializing if necessary."""
    global _connection_manager

    if not _connection_manager:
        # Try to lazy-initialize the connection manager
        from . import server
        await server.lazy_initialize_database()

        # Check again after lazy initialization
        if not _connection_manager:
            raise ConnectionError(
                "Database connection not initialized. "
                "Please set DATABASE_URI environment variable or provide database URL."
            )

    return await _connection_manager.ensure_connection()


# --- Database Query Functions ---

@with_connection_retry()
async def execute_query(sql: str) -> ResponseType:
    """Execute a SQL query and return plain tabular results."""
    logger.debug(f"Executing query: {sql}")
    tdconn = await get_connection()

    def _run():
        _set_queryband(tdconn, "query")
        cur = tdconn.cursor()
        rows = cur.execute(sql)
        if rows is None:
            return format_text_response("No results")
        columns = [desc[0] for desc in cur.description] if cur.description else []
        raw_rows = rows.fetchall()
        if not columns:
            return format_text_response(list(raw_rows))
        data = []
        for row in raw_rows:
            row_dict = {}
            for i, col in enumerate(columns):
                row_dict[col] = _serialize_value(row[i])
            data.append(row_dict)
        return format_text_response({"columns": columns, "rows": data, "row_count": len(data)})

    try:
        return await asyncio.to_thread(_run)
    except ConnectionError as e:
        logger.error(f"Database connection error: {e}")
        raise
    except Exception as e:
        logger.error(f"Error executing query: {e}")
        return format_error_response(str(e))


@with_connection_retry()
async def visualize_query(sql: str) -> ResponseType:
    """Execute a SQL query and return results as structured JSON for ECharts visualization."""
    logger.debug(f"Visualizing query: {sql}")
    tdconn = await get_connection()

    def _run():
        _set_queryband(tdconn, "visualize_query")
        cur = tdconn.cursor()
        rows = cur.execute(sql)
        if rows is None:
            return format_text_response(json.dumps({"data": [], "title": "No Results"}))
        columns = [desc[0] for desc in cur.description] if cur.description else []
        raw_rows = rows.fetchall()
        if not columns:
            return format_text_response(json.dumps({"data": [], "title": "No Results"}))
        data = []
        for row in raw_rows:
            row_dict = {}
            for i, col in enumerate(columns):
                row_dict[col] = _serialize_value(row[i])
            data.append(row_dict)
        result = {"data": data, "title": "Query Results"}
        return [types.TextContent(type="text", text=json.dumps(result))]

    try:
        return await asyncio.to_thread(_run)
    except ConnectionError as e:
        logger.error(f"Database connection error: {e}")
        raise
    except Exception as e:
        logger.error(f"Error visualizing query: {e}")
        return format_error_response(str(e))


@with_connection_retry()
async def list_db() -> ResponseType:
    """List all databases in the Teradata."""
    tdconn = await get_connection()

    def _run():
        _set_queryband(tdconn, "list_db")
        cur = tdconn.cursor()
        rows = cur.execute("select DataBaseName, DECODE(DBKind, 'U', 'User', 'D','DataBase') as DBType , CommentString from dbc.DatabasesV dv where OwnerName <> 'PDCRADM'")
        return format_text_response(list(rows.fetchall()))

    try:
        return await asyncio.to_thread(_run)
    except ConnectionError as e:
        logger.error(f"Database connection error: {e}")
        raise
    except Exception as e:
        logger.error(f"Error listing databases: {e}")
        return format_error_response("Failed to list databases. Check server logs for details.")


@with_connection_retry()
async def list_tables(db_name: str) -> ResponseType:
    """List tables in a database of the given name."""
    tdconn = await get_connection()

    def _run():
        _set_queryband(tdconn, "list_tables")
        cur = tdconn.cursor()
        rows = cur.execute("select TableName from dbc.TablesV tv where UPPER(tv.DatabaseName) = UPPER(?) and tv.TableKind in ('T','V','O');", [db_name])
        return format_text_response(list(rows.fetchall()))

    try:
        return await asyncio.to_thread(_run)
    except ConnectionError as e:
        logger.error(f"Database connection error: {e}")
        raise
    except Exception as e:
        logger.error(f"Error listing tables: {e}")
        return format_error_response("Failed to list tables. Check server logs for details.")


@with_connection_retry()
async def show_tables_details(db_name: str, table_name: str) -> ResponseType:
    """Get detailed information about a database table."""
    if len(db_name) == 0:
        db_name = "%"
    if len(table_name) == 0:
        table_name = "%"
    tdconn = await get_connection()

    def _run():
        _set_queryband(tdconn, "show_tables_details")
        cur = tdconn.cursor()
        rows = cur.execute(
            f"""
            sel TableName, ColumnName, {COLUMN_TYPE_CASE_SQL} as CType
      from DBC.ColumnsVX where upper(tableName) like upper(?) and upper(DatabaseName) like upper(?)
            """
                           , [table_name, db_name])
        return format_text_response(list(rows.fetchall()))

    try:
        return await asyncio.to_thread(_run)
    except ConnectionError as e:
        logger.error(f"Database connection error: {e}")
        raise
    except Exception as e:
        logger.error(f"Error showing table details: {e}")
        return format_error_response("Failed to show table details. Check server logs for details.")


@with_connection_retry()
async def list_missing_val(table_name: str) -> ResponseType:
    """List of columns with count of null values."""
    validate_identifier(table_name, "table name")
    tdconn = await get_connection()

    def _run():
        _set_queryband(tdconn, "list_missing_values")
        cur = tdconn.cursor()
        rows = cur.execute(f"select ColumnName, NullCount, NullPercentage from TD_ColumnSummary ( on {table_name} as InputTable using TargetColumns ('[:]')) as dt ORDER BY NullCount desc")
        return format_text_response(list(rows.fetchall()))

    try:
        return await asyncio.to_thread(_run)
    except ConnectionError as e:
        logger.error(f"Database connection error: {e}")
        raise
    except Exception as e:
        logger.error(f"Error listing missing values: {e}")
        return format_error_response("Failed to analyze missing values. Check server logs for details.")


@with_connection_retry()
async def list_negative_val(table_name: str) -> ResponseType:
    """List of columns with count of negative values."""
    validate_identifier(table_name, "table name")
    tdconn = await get_connection()

    def _run():
        _set_queryband(tdconn, "list_negative_values")
        cur = tdconn.cursor()
        rows = cur.execute(f"select ColumnName, NegativeCount from TD_ColumnSummary ( on {table_name} as InputTable using TargetColumns ('[:]')) as dt ORDER BY NegativeCount desc")
        return format_text_response(list(rows.fetchall()))

    try:
        return await asyncio.to_thread(_run)
    except ConnectionError as e:
        logger.error(f"Database connection error: {e}")
        raise
    except Exception as e:
        logger.error(f"Error listing negative values: {e}")
        return format_error_response("Failed to analyze negative values. Check server logs for details.")


@with_connection_retry()
async def list_dist_cat(table_name: str, col_name: str) -> ResponseType:
    """List distinct categories in the column."""
    validate_identifier(table_name, "table name")
    if col_name and col_name != "[:]":
        validate_identifier(col_name, "column name")
    if col_name == "":
        col_name = "[:]"
    tdconn = await get_connection()

    def _run():
        _set_queryband(tdconn, "list_distinct_values")
        cur = tdconn.cursor()
        rows = cur.execute(f"select * from TD_CategoricalSummary ( on {table_name} as InputTable using TargetColumns ('{col_name}')) as dt")
        return format_text_response(list(rows.fetchall()))

    try:
        return await asyncio.to_thread(_run)
    except ConnectionError as e:
        logger.error(f"Database connection error: {e}")
        raise
    except Exception as e:
        logger.error(f"Error listing distinct values: {e}")
        return format_error_response("Failed to analyze distinct values. Check server logs for details.")


@with_connection_retry()
async def stnd_dev(table_name: str, col_name: str) -> ResponseType:
    """Display standard deviation for column."""
    validate_identifier(table_name, "table name")
    validate_identifier(col_name, "column name")
    tdconn = await get_connection()

    def _run():
        _set_queryband(tdconn, "standard_deviation")
        cur = tdconn.cursor()
        rows = cur.execute(f"select * from TD_UnivariateStatistics ( on {table_name} as InputTable using TargetColumns ('{col_name}') Stats('MEAN','STD')) as dt ORDER BY 1,2")
        return format_text_response(list(rows.fetchall()))

    try:
        return await asyncio.to_thread(_run)
    except ConnectionError as e:
        logger.error(f"Database connection error: {e}")
        raise
    except Exception as e:
        logger.error(f"Error computing standard deviation: {e}")
        return format_error_response("Failed to compute standard deviation. Check server logs for details.")



# --- MCP Handler Functions ---

async def handle_list_tools() -> list[types.Tool]:
    """
    List available tools.
    Each tool specifies its arguments using JSON Schema validation.
    """
    logger.info("Listing tools")
    return [
        types.Tool(
            name="query",
            description="Execute a SQL query against the Teradata database and return plain tabular results. Use this to inspect data, answer factual questions, or process results programmatically. If the user asks to visualize, chart, or graph results, use visualize_query instead.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "SQL query to execute in Teradata SQL dialect",
                    },
                },
                "required": ["query"],
            },
        ),
        types.Tool.model_validate({
            "name": "visualize_query",
            "description": "Execute a SQL query against the Teradata database and display results as an interactive ECharts chart. PREFER THIS TOOL whenever the user asks to visualize, chart, plot, graph, or display data visually.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "SQL query to execute in Teradata SQL dialect",
                    },
                },
                "required": ["query"],
            },
            "_meta": {
                "ui": {
                    "resourceUri": "ui://visualize_query/mcp-app.html"
                }
            }
        }),
        types.Tool(
            name="list_db",
            description="List all databases in the Teradata system",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        types.Tool(
            name="list_tables",
            description="List tables in a database",
            inputSchema={
                "type": "object",
                "properties": {
                    "db_name": {
                        "type": "string",
                        "description": "Database name to list",
                    },
                },
                "required": ["db_name"],
            },
        ),
        types.Tool(
            name="show_tables_details",
            description="Show detailed information about a database tables",
            inputSchema={
                "type": "object",
                "properties": {
                    "db_name": {
                        "type": "string",
                        "description": "Database name to list",
                    },                
                    "table_name": {
                        "type": "string",
                        "description": "Table name to list",
                    },
                },
                "required": ["db_name"],
            },
        ),
        types.Tool(
            name="list_missing_values",
            description="What are the top features with missing values in a table",
            inputSchema={
                "type": "object",
                "properties": {
                    "table_name": {
                        "type": "string",
                        "description": "Table name to list",
                    },
                },
                "required": ["table_name"],
            },
        ),
        types.Tool(
            name="list_negative_values",
            description="How many features have negative values in a table",
            inputSchema={
                "type": "object",
                "properties": {
                    "table_name": {
                        "type": "string",
                        "description": "Table name to list",
                    },
                },
                "required": ["table_name"],
            },
        ),
        types.Tool(
            name="list_distinct_values",
            description="How many distinct categories are there for column in the table",
            inputSchema={
                "type": "object",
                "properties": {
                    "table_name": {
                        "type": "string",
                        "description": "Table name to list",
                    },
                },
                "required": ["table_name"],
            },
        ),
        types.Tool(
            name="standard_deviation",
            description="What is the mean and standard deviation for column in table?",
            inputSchema={
                "type": "object",
                "properties": {
                    "table_name": {
                        "type": "string",
                        "description": "Table name to list",
                    },
                    "column_name": {
                        "type": "string",
                        "description": "Column name to list",
                    },
                },
                "required": ["table_name", "column_name"],
            },
        ),
    ]


async def execute_tool_with_retry(name: str, arguments: dict | None) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """
    Execute a tool with connection retry logic.
    
    This function wraps the actual tool execution with connection retry capability.
    If a connection error occurs, it will attempt to re-establish the connection
    and retry the tool execution once.
    """
    logger.debug(f"Executing tool: {name} with arguments: {arguments}")
    
    if name == "query":
        if arguments is None:
            return [types.TextContent(type="text", text="Error: No query provided")]
        tool_response = await execute_query(arguments["query"])
        return tool_response
    elif name == "visualize_query":
        if arguments is None:
            return [types.TextContent(type="text", text="Error: No query provided")]
        tool_response = await visualize_query(arguments["query"])
        return tool_response
    elif name == "list_db":
        tool_response = await list_db()
        return tool_response
    elif name == "list_tables":
        if arguments is None:
            return [types.TextContent(type="text", text="Error: Database name not provided")]
        tool_response = await list_tables(arguments["db_name"])
        return tool_response
    elif name == "show_tables_details":
        if arguments is None:
            return [types.TextContent(type="text", text="Error: Database or table name not provided")]
        tool_response = await show_tables_details(arguments["db_name"], arguments["table_name"])
        return tool_response
    elif name == "list_missing_values":
        if arguments is None:
            return [types.TextContent(type="text", text="Error: Table name not provided")]
        tool_response = await list_missing_val(arguments["table_name"])
        return tool_response
    elif name == "list_negative_values":
        if arguments is None:
            return [types.TextContent(type="text", text="Error: Table name not provided")]
        tool_response = await list_negative_val(arguments["table_name"])
        return tool_response
    elif name == "list_distinct_values":
        if arguments is None:
            return [types.TextContent(type="text", text="Error: Table name not provided")]
        tool_response = await list_dist_cat(arguments["table_name"], "")
        return tool_response
    elif name == "standard_deviation":
        if arguments is None:
            return [types.TextContent(type="text", text="Error: Table name or column name not provided")]
        tool_response = await stnd_dev(arguments["table_name"], arguments["column_name"])
        return tool_response                        

    return [types.TextContent(type="text", text=f"Unsupported tool: {name}")]


async def handle_tool_call(
    name: str, arguments: dict | None
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """
    Handle tool execution requests with OAuth authorization and connection retry.
    Tools can modify server state and notify clients of changes.
    """
    logger.info(f"Calling tool: {name}::{arguments}")
    
    # Check OAuth authorization for this tool
    if not require_oauth_authorization(name):
        error_msg = get_oauth_error(name)
        logger.warning(f"OAuth authorization failed for tool {name}: {error_msg}")
        return [types.TextContent(type="text", text=f"Authorization Error: {error_msg}")]
    
    try:
        # Execute the tool with connection retry logic
        return await execute_tool_with_retry(name, arguments)
        
    except ConnectionError as e:
        logger.error(f"Connection error executing tool {name} after retries: {e}")
        return [types.TextContent(
            type="text", 
            text=f"Database connection error: {str(e)}. Please check your database connection and try again."
        )]
    except Exception as e:
        logger.error(f"Error executing tool {name}: {e}")
        return [types.TextContent(
            type="text",
            text=f"Error executing tool {name}. An internal error occurred. Check server logs for details."
        )]


