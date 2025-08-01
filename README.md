# Teradata MCP Server

## Overview
A Model Context Protocol (MCP) server implementation that provides database interaction and business intelligence capabilities through Teradata. This server enables running SQL queries, analyzing business data

## Components

### Tools
The server offers six core tools:

#### Query Tools
- `query`
   - Execute SELECT queries to read data from the database
   - Input:
     - `query` (string): The SELECT SQL query to execute
   - Returns: Query results as array of objects

#### Schema Tools
- `list_db`
   - Lists all databases in the Teradata system
   - Returns: List of databases

- `list_tables`
   - Lists objects in a database
   - Input:
     - `db_name` (string): Database name
   - Returns: List of database objects under provided or user defaul database

- `show_tables_details`
   - Show detailed information about a database tables
   - Input:
    - `table_name` (string): Name of the table
    - `db_name` (string): Name of the database
   - Returns: Array of column names and data types

#### Analysis Tools
- `list_missing_values`
    - Lists the top features with missing values in a table
- `list_negative_values`
    - Lists how many features have negative values in a table
- `list_distinct_values`
    - Lists how many distinct categories are there for column in the table
- `standard_deviation`
    -  What is the mean and standard deviation for column in table?

## Usage with Claude Desktop

### uv

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

## Building

UV:

```bash
uv build
```

## License

This MCP server is licensed under the MIT License. This means you are free to use, modify, and distribute the software, subject to the terms and conditions of the MIT License. For more details, please see the LICENSE file in the project repository.

## Keycloak Authentication Setup

### 1. Keycloak Configuration
- Create a new realm for MCP
- Create a client for the Teradata MCP server
- Configure client roles and user roles
- Set up proper redirect URIs

### 2. Environment Variables
```bash
KEYCLOAK_ENABLED=true
KEYCLOAK_SERVER_URL=https://your-keycloak-server.com
KEYCLOAK_REALM=mcp-realm
KEYCLOAK_CLIENT_ID=teradata-mcp-client
KEYCLOAK_CLIENT_SECRET=your-client-secret
```