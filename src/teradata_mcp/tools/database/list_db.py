"""
List Databases Tool - List all databases in the Teradata system.
"""

from typing import Any, Dict, List
from pydantic import Field
import logging

from ..base import ToolBase, ToolInput, ToolOutput, ToolMetadata
from ...retry_utils import with_connection_retry

logger = logging.getLogger(__name__)


class ListDbInput(ToolInput):
    """Input schema for list_db tool (no parameters required)."""
    pass


class DatabaseInfo(Dict[str, Any]):
    """Database information dictionary."""
    pass


class ListDbOutput(ToolOutput):
    """Output schema for list_db tool."""
    databases: List[List[Any]] = Field(
        default_factory=list,
        description="List of databases with their type and description"
    )
    count: int = Field(
        default=0,
        description="Number of databases found"
    )


class ListDbTool(ToolBase):
    """
    Lists all databases in the Teradata system.

    Returns information about each database including:
    - Database name
    - Database type (User or Database)
    - Comment/description

    Excludes system databases owned by PDCRADM.
    """

    METADATA = ToolMetadata(
        name="list_db",
        description="List all databases in the Teradata system",
        category="database",
        tags=["database", "list", "schema", "metadata", "teradata"],
        requires_connection=True,
        requires_oauth=False
    )

    class InputSchema(ListDbInput):
        pass

    class OutputSchema(ListDbOutput):
        pass

    @with_connection_retry()
    async def execute(self, input_data: ListDbInput, context: Dict[str, Any]) -> ListDbOutput:
        """
        List all databases.

        Args:
            input_data: Empty input (no parameters)
            context: Execution context with connection_manager

        Returns:
            List of databases
        """
        connection_manager = context.get('connection_manager')
        if not connection_manager:
            return ListDbOutput(
                success=False,
                error="Database connection not initialized"
            )

        try:
            # Ensure we have a healthy connection
            tdconn = await connection_manager.ensure_connection()
            cur = tdconn.cursor()

            query = """
                SELECT DataBaseName,
                       DECODE(DBKind, 'U', 'User', 'D','DataBase') as DBType,
                       CommentString
                FROM dbc.DatabasesV
                WHERE OwnerName <> 'PDCRADM'
            """
            rows = cur.execute(query)

            databases = [list(row) for row in rows.fetchall()]

            return ListDbOutput(
                success=True,
                databases=databases,
                count=len(databases)
            )

        except ConnectionError as e:
            logger.error(f"Database connection error: {e}")
            raise ConnectionError(f"Database connection failed: {str(e)}")
        except Exception as e:
            logger.error(f"Error listing databases: {e}")
            return ListDbOutput(
                success=False,
                error=str(e)
            )
