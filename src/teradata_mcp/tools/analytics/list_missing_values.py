"""
List Missing Values Tool - Analyze columns with null values.
"""

from typing import Any, Dict, List
from pydantic import Field
import logging

from ..base import ToolBase, ToolInput, ToolOutput, ToolMetadata
from ...retry_utils import with_connection_retry

logger = logging.getLogger(__name__)


class ListMissingValuesInput(ToolInput):
    """Input schema for list_missing_values tool."""
    table_name: str = Field(
        ...,
        description="Fully qualified table name (e.g., database.table)"
    )


class ListMissingValuesOutput(ToolOutput):
    """Output schema for list_missing_values tool."""
    columns: List[List[Any]] = Field(
        default_factory=list,
        description="List of columns with null count and percentage, ordered by null count descending"
    )
    count: int = Field(
        default=0,
        description="Number of columns analyzed"
    )


class ListMissingValuesTool(ToolBase):
    """
    Analyzes columns with missing (null) values in a table.

    Uses Teradata's TD_ColumnSummary function to identify columns
    with null values and their frequency. Results are ordered by
    null count (highest first) to identify data quality issues.

    Returns:
    - Column name
    - Null count
    - Null percentage
    """

    METADATA = ToolMetadata(
        name="list_missing_values",
        description="What are the top features with missing values in a table",
        category="analytics",
        tags=["analytics", "data-quality", "null", "missing", "statistics"],
        requires_connection=True,
        requires_oauth=False
    )

    class InputSchema(ListMissingValuesInput):
        pass

    class OutputSchema(ListMissingValuesOutput):
        pass

    @with_connection_retry()
    async def execute(self, input_data: ListMissingValuesInput, context: Dict[str, Any]) -> ListMissingValuesOutput:
        """
        Analyze missing values in table.

        Args:
            input_data: Table name
            context: Execution context with connection_manager

        Returns:
            Column null statistics
        """
        connection_manager = context.get('connection_manager')
        if not connection_manager:
            return ListMissingValuesOutput(
                success=False,
                error="Database connection not initialized"
            )

        try:
            tdconn = await connection_manager.ensure_connection()
            cur = tdconn.cursor()

            query = f"""
                SELECT ColumnName, NullCount, NullPercentage
                FROM TD_ColumnSummary (
                    ON {input_data.table_name} AS InputTable
                    USING TargetColumns ('[:]')
                ) AS dt
                ORDER BY NullCount DESC
            """
            rows = cur.execute(query)

            columns = [list(row) for row in rows.fetchall()]

            return ListMissingValuesOutput(
                success=True,
                columns=columns,
                count=len(columns)
            )

        except ConnectionError as e:
            logger.error(f"Database connection error: {e}")
            raise ConnectionError(f"Database connection failed: {str(e)}")
        except Exception as e:
            logger.error(f"Error analyzing missing values: {e}")
            return ListMissingValuesOutput(
                success=False,
                error=str(e)
            )
