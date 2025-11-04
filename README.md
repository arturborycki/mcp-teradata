# Teradata MCP Server with OAuth 2.1 Authentication

## Overview
A Model Context Protocol (MCP) server implementation that provides secure database interaction and business intelligence capabilities through Teradata. This server enables running SQL queries, analyzing business data, and workload management with enterprise-grade OAuth 2.1 authentication.

## 🔐 Security Features

- **OAuth 2.1 Authentication** with Keycloak integration
- **JWT Token Validation** using JWKS endpoints
- **Scope-based Authorization** for fine-grained access control
- **Protected Resource Metadata** (RFC 9728 compliant)
- **Token Introspection** support for opaque tokens
- **Production-ready** connection resilience and error handling
- **Automatic Connection Retry** for improved reliability

## Components

### Tools
The server offers comprehensive database and workload management tools:

#### Query Tools
- `query`
   - Execute SELECT queries to read data from the database
   - **Required Scopes:** `teradata:query`, `teradata:read`
   - Input:
     - `query` (string): The SELECT SQL query to execute
   - Returns: Query results as array of objects

#### Schema Tools
- `list_db`
   - Lists all databases in the Teradata system
   - **Required Scopes:** `teradata:read`
   - Returns: List of databases

- `list_tables`
   - Lists objects in a database
   - **Required Scopes:** `teradata:read`
   - Input:
     - `db_name` (string): Database name
   - Returns: List of database objects under provided or user default database

- `show_tables_details`
   - Show detailed information about a database tables
   - **Required Scopes:** `teradata:read`
   - Input:
    - `table_name` (string): Name of the table
    - `db_name` (string): Name of the database
   - Returns: Array of column names and data types

#### Analysis Tools
- `list_missing_values`
    - Lists the top features with missing values in a table
    - **Required Scopes:** `teradata:read`
- `list_negative_values`
    - Lists how many features have negative values in a table
    - **Required Scopes:** `teradata:read`
- `list_distinct_values`
    - Lists how many distinct categories are there for column in the table
    - **Required Scopes:** `teradata:read`
- `standard_deviation`
    -  What is the mean and standard deviation for column in table?
    - **Required Scopes:** `teradata:read`

## 🚀 Quick Start

### 1. Basic Setup (No Authentication)

```bash
# Clone the repository
git clone https://github.com/arturborycki/mcp-teradata.git
cd mcp-teradata

# Install dependencies
uv install

# Run with database connection
uv run teradata-mcp "teradatasql://user:password@host/database"
```

### 2. OAuth-Enabled Setup

```bash
# Copy environment configuration
cp .env.example .env

# Edit .env with your OAuth settings
OAUTH_ENABLED=true
KEYCLOAK_URL=https://your-keycloak.com
KEYCLOAK_REALM=teradata-realm
KEYCLOAK_CLIENT_ID=teradata-mcp
KEYCLOAK_CLIENT_SECRET=your-secret
OAUTH_RESOURCE_SERVER_URL=https://your-mcp-server.com

# Run with OAuth
uv run teradata-mcp "teradatasql://user:password@host/database"
```

### Configuration

### Database Connection
```bash
DATABASE_URI=teradatasql://username:password@hostname/database
```

### Connection Retry Settings
```bash
# Number of retry attempts for database connections (default: 1)
TOOL_RETRY_MAX_ATTEMPTS=1

# Delay between retry attempts in seconds (default: 1.0)  
TOOL_RETRY_DELAY_SECONDS=1.0
```

### OAuth 2.1 Settings
```bash
# Enable OAuth authentication
OAUTH_ENABLED=true

# Keycloak configuration
KEYCLOAK_URL=https://keycloak.example.com
KEYCLOAK_REALM=teradata-realm  
KEYCLOAK_CLIENT_ID=teradata-mcp
KEYCLOAK_CLIENT_SECRET=your-client-secret

# Resource server identification
OAUTH_RESOURCE_SERVER_URL=https://your-mcp-server.com

# Optional: Required scopes
OAUTH_REQUIRED_SCOPES=teradata:read,teradata:query

# Security settings
OAUTH_VALIDATE_AUDIENCE=true
OAUTH_VALIDATE_SCOPES=true
OAUTH_REQUIRE_HTTPS=true
```

### Supported OAuth Scopes
- `teradata:read` - Read access to database resources
- `teradata:write` - Write access to database resources  
- `teradata:query` - Execute SQL queries
- `teradata:admin` - Administrative access (TDWM, user management)
- `teradata:schema` - Schema management operations

### Transport Compatibility

OAuth 2.1 authentication is supported across all MCP transport methods:

| Transport | OAuth Support | Discovery Endpoints | Notes |
|-----------|---------------|-------------------|-------|
| **SSE** | ✅ Full Support | ✅ Available | OAuth endpoints integrated into Starlette app |
| **Streamable HTTP** | ✅ Full Support | ✅ Available | OAuth endpoints via FastMCP FastAPI integration |
| **Stdio** | ➖ N/A | ➖ N/A | No HTTP endpoints, authentication via environment |

**Discovery Endpoints Available:**
- `/.well-known/oauth-protected-resource` - Protected resource metadata (RFC 9728)
- `/.well-known/mcp-server-info` - MCP server capabilities and OAuth configuration
- `/health` - Health check with OAuth status

**Transport Selection:**
```bash
# SSE (Server-Sent Events) - Recommended for web applications
export MCP_TRANSPORT=sse
export MCP_HOST=0.0.0.0
export MCP_PORT=8000

# Streamable HTTP - Recommended for API integrations  
export MCP_TRANSPORT=streamable-http
export MCP_HOST=0.0.0.0
export MCP_PORT=8000
export MCP_PATH=/mcp/

# Stdio - For command-line clients (Claude Desktop)
export MCP_TRANSPORT=stdio
```

## 🐳 Docker Deployment

### Without OAuth (Development)
```bash
docker-compose up -d
```

### With OAuth (Production)
```bash
# Edit environment variables in docker-compose.oauth.yml
docker-compose -f docker-compose.oauth.yml up -d
```

### With Keycloak (Testing)
```bash
# Includes Keycloak server for testing
docker-compose -f docker-compose.oauth.yml up keycloak mcp-teradata
```

## 🔑 Keycloak Setup

### Automated Setup
Use the provided script to automatically configure Keycloak:

```bash
# For local development
./scripts/setup-keycloak.sh http://localhost:8080 admin admin

# For remote Keycloak
./scripts/setup-keycloak.sh https://your-keycloak.com admin-user admin-pass
```

### Manual Setup
See the comprehensive guide in [`docs/OAUTH.md`](docs/OAUTH.md) for detailed Keycloak configuration instructions.

## 🧪 Testing OAuth

Test your OAuth configuration:

```bash
# Run OAuth tests
./scripts/test-oauth.py

# Test with custom settings
./scripts/test-oauth.py --keycloak-url https://your-keycloak.com --realm your-realm
```

## 📋 API Endpoints

When OAuth is enabled, the server exposes discovery endpoints:

- `/.well-known/oauth-protected-resource` - Protected resource metadata (RFC 9728)
- `/.well-known/mcp-server-info` - MCP server capabilities and OAuth info
- `/health` - Health check with OAuth status

## Usage with Claude Desktop

### Basic Configuration
```json
{
  "mcpServers": {
    "teradata": {
      "command": "uv",
      "args": [
        "--directory",
        "/Users/MCP/mcp-teradata",
        "run",
        "teradata-mcp"
      ],
      "env": {
        "DATABASE_URI": "teradatasql://user:passwd@host/database"
      }
    }
  }
}
```

### OAuth-Enabled Configuration
```json
{
  "mcpServers": {
    "teradata": {
      "command": "uv", 
      "args": [
        "--directory",
        "/Users/MCP/mcp-teradata",
        "run",
        "teradata-mcp"
      ],
      "env": {
        "DATABASE_URI": "teradatasql://user:passwd@host/database",
        "OAUTH_ENABLED": "true",
        "KEYCLOAK_URL": "https://your-keycloak.com",
        "KEYCLOAK_REALM": "teradata-realm",
        "KEYCLOAK_CLIENT_ID": "teradata-mcp",
        "KEYCLOAK_CLIENT_SECRET": "your-secret",
        "OAUTH_RESOURCE_SERVER_URL": "https://your-server.com"
      }
    }
  }
}
```

```bash
# Add the server to your claude_desktop_config.json
{
  "mcpServers": {
    "teradata": {
      "command": "uv",
      "args": [
        "--directory",
        "/Users/MCP/mcp-teradata",
        "run",
        "teradata-mcp"
      ],
      "env": {
        "DATABASE_URI": "teradata://user:passwd@host"
      }
    }
  }
}
```
## Usage as API container
Make sure to edit docker-compose.yml and update environment variable
```
docker compose build
docker compose up
```


## 🔧 Building

```bash
uv build
```

## 📚 Documentation

- **[OAuth 2.1 Guide](docs/OAUTH.md)** - Comprehensive OAuth setup and usage
- **[Keycloak Configuration](scripts/setup-keycloak.sh)** - Automated Keycloak setup
- **[Environment Variables](.env.example)** - Configuration reference

## 🔒 Security Best Practices

1. **Use HTTPS** in production (`OAUTH_REQUIRE_HTTPS=true`)
2. **Secure client secrets** using environment variables or secret management
3. **Implement proper token refresh** for long-running applications
4. **Follow principle of least privilege** when assigning scopes
5. **Regularly audit** user permissions and access logs

## 🐛 Troubleshooting

### Common Issues

**OAuth authentication fails:**
```bash
# Test Keycloak connectivity
curl https://your-keycloak.com/auth/realms/master/.well-known/openid-configuration

# Check server health
curl https://your-mcp-server.com/health
```

**Database connection issues:**
- Verify `DATABASE_URI` format: `teradatasql://user:pass@host/database`
- Check network connectivity to Teradata server
- Ensure database credentials are correct
- Connection issues are automatically retried once by default

**Connection retry configuration:**
- Set `TOOL_RETRY_MAX_ATTEMPTS` to control retry behavior (0 = no retries)
- Set `TOOL_RETRY_DELAY_SECONDS` to control delay between retries
- Monitor logs for retry attempt messages

**Permission denied errors:**
- Verify user has required OAuth scopes
- Check Keycloak role assignments
- Review scope mappings in client configuration

### Debug Mode

Enable debug logging:
```bash
export LOG_LEVEL=DEBUG
export OAUTH_ENABLED=true
uv run teradata-mcp "teradatasql://user:pass@host/db"
```

## 🤝 Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This MCP server is licensed under the MIT License. This means you are free to use, modify, and distribute the software, subject to the terms and conditions of the MIT License. For more details, please see the LICENSE file in the project repository.

## 🙏 Acknowledgments

- [Model Context Protocol](https://modelcontextprotocol.io/) specification
- [Keycloak](https://www.keycloak.org/) for OAuth 2.1 implementation
- [Teradata](https://www.teradata.com/) for the database platform
- [FastMCP](https://github.com/modelcontextprotocol/python-sdk) for the MCP server framework