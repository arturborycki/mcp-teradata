"""
List Missing Values Tool - Analyze columns with null values.
"""

from typing import Any, Dict, List, Optional
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
    async def execute(self, input_data: ListMissingValuesInput, context: Optional[Dict[str, Any]] = None) -> ListMissingValuesOutput:
        """
        Analyze missing values in table.

        Connection Resolution (priority order):
        1. Attached connection (self._connection_manager) - set via attach_connection()
        2. Context parameter (context['connection_manager']) - backward compatible
        3. ConnectionRegistry default - global fallback

        Args:
            input_data: Table name
            context: Optional execution context with connection_manager (backward compatible)

        Returns:
            Column null statistics
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
            return ListMissingValuesOutput(
                success=False,
                error="Database connection not initialized (no attached, context, or registry connection available)"
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
