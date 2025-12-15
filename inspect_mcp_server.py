import inspect
from pydantic_ai.mcp import MCPServer

print(f"MCPServer signature: {inspect.signature(MCPServer.__init__)}")
print(f"MCPServer docstring: {MCPServer.__doc__}")
