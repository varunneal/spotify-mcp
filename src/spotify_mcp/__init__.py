import asyncio

def main():
    """Main entry point for the package."""
    from . import server

    asyncio.run(server.main())

__all__ = ['main']
