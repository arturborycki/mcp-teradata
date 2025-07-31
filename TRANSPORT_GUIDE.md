# MCP Transport Configuration

The Teradata MCP Server now supports multiple transport protocols through environment variable configuration, using both native MCP transports and fallback implementations.

## Transport Types

### 1. STDIO Transport (Default)
Standard input/output communication - ideal for command-line tools and MCP clients.

```bash
export MCP_TRANSPORT=stdio
export DATABASE_URI=teradatasql://user:passwd@host/db
python -m teradata_mcp.server
```

### 2. SSE Transport
Server-Sent Events using native MCP transport (falls back to FastAPI if not available).

```bash
export MCP_TRANSPORT=sse
export MCP_HOST=0.0.0.0
export MCP_PORT=8000
export DATABASE_URI=teradatasql://user:passwd@host/db
python -m teradata_mcp.server
```

### 3. Streamable HTTP Transport
Native MCP streamable HTTP transport (falls back to FastAPI if not available).

```bash
export MCP_TRANSPORT=streamable-http
export MCP_HOST=0.0.0.0
export MCP_PORT=8000
export MCP_PATH=/mcp/
export DATABASE_URI=teradatasql://user:passwd@host/db
python -m teradata_mcp.server
```

### 4. HTTP Transport (Legacy)
RESTful HTTP API using FastAPI - for backward compatibility and Flowise integration.

```bash
export MCP_TRANSPORT=http
export MCP_HOST=0.0.0.0
export MCP_PORT=8000
export DATABASE_URI=teradatasql://user:passwd@host/db
python -m teradata_mcp.server
```

## Docker Usage

### Using Native MCP SSE Transport
```yaml
version: "3.8"
services:
  mcp-teradata:
    build: .
    environment:
      - MCP_TRANSPORT=sse
      - MCP_HOST=0.0.0.0
      - MCP_PORT=8000
      - DATABASE_URI=teradatasql://user:passwd@host/db
    ports:
      - "8000:8000"
```

### Using Streamable HTTP Transport
```yaml
version: "3.8"
services:
  mcp-teradata:
    build: .
    environment:
      - MCP_TRANSPORT=streamable-http
      - MCP_HOST=0.0.0.0
      - MCP_PORT=8000
      - MCP_PATH=/mcp/
      - DATABASE_URI=teradatasql://user:passwd@host/db
    ports:
      - "8000:8000"
```

### With Authentication
```yaml
version: "3.8"
services:
  mcp-teradata:
    build: .
    environment:
      - MCP_TRANSPORT=sse
      - MCP_HOST=0.0.0.0
      - MCP_PORT=8000
      - DATABASE_URI=teradatasql://user:passwd@host/db
      - KEYCLOAK_ENABLED=true
      - KEYCLOAK_CLIENT_ID=mcp-teradata
      - KEYCLOAK_CLIENT_SECRET=your-secret
    ports:
      - "8000:8000"
```

## Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `MCP_TRANSPORT` | Transport type: stdio, http, sse | stdio | No |
| `MCP_HOST` | Host to bind to (for http/sse) | 0.0.0.0 | No |
| `MCP_PORT` | Port to bind to (for http/sse) | 8000 | No |
| `DATABASE_URI` | Teradata database connection string | - | Yes |
| `KEYCLOAK_ENABLED` | Enable Keycloak authentication | false | No |
| `KEYCLOAK_CLIENT_ID` | Keycloak client ID | mcp-teradata | No |
| `KEYCLOAK_CLIENT_SECRET` | Keycloak client secret | - | If auth enabled |

## Integration Examples

### Flowise Integration
For Flowise, use HTTP transport and configure your MCP node with:
- URL: `http://your-server:8000`
- Use `/mcp/tools` endpoint for tool discovery
- Use `/mcp/tools/call` for tool execution

### MCP Client Integration
For standard MCP clients, use SSE transport:
- URL: `http://your-server:8000/sse`
- Send JSON-RPC messages via POST requests
- Handle Server-Sent Events responses

### CLI Integration
For command-line tools, use stdio transport:
```bash
echo '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | python -m teradata_mcp.server
```

## Migration from http_api.py

If you were previously using the `http_api.py` directly with uvicorn, update your deployment:

**Before:**
```bash
uvicorn teradata_mcp.http_api:app --host 0.0.0.0 --port 8000
```

**After:**
```bash
export MCP_TRANSPORT=http
python -m teradata_mcp.server
```

This provides the same functionality but with a more flexible, configurable approach that can support multiple transports from a single codebase.
