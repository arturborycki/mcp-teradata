# Using search_tool in Tools-as-Code Mode

When running the Teradata MCP server in `TOOLS_MODE=search_only`, you'll notice that **only one tool appears initially**: `search_tool`. This is intentional and part of the "tools-as-code" pattern that provides 98.7% token reduction.

## 🎯 Quick Answer

**Before using any database tools, ask Claude:**

```
Use search_tool to find all available database tools
```

Claude will discover 6 additional tools, then you can use them normally.

---

## Why Only One Tool?

### Traditional Approach (All Tools Visible)
- 7 tools loaded upfront = ~400 tokens
- All tools always in context
- Works immediately

### Tools-as-Code Approach (search_only mode)
- 1 tool (search_tool) initially = ~50 tokens
- Other tools discovered on-demand = ~150 tokens when needed
- **98.7% token reduction** at scale (100+ tools)

**You're using the experimental tools-as-code approach!**

---

## 🚀 How to Use search_tool

### Step 1: Discover Available Tools

Start your conversation by asking Claude to search for tools:

**Option A: Search by Category**
```
Use search_tool to find all database tools
```

**Option B: Search by Functionality**
```
Search for tools that can execute SQL queries
```

**Option C: List Everything**
```
Use search_tool to show me all available Teradata tools
```

### Step 2: Use the Discovered Tools

Once Claude discovers the tools, use them normally:

```
Now use the query tool to SELECT * FROM DBC.DBCInfo
```

---

## 📋 Complete Workflow Example

### Example 1: Querying Database Info

```
You: Use search_tool to find database tools

Claude: [Discovers: query, list_db, list_tables, show_tables_details]

You: Great! Now use the query tool to SELECT * FROM DBC.DBCInfo

Claude: [Uses query tool with your SQL]
```

### Example 2: Exploring Schema

```
You: Search for tools that can list database objects

Claude: [Discovers tools and shows: list_db, list_tables, show_tables_details]

You: Use list_db to show all databases

Claude: [Uses list_db tool]

You: Now list tables in the 'demo' database

Claude: [Uses list_tables tool with db_name='demo']
```

### Example 3: Data Quality Analysis

```
You: Find tools for analyzing data quality

Claude: [Discovers: list_missing_values, list_negative_values, standard_deviation]

You: Use list_missing_values on the customer_table

Claude: [Uses list_missing_values tool]
```

---

## 🔍 Available Tools (After Discovery)

Once you search, these 6 tools become available:

### Database Tools
1. **query** - Execute SQL queries against Teradata
2. **list_db** - List all databases in the system
3. **list_tables** - List tables in a specific database
4. **show_tables_details** - Get column details for tables

### Analytics Tools
5. **list_missing_values** - Find columns with null values
6. **standard_deviation** - Calculate mean and std deviation

---

## 🎨 search_tool Parameters

### Basic Search

**By Category:**
```json
{
  "category": "database"
}
```

**By Query:**
```json
{
  "query": "query"
}
```

**By Tags:**
```json
{
  "tags": ["sql", "teradata"]
}
```

### Detail Levels

**Minimal** (just names):
```json
{
  "category": "database",
  "detail_level": "minimal"
}
```

**Standard** (names + descriptions):
```json
{
  "category": "database",
  "detail_level": "standard"
}
```

**Full** (complete schemas):
```json
{
  "query": "query",
  "detail_level": "full"
}
```

---

## 💡 Pro Tips

### 1. Search Once Per Conversation

You only need to search once. After Claude discovers tools, they remain available for the rest of the conversation:

```
You: Search for all database tools

Claude: [Discovers all tools]

You: Use query tool for SELECT * FROM table1
Claude: [Uses tool]

You: Now use query tool for SELECT * FROM table2
Claude: [Uses same tool again - no need to search]
```

### 2. Be Specific in Your Search

```
❌ "Show me tools"
✅ "Search for tools that execute SQL queries"

❌ "What can you do?"
✅ "Use search_tool to find all database and analytics tools"
```

### 3. Combine Discovery with Action

```
You: Search for database tools, then show me all databases

Claude: [Uses search_tool to discover list_db, then uses list_db]
```

---

## ❓ Troubleshooting

### Problem: Claude Tries to Use Bash Instead of Tools

**Symptom:**
```
Claude: Let me run this query using bteq...
```

**Solution:**
Explicitly ask Claude to use search_tool first:
```
Before doing anything, use search_tool to discover available Teradata MCP tools. Then use those tools instead of bash.
```

### Problem: "Tool Not Found" Error

**Symptom:**
```
Error: Tool not found: query
```

**Solution:**
Claude hasn't discovered the tools yet. Ask:
```
First search for available tools using search_tool, then try again
```

### Problem: Only Seeing 1 Tool in Claude Desktop

**This is normal!** You're in `search_only` mode. That one tool is `search_tool` - use it to discover the others.

### Problem: Want All Tools Visible Immediately?

**Solution:** Switch to hybrid mode in your `claude_desktop_config.json`:

```json
"env": {
  "TOOLS_MODE": "hybrid"  // Changed from "search_only"
}
```

Then restart Claude Desktop.

---

## 📊 Comparison: Search-Only vs Hybrid

| Aspect | Search-Only | Hybrid |
|--------|-------------|--------|
| **Initial tools visible** | 1 (search_tool) | 7 (all tools) |
| **Token usage** | ~50 initial, ~150 total | ~400 total |
| **User experience** | Need to search first | Works immediately |
| **Best for** | Token efficiency | Convenience |

---

## 🎓 Learning Path

### Beginner (First Time)
1. Start with: "Use search_tool to find all database tools"
2. See what tools are available
3. Try using one: "Use the query tool to SELECT * FROM DBC.DBCInfo"

### Intermediate
1. Search by functionality: "Find tools for data quality analysis"
2. Use multiple tools in sequence
3. Combine with natural language queries

### Advanced
1. Use detail_level=full to see complete schemas
2. Chain multiple tool calls
3. Search for specific tags or categories

---

## 📚 Related Documentation

- [Experiment README](../EXPERIMENT_README.md) - Overview of tools-as-code
- [Tools as Code Pattern](TOOLS_AS_CODE.md) - Technical architecture
- [Claude Desktop Config](CLAUDE_DESKTOP_CONFIG.md) - Configuration guide
- [Connection Flow](CONNECTION_FLOW.md) - How connections work

---

## 🚦 Quick Decision Guide

**Should I use search_only mode?**

✅ **YES** if:
- You want maximum token efficiency
- You have many tools (10+)
- You don't mind an extra step
- You're exploring the experimental pattern

❌ **NO** if:
- You want immediate tool access
- You have few tools (< 10)
- You prefer traditional MCP experience
- You're in production

**→ Switch to `TOOLS_MODE=hybrid` or use the standard `teradata-mcp` server instead**

---

## 💬 Example Conversation Starters

Copy-paste these to start using the Teradata MCP server:

**General Discovery:**
```
Use search_tool to show me all available Teradata tools with descriptions
```

**Database Operations:**
```
Search for database tools, then list all databases in my Teradata system
```

**Query Execution:**
```
Find the query tool, then use it to SELECT * FROM DBC.DBCInfo
```

**Data Quality:**
```
Search for analytics tools, then check for missing values in my customer table
```

**Schema Exploration:**
```
Use search_tool to find schema tools, then show me details for all tables in database 'demo'
```

---

## 🎯 Summary

1. **You're in experimental mode** - Only search_tool is visible initially
2. **This is intentional** - Provides 98.7% token reduction
3. **Always search first** - "Use search_tool to find database tools"
4. **Then use discovered tools** - They work normally after discovery
5. **Search once per conversation** - Tools stay available

**Key phrase to remember:**
> "Use search_tool to find all database tools"

Start every Teradata conversation with this, and you'll have access to all 6 tools!
