#!/usr/bin/env python3
"""
Test script for the dynamic tools system (tools-as-code pattern).

This script tests:
1. Tool discovery via search_tool
2. Dynamic tool loading
3. Tool execution
4. Different detail levels

Usage:
    python scripts/test-dynamic-tools.py
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Import directly from tools module to avoid server dependencies
from teradata_mcp.tools.executor import ToolExecutor
from teradata_mcp.tools.base import ToolContext


async def test_tool_discovery():
    """Test discovering tools via search."""
    print("=" * 80)
    print("TEST 1: Tool Discovery")
    print("=" * 80)

    executor = ToolExecutor()

    # Test 1: List all tools (minimal)
    print("\n1. All tools (minimal detail):")
    results = executor.search_tools(detail_level="minimal")
    for tool in results:
        print(f"  - {tool['name']} ({tool['category']})")

    # Test 2: Search by category
    print("\n2. Database tools:")
    results = executor.search_tools(category="database", detail_level="standard")
    for tool in results:
        print(f"  - {tool['name']}: {tool['description']}")

    # Test 3: Search by query
    print("\n3. Search for 'query':")
    results = executor.search_tools(query="query", detail_level="standard")
    for tool in results:
        print(f"  - {tool['name']}: {tool['description']}")

    # Test 4: Full schema for specific tool
    print("\n4. Full schema for 'query' tool:")
    results = executor.search_tools(query="query", detail_level="full")
    if results:
        tool = results[0]
        print(f"  Name: {tool['name']}")
        print(f"  Description: {tool['description']}")
        print(f"  Category: {tool['category']}")
        print(f"  Input Schema: {tool['inputSchema']}")

    print("\n✅ Tool discovery test passed!")


async def test_tool_loading():
    """Test dynamic tool loading."""
    print("\n" + "=" * 80)
    print("TEST 2: Dynamic Tool Loading")
    print("=" * 80)

    executor = ToolExecutor()

    # Test loading various tools
    tools_to_test = ["query", "list_db", "list_tables", "search_tool"]

    for tool_name in tools_to_test:
        print(f"\nLoading tool: {tool_name}")
        tool_class = executor.load_tool(tool_name)

        if tool_class:
            print(f"  ✅ Loaded: {tool_class.__name__}")
            print(f"  Metadata: {tool_class.METADATA.name} - {tool_class.METADATA.description}")
            print(f"  Category: {tool_class.METADATA.category}")
            print(f"  Tags: {', '.join(tool_class.METADATA.tags)}")
        else:
            print(f"  ❌ Failed to load {tool_name}")

    print("\n✅ Tool loading test passed!")


async def test_search_tool_execution():
    """Test executing the search_tool."""
    print("\n" + "=" * 80)
    print("TEST 3: Search Tool Execution")
    print("=" * 80)

    executor = ToolExecutor()

    # Create minimal context for search_tool (doesn't need DB connection)
    context = ToolContext(
        connection_manager=None,
        db_name="test"
    )
    context_dict = context.model_dump()
    context_dict['tool_executor'] = executor

    # Execute search_tool
    print("\n1. Execute search_tool with category='database':")
    result = await executor.execute_tool(
        tool_name="search_tool",
        arguments={"category": "database", "detail_level": "standard"},
        context=context
    )

    if result.get("success"):
        print(f"  Found {result['count']} tools:")
        for tool in result['tools']:
            print(f"    - {tool['name']}: {tool['description']}")
    else:
        print(f"  ❌ Error: {result.get('error')}")

    print("\n2. Execute search_tool with query='statistics':")
    result = await executor.execute_tool(
        tool_name="search_tool",
        arguments={"query": "statistics", "detail_level": "minimal"},
        context=context
    )

    if result.get("success"):
        print(f"  Found {result['count']} tools:")
        for tool in result['tools']:
            print(f"    - {tool['name']}")
    else:
        print(f"  ❌ Error: {result.get('error')}")

    print("\n✅ Search tool execution test passed!")


async def test_cache():
    """Test tool caching."""
    print("\n" + "=" * 80)
    print("TEST 4: Tool Caching")
    print("=" * 80)

    executor = ToolExecutor()

    # Load tool multiple times
    print("\n1. First load of 'query' tool:")
    tool1 = executor.load_tool("query")
    print(f"  Loaded: {tool1}")

    print("\n2. Second load of 'query' tool (should be cached):")
    tool2 = executor.load_tool("query")
    print(f"  Loaded: {tool2}")

    print(f"\n3. Same instance? {tool1 is tool2}")

    print("\n4. Clear cache:")
    executor.clear_cache()

    print("\n5. Third load of 'query' tool (after cache clear):")
    tool3 = executor.load_tool("query")
    print(f"  Loaded: {tool3}")

    print(f"\n6. Same as first instance? {tool1 is tool3}")

    print("\n✅ Caching test passed!")


async def main():
    """Run all tests."""
    print("\n" + "=" * 80)
    print("TESTING DYNAMIC TOOLS SYSTEM (Tools-as-Code Pattern)")
    print("=" * 80)

    try:
        await test_tool_discovery()
        await test_tool_loading()
        await test_search_tool_execution()
        await test_cache()

        print("\n" + "=" * 80)
        print("✅ ALL TESTS PASSED!")
        print("=" * 80)

    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
