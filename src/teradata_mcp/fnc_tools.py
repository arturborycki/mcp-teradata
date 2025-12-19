"""
MCP Tool Functions for Teradata Database Operations

This module contains all the tool functions that are exposed through the MCP server.
Each function implements a specific database operation and returns properly formatted responses.
Includes OAuth 2.1 authorization support and connection retry logic.
"""

import logging
import yaml
from typing import Any, List
from pydantic import AnyUrl

import mcp.types as types
from .oauth_context import require_oauth_authorization, get_oauth_error
from .retry_utils import with_connection_retry

logger = logging.getLogger(__name__)

ResponseType = List[types.TextContent | types.ImageContent | types.EmbeddedResource]

# Global connection and database variables
_connection_manager = None
_db = ""


def set_tools_connection(connection_manager, db: str):
    """Set the global database connection manager and database name."""
    global _connection_manager, _db
    _connection_manager = connection_manager
    _db = db


async def call_tool_impl(name: str, arguments: dict[str, Any]) -> ResponseType:
    """Implementation of tool calling that can be used with FastMCP decorators."""
    return await handle_tool_call(name, arguments)


def format_text_response(text: Any) -> ResponseType:
    """Format a text response."""
    return [types.TextContent(type="text", text=str(text))]


def format_error_response(error: str) -> ResponseType:
    """Format an error response."""
    return format_text_response(f"Error: {error}")


async def get_connection():
    """Get a healthy database connection."""
    global _connection_manager
    
    if not _connection_manager:
        raise ConnectionError("Database connection not initialized")
    
    return await _connection_manager.ensure_connection()


# --- Database Query Functions ---

@with_connection_retry()
async def execute_query(query: str) -> ResponseType:
    """Execute a SQL query and return results as a table."""
    logger.debug(f"Executing query: {query}")

    try:
        # get_connection will raise ConnectionError if manager is not initialized
        tdconn = await get_connection()
        cur = tdconn.cursor()
        rows = cur.execute(query)
        if rows is None:
            return format_text_response("No results")
        return format_text_response(list([row for row in rows.fetchall()]))
    except ConnectionError as e:
        logger.error(f"Database connection error: {e}")
        # Re-raise ConnectionError so retry logic can handle it
        raise
    except Exception as e:
        logger.error(f"Error executing query: {e}")
        return format_error_response(str(e))


@with_connection_retry()
async def list_db() -> ResponseType:
    """List all databases in the Teradata."""
    try:
        # get_connection will raise ConnectionError if manager is not initialized
        tdconn = await get_connection()
        cur = tdconn.cursor()
        rows = cur.execute("select DataBaseName, DECODE(DBKind, 'U', 'User', 'D','DataBase') as DBType , CommentString from dbc.DatabasesV dv where OwnerName <> 'PDCRADM'")
        return format_text_response(list([row for row in rows.fetchall()]))
    except ConnectionError as e:
        logger.error(f"Database connection error: {e}")
        # Re-raise ConnectionError so retry logic can handle it
        raise
    except Exception as e:
        logger.error(f"Error listing schemas: {e}")
        return format_error_response(str(e))


@with_connection_retry()
async def list_tables(db_name: str) -> ResponseType:
    """List tables in a database of the given name."""
    try:
        tdconn = await get_connection()
        cur = tdconn.cursor()
        rows = cur.execute("select TableName from dbc.TablesV tv where UPPER(tv.DatabaseName) = UPPER(?) and tv.TableKind in ('T','V','O');", [db_name])
        return format_text_response(list([row for row in rows.fetchall()]))
    except ConnectionError as e:
        logger.error(f"Database connection error: {e}")
        # Re-raise ConnectionError so retry logic can handle it
        raise ConnectionError(f"Database connection failed: {str(e)}")
    except Exception as e:
        logger.error(f"Error listing schemas: {e}")
        return format_error_response(str(e))


@with_connection_retry()
async def show_tables_details(db_name: str, table_name: str) -> ResponseType:
    """Get detailed information about a database table."""
    if len(db_name) == 0:
        db_name = "%"
    if len(table_name) == 0:
        table_name = "%"
    try:
        tdconn = await get_connection()
        cur = tdconn.cursor()
        rows = cur.execute(
            """
            sel TableName, ColumnName, CASE ColumnType
          WHEN '++' THEN 'TD_ANYTYPE'
          WHEN 'A1' THEN 'UDT'
          WHEN 'AT' THEN 'TIME'
          WHEN 'BF' THEN 'BYTE'
          WHEN 'BO' THEN 'BLOB'
          WHEN 'BV' THEN 'VARBYTE'
          WHEN 'CF' THEN 'CHAR'
          WHEN 'CO' THEN 'CLOB'
          WHEN 'CV' THEN 'VARCHAR'
          WHEN 'D' THEN  'DECIMAL'
          WHEN 'DA' THEN 'DATE'
          WHEN 'DH' THEN 'INTERVAL DAY TO HOUR'
          WHEN 'DM' THEN 'INTERVAL DAY TO MINUTE'
          WHEN 'DS' THEN 'INTERVAL DAY TO SECOND'
          WHEN 'DY' THEN 'INTERVAL DAY'
          WHEN 'F' THEN  'FLOAT'
          WHEN 'HM' THEN 'INTERVAL HOUR TO MINUTE'
          WHEN 'HR' THEN 'INTERVAL HOUR'
          WHEN 'HS' THEN 'INTERVAL HOUR TO SECOND'
          WHEN 'I1' THEN 'BYTEINT'
          WHEN 'I2' THEN 'SMALLINT'
          WHEN 'I8' THEN 'BIGINT'
          WHEN 'I' THEN  'INTEGER'
          WHEN 'MI' THEN 'INTERVAL MINUTE'
          WHEN 'MO' THEN 'INTERVAL MONTH'
          WHEN 'MS' THEN 'INTERVAL MINUTE TO SECOND'
          WHEN 'N' THEN 'NUMBER'
          WHEN 'PD' THEN 'PERIOD(DATE)'
          WHEN 'PM' THEN 'PERIOD(TIMESTAMP WITH TIME ZONE)'
          WHEN 'PS' THEN 'PERIOD(TIMESTAMP)'
          WHEN 'PT' THEN 'PERIOD(TIME)'
          WHEN 'PZ' THEN 'PERIOD(TIME WITH TIME ZONE)'
          WHEN 'SC' THEN 'INTERVAL SECOND'
          WHEN 'SZ' THEN 'TIMESTAMP WITH TIME ZONE'
          WHEN 'TS' THEN 'TIMESTAMP'
          WHEN 'TZ' THEN 'TIME WITH TIME ZONE'
          WHEN 'UT' THEN 'UDT'
          WHEN 'YM' THEN 'INTERVAL YEAR TO MONTH'
          WHEN 'YR' THEN 'INTERVAL YEAR'
          WHEN 'AN' THEN 'UDT'
          WHEN 'XM' THEN 'XML'
          WHEN 'JN' THEN 'JSON'
          WHEN 'DT' THEN 'DATASET'
          WHEN '??' THEN 'STGEOMETRY''ANY_TYPE'
          END as CType
      from DBC.ColumnsVX where upper(tableName) like upper(?) and upper(DatabaseName) like upper(?)
            """
                           , [table_name, db_name])
        return format_text_response(list([row for row in rows.fetchall()]))
    except ConnectionError as e:
        logger.error(f"Database connection error: {e}")
        # Re-raise ConnectionError so retry logic can handle it
        raise ConnectionError(f"Database connection failed: {str(e)}")
    except Exception as e:
        logger.error(f"Error listing schemas: {e}")
        return format_error_response(str(e))


@with_connection_retry()
async def list_missing_val(table_name: str) -> ResponseType:
    """List of columns with count of null values."""
    try:
        tdconn = await get_connection()
        cur = tdconn.cursor()
        rows = cur.execute(f"select ColumnName, NullCount, NullPercentage from TD_ColumnSummary ( on {table_name} as InputTable using TargetColumns ('[:]')) as dt ORDER BY NullCount desc")
        return format_text_response(list([row for row in rows.fetchall()]))
    except ConnectionError as e:
        logger.error(f"Database connection error: {e}")
        # Re-raise ConnectionError so retry logic can handle it
        raise ConnectionError(f"Database connection failed: {str(e)}")
    except Exception as e:
        logger.error(f"Error evaluating features: {e}")
        return format_error_response(str(e))


@with_connection_retry()
async def list_negative_val(table_name: str) -> ResponseType:
    """List of columns with count of negative values."""
    try:
        tdconn = await get_connection()
        cur = tdconn.cursor()
        rows = cur.execute(f"select ColumnName, NegativeCount from TD_ColumnSummary ( on {table_name} as InputTable using TargetColumns ('[:]')) as dt ORDER BY NegativeCount desc")
        return format_text_response(list([row for row in rows.fetchall()]))
    except ConnectionError as e:
        logger.error(f"Database connection error: {e}")
        # Re-raise ConnectionError so retry logic can handle it
        raise ConnectionError(f"Database connection failed: {str(e)}")
    except Exception as e:
        logger.error(f"Error evaluating features: {e}")
        return format_error_response(str(e))


@with_connection_retry()
async def list_dist_cat(table_name: str, col_name: str) -> ResponseType:
    """List distinct categories in the column."""
    try:
        tdconn = await get_connection()
        cur = tdconn.cursor()
        if col_name == "":
            col_name = "[:]"
        rows = cur.execute(f"select * from TD_CategoricalSummary ( on {table_name} as InputTable using TargetColumns ('{col_name}')) as dt")
        return format_text_response(list([row for row in rows.fetchall()]))
    except ConnectionError as e:
        logger.error(f"Database connection error: {e}")
        # Re-raise ConnectionError so retry logic can handle it
        raise ConnectionError(f"Database connection failed: {str(e)}")
    except Exception as e:
        logger.error(f"Error evaluating features: {e}")
        return format_error_response(str(e))


@with_connection_retry()
async def stnd_dev(table_name: str, col_name: str) -> ResponseType:
    """Display standard deviation for column."""
    try:
        tdconn = await get_connection()
        cur = tdconn.cursor()
        rows = cur.execute(f"select * from TD_UnivariateStatistics ( on {table_name} as InputTable using TargetColumns ('{col_name}') Stats('MEAN','STD')) as dt ORDER BY 1,2")
        return format_text_response(list([row for row in rows.fetchall()]))
    except ConnectionError as e:
        logger.error(f"Database connection error: {e}")
        # Re-raise ConnectionError so retry logic can handle it
        raise ConnectionError(f"Database connection failed: {str(e)}")
    except Exception as e:
        logger.error(f"Error evaluating features: {e}")
        return format_error_response(str(e))



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
            description="Executes a SQL query against the Teradata database",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "SQL query to execute that is a dialect of Teradata SQL",
                    },
                },
                "required": ["query"],
            },
        ),
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
    elif name == "list_db":
        tool_response = await list_db()
        return tool_response
    elif name == "list_tables":
        if arguments is None:
            return [types.TextContent(type="text", text="Error: Database name provided")]
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
            text=f"Error executing tool {name}: {str(e)}"
        )]


