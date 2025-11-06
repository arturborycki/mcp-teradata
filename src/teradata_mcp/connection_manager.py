"""
Teradata Connection Manager
Handles connection resilience, health checking, and automatic reconnection.
"""

import asyncio
import logging
import time
from typing import Optional

from .tdsql import TDConn, obfuscate_password

logger = logging.getLogger(__name__)


class TeradataConnectionManager:
    """Manages Teradata database connections with automatic reconnection and health checking."""
    
    def __init__(self, database_url: str, db_name: str, max_retries: int = 3, 
                 initial_backoff: float = 1.0, max_backoff: float = 30.0):
        """
        Initialize the connection manager.
        
        Args:
            database_url: Full database connection URL
            db_name: Database name
            max_retries: Maximum number of reconnection attempts
            initial_backoff: Initial backoff time in seconds
            max_backoff: Maximum backoff time in seconds
        """
        self.database_url = database_url
        self.db_name = db_name
        self.max_retries = max_retries
        self.initial_backoff = initial_backoff
        self.max_backoff = max_backoff
        
        self._connection: Optional[TDConn] = None
        self._last_health_check = 0.0
        self._health_check_interval = 30.0  # Check every 30 seconds
        self._is_connecting = False
        self._connection_lock = asyncio.Lock()
        
        # Connection state
        self._connection_attempts = 0
        self._last_connection_time = 0.0
        
    async def ensure_connection(self) -> TDConn:
        """
        Ensure we have a healthy connection, reconnecting if necessary.
        
        Returns:
            Active TDConn instance
            
        Raises:
            ConnectionError: If connection cannot be established after max retries
        """
        async with self._connection_lock:
            # If we have a connection and it's recently checked, return it
            current_time = time.time()
            if (self._connection and 
                current_time - self._last_health_check < self._health_check_interval):
                return self._connection
            
            # Check if current connection is still healthy
            if self._connection and await self._is_connection_healthy():
                self._last_health_check = current_time
                return self._connection
            
            # Connection is not healthy or doesn't exist, reconnect
            logger.warning("Database connection is not healthy, attempting to reconnect...")
            return await self._reconnect_with_backoff()
    
    async def _is_connection_healthy(self) -> bool:
        """
        Check if the current connection is healthy.
        
        Returns:
            True if connection is healthy, False otherwise
        """
        if not self._connection:
            return False
        
        try:
            # Simple health check query
            cursor = self._connection.cursor()
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            cursor.close()
            return result is not None
        except Exception as e:
            logger.warning(f"Connection health check failed: {obfuscate_password(str(e))}")
            return False
    
    async def _reconnect_with_backoff(self) -> TDConn:
        """
        Attempt to reconnect with exponential backoff.
        
        Returns:
            New TDConn instance
            
        Raises:
            ConnectionError: If all reconnection attempts fail
        """
        if self._is_connecting:
            # Another coroutine is already attempting to connect
            while self._is_connecting:
                await asyncio.sleep(0.1)
            if self._connection:
                return self._connection
        
        self._is_connecting = True
        backoff_time = self.initial_backoff
        
        try:
            for attempt in range(self.max_retries):
                try:
                    logger.info(f"Attempting database connection (attempt {attempt + 1}/{self.max_retries})")
                    
                    # Close existing connection if any
                    if self._connection:
                        try:
                            self._connection.close()
                        except Exception:
                            pass
                        self._connection = None
                    
                    # Create new connection
                    self._connection = TDConn(self.database_url)

                    # Set query band for connection tracking
                    query_band_string = "ApplicationName=Teradata_MCP;"
                    set_query_band_sql = f"SET QUERY_BAND = '{query_band_string}' UPDATE FOR SESSION;"
                    try:
                        cur = self._connection.cursor()
                        cur.execute(set_query_band_sql)
                        cur.close()
                        logger.debug("Query band set successfully")
                    except Exception as qb_error:
                        logger.warning(f"Failed to set query band: {obfuscate_password(str(qb_error))}")

                    # Verify connection works
                    if await self._is_connection_healthy():
                        self._last_health_check = time.time()
                        self._last_connection_time = time.time()
                        self._connection_attempts = 0
                        logger.info("Database connection established successfully")
                        return self._connection
                    else:
                        raise Exception("Connection health check failed")
                        
                except Exception as e:
                    self._connection_attempts += 1
                    error_msg = obfuscate_password(str(e))
                    
                    if attempt < self.max_retries - 1:
                        logger.warning(
                            f"Connection attempt {attempt + 1} failed: {error_msg}. "
                            f"Retrying in {backoff_time:.1f} seconds..."
                        )
                        await asyncio.sleep(backoff_time)
                        backoff_time = min(backoff_time * 2, self.max_backoff)
                    else:
                        logger.error(f"All connection attempts failed. Last error: {error_msg}")
                        raise ConnectionError(
                            f"Failed to connect to database after {self.max_retries} attempts: {error_msg}"
                        )
            
            raise ConnectionError("Unexpected end of reconnection loop")
            
        finally:
            self._is_connecting = False
    
    def get_connection_info(self) -> dict:
        """
        Get information about the current connection state.
        
        Returns:
            Dictionary with connection information
        """
        return {
            "connected": self._connection is not None,
            "last_health_check": self._last_health_check,
            "last_connection_time": self._last_connection_time,
            "connection_attempts": self._connection_attempts,
            "is_connecting": self._is_connecting,
            "database_url": obfuscate_password(self.database_url),
            "database_name": self.db_name
        }
    
    async def close(self):
        """Close the current connection."""
        async with self._connection_lock:
            if self._connection:
                try:
                    self._connection.close()
                    logger.info("Database connection closed")
                except Exception as e:
                    logger.warning(f"Error closing connection: {obfuscate_password(str(e))}")
                finally:
                    self._connection = None
    
    def __del__(self):
        """Cleanup when the connection manager is destroyed."""
        if self._connection:
            try:
                self._connection.close()
            except Exception:
                pass
