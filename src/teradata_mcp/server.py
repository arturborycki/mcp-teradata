import argparse
import asyncio
import logging
import os
import signal
import yaml
from urllib.parse import urlparse
from typing import Any, List
import mcp.types as types
from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.prompts.base import UserMessage, TextContent

from .tdsql import obfuscate_password, TDConn
from .prompt import PROMPTS

# Initialize FastMCP
mcp = FastMCP("teradata-mcp")

logger = logging.getLogger(__name__)
_tdconn = TDConn()

ResponseType = List[types.TextContent | types.ImageContent | types.EmbeddedResource]

# Global shutdown flag
shutdown_event = asyncio.Event()

async def shutdown(sig: signal.Signals = None):
    """Graceful shutdown handler"""
    if sig:
        logger.info(f"Received shutdown signal: {sig.name}")
    else:
        logger.info("Shutting down server")
    shutdown_event.set()

def format_text_response(text: Any) -> ResponseType:
    """Format a text response."""
    return [types.TextContent(type="text", text=str(text))]


def format_error_response(error: str) -> ResponseType:
    """Format an error response."""
    return format_text_response(f"Error: {error}")

async def execute_query(query: str) -> ResponseType:
    """Execute a SQL query and return results as a table """
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

async def list_databases() -> ResponseType:
    """List all databases in the Teradata."""
    try:
        global _tdconn
        cur = _tdconn.cursor()
        rows = cur.execute("select DataBaseName, DECODE(DBKind, 'U', 'User', 'D','DataBase') as DBType , CommentString from dbc.DatabasesV dv where OwnerName <> 'PDCRADM'")
        return format_text_response(list([row for row in rows.fetchall()]))
    except Exception as e:
        logger.error(f"Error listing schemas: {e}")
        return format_error_response(str(e))

async def list_objects_in_db(db_name: str) -> ResponseType:
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
        logger.error(f"Error listing schemas: {e}")
        return format_error_response(str(e))

    
async def list_negative_val(table_name: str) -> ResponseType:
    """List of columns with count of negative values."""
    try:
        global _tdconn
        cur = _tdconn.cursor()
        rows = cur.execute(f"select ColumnName, NegativeCount from TD_ColumnSummary ( on {table_name} as InputTable using TargetColumns ('[:]')) as dt ORDER BY NegativeCount desc")
        return format_text_response(list([row for row in rows.fetchall()]))
    except Exception as e:
        logger.error(f"Error listing schemas: {e}")
        return format_error_response(str(e))

async def list_dist_cat(table_name: str, col_name: str = "") -> ResponseType:
    """List distinct categories in the column."""
    try:
        global _tdconn
        cur = _tdconn.cursor()
        if col_name == "":
            col_name = "[:]"
        rows = cur.execute(f"select * from TD_CategoricalSummary ( on {table_name} as InputTable using TargetColumns ('{col_name}')) as dt")
        return format_text_response(list([row for row in rows.fetchall()]))
    except Exception as e:
        logger.error(f"Error listing schemas: {e}")
        return format_error_response(str(e))

async def stnd_dev(table_name: str, col_name: str) -> ResponseType:
    """Display standard deviation for column."""
    try:
        global _tdconn
        cur = _tdconn.cursor()
        rows = cur.execute(f"select * from TD_UnivariateStatistics ( on {table_name} as InputTable using TargetColumns ('{col_name}') Stats('MEAN','STD')) as dt ORDER BY 1,2")
        return format_text_response(list([row for row in rows.fetchall()]))
    except Exception as e:
        logger.error(f"Error listing schemas: {e}")
        return format_error_response(str(e))

async def prefetch_tables(db_name: str) -> dict:
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

# --- FastMCP Tool Definitions ---

@mcp.tool()
async def query(query: str) -> ResponseType:
    """Executes a SQL query against the Teradata database and display results as a table"""
    return await execute_query(query)

@mcp.tool()
async def list_db() -> ResponseType:
    """List all databases in the Teradata system"""
    return await list_databases()

@mcp.tool()
async def list_objects(db_name: str) -> ResponseType:
    """List objects in a database"""
    return await list_objects_in_db(db_name)

@mcp.tool()
async def show_tables(db_name: str, obj_name: str = "") -> ResponseType:
    """Show detailed information about a database tables"""
    return await get_object_details(db_name, obj_name)

@mcp.tool()
async def list_missing_values(table_name: str) -> ResponseType:
    """What are the top features with missing values in a table"""
    return await list_missing_val(table_name)

@mcp.tool()
async def list_negative_values(table_name: str) -> ResponseType:
    """How many features have negative values in a table"""
    return await list_negative_val(table_name)

@mcp.tool()
async def list_distinct_values(table_name: str) -> ResponseType:
    """How many distinct categories are there for column in the table"""
    return await list_dist_cat(table_name)

@mcp.tool()
async def standard_deviation(table_name: str, column_name: str) -> ResponseType:
    """What is the mean and standard deviation for column in table?"""
    return await stnd_dev(table_name, column_name)

# --- FastMCP Prompt Definitions ---

@mcp.prompt()
async def Analyze_database(database: str) -> str:
    """A prompt demonstrate how to analyze objects in Teradata database"""
    prompt_text = PROMPTS["Analyze_database"].format(database=database)
    return f"I am Database expert specializing in performing database tasks for the user.\n\n{prompt_text}"

@mcp.prompt()
async def Analyze_table(database: str, table: str) -> str:
    """A prompt demonstrate how to analyze objects in Teradata database"""
    prompt_text = PROMPTS["Analyze_database"].format(table=table, database=database)
    return f"I am database expert analyzing your database.\n\n{prompt_text}"

@mcp.prompt()
async def glm(database: str, table: str) -> str:
    """A prompt demonstrate how to train model with GLM in Teradata database"""
    prompt_text = PROMPTS["glm"].format(table=table, database=database)
    return f"I am database expert analyzing your database.\n\n{prompt_text}"

# --- FastMCP Resource Definitions ---

@mcp.resource("teradata://table/{table_name}")
async def get_table_resource(table_name: str) -> str:
    """Get table schema and information"""
    global _tdconn
    tables_info = await prefetch_tables(_tdconn)
    if isinstance(tables_info, dict) and table_name in tables_info:
        return data_to_yaml(tables_info[table_name])
    else:
        return f"Error: Table {table_name} not found or database error"

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
    
    # Initialize database connection only when server starts (fixes RuntimeWarning)
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

    # Start FastMCP server with the specified transport
    if mcp_transport == "sse":
        mcp.settings.host = os.getenv("MCP_HOST")
        mcp.settings.port = int(os.getenv("MCP_PORT"))
        logger.info(f"Starting MCP server on {mcp.settings.host}:{mcp.settings.port}")
        await mcp.run_sse_async()
    elif mcp_transport == "stdio":
        logger.info("Starting FastMCP server with stdio transport")
        await mcp.run_stdio_async()
    elif mcp_transport == "streamable-http":
        mcp.settings.host = os.getenv("MCP_HOST")
        mcp.settings.port = int(os.getenv("MCP_PORT"))
        mcp.settings.streamable_http_path = os.getenv("MCP_PATH", "/mcp/")
        logger.info(f"Starting MCP server on {mcp.settings.host}:{mcp.settings.port} with path {mcp.settings.streamable_http_path}")
        await mcp.run_streamable_http_async()
    else:
        logger.error(f"Unknown transport: {mcp_transport}")
        raise ValueError(f"Unsupported transport: {mcp_transport}")

if __name__ == "__main__":
    asyncio.run(main())