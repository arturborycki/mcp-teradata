"""
Entry point for the Teradata MCP server when run as a module.

This file allows the package to be executed with:
python -m teradata_mcp
"""

from .server import main
import asyncio

if __name__ == "__main__":
    asyncio.run(main())
