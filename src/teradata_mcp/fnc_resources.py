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

logger = logging.getLogger(__name__)
ResponseType = List[types.TextContent | types.ImageContent | types.EmbeddedResource]

# Global connection and database variables
_connection_manager = None
_db = ""


def set_resource_connection(connection_manager, db: str):
    """Set the global database connection manager and database name."""
    global _connection_manager, _db
    _connection_manager = connection_manager
    _db = db


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

async def read_resource_impl(uri: str) -> str:
    """Implementation of resource reading that can be used with FastMCP decorators."""
    from mcp.server.lowlevel.helper_types import ReadResourceContents
    result = await handle_read_resource(uri)
    # Extract content from ReadResourceContents
    if result and len(result) > 0:
        return result[0].content
    return ""

def data_to_yaml(data: Any) -> str:
    """Convert data to YAML format."""
    return yaml.dump(data, indent=2, sort_keys=False)

async def prefetch_tables(db_name: str) -> dict:
    """Prefetch table and column information."""
    try:
        logger.info("Prefetching table descriptions")
        tdconn = await get_connection()
        cur = tdconn.cursor()
        rows = cur.execute("select TableName, CommentString, DatabaseName from dbc.TablesV tv where UPPER(tv.DatabaseName) = UPPER(?) and tv.TableKind in ('T','V','O');", [db_name])
        table_results = rows.fetchall()
        
        cur_columns = tdconn.cursor()
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

    except ConnectionError as e:
        logger.error(f"Database connection error: {e}")
        return f"Database connection error: {e}"
    except Exception as e:
        logger.error(f"Error prefetching table descriptions: {e}")
        return f"Error prefetching table descriptions: {e}"

# --- Resource Handler Functions ---

async def handle_list_resources() -> list[types.Resource]:
    """Handle listing of available resources."""
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
    """Handle reading of a specific resource."""
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
