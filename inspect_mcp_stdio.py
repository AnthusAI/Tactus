import inspect
from pydantic_ai.mcp import MCPServerStdio, StdioServerParameters

print(f"MCPServerStdio signature: {inspect.signature(MCPServerStdio.__init__)}")
print(f"StdioServerParameters signature: {inspect.signature(StdioServerParameters.__init__)}")
