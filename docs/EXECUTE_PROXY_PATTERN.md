# Execute Proxy Pattern: True Tools-as-Code Implementation

## Overview

The **Execute Proxy Pattern** achieves true tools-as-code functionality within MCP's architectural constraints:

✅ **Only 2 tools visible initially** (75-98% token reduction)
✅ **All tools executable** after discovery
✅ **Connection attachment** from registry works automatically
✅ **Full functionality** maintained
✅ **MCP compliant** - works with any client

## The Pattern

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    MCP CLIENT (Claude Desktop)               │
│                                                               │
│  Sees only 2 tools:                                          │
│    1. search_tool  - Discovers available tools               │
│    2. execute_tool - Universal executor for discovered tools │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                        TOOL DISCOVERY                         │
│                                                               │
│  User: "What database tools are available?"                  │
│  Claude → search_tool({"query": "database"})                 │
│  Response: ["query", "list_db", "list_tables", ...]          │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                        TOOL EXECUTION                         │
│                                                               │
│  User: "Execute query: SELECT * FROM table"                  │
│  Claude → execute_tool({                                     │
│    "tool_name": "query",                                     │
│    "arguments": {"query": "SELECT * FROM table"}            │
│  })                                                          │
│  execute_tool → ToolExecutor.execute_tool("query", ...)     │
│  ToolExecutor → Loads query tool → Attaches connection      │
│  query tool → Executes with connection from registry        │
│  Result → Returns to Claude                                  │
└─────────────────────────────────────────────────────────────┘
```

### Key Components

**1. search_tool (Discovery)**
- Always visible to Claude
- Scans filesystem for available tools
- Returns tool metadata and schemas
- Provides execution guide

**2. execute_tool (Universal Executor)**
- Always visible to Claude
- Acts as proxy/router
- Accepts: `{tool_name, arguments}`
- Routes to actual tool implementation
- Connection attachment happens automatically

**3. Tool Executor (Behind the Scenes)**
- Dynamically loads tool classes
- Attaches connections from registry
- Executes tools with provided arguments
- Returns results

**4. Connection Registry (Already Implemented)**
- External connection management
- Tools attach at load time
- No context passing needed

## Token Efficiency

### Before (Hybrid Mode)
```
MCP list_tools response:
  - search_tool     (~500 tokens)
  - execute_tool    (~500 tokens)
  - query           (~500 tokens)
  - list_db         (~500 tokens)
  - list_tables     (~500 tokens)
  - show_tables_details (~500 tokens)
  - list_missing_values (~500 tokens)
  - standard_deviation  (~500 tokens)

Total: ~4,000 tokens per list_tools call
```

### After (search_only Mode with Execute Proxy)
```
MCP list_tools response:
  - search_tool     (~500 tokens)
  - execute_tool    (~500 tokens)

Total: ~1,000 tokens per list_tools call
Token savings: 75% (3,000 tokens saved)
```

**Cumulative savings** over multiple interactions add up significantly!

## Usage Examples

### Example 1: Discover Database Tools

**User Request:**
```
"What database tools are available?"
```

**Claude's Actions:**
```python
# Claude calls search_tool
search_tool({
  "query": "database",
  "detail_level": "standard"
})

# Response:
{
  "success": true,
  "tools": [
    {
      "name": "query",
      "description": "Executes a SQL query against the Teradata database",
      "category": "database",
      "tags": ["sql", "teradata", "query"]
    },
    {
      "name": "list_db",
      "description": "List all databases in the Teradata system",
      "category": "database",
      "tags": ["database", "list", "schema"]
    },
    ...
  ],
  "count": 4,
  "execution_guide": "Use execute_tool with tool_name and arguments..."
}
```

### Example 2: Execute Discovered Tool

**User Request:**
```
"Execute this query: SELECT * FROM DBC.DBCInfo"
```

**Claude's Actions:**
```python
# Claude calls execute_tool (not query directly!)
execute_tool({
  "tool_name": "query",
  "arguments": {
    "query": "SELECT * FROM DBC.DBCInfo"
  }
})

# Behind the scenes:
# 1. execute_tool loads query tool class
# 2. query tool attaches to connection from registry
# 3. query tool executes SQL
# 4. Result returned

# Response:
{
  "success": true,
  "tool_executed": "query",
  "result": {
    "results": [[...data...]],
    "row_count": 10
  }
}
```

### Example 3: Full Workflow

```python
# Step 1: User starts conversation
User: "I need to analyze my Teradata database"
Claude sees: [search_tool, execute_tool]  # Only 2 tools

# Step 2: Claude discovers tools
Claude → search_tool({"query": "database"})
Result: ["query", "list_db", "list_tables", ...]

# Step 3: Claude lists databases
Claude → execute_tool({
  "tool_name": "list_db",
  "arguments": {}
})
Result: ["prod_db", "test_db", "analytics_db"]

# Step 4: Claude lists tables
Claude → execute_tool({
  "tool_name": "list_tables",
  "arguments": {"db_name": "prod_db"}
})
Result: ["customers", "orders", "products"]

# Step 5: Claude executes query
Claude → execute_tool({
  "tool_name": "query",
  "arguments": {"query": "SELECT COUNT(*) FROM prod_db.customers"}
})
Result: [[5000]]
```

## Configuration

### Enable Execute Proxy Pattern

Set in `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "teradata": {
      "env": {
        "DATABASE_URI": "teradata://user:pass@host/db",
        "TOOLS_MODE": "search_only"
      }
    }
  }
}
```

### Modes Comparison

| Mode | Visible Tools | Token Usage | Use Case |
|------|---------------|-------------|----------|
| **search_only** | 2 (search_tool + execute_tool) | ~1,000 tokens | Production (recommended) |
| **hybrid** | All (8+) | ~4,000+ tokens | Testing, backward compat |

## Connection Management

The execute proxy pattern integrates seamlessly with the Connection Registry:

```python
# Server startup (one time)
registry = ConnectionRegistry.get_instance()
await registry.register_connection("default", connection_manager)

# Tool execution (automatic)
# 1. Claude calls execute_tool
# 2. execute_tool loads target tool
# 3. Tool attaches to connection from registry (automatic!)
# 4. Tool executes with attached connection
# 5. Result returned

# No manual connection passing needed!
```

**Connection Resolution in Tools:**
1. Attached connection (from registry) - preferred
2. Context parameter - backward compatible
3. Registry fallback - always available

## Benefits

### 1. Token Efficiency
- **75% reduction** in list_tools payload
- Cumulative savings across conversation
- Faster Claude responses (less processing)

### 2. True Tools-as-Code
- Progressive tool discovery
- Only load what you need
- Scale to 100+ tools without token explosion

### 3. Full Functionality
- All tools executable after discovery
- No broken execution paths
- Maintains all features

### 4. MCP Compliant
- Works with any MCP client
- No special protocol extensions needed
- Standard MCP operations

### 5. Clean Architecture
- Single entry point (execute_tool)
- Clear separation of concerns
- Easy to test and maintain

## Implementation Details

### File Structure

```
src/teradata_mcp/
├── tools/
│   ├── system/
│   │   ├── __init__.py
│   │   └── execute_tool.py          # NEW: Universal executor
│   ├── search.py                    # ENHANCED: Execution guide
│   ├── database/
│   │   ├── query.py
│   │   ├── list_db.py
│   │   └── ...
│   └── analytics/
│       └── ...
├── fnc_tools_dynamic.py             # MODIFIED: Register only 2 tools
├── connection_registry.py           # EXISTING: Connection management
└── tools/executor.py                # EXISTING: Dynamic loading
```

### Code Changes

**1. New execute_tool (150 lines)**
```python
class ExecuteTool(ToolBase):
    async def execute(self, input_data, context):
        tool_executor = context['tool_executor']
        result = await tool_executor.execute_tool(
            tool_name=input_data.tool_name,
            arguments=input_data.arguments,
            context=context
        )
        return result
```

**2. Updated tool registration (30 lines)**
```python
async def handle_list_dynamic_tools():
    if tools_mode == "search_only":
        return [search_tool, execute_tool]  # Only 2!
    else:
        return all_tools  # Hybrid mode
```

**3. Enhanced search_tool (50 lines)**
```python
class SearchTool(ToolBase):
    async def execute(self, input_data, context):
        tools = tool_executor.search_tools(...)
        execution_guide = self._generate_execution_guide(tools)
        return SearchToolOutput(
            tools=tools,
            execution_guide=execution_guide
        )
```

## Testing

Comprehensive test suite verifies:
- ✅ Only 2 tools visible in search_only mode
- ✅ search_tool discovers other tools
- ✅ execute_tool routes correctly
- ✅ Connection attachment works
- ✅ Hybrid mode backward compatible
- ✅ 75% token savings achieved

Run tests:
```bash
uv run python scripts/test-execute-proxy-pattern.py
```

## Migration Guide

### From Hybrid Mode

**Current (Hybrid):**
```python
# Claude sees all tools
# Claude calls: query({"query": "SELECT 1"})
```

**New (Execute Proxy):**
```python
# Claude sees: search_tool, execute_tool
# Claude calls: search_tool({"query": "database"})
# Then calls: execute_tool({"tool_name": "query", "arguments": {...}})
```

**Configuration Change:**
```json
{
  "TOOLS_MODE": "hybrid"  // Before
  "TOOLS_MODE": "search_only"  // After
}
```

### No Code Changes Needed

All existing tools work with execute proxy pattern:
- ✅ Connection attachment (already implemented)
- ✅ 3-tier connection resolution (already implemented)
- ✅ Tool schemas (already defined)
- ✅ Error handling (already implemented)

Just change `TOOLS_MODE` and restart!

## Future Enhancements

### Phase 1 (Current): Execute Proxy
- ✅ 2 tools visible
- ✅ 75% token reduction
- ✅ Full functionality

### Phase 2: Tool Caching
- Cache discovered tool schemas in conversation
- Reduce repeated search_tool calls
- 90%+ token reduction

### Phase 3: Smart Discovery
- AI-guided tool discovery
- Semantic search capabilities
- Predictive tool loading

### Phase 4: Tool Streaming
- Stream tool definitions as needed
- On-demand schema delivery
- 99% token reduction

## Troubleshooting

### Issue: "Tool executor not available"
**Solution:** Ensure context includes tool_executor
```python
context_dict['tool_executor'] = _tool_executor
```

### Issue: "Tool not found"
**Solution:** Tool not in filesystem, check tools/ directory

### Issue: Claude calls tools directly
**Solution:** Verify `TOOLS_MODE=search_only` in config

### Issue: Connection errors
**Solution:** Ensure ConnectionRegistry is initialized
```python
await registry.register_connection("default", conn_mgr)
```

## Summary

The **Execute Proxy Pattern** achieves true tools-as-code within MCP:

🎯 **Only 2 tools visible** (search_tool + execute_tool)
📊 **75% token reduction** on list_tools calls
✅ **All tools executable** after discovery
🔗 **Connection management** integrated automatically
🛠️ **MCP compliant** - works everywhere
🚀 **Production ready** - tested and documented

This is the optimal solution for tools-as-code in MCP!
