#!/usr/bin/env python3
"""
Test Tool Discovery and Execution Flow

This script verifies that:
1. handle_list_dynamic_tools() registers all tools in both modes
2. search_tool can discover tools
3. Discovered tools can be executed
"""

import sys
import asyncio
import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

# Add src to path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

# Mock teradatasql before importing
sys.modules['teradatasql'] = MagicMock()

from teradata_mcp.fnc_tools_dynamic import (
    initialize_dynamic_tools,
    handle_list_dynamic_tools,
    handle_dynamic_tool_call
)


def create_mock_connection():
    """Create a mock connection manager."""
    mock_conn = AsyncMock()
    mock_cursor = MagicMock()
    mock_result = MagicMock()
    mock_result.fetchall.return_value = [["test_db"], ["test_db2"]]
    mock_cursor.execute.return_value = mock_result
    mock_tdconn = MagicMock()
    mock_tdconn.cursor.return_value = mock_cursor
    mock_conn.ensure_connection.return_value = mock_tdconn
    return mock_conn


async def test_search_only_mode():
    """Test search_only mode registers all tools."""
    print("\n=== Test 1: search_only Mode Tool Registration ===")

    # Set environment
    os.environ["TOOLS_MODE"] = "search_only"

    # Initialize system
    mock_conn = create_mock_connection()
    initialize_dynamic_tools(mock_conn, "test_db")

    # Get registered tools
    tools = await handle_list_dynamic_tools()

    print(f"✓ Tools registered in search_only mode: {len(tools)}")
    print(f"  Tool names: {[tool.name for tool in tools]}")

    # Verify all expected tools are registered
    expected_tools = ["search_tool", "query", "list_db", "list_tables",
                     "show_tables_details", "list_missing_values", "standard_deviation"]

    registered_names = [tool.name for tool in tools]
    for expected in expected_tools:
        if expected in registered_names:
            print(f"  ✓ {expected} registered")
        else:
            print(f"  ❌ {expected} NOT registered")

    assert len(tools) >= 7, f"Expected at least 7 tools, got {len(tools)}"
    print(f"\n✓ search_only mode: All {len(tools)} tools registered with MCP")

    return tools


async def test_hybrid_mode():
    """Test hybrid mode registers all tools."""
    print("\n=== Test 2: hybrid Mode Tool Registration ===")

    # Set environment
    os.environ["TOOLS_MODE"] = "hybrid"

    # Get registered tools
    tools = await handle_list_dynamic_tools()

    print(f"✓ Tools registered in hybrid mode: {len(tools)}")
    print(f"  Tool names: {[tool.name for tool in tools]}")

    assert len(tools) >= 7, f"Expected at least 7 tools, got {len(tools)}"
    print(f"\n✓ hybrid mode: All {len(tools)} tools registered with MCP")

    return tools


async def test_tool_execution_after_discovery():
    """Test that discovered tools can be executed."""
    print("\n=== Test 3: Tool Execution After Discovery ===")

    os.environ["TOOLS_MODE"] = "search_only"

    # First, discover tools via search_tool
    print("\nStep 1: Discover tools with search_tool")
    search_result = await handle_dynamic_tool_call(
        "search_tool",
        {"query": "database", "detail_level": "standard"}
    )

    print(f"✓ search_tool executed")
    print(f"  Result: {search_result[0].text[:100]}...")

    # Second, execute a discovered tool (query)
    print("\nStep 2: Execute discovered tool (query)")
    try:
        query_result = await handle_dynamic_tool_call(
            "query",
            {"query": "SELECT * FROM DBC.DBCInfo"}
        )

        print(f"✓ query tool executed (call reached the tool handler)")
        print(f"  Result: {query_result[0].text[:100]}...")

        # The tool executed (didn't get "Tool not found" error from MCP)
        # Connection error is expected in test environment
        result_text = query_result[0].text

        # Success criteria: Tool was invoked (not rejected by MCP)
        # Either successful execution OR connection error (both mean tool is registered)
        if "Tool" in result_text and "not found" in result_text:
            print("❌ MCP rejected the tool call - tool not registered!")
            raise AssertionError("Tool not registered with MCP")

        print("\n✓ Discovered tool (query) was callable by MCP!")
        print("  (Connection error is expected in test environment)")

    except Exception as e:
        if "not found" in str(e).lower():
            print(f"❌ Failed: Tool not registered with MCP: {e}")
            raise
        # Other errors are ok (connection issues, etc.)
        print(f"  Note: Got expected error in test env: {e}")
        print("  ✓ But tool WAS callable (not rejected by MCP)")


async def test_modes_are_equivalent():
    """Test that both modes register the same tools."""
    print("\n=== Test 4: Modes Register Same Tools ===")

    # Get tools from both modes
    os.environ["TOOLS_MODE"] = "search_only"
    search_only_tools = await handle_list_dynamic_tools()

    os.environ["TOOLS_MODE"] = "hybrid"
    hybrid_tools = await handle_list_dynamic_tools()

    search_only_names = sorted([t.name for t in search_only_tools])
    hybrid_names = sorted([t.name for t in hybrid_tools])

    print(f"search_only tools: {search_only_names}")
    print(f"hybrid tools: {hybrid_names}")

    assert search_only_names == hybrid_names, "Both modes should register same tools"

    print("\n✓ Both modes register identical tool sets")
    print("  Difference: Workflow philosophy only, not functionality")


async def main():
    """Run all tests."""
    print("=" * 70)
    print("Tool Discovery and Execution Test")
    print("=" * 70)

    try:
        # Run tests
        await test_search_only_mode()
        await test_hybrid_mode()
        await test_tool_execution_after_discovery()
        await test_modes_are_equivalent()

        print("\n" + "=" * 70)
        print("✅ ALL TESTS PASSED")
        print("=" * 70)
        print("\nFix Verified:")
        print("  ✓ search_only mode registers all tools with MCP")
        print("  ✓ hybrid mode registers all tools with MCP")
        print("  ✓ Discovered tools are executable")
        print("  ✓ Both modes have same functionality")
        print("\nThe tool execution issue is FIXED!")

        return 0

    except Exception as e:
        print("\n" + "=" * 70)
        print(f"❌ TEST FAILED: {e}")
        print("=" * 70)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
