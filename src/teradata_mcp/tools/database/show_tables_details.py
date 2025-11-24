"""
Show Table Details Tool - Get detailed column information about tables.
"""

from typing import Any, Dict, List
from pydantic import Field
import logging

from ..base import ToolBase, ToolInput, ToolOutput, ToolMetadata
from ...retry_utils import with_connection_retry

logger = logging.getLogger(__name__)


class ShowTablesDetailsInput(ToolInput):
    """Input schema for show_tables_details tool."""
    db_name: str = Field(
        ...,
        description="Database name (use '%' for wildcard)"
    )
    table_name: str = Field(
        default="",
        description="Table name (use '%' for wildcard, empty defaults to '%')"
    )


class ShowTablesDetailsOutput(ToolOutput):
    """Output schema for show_tables_details tool."""
    columns: List[List[Any]] = Field(
        default_factory=list,
        description="List of columns with their table name, column name, and data type"
    )
    count: int = Field(
        default=0,
        description="Number of columns found"
    )


class ShowTablesDetailsTool(ToolBase):
    """
    Get detailed column information about database tables.

    Returns column-level metadata including:
    - Table name
    - Column name
    - Data type (decoded to human-readable format)

    Supports wildcard patterns using '%' for both database and table names.
    """

    METADATA = ToolMetadata(
        name="show_tables_details",
        description="Show detailed information about database tables including column names and types",
        category="database",
        tags=["database", "tables", "columns", "schema", "metadata", "details"],
        requires_connection=True,
        requires_oauth=False
    )

    class InputSchema(ShowTablesDetailsInput):
        pass

    class OutputSchema(ShowTablesDetailsOutput):
        pass

    @with_connection_retry()
    async def execute(self, input_data: ShowTablesDetailsInput, context: Dict[str, Any]) -> ShowTablesDetailsOutput:
        """
        Get detailed table and column information.

        Args:
            input_data: Database and table name (supports wildcards)
            context: Execution context with connection_manager

        Returns:
            Column details
        """
        connection_manager = context.get('connection_manager')
        if not connection_manager:
            return ShowTablesDetailsOutput(
                success=False,
                error="Database connection not initialized"
            )

        # Handle empty table name
        table_name = input_data.table_name if input_data.table_name else "%"
        db_name = input_data.db_name if input_data.db_name else "%"

        try:
            tdconn = await connection_manager.ensure_connection()
            cur = tdconn.cursor()

            query = """
                SELECT TableName, ColumnName,
                       CASE ColumnType
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
                          WHEN '??' THEN 'STGEOMETRY'
                          ELSE 'UNKNOWN'
                       END AS CType
                FROM DBC.ColumnsVX
                WHERE UPPER(tableName) LIKE UPPER(?)
                  AND UPPER(DatabaseName) LIKE UPPER(?)
            """
            rows = cur.execute(query, [table_name, db_name])

            columns = [list(row) for row in rows.fetchall()]

            return ShowTablesDetailsOutput(
                success=True,
                columns=columns,
                count=len(columns)
            )

        except ConnectionError as e:
            logger.error(f"Database connection error: {e}")
            raise ConnectionError(f"Database connection failed: {str(e)}")
        except Exception as e:
            logger.error(f"Error getting table details: {e}")
            return ShowTablesDetailsOutput(
                success=False,
                error=str(e)
            )
