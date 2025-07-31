import argparse
import asyncio
import logging
import os
import signal
import re
import teradatasql
import yaml
import asyncio
from urllib.parse import urlparse
from pydantic import AnyUrl
from typing import Literal
from typing import Any
from typing import List
import io
from contextlib import redirect_stdout
import mcp.server.stdio
import mcp.types as types
import mcp
from .tdsql import obfuscate_password
from .tdsql import TDConn
from .prompt import PROMPTS


logger = logging.getLogger(__name__)
ResponseType = List[types.TextContent | types.ImageContent | types.EmbeddedResource]
_tdconn = TDConn()
_db = ""

def _init_db_from_env():
    global _tdconn, _db
    database_url = os.environ.get("DATABASE_URI")
    if database_url:
        parsed_url = urlparse(database_url)
        _db = parsed_url.path.lstrip('/')
        try:
            _tdconn = TDConn(database_url)
            logger.info("Successfully connected to database and initialized connection (HTTP mode)")
        except Exception as e:
            logger.warning(f"Could not connect to database: {obfuscate_password(str(e))}")
            logger.warning("Database operations will fail until a valid connection is established.")

#_init_db_from_env()

def format_text_response(text: Any) -> ResponseType:
    """Format a text response."""
    return [types.TextContent(type="text", text=str(text))]

def format_error_response(error: str) -> ResponseType:
    """Format an error response."""
    return format_text_response(f"Error: {error}")

# Global shutdown flag
shutdown_event = asyncio.Event()

async def shutdown(sig: signal.Signals = None):
    """Graceful shutdown handler"""
    if sig:
        logger.info(f"Received shutdown signal: {sig.name}")
    else:
        logger.info("Shutting down server")
    shutdown_event.set()

logger = logging.getLogger("teradata_mcp")

async def execute_query(query: str) -> ResponseType:
    """Execute a SQL query and return results as a list """
    logger.debug(f"Executing query: {query}")
    global _tdconn
    try:
        cur = _tdconn.cursor()
        rows = cur.execute(query)
        if rows is None:
            return format_text_response("No results")
        return format_text_response(list([row for row in rows.fetchall()]))
    except Exception as e:
        logger.error(f"Error executing query: {e}")
        return format_error_response(str(e))
    except Exception as e:
        logger.error(f"Database error executing query: {e}")
        raise


async def list_db() -> ResponseType:
    """List all databases in the Teradata."""
    try:
        global _tdconn
        cur = _tdconn.cursor()
        rows = cur.execute("select DataBaseName, DECODE(DBKind, 'U', 'User', 'D','DataBase') as DBType , CommentString from dbc.DatabasesV dv where OwnerName <> 'PDCRADM'")
        return format_text_response(list([row for row in rows.fetchall()]))
    except Exception as e:
        logger.error(f"Error listing schemas: {e}")
        return format_error_response(str(e))

async def list_objects(db_name: str) -> ResponseType:
    """List objects of in a database of the given name."""
    try:
        global _tdconn
        cur = _tdconn.cursor()
        rows = cur.execute("select TableName from dbc.TablesV tv where UPPER(tv.DatabaseName) = UPPER(?) and tv.TableKind in ('T','V','O');", [db_name])
        return format_text_response(list([row for row in rows.fetchall()]))
    except Exception as e:
        logger.error(f"Error listing schemas: {e}")
        return format_error_response(str(e))

async def get_object_details(db_name: str, obj_name: str) -> ResponseType:
    """Get detailed information about a database tables."""
    if len(db_name) == 0:
        db_name = "%"
    if len(obj_name) == 0:
        obj_name = "%"
    try:
        global _tdconn
        cur = _tdconn.cursor()
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
                           , [obj_name,db_name])
        return format_text_response(list([row for row in rows.fetchall()]))
    except Exception as e:
        logger.error(f"Error listing schemas: {e}")
        return format_error_response(str(e))

async def list_missing_val(table_name: str) -> ResponseType:
    """List of columns with count of null values."""
    try:
        global _tdconn
        cur = _tdconn.cursor()
        rows = cur.execute(f"select ColumnName, NullCount, NullPercentage from TD_ColumnSummary ( on {table_name} as InputTable using TargetColumns ('[:]')) as dt ORDER BY NullCount desc")
        return format_text_response(list([row for row in rows.fetchall()]))
    except Exception as e:
        logger.error(f"Error evaluating features: {e}")
        return format_error_response(str(e))
    
async def list_negative_val(table_name: str) -> ResponseType:
    """List of columns with count of negative values."""
    try:
        global _tdconn
        cur = _tdconn.cursor()
        rows = cur.execute(f"select ColumnName, NegativeCount from TD_ColumnSummary ( on {table_name} as InputTable using TargetColumns ('[:]')) as dt ORDER BY NegativeCount desc")
        return format_text_response(list([row for row in rows.fetchall()]))
    except Exception as e:
        logger.error(f"Error evaluating features: {e}")
        return format_error_response(str(e))

async def list_dist_cat(table_name: str, col_name: str) -> ResponseType:
    """List distinct categories in the column."""
    try:
        global _tdconn
        cur = _tdconn.cursor()
        if col_name == "":
            col_name = "[:]"
        rows = cur.execute(f"select * from TD_CategoricalSummary ( on {table_name} as InputTable using TargetColumns ('{col_name}')) as dt")
        return format_text_response(list([row for row in rows.fetchall()]))
    except Exception as e:
        logger.error(f"Error evaluating features: {e}")
        return format_error_response(str(e))

async def stnd_dev(table_name: str, col_name: str) -> ResponseType:
    """Display standard deviation for column."""
    try:
        global _tdconn
        cur = _tdconn.cursor()
        rows = cur.execute(f"select * from TD_UnivariateStatistics ( on {table_name} as InputTable using TargetColumns ('{col_name}') Stats('MEAN','STD')) as dt ORDER BY 1,2")
        return format_text_response(list([row for row in rows.fetchall()]))
    except Exception as e:
        logger.error(f"Error evaluating features: {e}")
        return format_error_response(str(e))

async def prefetch_tables( db_name: str) -> dict:
    """Prefetch table and column information"""
    try:
        logger.info("Prefetching table descriptions")
        global _tdconn
        cur = _tdconn.cursor()
        rows = cur.execute("select TableName, CommentString, DatabaseName from dbc.TablesV tv where UPPER(tv.DatabaseName) = UPPER(?) and tv.TableKind in ('T','V','O');", [db_name])
        table_results = rows.fetchall()
        
        cur_columns = _tdconn.cursor()
        cur_columns.execute(
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
                        END as CType, CommentString
                    from DBC.ColumnsVX where upper(DatabaseName) = upper(?)
                    """
                                , [db_name])
        column_results = cur_columns.fetchall()
        tables_schema = {}
        for table_row in table_results:
            table_name = table_row[0]
            table_description = table_row[1]
            database_name = table_row[2]
            tables_schema[table_name] = {
            "description": table_description,
            "database": database_name,
            "columns": {}
            }
        for column_row in column_results:
            table_name = column_row[0]
            column_name = column_row[1]
            column_type = column_row[2]
            column_description = column_row[3]
            if table_name in tables_schema:
                tables_schema[table_name]["columns"][column_name] = {
                "type": column_type,
                "description": column_description
                }
        return tables_schema

    except Exception as e:
        logger.error(f"Error prefetching table descriptions: {e}")
        return f"Error prefetching table descriptions: {e}"

def data_to_yaml(data: Any) -> str:
    return yaml.dump(data, indent=2, sort_keys=False)


# --- Handler function definitions (NO decorators here!) ---

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


async def handle_list_resources() -> list[types.Resource]:
    global _db
    tables_info = (await prefetch_tables(_db))
    # If prefetch_tables returned an error string, handle it gracefully
    if not isinstance(tables_info, dict):
        # Return a single resource with the error message
        return [
            types.Resource(
                uri=AnyUrl("teradata://error"),
                name="Error",
                description=str(tables_info),
                mimeType="text/plain",
            )
        ]
    table_resources = [
        types.Resource(
            uri=AnyUrl(f"teradata://table/{table_name}"),
            name=f"{table_name} table",
            description=f"{tables_info[table_name]['description']}" if tables_info[table_name]['description'] else f"Description of the {table_name} table",
            mimeType="text/plain",
        )
        for table_name in tables_info
    ]
    return table_resources


async def handle_read_resource(uri: AnyUrl) -> str:
    global _db
    tables_info = (await prefetch_tables(_db)) 
    if str(uri).startswith("teradata://table"):
        table_name = str(uri).split("/")[-1]
        if table_name in tables_info:
            return data_to_yaml(tables_info[table_name])
        else:
            raise ValueError(f"Unknown table: {table_name}")
    else:
        raise ValueError(f"Unknown resource: {uri}")


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
            name="list_objects",
            description="List objects in a database",
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
            name="show_tables",
            description="Show detailed information about a database tables",
            inputSchema={
                "type": "object",
                "properties": {
                    "db_name": {
                        "type": "string",
                        "description": "Database name to list",
                    },                
                    "obj_name": {
                        "type": "string",
                        "description": "Table, object name to list",
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


async def handle_tool_call(
    name: str, arguments: dict | None
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """
    Handle tool execution requests.
    Tools can modify server state and notify clients of changes.
    """
    logger.info(f"Calling tool: {name}::{arguments}")
    try:
        if name == "query":
            if arguments is None:
                return [
                    types.TextContent(type="text", text="Error: No query provided")
                ]
            tool_response = await execute_query(arguments["query"])
            return tool_response
        elif name == "list_db":
            tool_response = await list_db()
            return tool_response
        elif name == "list_objects":
            if arguments is None:
                return [
                    types.TextContent(type="text", text="Error: Database name provided")
                ]
            tool_response = await list_objects(arguments["db_name"])
            return tool_response
        elif name == "show_tables":
            if arguments is None:
                return [
                    types.TextContent(type="text", text="Error: Database or table name not provided")
                ]
            tool_response = await get_object_details(arguments["db_name"], arguments["obj_name"])
            return tool_response
        elif name == "list_missing_values":
            if arguments is None:
                return [
                    types.TextContent(type="text", text="Error: Table name not provided")
                ]
            tool_response = await list_missing_val(arguments["table_name"])
            return tool_response
        elif name == "list_negative_values":
            if arguments is None:
                return [
                    types.TextContent(type="text", text="Error: Table name not provided")
                ]
            tool_response = await list_negative_val(arguments["table_name"])
            return tool_response
        elif name == "list_distinct_values":
            if arguments is None:
                return [
                    types.TextContent(type="text", text="Error: Table name not provided")
                ]
            tool_response = await list_dist_cat(arguments["table_name"])
            return tool_response
        elif name == "standard_deviation":
            if arguments is None:
                return [
                    types.TextContent(type="text", text="Error: Table name or column name not provided")
                ]
            tool_response = await stnd_dev(arguments["table_name"], arguments["column_name"])
            return tool_response                        

        return [types.TextContent(type="text", text=f"Unsupported tool: {name}")]

    except Exception as e:
        logger.error(f"Error executing tool {name}: {e}")
        raise ValueError(f"Error executing tool {name}: {str(e)}")


# --- CLI/stdio entrypoint ---
async def main():
    global _tdconn
    
    logger.info("Starting Teradata MCP Server")
    
    # Get transport type from environment
    mcp_transport = os.getenv("MCP_TRANSPORT", "stdio").lower()
    logger.info(f"MCP_TRANSPORT: {mcp_transport}")

    # Set up proper shutdown handling
    try:
        loop = asyncio.get_running_loop()
        signals = (signal.SIGTERM, signal.SIGINT)
        for s in signals:
            logger.info(f"Registering signal handler for {s.name}")
            loop.add_signal_handler(s, lambda s=s: asyncio.create_task(shutdown(s)))
    except NotImplementedError:
        # Windows doesn't support signals properly
        logger.warning("Signal handling not supported on Windows")
        pass
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Teradata MCP Server")
    parser.add_argument("database_url", help="Database connection URL", nargs="?")
    args = parser.parse_args()
    database_url = os.environ.get("DATABASE_URI", args.database_url)
    
    if database_url:
        parsed_url = urlparse(database_url)
        _db = parsed_url.path.lstrip('/') 
        try:
            _tdconn = TDConn(database_url)
            logger.info("Successfully connected to database and initialized connection")
        except Exception as e:
            logger.warning(
                f"Could not connect to database: {obfuscate_password(str(e))}",
            )
            logger.warning(
                "The MCP server will start but database operations will fail until a valid connection is established.",
            )
    else:
        logger.warning("No database URL provided. Database operations will fail.")

    # Start the appropriate transport
    if mcp_transport == "sse":
        # SSE transport (Server-Sent Events)
        mcp.settings.host = os.getenv("MCP_HOST", "0.0.0.0")
        mcp.settings.port = int(os.getenv("MCP_PORT", "8000"))
        logger.info(f"Starting MCP server on {mcp.settings.host}:{mcp.settings.port}")
        await mcp.run_sse_async()
            
    elif mcp_transport == "streamable-http":
        # Streamable HTTP transport
        mcp.settings.host = os.getenv("MCP_HOST", "0.0.0.0")
        mcp.settings.port = int(os.getenv("MCP_PORT", "8000"))
        mcp.settings.streamable_http_path = os.getenv("MCP_PATH", "/mcp/")
        logger.info(f"Starting MCP server on {mcp.settings.host}:{mcp.settings.port} with path {mcp.settings.streamable_http_path}")
        await mcp.run_streamable_http_async()
        
    # Default to stdio transport
    elif mcp_transport == "stdio":
        logger.info("Starting MCP server on stdin/stdout")
        await mcp.run_stdio_async()
    else:
        logger.error(f"Unknown transport: {mcp_transport}")
        raise ValueError(f"Unsupported transport: {mcp_transport}")

if __name__ == "__main__":
    asyncio.run(main())
