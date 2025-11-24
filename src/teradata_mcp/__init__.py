import asyncio

def main():
    """Main entry point for the package."""
    # Lazy import to avoid loading heavy dependencies at package import time
    from . import server
    asyncio.run(server.main())

# Optionally expose other important items at package level
__all__ = [
    "main",
]