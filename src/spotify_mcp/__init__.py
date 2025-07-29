from .fastmcp_server import mcp

def main() -> None:
    """Main entry point for the package."""
    mcp.run()

# Optionally expose other important items at package level
__all__ = ['main', 'mcp']

