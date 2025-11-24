"""
External Connection Registry - Shareable connection management for tools-as-code pattern.

This module implements a registry pattern that allows database connections to be:
1. Registered externally (not tied to module globals)
2. Shared across all tools and modules
3. Attached to tools at registration/discovery time (not execution time)
4. Swapped or updated at runtime
5. Easily tested with mock connections

Key Innovation:
Instead of passing connections via context at execution time, connections are
registered once and tools "attach" to them when they're loaded. This aligns with
the tools-as-code pattern where tools discover and attach to existing resources.
"""

import asyncio
import logging
from typing import Dict, Optional, List, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class ConnectionRegistry:
    """
    Global registry for database connections.

    Provides external, shareable connection management that decouples connections
    from module globals and allows tools to attach to connections at registration time.

    Features:
    - Singleton pattern for global access
    - Multiple named connections (primary, replica, analytics, etc.)
    - Default connection selection
    - Runtime connection registration/removal
    - Thread-safe access with async locks
    - Connection health monitoring
    - Easy testing with mock connections

    Example Usage:
        # Server startup - register connection
        registry = ConnectionRegistry.get_instance()
        await registry.register_connection("default", connection_manager)

        # Tool discovery - attach connection
        tool = QueryTool()
        connection = registry.get_connection()
        tool.attach_connection(connection)

        # Tool execution - use attached connection
        result = await tool.execute(input_data)  # No context needed!
    """

    _instance: Optional['ConnectionRegistry'] = None
    _lock = asyncio.Lock()

    def __init__(self):
        """Initialize the registry."""
        self._connections: Dict[str, Any] = {}  # name -> ConnectionManager
        self._connection_info: Dict[str, Dict[str, Any]] = {}  # name -> metadata
        self._default_connection: Optional[str] = None
        self._instance_lock = asyncio.Lock()

    @classmethod
    def get_instance(cls) -> 'ConnectionRegistry':
        """
        Get the singleton instance of the connection registry.

        Returns:
            ConnectionRegistry instance
        """
        if cls._instance is None:
            cls._instance = ConnectionRegistry()
            logger.debug("Created new ConnectionRegistry instance")
        return cls._instance

    @classmethod
    def reset_instance(cls):
        """
        Reset the singleton instance.

        Useful for testing to ensure clean state between tests.
        """
        cls._instance = None
        logger.debug("Reset ConnectionRegistry instance")

    async def register_connection(
        self,
        name: str,
        connection_manager: Any,
        set_as_default: bool = False,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Register a connection manager in the registry.

        Args:
            name: Connection name (e.g., "default", "primary", "replica", "analytics")
            connection_manager: ConnectionManager instance to register
            set_as_default: Whether to set as the default connection
            metadata: Optional metadata about the connection (for monitoring)

        Example:
            await registry.register_connection(
                "primary",
                primary_conn_manager,
                set_as_default=True,
                metadata={"host": "prod.db.company.com", "purpose": "production"}
            )
        """
        async with self._instance_lock:
            self._connections[name] = connection_manager
            self._connection_info[name] = {
                "name": name,
                "registered_at": datetime.now().isoformat(),
                "is_default": False,
                "metadata": metadata or {}
            }

            if set_as_default or self._default_connection is None:
                # Update previous default
                if self._default_connection and self._default_connection in self._connection_info:
                    self._connection_info[self._default_connection]["is_default"] = False

                self._default_connection = name
                self._connection_info[name]["is_default"] = True
                logger.info(f"Registered connection '{name}' as default")
            else:
                logger.info(f"Registered connection '{name}'")

    def get_connection(self, name: Optional[str] = None) -> Optional[Any]:
        """
        Get a connection manager by name.

        Args:
            name: Connection name (uses default if None)

        Returns:
            ConnectionManager instance or None if not found

        Example:
            # Get default connection
            connection = registry.get_connection()

            # Get specific connection
            replica_conn = registry.get_connection("replica")
        """
        if name is None:
            name = self._default_connection

        if name is None:
            logger.warning("No default connection set and no name provided")
            return None

        connection = self._connections.get(name)
        if connection is None:
            logger.warning(f"Connection '{name}' not found in registry")

        return connection

    async def remove_connection(self, name: str):
        """
        Remove a connection from the registry.

        Args:
            name: Connection name to remove

        Note: This will close the connection before removing it.

        Example:
            await registry.remove_connection("replica")
        """
        async with self._instance_lock:
            if name not in self._connections:
                logger.warning(f"Connection '{name}' not found, cannot remove")
                return

            connection = self._connections[name]

            # Close the connection if it has a close method
            if hasattr(connection, 'close'):
                try:
                    await connection.close()
                    logger.info(f"Closed connection '{name}'")
                except Exception as e:
                    logger.error(f"Error closing connection '{name}': {e}")

            # Remove from registry
            del self._connections[name]
            del self._connection_info[name]

            # Update default if this was the default
            if self._default_connection == name:
                self._default_connection = None
                # Set first available connection as default
                if self._connections:
                    first_name = next(iter(self._connections.keys()))
                    self._default_connection = first_name
                    self._connection_info[first_name]["is_default"] = True
                    logger.info(f"Set '{first_name}' as new default connection")

            logger.info(f"Removed connection '{name}' from registry")

    def list_connections(self) -> List[str]:
        """
        List all registered connection names.

        Returns:
            List of connection names

        Example:
            names = registry.list_connections()
            # ['default', 'replica', 'analytics']
        """
        return list(self._connections.keys())

    def get_connection_info(self, name: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Get information about a connection.

        Args:
            name: Connection name (uses default if None)

        Returns:
            Connection info dictionary or None if not found

        Example:
            info = registry.get_connection_info("primary")
            # {
            #     "name": "primary",
            #     "registered_at": "2025-01-24T10:30:00",
            #     "is_default": True,
            #     "metadata": {"host": "prod.db.company.com"}
            # }
        """
        if name is None:
            name = self._default_connection

        if name is None:
            return None

        return self._connection_info.get(name)

    def get_default_connection_name(self) -> Optional[str]:
        """
        Get the name of the default connection.

        Returns:
            Default connection name or None if not set
        """
        return self._default_connection

    async def set_default_connection(self, name: str):
        """
        Set a connection as the default.

        Args:
            name: Connection name to set as default

        Raises:
            ValueError: If connection name not found

        Example:
            await registry.set_default_connection("replica")
        """
        async with self._instance_lock:
            if name not in self._connections:
                raise ValueError(f"Connection '{name}' not found in registry")

            # Update previous default
            if self._default_connection and self._default_connection in self._connection_info:
                self._connection_info[self._default_connection]["is_default"] = False

            # Set new default
            self._default_connection = name
            self._connection_info[name]["is_default"] = True
            logger.info(f"Set '{name}' as default connection")

    def has_connection(self, name: Optional[str] = None) -> bool:
        """
        Check if a connection exists in the registry.

        Args:
            name: Connection name (checks for default if None)

        Returns:
            True if connection exists, False otherwise

        Example:
            if registry.has_connection("replica"):
                replica = registry.get_connection("replica")
        """
        if name is None:
            return self._default_connection is not None
        return name in self._connections

    async def get_all_connection_info(self) -> Dict[str, Dict[str, Any]]:
        """
        Get information about all registered connections.

        Returns:
            Dictionary mapping connection names to their info

        Example:
            all_info = await registry.get_all_connection_info()
            for name, info in all_info.items():
                print(f"{name}: {info['registered_at']}")
        """
        return dict(self._connection_info)

    async def health_check(self, name: Optional[str] = None) -> Dict[str, Any]:
        """
        Perform a health check on a connection.

        Args:
            name: Connection name (uses default if None)

        Returns:
            Health check results

        Example:
            health = await registry.health_check("primary")
            if health["healthy"]:
                print("Connection is healthy!")
        """
        connection = self.get_connection(name)
        if not connection:
            return {
                "healthy": False,
                "error": "Connection not found"
            }

        try:
            # Check if connection has health check method
            if hasattr(connection, '_is_connection_healthy'):
                healthy = connection._is_connection_healthy()
                return {
                    "healthy": healthy,
                    "connection_name": name or self._default_connection
                }
            else:
                # No health check method, assume healthy if exists
                return {
                    "healthy": True,
                    "connection_name": name or self._default_connection,
                    "note": "No health check method available"
                }
        except Exception as e:
            logger.error(f"Health check failed for connection '{name}': {e}")
            return {
                "healthy": False,
                "error": str(e),
                "connection_name": name or self._default_connection
            }

    def __repr__(self) -> str:
        """String representation of the registry."""
        conn_count = len(self._connections)
        default = self._default_connection or "None"
        return f"ConnectionRegistry(connections={conn_count}, default='{default}')"
