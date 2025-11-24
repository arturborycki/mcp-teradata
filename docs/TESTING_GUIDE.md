# Testing Guide: Execute Proxy Pattern

This guide helps you test the Execute Proxy Pattern implementation in Claude Desktop.

## What Was Fixed

### Fix 1: Tool executor not available in context (Commit d97b165)

**Problem:** execute_tool was receiving error "Tool executor not available in context"

**Root Cause:** We were passing ToolContext object instead of context_dict to the tool executor

**Fix Applied:** Changed line 183 in `fnc_tools_dynamic.py` to pass `context_dict` instead of `context`

### Fix 2: Dict object has no attribute 'model_dump' (Commit 46c2e31)

**Problem:** After Fix 1, getting error "'dict' object has no attribute 'model_dump'"

**Root Cause:** executor.py:231 assumed context was always ToolContext object, called `.model_dump()` on dict

**Fix Applied:** Added type checking in executor.py to handle both dict and ToolContext objects

**Current Commit:** 46c2e31

## Testing in Claude Desktop

### Step 1: Restart Claude Desktop

After pulling the latest changes, you MUST restart Claude Desktop completely:

1. Quit Claude Desktop (Cmd+Q on macOS)
2. Reopen Claude Desktop
3. Check Server Logs (View → Developer → Server Logs)
4. Look for: `[teradata] [info] Server started and connected successfully`

### Step 2: Verify Only 2 Tools Visible

**What to expect:**
- Only 2 tools should be visible initially
- Tool names: `search_tool` and `execute_tool`
- This achieves ~75% token reduction

**How to verify:**
Ask Claude: "What tools do you have available?"

Claude should see only:
- search_tool
- execute_tool

### Step 3: Test Tool Discovery

**Test command:**
```
Search for available database tools
```

**Expected behavior:**
1. Claude calls `search_tool({"query": "database"})`
2. Response includes:
   - List of discovered tools (query, list_db, list_tables, etc.)
   - Execution guide explaining how to use execute_tool
   - Tool schemas (depending on detail_level)

**Success criteria:**
- ✅ search_tool executes without errors
- ✅ Multiple tools discovered (query, list_db, etc.)
- ✅ execution_guide field present
- ✅ No "Tool executor not available in context" error

### Step 4: Test Tool Execution via Proxy

**Test command:**
```
Execute this query: SELECT * FROM DBC.DBCInfo
```

**Expected behavior:**
1. Claude calls `execute_tool({
     "tool_name": "query",
     "arguments": {"query": "SELECT * FROM DBC.DBCInfo"}
   })`
2. execute_tool routes to query tool
3. query tool attaches to connection from registry
4. Query executes and returns results

**Success criteria:**
- ✅ No "Tool executor not available in context" error
- ✅ execute_tool successfully routes to query tool
- ✅ Query executes (results or connection error, not routing error)
- ✅ Connection attachment works

### Step 5: Test Connection Attachment

**Test command:**
```
List all databases in the system
```

**Expected behavior:**
1. Claude calls `execute_tool({
     "tool_name": "list_db",
     "arguments": {}
   })`
2. execute_tool routes to list_db tool
3. list_db attaches to connection from registry
4. Returns list of databases

**Success criteria:**
- ✅ Tool executes successfully
- ✅ Connection is retrieved from registry
- ✅ Database list returned (or appropriate connection error)

### Step 6: Full Workflow Test

**Test command:**
```
I need to analyze the customers table in the prod_db database.
First discover what tools are available, then list the tables,
then show me the row count.
```

**Expected behavior:**
1. Claude uses search_tool to discover tools
2. Claude uses execute_tool → list_tables
3. Claude uses execute_tool → query (for COUNT)
4. All steps execute successfully

**Success criteria:**
- ✅ Multi-step workflow completes
- ✅ All execute_tool calls route correctly
- ✅ Connections shared across calls
- ✅ No routing or context errors

## Common Issues and Solutions

### Issue 1: "Tool executor not available in context"

**Status:** Should be FIXED in commit d97b165

**If still occurring:**
1. Verify you pulled latest changes: `git log --oneline -1`
2. Should show: `46c2e31 Fix: Handle dict context in executor`
3. Restart Claude Desktop completely
4. Check server logs for initialization errors

### Issue 2: "'dict' object has no attribute 'model_dump'"

**Status:** Should be FIXED in commit 46c2e31

**If still occurring:**
1. Verify you have both fixes: `git log --oneline -2`
2. Should show both d97b165 and 46c2e31
3. Restart Claude Desktop completely

### Issue 3: All Tools Visible (Not Just 2)

**Cause:** `TOOLS_MODE` not set to `search_only`

**Solution:**
Check `~/Library/Application Support/Claude/claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "teradata": {
      "env": {
        "TOOLS_MODE": "search_only"  // ← Must be this value
      }
    }
  }
}
```

### Issue 4: Claude Calls Tools Directly

**Cause:** Tools are visible (not in search_only mode)

**Solution:** Set `TOOLS_MODE=search_only` and restart Claude Desktop

### Issue 5: Connection Errors

**Cause:** Connection not registered or DATABASE_URI incorrect

**Check:**
1. Verify DATABASE_URI in config: `teradatasql://user:pass@host/db`
2. Check server logs for connection errors
3. Verify Teradata system is accessible

## Verification Checklist

After testing, verify these criteria:

- [ ] Only 2 tools visible initially (search_tool + execute_tool)
- [ ] search_tool discovers other tools successfully
- [ ] execute_tool routes to discovered tools without errors
- [ ] No "Tool executor not available in context" errors
- [ ] Connection attachment works from registry
- [ ] Multi-step workflows complete successfully
- [ ] ~75% token savings achieved (2 tools vs 7+ tools)

## Expected Log Output

### Successful Initialization
```
[teradata] [info] Dynamic tools system initialized with tools directory: .../tools
[teradata] [info] Discovered 7 tools:
[teradata] [info]   - search_tool (system): Search and discover available tools
[teradata] [info]   - execute_tool (system): Execute a tool discovered via search_tool
[teradata] [info]   - query (database): Executes a SQL query
[teradata] [info]   ...
[teradata] [info] 🎯 Listing tools in search_only mode (Execute Proxy Pattern)
[teradata] [info]    Only 2 tools visible: search_tool + execute_tool
[teradata] [info]    Token savings: ~71-98% compared to exposing all tools
[teradata] [info]    ✓ search_tool - Discover available tools
[teradata] [info]    ✓ execute_tool - Execute discovered tools
[teradata] [info]    Total: 2 tools registered (down from 7)
```

### Successful Tool Discovery
```
[teradata] [info] Dynamic tool call: search_tool with arguments: {'query': 'database'}
[teradata] [info] Searching for tools: query='database', category=None, tags=None
[teradata] [info] Found 4 matching tools
```

### Successful Tool Execution
```
[teradata] [info] Dynamic tool call: execute_tool with arguments: {'tool_name': 'query', 'arguments': {...}}
[teradata] [info] Executing tool: query
[teradata] [info] Tool attached to connection: default
[teradata] [info] Executing SQL query: SELECT * FROM DBC.DBCInfo
```

## Running Automated Tests

Before testing in Claude Desktop, run the automated test suite:

```bash
cd /Users/naotar/Workfiles/MCP/mcp-teradata
uv run python scripts/test-execute-proxy-pattern.py
```

**Expected output:**
```
======================================================================
Execute Proxy Pattern Test (True Tools-as-Code)
======================================================================

=== Test 1: Only 2 Tools Visible (Token Efficiency) ===
✓ Tools registered: 2
  Tool names: ['search_tool', 'execute_tool']
✓ Only search_tool and execute_tool visible
✓ Token savings: ~71-98% vs exposing all 7 tools

=== Test 2: search_tool Discovers Other Tools ===
✓ search_tool executed successfully
✓ search_tool discovered other tools
✓ Execution guide included

=== Test 3: execute_tool Routes to Discovered Tools ===
✓ execute_tool called successfully
✓ execute_tool successfully routed to query tool
✓ No 'tool not found' errors

... [more tests]

======================================================================
✅ ALL TESTS PASSED
======================================================================

🎯 TRUE TOOLS-AS-CODE ACHIEVED!
   • Token efficient (71-98% reduction)
   • Fully functional (all tools executable)
   • Connection management integrated
```

## Next Steps

After successful testing:

1. **Document results** - Note any issues or successes
2. **Measure token savings** - Compare list_tools size before/after
3. **Test edge cases** - Try complex multi-step workflows
4. **Performance testing** - Verify connection sharing works efficiently

## Reporting Issues

If you encounter issues:

1. **Collect logs** from Claude Desktop (View → Developer → Server Logs)
2. **Note the exact command** you used
3. **Include error messages** from logs
4. **Check git commit** - Should be d97b165 or later
5. **Open issue** on GitHub with details

## Success Indicators

You'll know it's working when:

✅ Claude says "I have access to search_tool and execute_tool"
✅ Claude discovers tools via search_tool
✅ Claude executes tools via execute_tool (not directly)
✅ No context or routing errors in logs
✅ Queries execute successfully with shared connection
✅ Multi-step workflows complete end-to-end

## Related Documentation

- [Execute Proxy Pattern](EXECUTE_PROXY_PATTERN.md) - Architecture details
- [Claude Desktop Config](CLAUDE_DESKTOP_CONFIG.md) - Configuration guide
- [Connection Flow](CONNECTION_FLOW.md) - Connection management details
