# Claude Desktop Configuration

This guide explains how to configure Claude Desktop to use the Teradata MCP server, including the experimental tools-as-code version.

## Configuration File Location

**macOS:**
```
~/Library/Application Support/Claude/claude_desktop_config.json
```

**Windows:**
```
%APPDATA%\Claude\claude_desktop_config.json
```

**Linux:**
```
~/.config/Claude/claude_desktop_config.json
```

## Configuration Options

### Option 1: Original Server (Stable)

Use the original server with all tools registered upfront:

```json
{
  "mcpServers": {
    "teradata": {
      "command": "uv",
      "args": [
        "--directory",
        "/Users/naotar/Workfiles/MCP/mcp-teradata",
        "run",
        "teradata-mcp"
      ],
      "env": {
        "DATABASE_URI": "teradatasql://user:pass@host/database"
      }
    }
  }
}
```

### Option 2: Dynamic Server - Search Only Mode (Experimental)

Use the tools-as-code pattern with only `search_tool` exposed:

```json
{
  "mcpServers": {
    "teradata": {
      "command": "uv",
      "args": [
        "--directory",
        "/Users/naotar/Workfiles/MCP/mcp-teradata",
        "run",
        "python",
        "-m",
        "teradata_mcp.server_dynamic"
      ],
      "env": {
        "DATABASE_URI": "teradatasql://user:pass@host/database",
        "TOOLS_MODE": "search_only"
      }
    }
  }
}
```

### Option 3: Dynamic Server - Hybrid Mode (Experimental)

All tools exposed but loaded dynamically:

```json
{
  "mcpServers": {
    "teradata": {
      "command": "uv",
      "args": [
        "--directory",
        "/Users/naotar/Workfiles/MCP/mcp-teradata",
        "run",
        "python",
        "-m",
        "teradata_mcp.server_dynamic"
      ],
      "env": {
        "DATABASE_URI": "teradatasql://user:pass@host/database",
        "TOOLS_MODE": "hybrid"
      }
    }
  }
}
```

## Environment Variables

### Required

- **DATABASE_URI**: Teradata connection string
  - Format: `teradatasql://username:password@hostname/database`
  - Example: `teradatasql://dbc:dbc@localhost/demo`

### Optional - Connection Management

- **DB_MAX_RETRIES**: Maximum retry attempts (default: `3`)
- **DB_INITIAL_BACKOFF**: Initial backoff in seconds (default: `1.0`)
- **DB_MAX_BACKOFF**: Maximum backoff in seconds (default: `30.0`)

### Optional - Server Configuration

- **MCP_TRANSPORT**: Transport method (default: `stdio`)
  - Options: `stdio`, `sse`, `streamable-http`
- **MCP_HOST**: Host for HTTP transports (default: `127.0.0.1`)
- **MCP_PORT**: Port for HTTP transports (default: `8000`)

### Optional - Dynamic Tools Mode

- **TOOLS_MODE**: Tool loading mode (default: `search_only`)
  - `search_only`: Only search_tool exposed (true tools-as-code)
  - `hybrid`: All tools exposed via dynamic system
  - `legacy`: Falls back to original tool system (use original server instead)

### Optional - OAuth Authentication

- **OAUTH_ENABLED**: Enable OAuth 2.1 (default: `false`)
- **OAUTH_KEYCLOAK_URL**: Keycloak server URL
- **OAUTH_REALM**: Keycloak realm name
- **OAUTH_CLIENT_ID**: OAuth client ID
- **OAUTH_CLIENT_SECRET**: OAuth client secret
- **OAUTH_REQUIRED_SCOPES**: Comma-separated list of required scopes

## Complete Configuration Example

### Full Configuration with All Options

```json
{
  "mcpServers": {
    "teradata": {
      "command": "uv",
      "args": [
        "--directory",
        "/Users/naotar/Workfiles/MCP/mcp-teradata",
        "run",
        "python",
        "-m",
        "teradata_mcp.server_dynamic"
      ],
      "env": {
        "DATABASE_URI": "teradatasql://dbc:dbc@tdhost.company.com/demo",
        "TOOLS_MODE": "search_only",
        "DB_MAX_RETRIES": "5",
        "DB_INITIAL_BACKOFF": "2.0",
        "DB_MAX_BACKOFF": "60.0",
        "MCP_TRANSPORT": "stdio"
      }
    }
  }
}
```

## Important Notes

### Path Configuration

**CRITICAL:** Update the `--directory` path to match your installation:

```json
"args": [
  "--directory",
  "/YOUR/ACTUAL/PATH/TO/mcp-teradata",  // ← Change this!
  "run",
  "python",
  "-m",
  "teradata_mcp.server_dynamic"
]
```

### Security Notes

1. **Never commit credentials** to version control
2. **Store DATABASE_URI securely** - consider using environment variables
3. **Use OAuth** in production environments
4. **Restrict database user permissions** to minimum required

### Troubleshooting Common Issues

#### Issue 1: "No such file or directory"

**Problem:**
```
error: Failed to spawn: `teradata-mcp`
  Caused by: No such file or directory (os error 2)
```

**Solution:**
Make sure you're using the correct module path format:
```json
"args": [
  "--directory",
  "/path/to/mcp-teradata",
  "run",
  "python",           // ← Important!
  "-m",               // ← Important!
  "teradata_mcp.server_dynamic"  // ← Use dot notation, not hyphen
]
```

#### Issue 2: "Connection refused"

**Problem:** Server starts but can't connect to database

**Solution:**
- Verify `DATABASE_URI` is correct
- Check network connectivity to Teradata server
- Ensure database user has proper permissions
- Check firewall rules

#### Issue 3: "Module not found"

**Problem:**
```
ModuleNotFoundError: No module named 'teradata_mcp'
```

**Solution:**
```bash
# Make sure dependencies are installed
cd /path/to/mcp-teradata
uv pip install -e .
```

#### Issue 4: Tools not appearing

**Problem:** Claude Desktop connects but no tools visible

**Solution:**
- Check server logs in Claude Desktop (View → Developer → Server Logs)
- Verify `TOOLS_MODE` environment variable is set correctly
- Try restarting Claude Desktop
- Check if server is initializing properly

## Testing Your Configuration

### Step 1: Validate JSON Syntax

Use a JSON validator or:
```bash
cat ~/Library/Application\ Support/Claude/claude_desktop_config.json | python -m json.tool
```

### Step 2: Test Server Manually

```bash
cd /Users/naotar/Workfiles/MCP/mcp-teradata
export DATABASE_URI="your-connection-string"
export TOOLS_MODE="search_only"
uv run python -m teradata_mcp.server_dynamic
```

Should see:
```
================================================================================
Teradata MCP Server - Tools-as-Code Pattern (EXPERIMENTAL)
================================================================================
Tools Mode: search_only

Starting MCP server on stdin/stdout
```

### Step 3: Check Claude Desktop Logs

1. Open Claude Desktop
2. View → Developer → Server Logs
3. Look for:
   - ✅ `[teradata] [info] Server started and connected successfully`
   - ❌ `[teradata] [error]` messages (indicates issues)

### Step 4: Test Tool Discovery

In Claude Desktop, try:
```
Can you search for available database tools?
```

Claude should use `search_tool` to discover tools.

## Comparison: Original vs Dynamic Server

### Original Server (server.py)

**Pros:**
- ✅ Stable and tested
- ✅ All tools immediately visible
- ✅ Simple configuration

**Configuration:**
```json
"args": ["--directory", "/path", "run", "teradata-mcp"]
```

### Dynamic Server (server_dynamic.py)

**Pros:**
- ✅ 98.7% token reduction
- ✅ Progressive tool discovery
- ✅ Experimental features

**Configuration:**
```json
"args": ["--directory", "/path", "run", "python", "-m", "teradata_mcp.server_dynamic"]
```

## Multiple Server Configurations

You can configure both versions side-by-side:

```json
{
  "mcpServers": {
    "teradata-stable": {
      "command": "uv",
      "args": [
        "--directory",
        "/Users/naotar/Workfiles/MCP/mcp-teradata",
        "run",
        "teradata-mcp"
      ],
      "env": {
        "DATABASE_URI": "teradatasql://user:pass@host/database"
      }
    },
    "teradata-experimental": {
      "command": "uv",
      "args": [
        "--directory",
        "/Users/naotar/Workfiles/MCP/mcp-teradata",
        "run",
        "python",
        "-m",
        "teradata_mcp.server_dynamic"
      ],
      "env": {
        "DATABASE_URI": "teradatasql://user:pass@host/database",
        "TOOLS_MODE": "search_only"
      }
    }
  }
}
```

Claude Desktop will show both servers and you can choose which to use.

## Recommended Configuration (Getting Started)

For first-time setup, use the **original server** (stable):

```json
{
  "mcpServers": {
    "teradata": {
      "command": "uv",
      "args": [
        "--directory",
        "/Users/naotar/Workfiles/MCP/mcp-teradata",
        "run",
        "teradata-mcp"
      ],
      "env": {
        "DATABASE_URI": "teradatasql://YOUR_USER:YOUR_PASS@YOUR_HOST/YOUR_DB"
      }
    }
  }
}
```

Once comfortable, try the **experimental dynamic server**:

```json
{
  "mcpServers": {
    "teradata": {
      "command": "uv",
      "args": [
        "--directory",
        "/Users/naotar/Workfiles/MCP/mcp-teradata",
        "run",
        "python",
        "-m",
        "teradata_mcp.server_dynamic"
      ],
      "env": {
        "DATABASE_URI": "teradatasql://YOUR_USER:YOUR_PASS@YOUR_HOST/YOUR_DB",
        "TOOLS_MODE": "search_only"
      }
    }
  }
}
```

## Getting Help

If you encounter issues:

1. **Check Server Logs** in Claude Desktop (View → Developer → Server Logs)
2. **Test manually** from command line first
3. **Verify paths** in configuration match your installation
4. **Check DATABASE_URI** format and credentials
5. **Open an issue** on GitHub with:
   - Configuration (redact credentials!)
   - Error messages from logs
   - Output of manual testing

## Related Documentation

- [Tools-as-Code Pattern](TOOLS_AS_CODE.md) - Architecture details
- [Connection Flow](CONNECTION_FLOW.md) - How connections are shared
- [Experiment README](../EXPERIMENT_README.md) - Overview of experimental features
