# Teradata MCP Server

A Model Context Protocol (MCP) server for Teradata database with OAuth 2.1 authentication, multiple authentication mechanisms (TD2, LDAP, Kerberos), and interactive data visualization.

## Features

- **Multiple Auth Mechanisms** — TD2 (default), LDAP, Kerberos, JWT via Teradata `LOGMECH`
- **OAuth 2.1** with Keycloak integration, JWT validation, scope-based authorization
- **Protected Resource Metadata** (RFC 9728 compliant)
- **Interactive Visualization** — ECharts-based MCP App with 19 chart types
- **Connection Resilience** — automatic retry with exponential backoff
- **Non-blocking I/O** — all DB operations run via `asyncio.to_thread()`
- **Per-tool QueryBand** — audit trail for Teradata workload management

## Tools

### Query Tools
- **`query`** — Execute SQL queries, return plain tabular results
- **`visualize_query`** — Execute SQL and render interactive ECharts charts via MCP App

### Schema Tools
- **`list_db`** — List all databases
- **`list_tables`** — List tables/views in a database
- **`show_tables_details`** — Show column names and types for a table

### Analysis Tools
- **`list_missing_values`** — Columns with NULL value counts
- **`list_negative_values`** — Columns with negative value counts
- **`list_distinct_values`** — Distinct category counts per column
- **`standard_deviation`** — Mean and standard deviation for a column

### MCP App — Interactive Visualization

The `visualize_query` tool renders results as interactive charts in the MCP client.

| Category | Charts |
|----------|--------|
| Bar | Basic, Grouped, Stacked, Horizontal, Sorted, Waterfall, Rounded, Polar |
| Line | Basic, Smooth, Area, Stacked Area, Step |
| Pie | Pie, Doughnut, Rose / Nightingale |
| Scatter | Scatter, Bubble |
| Mixed | Bar + Line |

## Quick Start

### Installation

```bash
git clone https://github.com/arturborycki/mcp-teradata.git
cd mcp-teradata
uv sync
```

### Run with TD2 (Standard Authentication)

```bash
uv run teradata-mcp "teradatasql://user:password@host/database"
```

Or via environment variable:

```bash
export DATABASE_URI="teradatasql://user:password@host/database"
uv run teradata-mcp
```

## Configuration

### Claude Desktop

Add to your `claude_desktop_config.json`:

#### TD2 (Username/Password)

```json
{
  "mcpServers": {
    "teradata": {
      "command": "uv",
      "args": [
        "--directory", "/path/to/mcp-teradata",
        "run", "teradata-mcp"
      ],
      "env": {
        "DATABASE_URI": "teradatasql://user:password@host/database"
      }
    }
  }
}
```

#### LDAP Authentication

```json
{
  "mcpServers": {
    "teradata": {
      "command": "uv",
      "args": [
        "--directory", "/path/to/mcp-teradata",
        "run", "teradata-mcp"
      ],
      "env": {
        "DATABASE_URI": "teradatasql://@host/database",
        "DB_LOGMECH": "LDAP",
        "DB_LOGDATA": "authcid=ldap_user password=ldap_password"
      }
    }
  }
}
```

The `authcid` format depends on the LDAP directory:

| Directory | Format |
|-----------|--------|
| Active Directory (Simple Bind) | `authcid=user@domain.com` |
| Active Directory (DIGEST-MD5) | `authcid=DOMAIN\username` |
| OpenLDAP / Sun DS | `authcid=username` |

#### Kerberos Authentication

```json
{
  "mcpServers": {
    "teradata": {
      "command": "uv",
      "args": [
        "--directory", "/path/to/mcp-teradata",
        "run", "teradata-mcp"
      ],
      "env": {
        "DATABASE_URI": "teradatasql://@host/database",
        "DB_LOGMECH": "KRB5"
      }
    }
  }
}
```

#### OAuth-Enabled Configuration

```json
{
  "mcpServers": {
    "teradata": {
      "command": "uv",
      "args": [
        "--directory", "/path/to/mcp-teradata",
        "run", "teradata-mcp"
      ],
      "env": {
        "DATABASE_URI": "teradatasql://user:password@host/database",
        "OAUTH_ENABLED": "true",
        "KEYCLOAK_URL": "https://your-keycloak.example.com",
        "KEYCLOAK_REALM": "teradata-realm",
        "KEYCLOAK_CLIENT_ID": "teradata-mcp",
        "KEYCLOAK_CLIENT_SECRET": "your-secret",
        "OAUTH_RESOURCE_SERVER_URL": "https://your-mcp-server.example.com"
      }
    }
  }
}
```

### Environment Variables

#### Database Connection

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URI` | Teradata connection URL (`teradatasql://user:pass@host/db`) | — |
| `DB_LOGMECH` | Authentication mechanism: `TD2`, `LDAP`, `KRB5`, `TDNEGO`, `JWT` | `TD2` |
| `DB_LOGDATA` | LDAP/JWT credentials (e.g., `authcid=user password=pass`) | — |
| `DB_SSL_MODE` | TLS mode: `ALLOW`, `PREFER`, `REQUIRE`, `VERIFY-CA`, `VERIFY-FULL` | — |
| `DB_ENCRYPT_DATA` | Enable transport encryption | `true` |

#### Connection Resilience

| Variable | Description | Default |
|----------|-------------|---------|
| `DB_MAX_RETRIES` | Max reconnection attempts | `3` |
| `DB_INITIAL_BACKOFF` | Initial backoff delay (seconds) | `1.0` |
| `DB_MAX_BACKOFF` | Max backoff delay (seconds) | `30.0` |

#### MCP Transport

| Variable | Description | Default |
|----------|-------------|---------|
| `MCP_TRANSPORT` | Transport: `stdio`, `sse`, `streamable-http` | `stdio` |
| `MCP_HOST` | Bind address for HTTP transports | `localhost` |
| `MCP_PORT` | Port for HTTP transports | `8000` |
| `MCP_PATH` | Path for streamable-http | `/mcp/` |

#### OAuth 2.1

| Variable | Description | Default |
|----------|-------------|---------|
| `OAUTH_ENABLED` | Enable OAuth authentication | `false` |
| `KEYCLOAK_URL` | Keycloak server URL | — |
| `KEYCLOAK_REALM` | Keycloak realm name | — |
| `KEYCLOAK_CLIENT_ID` | OAuth client ID | — |
| `KEYCLOAK_CLIENT_SECRET` | OAuth client secret | — |
| `OAUTH_RESOURCE_SERVER_URL` | Resource server URL | — |
| `OAUTH_REQUIRED_SCOPES` | Required scopes (comma-separated) | — |
| `OAUTH_VALIDATE_AUDIENCE` | Validate token audience | `true` |
| `OAUTH_VALIDATE_SCOPES` | Validate token scopes | `true` |
| `OAUTH_REQUIRE_HTTPS` | Require HTTPS for OAuth URLs | `true` |
| `CORS_ALLOWED_ORIGINS` | CORS allowed origins | `*` |

### OAuth Scopes

| Scope | Description |
|-------|-------------|
| `teradata:read` | Read access to database resources |
| `teradata:write` | Write access to database resources |
| `teradata:query` | Execute SQL queries |
| `teradata:admin` | Administrative access |
| `teradata:schema` | Schema management operations |

### Transport Compatibility

| Transport | OAuth | Discovery Endpoints | Use Case |
|-----------|-------|-------------------|----------|
| **stdio** | N/A | N/A | Claude Desktop, CLI clients |
| **SSE** | Full | Available | Web applications |
| **Streamable HTTP** | Full | Available | API integrations |

Discovery endpoints (when OAuth enabled):
- `/.well-known/oauth-protected-resource` — RFC 9728 metadata
- `/.well-known/mcp-server-info` — MCP capabilities
- `/health` — Health check

## Docker Deployment

### Development

```bash
docker compose up -d
```

### With OAuth

```bash
docker compose -f docker-compose.oauth.yml up -d
```

### Build

```bash
uv build
```

## Troubleshooting

**Database connection issues:**
- Verify `DATABASE_URI` format: `teradatasql://user:pass@host/database`
- Check network connectivity to Teradata server
- For LDAP: ensure `DB_LOGMECH=LDAP` and `DB_LOGDATA` are set correctly
- Connection issues are automatically retried (configurable via `DB_MAX_RETRIES`)

**LDAP authentication fails:**
- Verify the Teradata server has LDAP configured in TDGSS
- Check `authcid` format matches your directory type
- Escape special characters in passwords (`@` → `\@`, spaces → use quotes)

**Permission denied errors:**
- Verify user has required OAuth scopes
- Check Keycloak role assignments
- `visualize_query` requires `teradata:query` scope (not just `teradata:read`)

**Debug logging:**
```bash
export LOG_LEVEL=DEBUG
uv run teradata-mcp
```

## License

MIT License. See [LICENSE](LICENSE) for details.

## Acknowledgments

- [Model Context Protocol](https://modelcontextprotocol.io/)
- [Keycloak](https://www.keycloak.org/)
- [Teradata](https://www.teradata.com/)
- [FastMCP](https://github.com/modelcontextprotocol/python-sdk)
