try:
    import pydantic_ai
    print(f"pydantic_ai version: {pydantic_ai.__version__}")
except ImportError:
    print("pydantic_ai not installed")

try:
    from pydantic_ai.toolsets.mcp import MCPServer
    print("MCPServer found in pydantic_ai.toolsets.mcp")
except ImportError:
    print("MCPServer NOT found in pydantic_ai.toolsets.mcp")

try:
    from pydantic_ai.mcp import MCPServer
    print("MCPServer found in pydantic_ai.mcp")
except ImportError:
    print("MCPServer NOT found in pydantic_ai.mcp")
