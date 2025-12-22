"""
MCP Server Manager for Tactus.

Manages multiple MCP server connections using Pydantic AI's native MCPServerStdio.
Handles lifecycle, tool prefixing, and tool call tracking.
"""

import logging
import os
import re
from contextlib import AsyncExitStack
from typing import Dict, Any, List

from pydantic_ai.mcp import MCPServerStdio

logger = logging.getLogger(__name__)


def substitute_env_vars(value: Any) -> Any:
    """
    Replace ${VAR} with environment variable values.

    Args:
        value: Value to process (can be str, dict, list, or other)

    Returns:
        Value with environment variables substituted
    """
    if isinstance(value, str):
        # Replace ${VAR} or $VAR with environment variable value
        return re.sub(r"\$\{(\w+)\}", lambda m: os.getenv(m.group(1), ""), value)
    elif isinstance(value, dict):
        return {k: substitute_env_vars(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [substitute_env_vars(v) for v in value]
    return value


class MCPServerManager:
    """
    Manages multiple native Pydantic AI MCP servers.

    Uses Pydantic AI's MCPServerStdio for stdio transport and automatic
    tool prefixing. Handles connection lifecycle and tool call tracking.
    """

    def __init__(self, server_configs: Dict[str, Dict[str, Any]], tool_primitive=None):
        """
        Initialize MCP server manager.

        Args:
            server_configs: Dict of {server_name: {command, args, env}}
            tool_primitive: Optional ToolPrimitive for recording tool calls
        """
        self.configs = server_configs
        self.tool_primitive = tool_primitive
        self.servers: List[MCPServerStdio] = []
        self._exit_stack = AsyncExitStack()
        logger.info(f"MCPServerManager initialized with {len(server_configs)} server(s)")

    async def __aenter__(self):
        """Connect to all configured MCP servers."""
        for name, config in self.configs.items():
            try:
                logger.info(f"Connecting to MCP server '{name}'...")

                # Substitute environment variables in config
                config = substitute_env_vars(config)

                # Create base server
                server = MCPServerStdio(
                    command=config["command"],
                    args=config.get("args", []),
                    env=config.get("env"),
                    process_tool_call=self._create_trace_callback(name),  # Tracking hook
                )

                # Wrap with prefix to namespace tools
                prefixed_server = server.prefixed(name)

                # Connect the prefixed server
                await self._exit_stack.enter_async_context(prefixed_server)
                self.servers.append(prefixed_server)
                logger.info(f"Successfully connected to MCP server '{name}' with prefix '{name}_'")
            except Exception as e:
                # Check if this is a fileno error (common in test environments)
                import io

                error_str = str(e)
                if "fileno" in error_str or isinstance(e, io.UnsupportedOperation):
                    logger.warning(
                        f"Failed to connect to MCP server '{name}': {e} "
                        f"(test environment with redirected streams)"
                    )
                else:
                    logger.error(f"Failed to connect to MCP server '{name}': {e}", exc_info=True)
                # Don't raise - allow procedure to continue without this MCP server
                logger.info(f"Continuing without MCP server '{name}'")
                continue

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Disconnect from all MCP servers."""
        logger.info("Disconnecting from all MCP servers...")
        await self._exit_stack.aclose()
        logger.info("All MCP servers disconnected")

    def _create_trace_callback(self, server_name: str):
        """
        Create a tool call tracing callback for a specific server.

        Args:
            server_name: Name of the MCP server

        Returns:
            Async callback function for process_tool_call
        """

        async def trace_tool_call(ctx, next_call, tool_name, tool_args):
            """Middleware to record tool calls in Tactus ToolPrimitive."""
            logger.debug(
                f"MCP server '{server_name}' calling tool '{tool_name}' with args: {tool_args}"
            )

            try:
                result = await next_call(tool_name, tool_args)

                # Record in ToolPrimitive if available
                if self.tool_primitive:
                    # Convert result to string for consistency with old behavior
                    # Pydantic AI tools can return various types
                    result_str = str(result) if not isinstance(result, str) else result
                    self.tool_primitive.record_call(tool_name, tool_args, result_str)

                logger.debug(f"Tool '{tool_name}' completed successfully")
                return result
            except Exception as e:
                logger.error(f"Tool '{tool_name}' failed: {e}", exc_info=True)
                # Still record the failed call
                if self.tool_primitive:
                    error_msg = f"Error: {str(e)}"
                    self.tool_primitive.record_call(tool_name, tool_args, error_msg)
                raise

        return trace_tool_call

    def get_toolsets(self) -> List[MCPServerStdio]:
        """
        Return list of connected servers as toolsets.

        Returns:
            List of MCPServerStdio instances (which are AbstractToolset)
        """
        return self.servers
