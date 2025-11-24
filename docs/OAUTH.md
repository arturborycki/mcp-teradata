# OAuth 2.1 Authentication for Teradata MCP Server

## Overview

The Teradata MCP Server supports OAuth 2.1 authentication with Keycloak integration across all transport methods (SSE, Streamable HTTP, and Stdio), providing enterprise-grade security for database operations. This implementation follows RFC 9728 (OAuth 2.1 Protected Resource Metadata) and includes support for:

- JWT token validation with JWKS
- Token introspection for opaque tokens
- Scope-based authorization
- Protected resource metadata discovery
- Keycloak realm integration
- Multi-transport OAuth endpoint integration
- Automatic connection retry with OAuth authorization checks

## Transport Compatibility

OAuth 2.1 is fully supported across all MCP transport methods:

### SSE Transport (Server-Sent Events)
- **OAuth Endpoints**: ✅ Integrated into Starlette app
- **Discovery**: ✅ All endpoints available
- **Use Case**: Web applications, real-time dashboards
- **Port**: Configurable via `MCP_PORT` (default: 8000)

### Streamable HTTP Transport
- **OAuth Endpoints**: ✅ Integrated into FastMCP/FastAPI app
- **Discovery**: ✅ All endpoints available  
- **Use Case**: REST API integrations, microservices
- **Path**: Configurable via `MCP_PATH` (default: /mcp/)

### Stdio Transport
- **OAuth Endpoints**: ➖ Not applicable (no HTTP)
- **Authentication**: Token can be passed via environment variables
- **Use Case**: Command-line clients (Claude Desktop), CI/CD pipelines

## Configuration

OAuth authentication is configured through environment variables:

### Required Environment Variables (when OAuth is enabled)

```bash
# Enable OAuth authentication
OAUTH_ENABLED=true

# Keycloak server configuration
KEYCLOAK_URL=https://your-keycloak-server.com
KEYCLOAK_REALM=your-realm
KEYCLOAK_CLIENT_ID=teradata-mcp

# Resource server identification
OAUTH_RESOURCE_SERVER_URL=https://your-mcp-server.com
```

### Optional Environment Variables

```bash
# Client secret (for confidential clients)
KEYCLOAK_CLIENT_SECRET=your-client-secret

# Required scopes (comma-separated)
OAUTH_REQUIRED_SCOPES=teradata:read,teradata:query

# Security settings
OAUTH_VALIDATE_AUDIENCE=true
OAUTH_VALIDATE_SCOPES=true
OAUTH_REQUIRE_HTTPS=true

# Custom endpoints (auto-generated if not provided)
OAUTH_TOKEN_VALIDATION_ENDPOINT=https://keycloak.example.com/auth/realms/your-realm/protocol/openid-connect/token/introspect
OAUTH_JWKS_ENDPOINT=https://keycloak.example.com/auth/realms/your-realm/protocol/openid-connect/certs
```

## Scopes and Permissions

The system defines the following scopes for Teradata operations:

### Database Access Scopes

- **`teradata:read`** - Read access to database resources (list databases, tables, view data)
- **`teradata:write`** - Write access to database resources (insert, update, delete)
- **`teradata:query`** - Execute SQL queries
- **`teradata:admin`** - Administrative access (schema management, user management)
- **`teradata:schema`** - Schema management operations

### Tool-Specific Authorization

Different MCP tools require different scopes:

| Tool | Required Scopes | Description |
|------|-----------------|-------------|
| `query` | `teradata:query`, `teradata:read` | Execute SQL queries |
| `list_db` | `teradata:read` | List databases |
| `list_tables` | `teradata:read` | List tables in database |
| `show_tables_details` | `teradata:read` | Show table details |
| `mcp_tdwm_*` (monitoring) | `teradata:read` | TDWM monitoring tools |
| `mcp_tdwm_*` (admin) | `teradata:admin` | TDWM administrative tools |

## Keycloak Configuration

### 1. Create a Realm

1. Access your Keycloak admin console
2. Create a new realm (e.g., `teradata-realm`)
3. Configure realm settings as needed

### 2. Create a Client

```json
{
  "clientId": "teradata-mcp",
  "name": "Teradata MCP Server",
  "description": "Teradata Model Context Protocol Server",
  "enabled": true,
  "clientAuthenticatorType": "client-secret",
  "redirectUris": [
    "http://localhost:8000/*",
    "https://your-mcp-server.com/*"
  ],
  "webOrigins": [
    "http://localhost:8000",
    "https://your-mcp-server.com"
  ],
  "protocol": "openid-connect",
  "access": {
    "view": true,
    "configure": true,
    "manage": true
  },
  "attributes": {
    "access.token.lifespan": "300",
    "pkce.code.challenge.method": "S256"
  }
}
```

### 3. Create Client Scopes

Create the following client scopes in Keycloak:

```json
[
  {
    "name": "teradata:read",
    "description": "Read access to Teradata resources",
    "protocol": "openid-connect",
    "include.in.token.scope": true
  },
  {
    "name": "teradata:write", 
    "description": "Write access to Teradata resources",
    "protocol": "openid-connect",
    "include.in.token.scope": true
  },
  {
    "name": "teradata:query",
    "description": "Execute Teradata queries",
    "protocol": "openid-connect", 
    "include.in.token.scope": true
  },
  {
    "name": "teradata:admin",
    "description": "Administrative access to Teradata",
    "protocol": "openid-connect",
    "include.in.token.scope": true
  },
  {
    "name": "teradata:schema",
    "description": "Schema management access",
    "protocol": "openid-connect",
    "include.in.token.scope": true
  }
]
```

### 4. Assign Scopes to Client

1. Go to **Clients** → **teradata-mcp** → **Client Scopes**
2. Add the created scopes to **Assigned Default Client Scopes**

### 5. Create Roles (Optional)

Create realm or client roles for easier user management:

```json
[
  {
    "name": "teradata-user",
    "description": "Basic Teradata user with read and query access",
    "composite": false
  },
  {
    "name": "teradata-analyst", 
    "description": "Teradata analyst with advanced query capabilities",
    "composite": false
  },
  {
    "name": "teradata-admin",
    "description": "Teradata administrator with full access",
    "composite": false
  }
]
```

## Usage Examples

### 1. Client Credentials Flow (Service-to-Service)

```bash
# Get access token
TOKEN_RESPONSE=$(curl -X POST \
  "https://keycloak.example.com/auth/realms/teradata-realm/protocol/openid-connect/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=client_credentials" \
  -d "client_id=teradata-mcp" \
  -d "client_secret=your-client-secret" \
  -d "scope=teradata:read teradata:query")

ACCESS_TOKEN=$(echo $TOKEN_RESPONSE | jq -r .access_token)

# Use token to access MCP server
curl -X GET "https://your-mcp-server.com/.well-known/oauth-protected-resource" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

### 2. Authorization Code Flow with PKCE

```javascript
// Frontend JavaScript example
const authUrl = new URL('https://keycloak.example.com/auth/realms/teradata-realm/protocol/openid-connect/auth');
authUrl.searchParams.append('client_id', 'teradata-mcp');
authUrl.searchParams.append('response_type', 'code');
authUrl.searchParams.append('scope', 'openid teradata:read teradata:query');
authUrl.searchParams.append('redirect_uri', 'https://your-app.com/callback');
authUrl.searchParams.append('code_challenge', codeChallenge);
authUrl.searchParams.append('code_challenge_method', 'S256');

// Redirect user to authorization URL
window.location.href = authUrl.toString();
```

### 3. Using with MCP Client

```python
import asyncio
import aiohttp
from mcp import ClientSession, StdioServerParameters

async def main():
    # Get OAuth token first
    async with aiohttp.ClientSession() as session:
        token_data = {
            'grant_type': 'client_credentials',
            'client_id': 'teradata-mcp',
            'client_secret': 'your-client-secret',
            'scope': 'teradata:read teradata:query'
        }
        
        async with session.post(
            'https://keycloak.example.com/auth/realms/teradata-realm/protocol/openid-connect/token',
            data=token_data
        ) as resp:
            token_response = await resp.json()
            access_token = token_response['access_token']
    
    # Create MCP client with OAuth token
    server_params = StdioServerParameters(
        command="teradata-mcp",
        args=["teradatasql://user:pass@host/db"],
        env={
            "OAUTH_ENABLED": "true",
            "OAUTH_TOKEN": access_token  # Custom implementation
        }
    )
    
    async with ClientSession(server_params) as session:
        # Use MCP tools with OAuth authentication
        result = await session.call_tool("query", {"query": "SELECT * FROM DBC.DatabasesV"})
        print(result)

if __name__ == "__main__":
    asyncio.run(main())
```

## Discovery Endpoints

The server exposes several discovery endpoints:

### Protected Resource Metadata (RFC 9728)

```http
GET /.well-known/oauth-protected-resource
```

Returns metadata about the protected resource:

```json
{
  "resource": "https://your-mcp-server.com",
  "authorization_servers": ["https://keycloak.example.com/auth/realms/teradata-realm"],
  "scopes_supported": ["teradata:read", "teradata:write", "teradata:query", "teradata:admin"],
  "jwks_uri": "https://keycloak.example.com/auth/realms/teradata-realm/protocol/openid-connect/certs",
  "introspection_endpoint": "https://keycloak.example.com/auth/realms/teradata-realm/protocol/openid-connect/token/introspect"
}
```

### MCP Server Information

```http
GET /.well-known/mcp-server-info  
```

Returns information about MCP capabilities and OAuth configuration:

```json
{
  "name": "teradata-mcp",
  "version": "1.0.0",
  "capabilities": {
    "tools": true,
    "resources": true,
    "prompts": true
  },
  "authentication": {
    "oauth2": {
      "enabled": true,
      "authorization_server": "https://keycloak.example.com/auth/realms/teradata-realm",
      "scopes_supported": ["teradata:read", "teradata:write", "teradata:query"]
    }
  }
}
```

### Health Check

```http
GET /health
```

Returns server health status including OAuth configuration:

```json
{
  "status": "healthy",
  "oauth": {
    "enabled": true,
    "configured": true
  },
  "database": {
    "status": "connected"
  }
}
```

## Docker Deployment

### Basic Deployment (OAuth Disabled)

```yaml
version: "3.8"
services:
  mcp-teradata:
    image: teradata-mcp:latest
    environment:
      - OAUTH_ENABLED=false
      - DATABASE_URI=teradatasql://user:pass@host/db
    ports:
      - "8000:8000"
```

### OAuth-Enabled Deployment

```yaml
version: "3.8"
services:
  mcp-teradata:
    image: teradata-mcp:latest
    environment:
      - OAUTH_ENABLED=true
      - KEYCLOAK_URL=https://keycloak.example.com
      - KEYCLOAK_REALM=teradata-realm
      - KEYCLOAK_CLIENT_ID=teradata-mcp
      - KEYCLOAK_CLIENT_SECRET=${KEYCLOAK_CLIENT_SECRET}
      - OAUTH_RESOURCE_SERVER_URL=https://mcp.example.com
      - DATABASE_URI=teradatasql://user:pass@host/db
    ports:
      - "8000:8000"
```

### Development with Keycloak

Use the provided `docker-compose.oauth.yml` for development:

```bash
# Start with OAuth and Keycloak
docker-compose -f docker-compose.oauth.yml up

# Keycloak admin console: http://localhost:8080 (admin/admin)
# MCP server: http://localhost:8000
```

## Security Considerations

### Token Validation

- JWT tokens are validated using JWKS endpoint
- Token introspection is used as fallback for opaque tokens
- Audience validation ensures tokens are intended for this resource server
- Scope validation enforces fine-grained permissions

### HTTPS Requirements

- Production deployments should use HTTPS for all endpoints
- Set `OAUTH_REQUIRE_HTTPS=true` to enforce HTTPS validation
- Keycloak should be configured with proper TLS certificates

### Secret Management

- Store client secrets securely (environment variables, secret management systems)
- Use service accounts for service-to-service authentication
- Implement proper token refresh mechanisms

### Scope Management

- Follow principle of least privilege when assigning scopes
- Use roles in Keycloak to simplify user management
- Regularly audit user permissions and scopes

## Troubleshooting

### Common Issues

1. **Token validation fails**
   - Check JWKS endpoint accessibility
   - Verify token issuer matches configuration
   - Ensure clock synchronization between services

2. **Scope authorization errors**
   - Verify required scopes are assigned to client
   - Check user has necessary roles/permissions
   - Review scope mapping configuration

3. **Keycloak connectivity issues**
   - Test Keycloak endpoints manually
   - Check network connectivity and DNS resolution
   - Verify SSL certificates if using HTTPS

### Debug Mode

Enable debug logging to troubleshoot issues:

```bash
export PYTHONPATH=/app/src
export OAUTH_ENABLED=true
export LOG_LEVEL=DEBUG
python -m teradata_mcp.server
```

### Testing OAuth Flow

Use the health check endpoint to verify OAuth configuration:

```bash
curl -v https://your-mcp-server.com/health
```

Expected response for properly configured OAuth:

```json
{
  "status": "healthy",
  "oauth": {
    "enabled": true,
    "configured": true
  }
}
```
