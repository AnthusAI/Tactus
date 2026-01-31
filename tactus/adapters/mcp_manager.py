"""
MCP Server Manager for Tactus.

Manages multiple MCP server connections using Pydantic AI's native MCPServerStdio.
Handles lifecycle, tool prefixing, and tool call tracking.
"""

import logging
import os
import re
import asyncio
from contextlib import AsyncExitStack
from typing import Any

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
        return re.sub(r"\$\{(\w+)\}", lambda match: os.getenv(match.group(1), ""), value)
    if isinstance(value, dict):
        return {k: substitute_env_vars(v) for k, v in value.items()}
    if isinstance(value, list):
        return [substitute_env_vars(v) for v in value]
    return value


class MCPServerManager:
    """
    Manages multiple native Pydantic AI MCP servers.

    Uses Pydantic AI's MCPServerStdio for stdio transport and automatic
    tool prefixing. Handles connection lifecycle and tool call tracking.
    """

    def __init__(self, server_configs: dict[str, dict[str, Any]], tool_primitive=None):
        """
        Initialize MCP server manager.

        Args:
            server_configs: Dict of {server_name: {command, args, env}}
            tool_primitive: Optional ToolPrimitive for recording tool calls
        """
        self.configs = server_configs
        self.tool_primitive = tool_primitive
        self.servers: list[MCPServerStdio] = []
        self.server_toolsets: dict[str, MCPServerStdio] = {}  # Map server names to toolsets
        self._exit_stack = AsyncExitStack()
        logger.info("MCPServerManager initialized with %s server(s)", len(server_configs))

    async def __aenter__(self):
        """Connect to all configured MCP servers."""
        for name, config in self.configs.items():
            # Retry a few times for transient stdio startup issues.
            last_error: Exception | None = None
            for attempt in range(1, 4):
                try:
                    logger.info(
                        "Connecting to MCP server '%s' (attempt %s/3)...",
                        name,
                        attempt,
                    )

                    # Substitute environment variables in config
                    resolved_config = substitute_env_vars(config)

                    # Create base server
                    server = MCPServerStdio(
                        command=resolved_config["command"],
                        args=resolved_config.get("args", []),
                        env=resolved_config.get("env"),
                        cwd=resolved_config.get("cwd"),
                        process_tool_call=self._create_trace_callback(name),  # Tracking hook
                    )

                    # Wrap with prefix to namespace tools
                    prefixed_server = server.prefixed(name)

                    # Connect the prefixed server
                    await self._exit_stack.enter_async_context(prefixed_server)
                    self.servers.append(prefixed_server)
                    self.server_toolsets[name] = prefixed_server  # Store by name for lookup
                    logger.info(
                        f"Successfully connected to MCP server '{name}' with prefix '{name}_'"
                    )
                    last_error = None
                    break
                except Exception as error:
                    last_error = error

                    # Check if this is a fileno error (common in test environments)
                    import io

                    error_str = str(error)
                    if "fileno" in error_str or isinstance(error, io.UnsupportedOperation):
                        logger.warning(
                            "Failed to connect to MCP server '%s': %s "
                            "(test environment with redirected streams)",
                            name,
                            error,
                        )
                        # Allow procedures to continue without MCP in this environment.
                        last_error = None
                        break

                    # Retry transient anyio TaskGroup/broken stream issues.
                    if (
                        "BrokenResourceError" in error_str
                        or "unhandled errors in a TaskGroup" in error_str
                    ):
                        logger.warning(
                            "Transient MCP connection failure for '%s': %s (retrying)",
                            name,
                            error,
                        )
                        await asyncio.sleep(0.05 * attempt)
                        continue

                    logger.error(
                        "Failed to connect to MCP server '%s': %s",
                        name,
                        error,
                        exc_info=True,
                    )
                    break

            if last_error is not None:
                # For non-transient failures, raise so callers can decide whether to ignore.
                raise last_error

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

        async def trace_tool_call(execution_context, invoke_next, tool_name, tool_args):
            """Middleware to record tool calls in Tactus ToolPrimitive."""
            logger.debug(
                "MCP server '%s' calling tool '%s' with args: %s",
                server_name,
                tool_name,
                tool_args,
            )

            try:
                result = await invoke_next(tool_name, tool_args)

                # Record in ToolPrimitive if available
                if self.tool_primitive:
                    # Convert result to string for consistency with old behavior
                    # Pydantic AI tools can return various types
                    result_str = str(result) if not isinstance(result, str) else result
                    self.tool_primitive.record_call(tool_name, tool_args, result_str)

                logger.debug("Tool '%s' completed successfully", tool_name)
                return result
            except Exception as error:
                logger.error("Tool '%s' failed: %s", tool_name, error, exc_info=True)
                # Still record the failed call
                if self.tool_primitive:
                    error_msg = f"Error: {str(error)}"
                    self.tool_primitive.record_call(tool_name, tool_args, error_msg)
                raise

        return trace_tool_call

    def get_toolsets(self) -> list[MCPServerStdio]:
        """
        Return list of connected servers as toolsets.

        Returns:
            List of MCPServerStdio instances (which are AbstractToolset)
        """
        return self.servers

    def get_toolset_by_name(self, server_name: str):
        """
        Get a specific toolset by server name.

        Args:
            server_name: Name of the MCP server

        Returns:
            MCPServerStdio instance for the named server, or None if not found
        """
        return self.server_toolsets.get(server_name)
