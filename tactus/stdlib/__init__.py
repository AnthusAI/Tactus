"""Tactus Standard Library.

Provides built-in tools and utilities that can be imported
using the 'use' attribute in Tool declarations.
"""

from typing import Any, Dict, Optional


def load_tool(name: str) -> Optional[Any]:
    """Load a tool function from the standard library.

    Args:
        name: Tool name (e.g., "done" for tactus.done)

    Returns:
        Tool function or None if not found
    """
    # Try to import the tool module
    try:
        import importlib

        module = importlib.import_module(f"tactus.stdlib.{name}")

        # Look for a function with the same name as the module
        if hasattr(module, name):
            return getattr(module, name)

        # If not found, look for any callable (first one found)
        for attr_name in dir(module):
            if not attr_name.startswith("_"):
                attr = getattr(module, attr_name)
                if callable(attr):
                    return attr

        return None
    except ImportError:
        return None


def load_stdlib_tool(name: str) -> Optional[Dict[str, Any]]:
    """Load a tool from the standard library (legacy).

    Args:
        name: Tool name (e.g., "done" for tactus.done)

    Returns:
        Tool definition dict or None if not found
    """
    tool_func = load_tool(name)
    if tool_func:
        return {"source": "stdlib", "function": tool_func, "name": name}
    return None


# Registry of available stdlib tools
STDLIB_TOOLS = {
    "done": "Standard completion tool",
    "log": "Logging utilities",
    "file": "File operations (read, write, list, exists)",
    "http": "HTTP request utilities (GET, POST, PUT, DELETE)",
    "read_file": "Read file contents",
    "write_file": "Write content to file",
    "list_files": "List files in directory",
    "file_exists": "Check if file exists",
    "get": "HTTP GET request",
    "post": "HTTP POST request",
    "put": "HTTP PUT request",
    "delete": "HTTP DELETE request",
}


def is_stdlib_tool(source: str) -> bool:
    """Check if a source string refers to a stdlib tool.

    Args:
        source: Source string (e.g., "tactus.done")

    Returns:
        True if this is a stdlib tool reference
    """
    return source.startswith("tactus.")


def get_stdlib_tool_name(source: str) -> str:
    """Extract the tool name from a stdlib source string.

    Args:
        source: Source string (e.g., "tactus.done")

    Returns:
        Tool name (e.g., "done")
    """
    if not source.startswith("tactus."):
        raise ValueError(f"Not a stdlib source: {source}")

    return source[7:]  # Remove "tactus." prefix
