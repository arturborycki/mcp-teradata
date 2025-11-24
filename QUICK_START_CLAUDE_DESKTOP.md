# Quick Start: Teradata MCP in Claude Desktop

**⚡ You're running in experimental `search_only` mode - only 1 tool visible initially!**

## 🎯 The One Thing You Need to Know

**Before using any Teradata tools, start with this:**

```
Use search_tool to find all available database tools
```

Then use the discovered tools normally!

---

## Why Only 1 Tool?

You're using the **experimental "tools-as-code" pattern**:
- ✅ 98.7% token reduction
- ✅ Scales to hundreds of tools
- ⚠️ Requires search first

---

## 📖 3-Step Workflow

### 1. Discover Tools

```
You: Use search_tool to find all database tools
```

### 2. See What's Available

```
Claude: Found 6 tools:
- query: Execute SQL queries
- list_db: List databases
- list_tables: List tables
- show_tables_details: Show table columns
- list_missing_values: Find null values
- standard_deviation: Calculate statistics
```

### 3. Use the Tools

```
You: Use the query tool to SELECT * FROM DBC.DBCInfo

Claude: [Executes your query using the Teradata MCP tool]
```

---

## 🎨 Common Prompts

### General Discovery
```
Use search_tool to show all available Teradata tools
```

### Database Operations
```
Search for database tools, then list all databases
```

### Execute Query
```
Find the query tool, then run: SELECT * FROM DBC.DBCInfo
```

### Data Quality
```
Search for analytics tools, then check missing values in my_table
```

---

## ⚙️ Your Current Configuration

**Mode:** `TOOLS_MODE=search_only` (experimental)

**Tools Available:**
- Initially: `search_tool` (1 tool)
- After search: 6 additional tools

**To see all tools immediately:** Change to `TOOLS_MODE=hybrid` in config

---

## 🆘 Troubleshooting

### Claude Uses Bash Instead of Tools?

**Fix:** Explicitly ask to search first:
```
Before doing anything, use search_tool to discover Teradata tools, then use those tools
```

### "Tool not found" Error?

**Fix:** Search first:
```
First use search_tool to find database tools, then try again
```

### Want Traditional Experience?

**Fix:** Edit `claude_desktop_config.json`:
```json
"env": {
  "TOOLS_MODE": "hybrid"  // Shows all 7 tools immediately
}
```

Or use the standard server:
```json
"args": ["--directory", "/path", "run", "teradata-mcp"]
```

---

## 📚 More Info

- Detailed guide: `docs/USING_SEARCH_TOOL.md`
- Full configuration: `docs/CLAUDE_DESKTOP_CONFIG.md`
- Architecture: `docs/TOOLS_AS_CODE.md`

---

## 💡 Remember

**One phrase to start every Teradata conversation:**

> "Use search_tool to find all database tools"

That's it! Search once, then use tools normally for the rest of the conversation.
