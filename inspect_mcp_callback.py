from typing import get_type_hints
from pydantic_ai.mcp import MCPServerStdio

# ProcessToolCallback is likely a type alias or protocol
# Let's try to find where it is defined or inferred from docstring/usage
import pydantic_ai.mcp
print(f"ProcessToolCallback: {getattr(pydantic_ai.mcp, 'ProcessToolCallback', 'Not found')}")
