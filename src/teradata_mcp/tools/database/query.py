"""
Query Tool - Execute SQL queries against Teradata database.
"""

from typing import Any, Dict, List
from pydantic import Field
import logging

from ..base import ToolBase, ToolInput, ToolOutput, ToolMetadata
from ...retry_utils import with_connection_retry

logger = logging.getLogger(__name__)


class QueryInput(ToolInput):
    """Input schema for query tool."""
    query: str = Field(
        ...,
        description="SQL query to execute (Teradata SQL dialect)"
    )


class QueryOutput(ToolOutput):
    """Output schema for query tool."""
    results: List[List[Any]] = Field(
        default_factory=list,
        description="Query results as list of rows"
    )
    row_count: int = Field(
        default=0,
        description="Number of rows returned"
    )


class QueryTool(ToolBase):
    """
    Executes a SQL query against the Teradata database.

    This tool allows execution of SELECT, INSERT, UPDATE, DELETE and other
    SQL statements using Teradata SQL dialect. Results are returned as a
    list of rows.

    Examples:
    - SELECT * FROM database.table LIMIT 10
    - SELECT COUNT(*) FROM database.table WHERE condition
    - INSERT INTO table VALUES (...)
    """

    METADATA = ToolMetadata(
        name="query",
        description="Executes a SQL query against the Teradata database",
        category="database",
        tags=["sql", "teradata", "query", "select", "database"],
        requires_connection=True,
        requires_oauth=False
    )

    class InputSchema(QueryInput):
        pass

    class OutputSchema(QueryOutput):
        pass

    @with_connection_retry()
    async def execute(self, input_data: QueryInput, context: Dict[str, Any]) -> QueryOutput:
        """
        Execute the SQL query.

        Args:
            input_data: Query parameters
            context: Execution context with connection_manager

        Returns:
            Query results
        """
        connection_manager = context.get('connection_manager')
        if not connection_manager:
            return QueryOutput(
                success=False,
                error="Database connection not initialized"
            )

        try:
            logger.debug(f"Executing query: {input_data.query}")

            # Ensure we have a healthy connection
            tdconn = await connection_manager.ensure_connection()
            cur = tdconn.cursor()
            rows = cur.execute(input_data.query)

            if rows is None:
                return QueryOutput(
                    success=True,
                    results=[],
                    row_count=0
                )

            results = [list(row) for row in rows.fetchall()]

            return QueryOutput(
                success=True,
                results=results,
                row_count=len(results)
            )

        except ConnectionError as e:
            logger.error(f"Database connection error: {e}")
            # Re-raise so retry logic can handle it
            raise ConnectionError(f"Database connection failed: {str(e)}")
        except Exception as e:
            logger.error(f"Error executing query: {e}")
            return QueryOutput(
                success=False,
                error=str(e)
            )
