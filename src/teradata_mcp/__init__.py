from . import server
import asyncio
from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("teradata-mcp")
except PackageNotFoundError:
    __version__ = "0.1.0"

def main():
    """Main entry point for the package."""
    asyncio.run(server.main())

# Optionally expose other important items at package level
__all__ = [
    "main",
    "server",
]