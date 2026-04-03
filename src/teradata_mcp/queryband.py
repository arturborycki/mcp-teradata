"""
QueryBand utilities for Teradata MCP Server.
Builds per-request QueryBand strings for audit and workload management.
"""

from __future__ import annotations


def sanitize_qb_value(val: str | None) -> str:
    """Sanitize a value for use in a Teradata QueryBand string."""
    if val is None:
        return ""
    s = str(val)
    s = s.replace(";", "_")
    s = s.replace("'", "''")
    return s.strip()


def build_queryband(
    application: str = "Teradata_MCP",
    tool_name: str | None = None,
    transport: str | None = None,
) -> str:
    """Build a QueryBand string for a tool execution.

    Args:
        application: Application name.
        tool_name: Name of the MCP tool being executed.
        transport: Transport type (stdio, sse, streamable-http).

    Returns:
        QueryBand string ready for SET QUERY_BAND SQL.
    """
    parts: list[str] = []

    def add(key: str, value):
        if value is None:
            return
        parts.append(f"{key}={sanitize_qb_value(value)};")

    add("ApplicationName", application)
    add("ToolName", tool_name)
    add("Transport", transport)

    return "".join(parts)
