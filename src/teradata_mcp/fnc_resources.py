"""
MCP Resource Functions for Teradata Database Operations

This module contains resource handlers exposed through the MCP server.
"""

import logging
import yaml
from pathlib import Path
from typing import Any, List
from pydantic import AnyUrl

import mcp.types as types
from mcp.server.lowlevel.helper_types import ReadResourceContents
from .sql_constants import COLUMN_TYPE_CASE_SQL

# Path to the built MCP App HTML
_MCP_APP_HTML = Path(__file__).parent.parent.parent / "mcp-app" / "dist" / "mcp-app.html"
_MCP_APP_RESOURCE_URI = "ui://query/mcp-app.html"
_VIZ_RESOURCE_URI = "ui://visualize_query/mcp-app.html"
_MCP_APP_MIME_TYPE = "text/html;profile=mcp-app"

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
        from . import server
        await server.lazy_initialize_database()

        if not _connection_manager:
            raise ConnectionError(
                "Database connection not initialized. "
                "Please set DATABASE_URI environment variable or provide database URL."
            )

    return await _connection_manager.ensure_connection()

async def read_resource_impl(uri: str) -> str:
    """Implementation of resource reading that can be used with FastMCP decorators."""
    result = await handle_read_resource(uri)
    if result and len(result) > 0:
        return result[0].content
    return ""

def data_to_yaml(data: Any) -> str:
    """Convert data to YAML format."""
    return yaml.dump(data, indent=2, sort_keys=False)

async def prefetch_tables(db_name: str) -> dict:
    """Prefetch table and column information.

    Returns:
        dict: Table schema information.

    Raises:
        ConnectionError: If database connection fails.
        RuntimeError: If prefetch operation fails.
    """
    logger.info("Prefetching table descriptions")
    tdconn = await get_connection()
    cur = tdconn.cursor()
    rows = cur.execute("select TableName, CommentString, DatabaseName from dbc.TablesV tv where UPPER(tv.DatabaseName) = UPPER(?) and tv.TableKind in ('T','V','O');", [db_name])
    table_results = rows.fetchall()

    cur_columns = tdconn.cursor()
    cur_columns.execute(
                f"""
                sel TableName, ColumnName, {COLUMN_TYPE_CASE_SQL} as CType, CommentString
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

# --- Resource Handler Functions ---

async def handle_list_resources() -> list[types.Resource]:
    """Handle listing of available resources."""
    global _db

    resources = []

    # Add the MCP App UI resources
    if _MCP_APP_HTML.exists():
        resources.append(
            types.Resource(
                uri=AnyUrl(_MCP_APP_RESOURCE_URI),
                name="Query Visualizer",
                description="Interactive ECharts visualization for visualize_query results",
                mimeType=_MCP_APP_MIME_TYPE,
            )
        )
        resources.append(
            types.Resource(
                uri=AnyUrl(_VIZ_RESOURCE_URI),
                name="Query Visualizer",
                description="Interactive ECharts visualization for visualize_query results",
                mimeType=_MCP_APP_MIME_TYPE,
            )
        )

    try:
        tables_info = await prefetch_tables(_db)
    except Exception as e:
        logger.warning(f"Could not prefetch tables: {e}")
        resources.append(
            types.Resource(
                uri=AnyUrl("teradata://error"),
                name="Error",
                description=f"Could not load table resources: check database connection",
                mimeType="text/plain",
            )
        )
        return resources

    for table_name in tables_info:
        resources.append(
            types.Resource(
                uri=AnyUrl(f"teradata://table/{table_name}"),
                name=f"{table_name} table",
                description=f"{tables_info[table_name]['description']}" if tables_info[table_name]['description'] else f"Description of the {table_name} table",
                mimeType="text/plain",
            )
        )
    return resources


async def handle_read_resource(uri: AnyUrl):
    """Handle reading of a specific resource."""
    global _db
    uri_str = str(uri)

    # Handle MCP App UI resources
    if uri_str in (_MCP_APP_RESOURCE_URI, _VIZ_RESOURCE_URI):
        if _MCP_APP_HTML.exists():
            html_content = _MCP_APP_HTML.read_text(encoding="utf-8")
            return [ReadResourceContents(
                content=html_content,
                mime_type=_MCP_APP_MIME_TYPE,
            )]
        else:
            raise ValueError(f"MCP App HTML not found at: {_MCP_APP_HTML}")

    if uri_str.startswith("teradata://table"):
        tables_info = await prefetch_tables(_db)
        table_name = uri_str.split("/")[-1]
        if table_name in tables_info:
            return [ReadResourceContents(
                content=data_to_yaml(tables_info[table_name]),
                mime_type="text/plain",
            )]
        else:
            raise ValueError(f"Unknown table: {table_name}")
    else:
        raise ValueError(f"Unknown resource: {uri}")
