"""
Test MCP Server: Filesystem-like tools.

This is a lightweight stand-in for `@modelcontextprotocol/server-filesystem` so
that MCP examples can run deterministically in CI without Node.js.
"""

from __future__ import annotations

from pathlib import Path

from fastmcp import FastMCP

mcp = FastMCP("TactusFilesystemTestServer")


@mcp.tool
def list_directory(path: str = ".") -> list[str]:
    """List directory entries (names only)."""
    p = Path(path)
    return sorted([child.name for child in p.iterdir()])


@mcp.tool
def read_file(path: str) -> str:
    """Read a UTF-8 text file."""
    return Path(path).read_text(encoding="utf-8")


@mcp.tool
def write_file(path: str, content: str) -> bool:
    """Write a UTF-8 text file."""
    Path(path).write_text(content, encoding="utf-8")
    return True


if __name__ == "__main__":
    mcp.run()
