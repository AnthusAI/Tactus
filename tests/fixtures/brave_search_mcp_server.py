"""
Test MCP Server: Brave-search-like tools.

This is a minimal stand-in for `@modelcontextprotocol/server-brave-search` so
that MCP examples can run deterministically in CI without external APIs.
"""

from __future__ import annotations

from fastmcp import FastMCP

mcp = FastMCP("TactusBraveSearchTestServer")


@mcp.tool
def search(query: str) -> dict:
    """Return deterministic search results for a query."""
    return {
        "query": query,
        "results": [
            {
                "title": "Lua",
                "url": "https://www.lua.org/",
                "snippet": "Lua is a lightweight language.",
            },
            {
                "title": "Tactus",
                "url": "https://example.invalid/tactus",
                "snippet": "Tactus is a workflow engine for agentic procedures.",
            },
        ],
    }


if __name__ == "__main__":
    mcp.run()
