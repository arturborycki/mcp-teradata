# Connection Sharing in Tools-as-Code Pattern

## Overview

The Teradata database connection is shared across all MCP tool calls through a **singleton pattern** using global state and context passing. This ensures efficient connection pooling and retry logic.

## Connection Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. Server Startup (server_dynamic.py)                          │
│    - initialize_database() creates TeradataConnectionManager    │
│    - Connection manager stored in global _connection_manager    │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│ 2. Initialize Dynamic Tools (fnc_tools_dynamic.py)             │
│    - initialize_dynamic_tools(_connection_manager, _db)         │
│    - Stores connection manager in module-level globals:         │
│      • _connection_manager (TeradataConnectionManager instance) │
│      • _db (database name)                                      │
│      • _tool_executor (ToolExecutor instance)                   │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│ 3. Agent Calls Tool (e.g., "query")                            │
│    - MCP receives tool call request                             │
│    - Routes to handle_dynamic_tool_call(name, arguments)        │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│ 4. Create Tool Context (fnc_tools_dynamic.py)                  │
│    context = ToolContext(                                       │
│        connection_manager=_connection_manager,  ← From globals  │
│        db_name=_db,                                             │
│        oauth_token=None,                                        │
│        user_id=None                                             │
│    )                                                            │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│ 5. Execute Tool (tools/executor.py)                            │
│    - ToolExecutor.execute_tool(name, arguments, context)        │
│    - Dynamically loads tool class (e.g., QueryTool)            │
│    - Passes context to tool.execute()                           │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│ 6. Tool Accesses Connection (e.g., tools/database/query.py)    │
│    async def execute(self, input_data, context):                │
│        connection_manager = context.get('connection_manager')   │
│        tdconn = await connection_manager.ensure_connection()    │
│        cur = tdconn.cursor()                                    │
│        rows = cur.execute(query)                                │
└─────────────────────────────────────────────────────────────────┘
```

## Key Components

### 1. TeradataConnectionManager (connection_manager.py)

**Purpose:** Manages a single Teradata connection with automatic retry logic.

```python
class TeradataConnectionManager:
    def __init__(self, database_url, db_name, max_retries=3, ...):
        self._database_url = database_url
        self._connection = None
        self._max_retries = max_retries

    async def ensure_connection(self):
        """Get healthy connection, reconnect if needed."""
        if not self._connection or not self._is_connection_healthy():
            await self._connect()
        return self._connection
```

**Features:**
- Single connection instance per server
- Automatic health checks
- Exponential backoff retry logic
- Connection state management

### 2. Global State (fnc_tools_dynamic.py)

**Module-level globals store the shared connection:**

```python
# Global variables - initialized once at server startup
_connection_manager = None  # TeradataConnectionManager instance
_db = ""                    # Database name
_tool_executor = None       # ToolExecutor instance

def initialize_dynamic_tools(connection_manager, db: str):
    """Called once during server initialization."""
    global _connection_manager, _db, _tool_executor
    _connection_manager = connection_manager
    _db = db
    _tool_executor = ToolExecutor(tools_dir)
```

### 3. ToolContext (tools/base.py)

**Carries connection to each tool execution:**

```python
class ToolContext(BaseModel):
    """Context passed to tool execution."""
    connection_manager: Any      # TeradataConnectionManager
    db_name: str
    oauth_token: Optional[str]
    user_id: Optional[str]
```

### 4. Tool Execution Flow (fnc_tools_dynamic.py)

```python
async def handle_dynamic_tool_call(name: str, arguments: dict):
    """Handle tool execution with shared connection."""

    # Create context with global connection manager
    context = ToolContext(
        connection_manager=_connection_manager,  # ← Shared connection
        db_name=_db,
        oauth_token=None,
        user_id=None
    )

    # Execute tool with context
    result = await _tool_executor.execute_tool(
        tool_name=name,
        arguments=arguments,
        context=context  # ← Context includes connection
    )

    return result
```

### 5. Individual Tools (e.g., tools/database/query.py)

**Each tool receives connection via context:**

```python
class QueryTool(ToolBase):
    @with_connection_retry()
    async def execute(self, input_data, context: Dict[str, Any]):
        # Extract connection manager from context
        connection_manager = context.get('connection_manager')

        # Get connection (reuses existing or reconnects)
        tdconn = await connection_manager.ensure_connection()

        # Use connection
        cur = tdconn.cursor()
        rows = cur.execute(input_data.query)

        return QueryOutput(results=rows.fetchall())
```

## Connection Lifecycle

### Initialization (Once)

```
Server Start
    ↓
Create TeradataConnectionManager (connection_manager.py)
    ↓
Store in global _connection_manager (fnc_tools_dynamic.py)
    ↓
Connection Ready for All Tools
```

### Per Tool Call (Many Times)

```
Agent Calls Tool
    ↓
handle_dynamic_tool_call() creates ToolContext
    ↓
Context contains _connection_manager reference
    ↓
Tool calls context.get('connection_manager')
    ↓
Tool calls connection_manager.ensure_connection()
    ↓
Connection manager returns healthy connection
    ↓
Tool executes query
    ↓
Connection stays open for next tool call
```

## Benefits of This Approach

### 1. Single Connection Instance
- **One connection** shared across all tool calls
- **No connection overhead** per tool call
- **Connection pooling** at manager level

### 2. Automatic Recovery
- Connection manager detects dead connections
- Automatically reconnects with retry logic
- Tools don't handle connection errors directly

### 3. Clean Separation
- Tools focus on business logic
- Connection management isolated in manager
- Context pattern allows dependency injection

### 4. Type Safety
- ToolContext ensures connection is passed
- Pydantic validation at context creation
- Type hints throughout the flow

## Example: Multiple Tools Sharing Connection

```python
# Tool Call 1: list_db
context = ToolContext(connection_manager=_connection_manager, db_name="db1")
await ListDbTool().execute(input1, context)
# Uses connection, leaves it open

# Tool Call 2: query
context = ToolContext(connection_manager=_connection_manager, db_name="db1")
await QueryTool().execute(input2, context)
# Reuses same connection from connection_manager

# Tool Call 3: list_tables
context = ToolContext(connection_manager=_connection_manager, db_name="db1")
await ListTablesTool().execute(input3, context)
# Still using same connection
```

**Result:** All three tools use the **same Teradata connection** managed by the **same TeradataConnectionManager** instance.

## Connection Manager Features

### Health Checking

```python
def _is_connection_healthy(self) -> bool:
    """Check if connection is alive."""
    try:
        if not self._connection:
            return False
        cur = self._connection.cursor()
        cur.execute("SELECT 1")
        return True
    except:
        return False
```

### Automatic Reconnection

```python
async def ensure_connection(self):
    """Ensure we have a healthy connection."""
    if not self._is_connection_healthy():
        logger.info("Connection unhealthy, reconnecting...")
        await self._connect()
    return self._connection
```

### Retry Logic with Backoff

```python
@with_connection_retry()
async def execute(self, input_data, context):
    """Decorator provides retry logic."""
    # If connection fails, decorator retries with exponential backoff
    # TeradataConnectionManager.ensure_connection() is called again
    # Up to max_retries attempts
```

## Thread Safety Considerations

**Current Implementation:**
- Single-threaded async/await model
- No concurrent tool execution
- Connection manager state is safe

**Future Enhancement:**
- If adding concurrent tool execution, use:
  - `asyncio.Lock()` for connection manager
  - Connection pool instead of single connection
  - Per-request connection from pool

## Debugging Connection Issues

### Enable Debug Logging

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Check Connection State

```python
# Add to tool execute method:
logger.debug(f"Connection manager: {connection_manager}")
logger.debug(f"Connection health: {connection_manager._is_connection_healthy()}")
```

### Monitor Connection Usage

```python
# In connection_manager.py:
logger.info(f"Connection used by: {tool_name}")
logger.info(f"Connection state: {self._connection}")
```

## Summary

**Connection sharing works through:**

1. ✅ **Single TeradataConnectionManager** instance created at server startup
2. ✅ **Global state** stores connection manager reference
3. ✅ **ToolContext** passes connection manager to each tool
4. ✅ **Tools extract** connection manager from context
5. ✅ **ensure_connection()** returns the same healthy connection
6. ✅ **Retry logic** handles connection failures transparently

**All tools share the same connection instance, managed centrally by TeradataConnectionManager.**
