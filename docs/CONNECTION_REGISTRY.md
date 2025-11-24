# Connection Registry Architecture

## Overview

The **Connection Registry** is an external, shareable connection management system that decouples database connections from module globals and enables tools to attach to connections at registration/discovery time rather than execution time.

This architectural pattern aligns with the **tools-as-code** vision where:
1. Server establishes connection(s) at startup
2. Tools discover existing connections when loaded
3. Tools attach to connections at registration time
4. Tools execute using pre-attached connections (no context needed)

## The Problem We're Solving

### Before: Context-Based Connection Passing

**Old Pattern:**
```python
# Server creates connection
connection_manager = TeradataConnectionManager(...)

# Tool receives connection at EXECUTION time via context
context = {"connection_manager": connection_manager, "db_name": "demo"}
result = await tool.execute(input_data, context)
```

**Issues:**
- ❌ Connection tied to module globals (`_connection_manager`)
- ❌ Connection passed at execution time (late binding)
- ❌ Difficult to swap connections at runtime
- ❌ Hard to test with mock connections
- ❌ Doesn't support connection pooling naturally
- ❌ Tools can't "discover" existing connections

### After: Registry-Based Connection Attachment

**New Pattern:**
```python
# 1. Server registers connection at startup
registry = ConnectionRegistry.get_instance()
await registry.register_connection("default", connection_manager)

# 2. Tool attaches to connection at REGISTRATION time
tool = QueryTool()
connection = registry.get_connection()
tool.attach_connection(connection)

# 3. Tool executes using attached connection (no context needed!)
result = await tool.execute(input_data)
```

**Benefits:**
- ✅ Connections externally shareable (not tied to modules)
- ✅ Connection attached at registration time (early binding)
- ✅ Easy to swap connections at runtime
- ✅ Simple to test with mock connections
- ✅ Supports multiple named connections
- ✅ Tools discover and attach to existing resources

## Architecture

### ConnectionRegistry Class

Located in: `src/teradata_mcp/connection_registry.py`

**Key Features:**
- **Singleton Pattern**: Global access via `ConnectionRegistry.get_instance()`
- **Named Connections**: Multiple connections with unique names (e.g., "default", "replica", "analytics")
- **Default Connection**: One connection marked as default for convenience
- **Runtime Management**: Register/remove connections dynamically
- **Thread-Safe**: Async locks for concurrent access
- **Health Monitoring**: Built-in health check methods
- **Metadata Tracking**: Store connection info for debugging

### Connection Resolution Priority

Tools now resolve connections using a **3-tier fallback** system:

```python
# Priority 1: Attached connection (preferred - tools-as-code pattern)
connection_manager = self._connection_manager

# Priority 2: Context parameter (backward compatible with old code)
if connection_manager is None and context:
    connection_manager = context.get('connection_manager')

# Priority 3: Registry default (global fallback)
if connection_manager is None:
    registry = ConnectionRegistry.get_instance()
    connection_manager = registry.get_connection()
```

This ensures:
- ✅ New pattern works (attached connections)
- ✅ Old code still works (context parameter)
- ✅ Graceful fallback (registry default)
- ✅ Zero breaking changes

## Implementation Guide

### 1. Server Startup (Register Connections)

**File:** `src/teradata_mcp/server_dynamic.py`

```python
from .connection_registry import ConnectionRegistry

async def initialize_database():
    # Create connection
    connection_manager = TeradataConnectionManager(
        database_url=database_url,
        db_name=db_name
    )
    await connection_manager.ensure_connection()

    # Register in external registry
    registry = ConnectionRegistry.get_instance()
    await registry.register_connection(
        "default",
        connection_manager,
        set_as_default=True,
        metadata={
            "database": db_name,
            "transport": "stdio"
        }
    )
    logger.info("Connection registered in ConnectionRegistry")
```

### 2. Tool Base Class (Support Attachment)

**File:** `src/teradata_mcp/tools/base.py`

```python
class ToolBase(ABC):
    def __init__(self):
        """Initialize tool with connection attachment support."""
        self._connection_manager = None

    def attach_connection(self, connection_manager):
        """Attach a connection manager to this tool instance."""
        self._connection_manager = connection_manager

    def get_connection_manager(self):
        """Get the attached connection manager."""
        return self._connection_manager
```

### 3. Tool Executor (Attach at Load Time)

**File:** `src/teradata_mcp/tools/executor.py`

```python
class ToolExecutor:
    def __init__(self, tools_dir: Optional[Path] = None):
        # Initialize with registry
        from ..connection_registry import ConnectionRegistry
        self._registry = ConnectionRegistry.get_instance()

    async def execute_tool(self, tool_name: str, arguments: Dict,
                          context: Optional[ToolContext] = None,
                          connection_name: Optional[str] = None):
        # Load tool
        tool_class = self.load_tool(tool_name)
        tool_instance = tool_class()

        # Attach connection from registry at REGISTRATION time
        if self._registry:
            if connection_name:
                # Use specific connection
                connection = self._registry.get_connection(connection_name)
            else:
                # Use default connection
                connection = self._registry.get_connection()

            if connection:
                tool_instance.attach_connection(connection)

        # Execute tool (connection already attached!)
        output = await tool_instance.execute(input_data, context)
        return output
```

### 4. Individual Tools (Use Attached Connection)

**File:** `src/teradata_mcp/tools/database/query.py`

```python
class QueryTool(ToolBase):
    async def execute(self, input_data: QueryInput,
                     context: Optional[Dict[str, Any]] = None):
        # Priority 1: Use attached connection
        connection_manager = self._connection_manager

        # Priority 2: Fallback to context (backward compatible)
        if connection_manager is None and context:
            connection_manager = context.get('connection_manager')

        # Priority 3: Fallback to registry
        if connection_manager is None:
            from ...connection_registry import ConnectionRegistry
            registry = ConnectionRegistry.get_instance()
            connection_manager = registry.get_connection()

        if not connection_manager:
            return QueryOutput(
                success=False,
                error="No connection available"
            )

        # Use connection
        tdconn = await connection_manager.ensure_connection()
        # ... execute query
```

## Usage Examples

### Basic Usage (Single Connection)

```python
# Server startup
registry = ConnectionRegistry.get_instance()
await registry.register_connection("default", connection_manager, set_as_default=True)

# Tool execution
executor = ToolExecutor()
result = await executor.execute_tool("query", {"query": "SELECT 1"})
# Tool automatically uses default connection!
```

### Advanced Usage (Multiple Connections)

```python
# Register multiple connections
registry = ConnectionRegistry.get_instance()

await registry.register_connection("primary", primary_conn, set_as_default=True)
await registry.register_connection("replica", replica_conn)
await registry.register_connection("analytics", analytics_conn)

# Use specific connection
result = await executor.execute_tool(
    "query",
    {"query": "SELECT * FROM large_table"},
    connection_name="replica"  # Read from replica to reduce primary load
)

# Use default connection
result = await executor.execute_tool("query", {"query": "INSERT INTO table ..."})
# Uses "primary" (default)
```

### Runtime Connection Management

```python
registry = ConnectionRegistry.get_instance()

# List all connections
connections = registry.list_connections()
# ['primary', 'replica', 'analytics']

# Get connection info
info = registry.get_connection_info("primary")
# {
#     "name": "primary",
#     "registered_at": "2025-01-24T10:30:00",
#     "is_default": True,
#     "metadata": {"host": "prod.db.com"}
# }

# Health check
health = await registry.health_check("primary")
# {"healthy": True, "connection_name": "primary"}

# Switch default
await registry.set_default_connection("replica")

# Remove connection
await registry.remove_connection("analytics")
```

### Testing with Mock Connections

```python
import pytest
from unittest.mock import AsyncMock

@pytest.fixture
async def mock_registry():
    # Reset singleton
    ConnectionRegistry.reset_instance()

    # Create mock connection
    mock_conn = AsyncMock()
    mock_conn.ensure_connection.return_value = mock_cursor

    # Register mock
    registry = ConnectionRegistry.get_instance()
    await registry.register_connection("default", mock_conn, set_as_default=True)

    yield registry

    # Cleanup
    ConnectionRegistry.reset_instance()

async def test_query_tool(mock_registry):
    tool = QueryTool()

    # Tool automatically gets mock connection from registry
    result = await tool.execute(QueryInput(query="SELECT 1"))

    assert result.success is True
```

## Migration Guide

### Step 1: Update Server to Register Connections

Add to your server's initialization:

```python
from .connection_registry import ConnectionRegistry

# After creating connection_manager
registry = ConnectionRegistry.get_instance()
await registry.register_connection("default", connection_manager, set_as_default=True)
```

### Step 2: Update Tools (Gradual Migration)

Tools can be updated gradually. Each tool follows this pattern:

**Before:**
```python
async def execute(self, input_data, context):
    connection_manager = context.get('connection_manager')
```

**After:**
```python
async def execute(self, input_data, context: Optional[Dict] = None):
    # 3-tier resolution
    connection_manager = self._connection_manager
    if connection_manager is None and context:
        connection_manager = context.get('connection_manager')
    if connection_manager is None:
        registry = ConnectionRegistry.get_instance()
        connection_manager = registry.get_connection()
```

### Step 3: Update Tool Executor

The executor attaches connections when loading tools:

```python
# In execute_tool()
tool_instance = tool_class()

if self._registry:
    connection = self._registry.get_connection(connection_name)
    if connection:
        tool_instance.attach_connection(connection)
```

### Step 4: Test Backward Compatibility

Old code should still work:

```python
# Old pattern (still works)
context = {"connection_manager": conn_mgr, "db_name": "demo"}
result = await tool.execute(input_data, context)

# New pattern (preferred)
result = await tool.execute(input_data)
```

## Benefits

### 1. Decoupling from Globals

**Before:**
```python
# Module-level global (tightly coupled)
_connection_manager = None

def set_connection(conn):
    global _connection_manager
    _connection_manager = conn
```

**After:**
```python
# External registry (loosely coupled)
registry = ConnectionRegistry.get_instance()
await registry.register_connection("default", conn)
```

### 2. Multi-Connection Support

```python
# Different connections for different purposes
await registry.register_connection("primary", primary_conn)  # Writes
await registry.register_connection("replica", replica_conn)  # Heavy reads
await registry.register_connection("analytics", analytics_conn)  # Analytics queries

# Route queries appropriately
result = await executor.execute_tool("query", {...}, connection_name="replica")
```

### 3. Runtime Swapping

```python
# Swap connections without restarting server
await registry.remove_connection("primary")
await registry.register_connection("primary", new_connection, set_as_default=True)
```

### 4. Easy Testing

```python
# Inject mock for testing
mock_conn = AsyncMock()
await registry.register_connection("default", mock_conn, set_as_default=True)
```

### 5. Connection Pooling

```python
# Register multiple connections to the same database
for i in range(5):
    conn = TeradataConnectionManager(...)
    await registry.register_connection(f"pool_{i}", conn)

# Round-robin or load balance across pool
connection_name = f"pool_{request_id % 5}"
result = await executor.execute_tool("query", {...}, connection_name=connection_name)
```

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                        SERVER STARTUP                        │
│                                                              │
│  1. Create TeradataConnectionManager(database_url)          │
│  2. await connection_manager.ensure_connection()            │
│  3. registry = ConnectionRegistry.get_instance()            │
│  4. await registry.register_connection("default", conn)     │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   CONNECTION REGISTRY                        │
│                      (Singleton)                             │
│                                                              │
│  _connections = {                                           │
│    "default": connection_manager,                           │
│    "replica": replica_manager,                              │
│    "analytics": analytics_manager                           │
│  }                                                          │
│                                                              │
│  _default_connection = "default"                            │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      TOOL DISCOVERY                          │
│                                                              │
│  1. executor = ToolExecutor()                               │
│  2. tool_class = executor.load_tool("query")                │
│  3. tool_instance = tool_class()                            │
│  4. connection = registry.get_connection()                  │
│  5. tool_instance.attach_connection(connection) ← KEY!      │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      TOOL EXECUTION                          │
│                                                              │
│  1. input_data = QueryInput(query="SELECT 1")               │
│  2. result = await tool_instance.execute(input_data)        │
│  3. Tool uses self._connection_manager (already attached!)  │
│  4. No context needed!                                      │
└─────────────────────────────────────────────────────────────┘
```

## Key Innovation

The critical insight from the user:

> "when search tool find good tools to be use then code of the tool attach to the existing connection"

This pattern makes connections **externally shareable** resources that tools discover and attach to at registration time, rather than receiving at execution time. This:

1. **Aligns with tools-as-code**: Tools discover existing resources (like files attach to filesystems)
2. **Decouples lifecycle**: Connection lifecycle independent of tool lifecycle
3. **Enables sharing**: Multiple tools share same connection instance
4. **Supports testing**: Easy to inject mock connections
5. **Enables scaling**: Connection pooling, multi-database, read replicas

## Performance Considerations

- **Registry overhead**: Minimal (dictionary lookup)
- **Attachment overhead**: None (one-time at load)
- **Execution overhead**: None (direct attribute access)
- **Memory**: Shared connection instances (not duplicated)

## Thread Safety

- **Registry access**: Protected by `asyncio.Lock()`
- **Connection operations**: Delegated to TeradataConnectionManager (already thread-safe)
- **Tool execution**: Each tool instance has own reference (no shared state)

## Related Documentation

- [Tools-as-Code Pattern](TOOLS_AS_CODE.md) - Overview of dynamic tool loading
- [Connection Flow](CONNECTION_FLOW.md) - Original connection flow (pre-registry)
- [Claude Desktop Config](CLAUDE_DESKTOP_CONFIG.md) - Configuration guide

## Summary

The **Connection Registry** pattern:

- ✅ Decouples connections from module globals
- ✅ Enables connection attachment at registration time (not execution time)
- ✅ Supports multiple named connections
- ✅ Allows runtime connection management
- ✅ Makes testing with mocks trivial
- ✅ Maintains 100% backward compatibility
- ✅ Aligns with tools-as-code vision

This is a **foundational architectural improvement** that makes the tools-as-code pattern work as intended: tools discover and attach to existing resources rather than receiving them at execution time.
