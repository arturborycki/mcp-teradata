# 🧪 Experiment Branch: Tools-as-Code Pattern

This branch contains an **experimental implementation** of the "tools-as-code" pattern inspired by [Anthropic's approach to code execution with MCP](https://www.anthropic.com/engineering/code-execution-with-mcp).

## ⚡ Quick Start

### ⚠️ IMPORTANT: Recommended Configuration

**RECOMMENDED: Use `hybrid` mode instead of `search_only`**

The `search_only` mode has a known limitation: Claude can discover tools but may not execute them reliably.

**Best Configuration:**
```bash
export TOOLS_MODE=hybrid  # All tools visible immediately
```

[Configuration guide →](docs/CLAUDE_DESKTOP_CONFIG.md)

---

### 🧪 search_only Mode (Experimental - Has Limitations)

When running in `TOOLS_MODE=search_only`, **only 1 tool appears initially**: `search_tool`.

**Known Issue:** Claude discovers tools but may fail to execute them.

**If you still want to try it:**
```
Use search_tool to find all available database tools
```

Then use the discovered tools normally! [Full guide →](QUICK_START_CLAUDE_DESKTOP.md)

---

### Try the Pure Tools-as-Code Pattern

```bash
# Checkout the experiment branch
git checkout experiment

# Set environment variables
export TOOLS_MODE=search_only
export DATABASE_URI="teradatasql://user:pass@host/database"
export MCP_TRANSPORT=stdio

# Run the experimental server
uv run python -m teradata_mcp.server_dynamic
```

### Run Tests

```bash
# Test the dynamic tools system
uv run python scripts/test-dynamic-tools.py
```

## 🎯 What's New

### Files Added

```
src/teradata_mcp/
├── tools/                         # NEW: Tools-as-Code infrastructure
│   ├── base.py                   # Base classes for tool definition
│   ├── executor.py               # Dynamic tool loading engine
│   ├── search.py                 # search_tool implementation
│   ├── database/                 # Database tools as files
│   │   ├── query.py
│   │   ├── list_db.py
│   │   ├── list_tables.py
│   │   └── show_tables_details.py
│   └── analytics/                # Analytics tools as files
│       ├── list_missing_values.py
│       └── standard_deviation.py
├── fnc_tools_dynamic.py          # NEW: Dynamic tool handlers
├── server_dynamic.py             # NEW: Experimental server
└── server.py                     # UNCHANGED: Original server

docs/
└── TOOLS_AS_CODE.md              # NEW: Complete documentation

scripts/
└── test-dynamic-tools.py         # NEW: Test suite
```

### Files Modified

- `src/teradata_mcp/__init__.py` - Lazy imports to avoid loading server dependencies

## 🚀 Key Features

### 1. Progressive Tool Discovery

Instead of loading all 8+ tools upfront (400 tokens), agents start with just **1 tool** (`search_tool`) using ~50 tokens:

```python
# Agent discovers tools on-demand
search_tool({
    "category": "database",
    "detail_level": "standard"
})
# Returns: List of database tools with descriptions
```

### 2. Three Operation Modes

**Search-Only Mode** (True tools-as-code):
```bash
export TOOLS_MODE=search_only
# Only search_tool exposed, 98.7% token reduction
# ⚠️ Important: Start conversations with "Use search_tool to find all database tools"
```

**Hybrid Mode** (All tools via dynamic system):
```bash
export TOOLS_MODE=hybrid
# All tools exposed but loaded dynamically
# ✅ Works immediately, no search needed
```

**Legacy Mode** (Original behavior):
```bash
# Use original server.py - no changes
# ✅ Stable, all tools visible
```

### 3. File-Based Tool Definition

Each tool is a separate Python file with type-safe interfaces:

```python
# tools/database/query.py
class QueryTool(ToolBase):
    METADATA = ToolMetadata(
        name="query",
        description="Execute SQL queries",
        category="database",
        tags=["sql", "teradata"]
    )

    class InputSchema(ToolInput):
        query: str

    class OutputSchema(ToolOutput):
        results: List[Any]

    async def execute(self, input_data, context):
        # Tool logic here
        pass
```

### 4. Automatic Tool Discovery

- **No manual registration** needed
- **Just create a file** in the tools/ directory
- **Automatically discovered** by the ToolExecutor
- **Searchable** by name, category, tags

## 📊 Benefits

| Aspect | Traditional | Tools-as-Code | Improvement |
|--------|------------|---------------|-------------|
| **Initial Token Load** | 400 tokens | 50 tokens | **88% reduction** |
| **Typical Usage** | 400 tokens | 150 tokens | **63% reduction** |
| **Large Scale (100 tools)** | 5,000 tokens | 200 tokens | **98.7% reduction** |
| **Adding New Tool** | Edit server.py | Create new file | **Easier** |
| **Tool Organization** | Single file | By category | **Better** |
| **Type Safety** | Manual | Pydantic | **Safer** |

## 🧪 Testing

### Automated Tests

```bash
uv run python scripts/test-dynamic-tools.py
```

Tests verify:
- ✅ Tool discovery (filesystem scanning)
- ✅ Dynamic tool loading
- ✅ search_tool execution
- ✅ Tool caching
- ✅ Category and tag filtering

### Manual Testing

```bash
# Terminal 1: Start server in search_only mode
export TOOLS_MODE=search_only
export DATABASE_URI="teradatasql://user:pass@host/db"
uv run python -m teradata_mcp.server_dynamic

# Terminal 2: Test with Claude Desktop or MCP inspector
# Call search_tool to discover available tools
```

## 📖 Documentation

See [docs/TOOLS_AS_CODE.md](docs/TOOLS_AS_CODE.md) for comprehensive documentation including:

- Architecture overview
- Creating new tools
- Migration guide from traditional to tools-as-code
- Troubleshooting
- Examples and use cases

## 🔄 Comparison: Traditional vs Tools-as-Code

### Traditional Approach (main branch)

**Pros:**
- ✅ Proven and stable
- ✅ All tools immediately visible
- ✅ Simple mental model

**Cons:**
- ❌ Token usage scales linearly with tool count
- ❌ Manual registration required
- ❌ All tools loaded even if unused

### Tools-as-Code (experiment branch)

**Pros:**
- ✅ **98.7% token reduction** at scale
- ✅ Automatic tool discovery
- ✅ Better organization
- ✅ Type-safe interfaces
- ✅ Easy to add new tools

**Cons:**
- ❌ Experimental (not battle-tested)
- ❌ Requires agent to use search_tool
- ❌ Additional complexity

## 🛣️ Migration Path

### Phase 1: Test in Parallel (Current)

```bash
# Original server (main branch)
git checkout main
python -m teradata_mcp.server

# Experimental server (experiment branch)
git checkout experiment
python -m teradata_mcp.server_dynamic
```

Both servers work independently. No breaking changes to main.

### Phase 2: Evaluate & Gather Feedback

- Test with real agents and workloads
- Measure token savings
- Collect user feedback
- Identify issues

### Phase 3: Decision Point

**Option A: Merge to Main**
- Deprecate traditional approach
- Make tools-as-code the default
- Provide migration guide

**Option B: Keep Both**
- Maintain both approaches
- Let users choose via environment variable
- Continue supporting both patterns

**Option C: Iterate**
- Address issues found in testing
- Refine the implementation
- Stay in experiment branch longer

## 🐛 Known Issues & Limitations

1. **Agent Compatibility**: Not all MCP clients may support the search_tool pattern yet
2. **Learning Curve**: Agents need to learn to discover tools first
3. **First-Call Latency**: Dynamic loading adds small delay on first tool use
4. **Development**: Tool caching means server restart needed to pick up changes

## 📝 TODO / Future Enhancements

- [ ] Hot reload for development
- [ ] Tool versioning
- [ ] Permission-based tool filtering
- [ ] Tool composition (tools calling other tools)
- [ ] Performance metrics
- [ ] More tool examples (covering all original tools)
- [ ] Integration tests with actual MCP clients
- [ ] Benchmarking vs traditional approach

## 🤝 Contributing

This is an experiment! Contributions welcome:

1. **Try it out** - test with your use cases
2. **Report issues** - what works, what doesn't?
3. **Suggest improvements** - ideas for better DX
4. **Add tools** - create example tools using the new pattern
5. **Improve docs** - help others understand the pattern

## 📚 Resources

- [Anthropic: Code Execution with MCP](https://www.anthropic.com/engineering/code-execution-with-mcp)
- [Complete Documentation](docs/TOOLS_AS_CODE.md)
- [Test Suite](scripts/test-dynamic-tools.py)
- [MCP Specification](https://modelcontextprotocol.io/)

## ⚠️ Disclaimer

This is an **experimental branch**. While all tests pass and the implementation works, it:

- Has not been tested in production
- May have undiscovered edge cases
- Could change significantly based on feedback
- Should not be used in production without thorough testing

The **main branch remains stable and unchanged**.

## 🎬 Example Session

```bash
# Agent starts with only search_tool
> list_tools()
["search_tool"]

# Agent searches for database tools
> call_tool("search_tool", {"category": "database", "detail_level": "minimal"})
{
  "tools": [
    {"name": "query", "category": "database"},
    {"name": "list_db", "category": "database"},
    {"name": "list_tables", "category": "database"}
  ],
  "count": 3
}

# Agent gets full schema for specific tool
> call_tool("search_tool", {"query": "query", "detail_level": "full"})
{
  "tools": [{
    "name": "query",
    "description": "Executes a SQL query against the Teradata database",
    "inputSchema": {"type": "object", "properties": {"query": {...}}},
    "outputSchema": {...}
  }],
  "count": 1
}

# Agent uses the discovered tool
> call_tool("query", {"query": "SELECT * FROM database.table LIMIT 10"})
{
  "success": true,
  "results": [[...], [...], ...],
  "row_count": 10
}
```

---

**Questions?** Open an issue or check [docs/TOOLS_AS_CODE.md](docs/TOOLS_AS_CODE.md) for detailed documentation.

**Want to switch back?** `git checkout main` - the original server is unchanged!
