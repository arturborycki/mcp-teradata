"""
Standard Deviation Tool - Calculate mean and standard deviation for columns.
"""

from typing import Any, Dict, List
from pydantic import Field
import logging

from ..base import ToolBase, ToolInput, ToolOutput, ToolMetadata
from ...retry_utils import with_connection_retry

logger = logging.getLogger(__name__)


class StandardDeviationInput(ToolInput):
    """Input schema for standard_deviation tool."""
    table_name: str = Field(
        ...,
        description="Fully qualified table name (e.g., database.table)"
    )
    column_name: str = Field(
        ...,
        description="Column name to calculate statistics for"
    )


class StandardDeviationOutput(ToolOutput):
    """Output schema for standard_deviation tool."""
    statistics: List[List[Any]] = Field(
        default_factory=list,
        description="Statistical summary including mean and standard deviation"
    )


class StandardDeviationTool(ToolBase):
    """
    Calculate mean and standard deviation for a numeric column.

    Uses Teradata's TD_UnivariateStatistics function to compute
    basic statistical measures for a column:
    - MEAN: Average value
    - STD: Standard deviation

    Useful for understanding data distribution and identifying outliers.
    """

    METADATA = ToolMetadata(
        name="standard_deviation",
        description="What is the mean and standard deviation for column in table?",
        category="analytics",
        tags=["analytics", "statistics", "mean", "std", "deviation", "numeric"],
        requires_connection=True,
        requires_oauth=False
    )

    class InputSchema(StandardDeviationInput):
        pass

    class OutputSchema(StandardDeviationOutput):
        pass

    @with_connection_retry()
    async def execute(self, input_data: StandardDeviationInput, context: Dict[str, Any]) -> StandardDeviationOutput:
        """
        Calculate statistics for column.

        Args:
            input_data: Table and column name
            context: Execution context with connection_manager

        Returns:
            Statistical summary
        """
        connection_manager = context.get('connection_manager')
        if not connection_manager:
            return StandardDeviationOutput(
                success=False,
                error="Database connection not initialized"
            )

        try:
            tdconn = await connection_manager.ensure_connection()
            cur = tdconn.cursor()

            query = f"""
                SELECT *
                FROM TD_UnivariateStatistics (
                    ON {input_data.table_name} AS InputTable
                    USING TargetColumns ('{input_data.column_name}')
                          Stats('MEAN','STD')
                ) AS dt
                ORDER BY 1,2
            """
            rows = cur.execute(query)

            statistics = [list(row) for row in rows.fetchall()]

            return StandardDeviationOutput(
                success=True,
                statistics=statistics
            )

        except ConnectionError as e:
            logger.error(f"Database connection error: {e}")
            raise ConnectionError(f"Database connection failed: {str(e)}")
        except Exception as e:
            logger.error(f"Error calculating statistics: {e}")
            return StandardDeviationOutput(
                success=False,
                error=str(e)
            )
