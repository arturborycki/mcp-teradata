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

- `list_objects`
   - Lists objects in a database
   - Input:
     - `db_name` (string): Database name
   - Returns: List of database objects under provided or user defaul database

- `show_tables`
   - Show detailed information about a database tables
   - Input:
    - `table_name` (string): Name of the table
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
        "DATABASE_URI": "teradata://user:passwd@host",
        "KEYCLOAK_SERVICE_URL": "https://KEYCLOAK_FQDN/realms/USER_REALM/.well-known/openid-configuration",
        "KEYCLOAK_CLIENT_ID": "KEYCLOAK_CLIENT_ID"
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

## Usage as API
Make sure uvicorn and dependencies are installed, before running 
```
uv run uvicorn teradata_mcp.http_api:app --host 0.0.0.0 --port 9999 --log-level debug --env-file .env --reload
```

## Building

UV:

```bash
uv build
```

## License

This MCP server is licensed under the MIT License. This means you are free to use, modify, and distribute the software, subject to the terms and conditions of the MIT License. For more details, please see the LICENSE file in the project repository.