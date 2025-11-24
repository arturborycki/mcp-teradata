"""
List Tables Tool - List tables in a specific database.
"""

from typing import Any, Dict, List, Optional
from pydantic import Field
import logging

from ..base import ToolBase, ToolInput, ToolOutput, ToolMetadata
from ...retry_utils import with_connection_retry

logger = logging.getLogger(__name__)


class ListTablesInput(ToolInput):
    """Input schema for list_tables tool."""
    db_name: str = Field(
        ...,
        description="Database name to list tables from"
    )


class ListTablesOutput(ToolOutput):
    """Output schema for list_tables tool."""
    tables: List[List[Any]] = Field(
        default_factory=list,
        description="List of table names in the database"
    )
    count: int = Field(
        default=0,
        description="Number of tables found"
    )
    database: str = Field(
        default="",
        description="Database name that was queried"
    )


class ListTablesTool(ToolBase):
    """
    Lists tables in a specific database.

    Returns all tables, views, and objects in the specified database.
    Includes tables (T), views (V), and other objects (O).
    """

    METADATA = ToolMetadata(
        name="list_tables",
        description="List tables in a database",
        category="database",
        tags=["database", "tables", "list", "schema", "metadata"],
        requires_connection=True,
        requires_oauth=False
    )

    class InputSchema(ListTablesInput):
        pass

    class OutputSchema(ListTablesOutput):
        pass

    @with_connection_retry()
    async def execute(self, input_data: ListTablesInput, context: Optional[Dict[str, Any]] = None) -> ListTablesOutput:
        """
        List tables in a database.

        Connection Resolution (priority order):
        1. Attached connection (self._connection_manager) - set via attach_connection()
        2. Context parameter (context['connection_manager']) - backward compatible
        3. ConnectionRegistry default - global fallback

        Args:
            input_data: Database name
            context: Optional execution context with connection_manager (backward compatible)

        Returns:
            List of tables
        """
        # Priority 1: Use attached connection
        connection_manager = self._connection_manager

        # Priority 2: Fallback to context (backward compatible)
        if connection_manager is None and context:
            connection_manager = context.get('connection_manager')

        # Priority 3: Fallback to registry
        if connection_manager is None:
            try:
                from ...connection_registry import ConnectionRegistry
                registry = ConnectionRegistry.get_instance()
                connection_manager = registry.get_connection()
                if connection_manager:
                    logger.debug("Using connection from ConnectionRegistry")
            except Exception as e:
                logger.warning(f"Could not get connection from registry: {e}")

        if not connection_manager:
            return ListTablesOutput(
                success=False,
                error="Database connection not initialized (no attached, context, or registry connection available)"
            )

        try:
            tdconn = await connection_manager.ensure_connection()
            cur = tdconn.cursor()

            query = """
                SELECT TableName
                FROM dbc.TablesV
                WHERE UPPER(DatabaseName) = UPPER(?)
                  AND TableKind IN ('T','V','O')
            """
            rows = cur.execute(query, [input_data.db_name])

            tables = [list(row) for row in rows.fetchall()]

            return ListTablesOutput(
                success=True,
                tables=tables,
                count=len(tables),
                database=input_data.db_name
            )

        except ConnectionError as e:
            logger.error(f"Database connection error: {e}")
            raise ConnectionError(f"Database connection failed: {str(e)}")
        except Exception as e:
            logger.error(f"Error listing tables: {e}")
            return ListTablesOutput(
                success=False,
                error=str(e)
            )
