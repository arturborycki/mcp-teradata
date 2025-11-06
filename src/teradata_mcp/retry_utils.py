"""
Retry Utilities for TDWM MCP Tools

Provides automatic retry mechanism for handling Teradata connection loss during
tool execution. Uses decorator pattern to transparently retry operations when
connection errors are detected.

Key Features:
- Smart error detection (connection errors vs SQL errors)
- Configurable retry attempts and delays
- Exponential backoff with jitter
- Operation safety categorization (read/write/dangerous)
- Detailed logging for troubleshooting
"""

import asyncio
import logging
import os
import random
from functools import wraps
from typing import Callable, Any

logger = logging.getLogger(__name__)

# Configuration from environment variables
MAX_RETRIES = int(os.environ.get("TOOL_MAX_RETRIES", "2"))
INITIAL_RETRY_DELAY = float(os.environ.get("TOOL_RETRY_INITIAL_DELAY", "0.5"))
MAX_RETRY_DELAY = float(os.environ.get("TOOL_MAX_RETRY_DELAY", "2.0"))

# Teradata connection error patterns
CONNECTION_ERROR_PATTERNS = [
    "connection",
    "network",
    "timeout",
    "lost connection",
    "broken pipe",
    "connection refused",
    "connection reset",
    "no route to host",
    "connection timed out",
    "connection closed",
    "session no longer exists",
    "unable to establish",
    "disconnected",
    "socket",
    "communication link failure",
]

# Teradata-specific error codes that indicate connection issues
CONNECTION_ERROR_CODES = [
    2631,  # Transaction ABORTed due to TDWM Termination
    3126,  # Session has been disconnected
    3127,  # Only an ET or null statement is legal after a transaction abort
    8017,  # Session limit exceeded
]


def is_connection_error(error: Exception) -> bool:
    """
    Determine if an error is a connection-related error that should be retried.

    Args:
        error: The exception to analyze

    Returns:
        True if the error is connection-related and should be retried

    Logic:
    - OperationalError and InterfaceError are typically connection issues
    - ProgrammingError (SQL syntax) should NOT be retried
    - DataError (data type issues) should NOT be retried
    - IntegrityError (constraint violations) should NOT be retried
    """
    error_str = str(error).lower()
    error_type = type(error).__name__

    # Check error type
    if error_type in ["ProgrammingError", "DataError", "IntegrityError"]:
        # These are code/data errors, not connection errors
        logger.debug(f"Not retrying {error_type}: {error}")
        return False

    # Check for Teradata error codes
    for code in CONNECTION_ERROR_CODES:
        if f"[Error {code}]" in str(error):
            logger.debug(f"Detected Teradata connection error code {code}")
            return True

    # Check error message patterns
    for pattern in CONNECTION_ERROR_PATTERNS:
        if pattern in error_str:
            logger.debug(f"Detected connection error pattern: {pattern}")
            return True

    # Check for specific error types that indicate connection issues
    if error_type in ["OperationalError", "InterfaceError", "ConnectionError"]:
        logger.debug(f"Detected connection error type: {error_type}")
        return True

    return False


def categorize_operation(func_name: str) -> str:
    """
    Categorize a tool operation by safety level for retry logic.

    Args:
        func_name: Name of the function/tool

    Returns:
        "read" | "write" | "dangerous"

    Categories:
    - read: Safe to retry multiple times (queries, shows, gets, lists)
    - write: Moderate retry (creates, updates with idempotent operations)
    - dangerous: No retry (deletes, drops, force operations)
    """
    func_lower = func_name.lower()

    # Dangerous operations - NO RETRY
    dangerous_keywords = [
        "delete", "drop", "remove", "purge", "terminate", "abort",
        "kill", "force", "reset", "clear", "flush"
    ]
    for keyword in dangerous_keywords:
        if keyword in func_lower:
            return "dangerous"

    # Read operations - FULL RETRY
    read_keywords = [
        "show", "get", "list", "query", "search", "find", "check",
        "view", "display", "fetch", "read", "select", "describe",
        "explain", "analyze", "count", "exists"
    ]
    for keyword in read_keywords:
        if keyword in func_lower:
            return "read"

    # Default to write for creates/updates/sets
    return "write"


def with_connection_retry(
    max_retries: int = None,
    initial_delay: float = None,
    max_delay: float = None
):
    """
    Decorator that automatically retries a function if a connection error occurs.

    Args:
        max_retries: Maximum retry attempts (default: from MAX_RETRIES config)
        initial_delay: Initial delay in seconds (default: from INITIAL_RETRY_DELAY)
        max_delay: Maximum delay in seconds (default: from MAX_RETRY_DELAY)

    Usage:
        @with_connection_retry()
        async def my_tool_function(...):
            # Tool implementation
            pass

    Behavior:
    - Detects connection errors using is_connection_error()
    - Adjusts retry count based on operation category
    - Uses exponential backoff with jitter
    - Logs all retry attempts
    - Re-raises the error if all retries fail
    """
    # Use defaults from config if not specified
    _max_retries = max_retries if max_retries is not None else MAX_RETRIES
    _initial_delay = initial_delay if initial_delay is not None else INITIAL_RETRY_DELAY
    _max_delay = max_delay if max_delay is not None else MAX_RETRY_DELAY

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            func_name = func.__name__
            operation_category = categorize_operation(func_name)

            # Adjust retries based on operation category
            if operation_category == "dangerous":
                allowed_retries = 0  # No retry for dangerous operations
            elif operation_category == "write":
                allowed_retries = min(1, _max_retries)  # Max 1 retry for writes
            else:  # read
                allowed_retries = _max_retries  # Full retries for reads

            last_error = None

            for attempt in range(allowed_retries + 1):
                try:
                    # Attempt to execute the function
                    result = await func(*args, **kwargs)

                    # If we succeeded after a retry, log it
                    if attempt > 0:
                        logger.info(
                            f"Tool '{func_name}' succeeded on retry attempt {attempt}/{allowed_retries}"
                        )

                    return result

                except Exception as e:
                    last_error = e

                    # Check if this is a connection error
                    if not is_connection_error(e):
                        # Not a connection error, don't retry
                        logger.debug(
                            f"Tool '{func_name}' failed with non-connection error: {type(e).__name__}"
                        )
                        raise

                    # This is a connection error
                    if attempt < allowed_retries:
                        # Calculate delay with exponential backoff and jitter
                        delay = min(
                            _initial_delay * (2 ** attempt),
                            _max_delay
                        )
                        # Add jitter (±25%)
                        jitter = delay * 0.25 * (2 * random.random() - 1)
                        delay_with_jitter = max(0, delay + jitter)

                        logger.warning(
                            f"Tool '{func_name}' (category: {operation_category}) "
                            f"connection error on attempt {attempt + 1}/{allowed_retries + 1}. "
                            f"Retrying in {delay_with_jitter:.2f}s... Error: {str(e)[:100]}"
                        )

                        await asyncio.sleep(delay_with_jitter)
                    else:
                        # All retries exhausted
                        logger.error(
                            f"Tool '{func_name}' failed after {allowed_retries + 1} attempts "
                            f"with connection error: {str(e)[:200]}"
                        )
                        raise

            # Should not reach here, but just in case
            if last_error:
                raise last_error

        return wrapper
    return decorator


# Convenience function for manual retry of arbitrary async operations
async def retry_on_connection_error(
    operation: Callable,
    operation_name: str = "operation",
    max_retries: int = MAX_RETRIES,
    initial_delay: float = INITIAL_RETRY_DELAY,
    max_delay: float = MAX_RETRY_DELAY
) -> Any:
    """
    Manually retry an async operation on connection errors.

    Args:
        operation: Async callable to execute
        operation_name: Name for logging
        max_retries: Maximum retry attempts
        initial_delay: Initial delay in seconds
        max_delay: Maximum delay in seconds

    Returns:
        Result of the operation

    Raises:
        The last exception if all retries fail

    Usage:
        result = await retry_on_connection_error(
            lambda: some_async_function(arg1, arg2),
            operation_name="some_async_function"
        )
    """
    last_error = None

    for attempt in range(max_retries + 1):
        try:
            result = await operation()

            if attempt > 0:
                logger.info(
                    f"Operation '{operation_name}' succeeded on retry attempt {attempt}/{max_retries}"
                )

            return result

        except Exception as e:
            last_error = e

            if not is_connection_error(e):
                logger.debug(
                    f"Operation '{operation_name}' failed with non-connection error: {type(e).__name__}"
                )
                raise

            if attempt < max_retries:
                delay = min(initial_delay * (2 ** attempt), max_delay)
                jitter = delay * 0.25 * (2 * random.random() - 1)
                delay_with_jitter = max(0, delay + jitter)

                logger.warning(
                    f"Operation '{operation_name}' connection error on attempt {attempt + 1}/{max_retries + 1}. "
                    f"Retrying in {delay_with_jitter:.2f}s... Error: {str(e)[:100]}"
                )

                await asyncio.sleep(delay_with_jitter)
            else:
                logger.error(
                    f"Operation '{operation_name}' failed after {max_retries + 1} attempts "
                    f"with connection error: {str(e)[:200]}"
                )
                raise

    if last_error:
        raise last_error
