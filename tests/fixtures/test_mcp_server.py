"""
Test MCP Server for Tactus Integration Testing.

A simple MCP server using FastMCP that provides basic tools for testing
the MCP integration functionality.
"""

from fastmcp import FastMCP

# Create the MCP server
mcp = FastMCP("TactusTestServer")


@mcp.tool
def add_numbers(a: int, b: int) -> int:
    """
    Add two numbers together.

    Args:
        a: First number
        b: Second number

    Returns:
        Sum of a and b
    """
    return a + b


@mcp.tool
def greet(name: str) -> str:
    """
    Greet someone by name.

    Args:
        name: Name of the person to greet

    Returns:
        Greeting message
    """
    return f"Hello, {name}!"


@mcp.tool
def get_status() -> dict:
    """
    Get server status information.

    Returns:
        Dictionary with status and version
    """
    return {"status": "ok", "version": "1.0.0", "server": "TactusTestServer"}


@mcp.tool
def multiply(x: float, y: float) -> float:
    """
    Multiply two numbers.

    Args:
        x: First number
        y: Second number

    Returns:
        Product of x and y
    """
    return x * y


if __name__ == "__main__":
    # Run the server when executed directly
    mcp.run()
