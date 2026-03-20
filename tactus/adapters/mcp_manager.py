"""
MCP Server Manager for Tactus.

Manages multiple MCP server connections using Pydantic AI's native MCPServerStdio.
Handles lifecycle, tool prefixing, and tool call tracking.
"""

from __future__ import annotations

import logging
import os
import re
import asyncio
from contextlib import AsyncExitStack
from typing import Any, Optional, Iterable

logger = logging.getLogger(__name__)


MCPServerStdio: Optional[Any] = None


def _is_transient_mcp_error(error: Exception) -> bool:
    """Detect transient MCP transport failures worth retrying."""
    error_str = str(error)
    return (
        "BrokenResourceError" in error_str
        or "ClosedResourceError" in error_str
        or "EndOfStream" in error_str
        or "unhandled errors in a TaskGroup" in error_str
    )


def _require_mcp_server_stdio():
    try:
        from pydantic_ai.mcp import MCPServerStdio
    except ImportError as import_error:
        raise RuntimeError(
            "MCP support requires optional dependencies. "
            'Install with `pip install "pydantic-ai-slim[mcp]"`.'
        ) from import_error
    return MCPServerStdio


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
        self.servers: list[Any] = []
        self.server_toolsets: dict[str, Any] = {}  # Map server names to toolsets
        self._exit_stack = AsyncExitStack()
        logger.info("MCPServerManager initialized with %s server(s)", len(server_configs))

    async def __aenter__(self):
        """Connect to all configured MCP servers."""
        for name, config in self.configs.items():
            # Retry a few times for transient stdio startup issues.
            last_error: Optional[Exception] = None
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
                    MCPServerStdio = globals().get("MCPServerStdio")
                    if MCPServerStdio is None:
                        MCPServerStdio = _require_mcp_server_stdio()
                    server = MCPServerStdio(
                        command=resolved_config["command"],
                        args=resolved_config.get("args", []),
                        env=resolved_config.get("env"),
                        cwd=resolved_config.get("cwd"),
                        timeout=resolved_config.get("timeout", 5),
                        read_timeout=resolved_config.get("read_timeout", 300),
                        max_retries=resolved_config.get("max_retries", 1),
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
                    if _is_transient_mcp_error(error):
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
                max_attempts = 3
                result = None
                for attempt in range(1, max_attempts + 1):
                    try:
                        result = await invoke_next(tool_name, tool_args)
                        break
                    except Exception as error:
                        if attempt < max_attempts and _is_transient_mcp_error(error):
                            logger.warning(
                                "Transient MCP tool failure on '%s' (%s/%s): %s (retrying)",
                                tool_name,
                                attempt,
                                max_attempts,
                                error,
                            )
                            await asyncio.sleep(0.05 * attempt)
                            continue
                        raise

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

    def get_toolsets(self) -> list[Any]:
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


class BrokerMCPToolset:
    """
    Broker-backed MCP toolset that proxies list/call through BrokerClient.
    """

    def __init__(self, server_name: str, client, tool_primitive=None):
        self.server_name = server_name
        self._client = client
        self._tool_primitive = tool_primitive
        self._tools_cache: Optional[dict[str, Any]] = None

    @property
    def id(self) -> str | None:
        return f"broker-mcp:{self.server_name}"

    async def get_tools(self, ctx):
        if self._tools_cache is not None:
            return self._tools_cache

        from pydantic_ai.toolsets import ToolsetTool
        from pydantic_ai.tools import ToolDefinition
        from pydantic_ai.mcp import TOOL_SCHEMA_VALIDATOR

        tools = await self._client.list_mcp_tools(server=self.server_name)
        tool_map: dict[str, ToolsetTool] = {}

        for tool in tools:
            if not isinstance(tool, dict) or "name" not in tool:
                continue
            tool_name = f"{self.server_name}_{tool['name']}"
            params_schema = tool.get("inputSchema") or {"type": "object", "properties": {}}
            tool_def = ToolDefinition(
                name=tool_name,
                description=tool.get("description"),
                parameters_json_schema=params_schema,
            )
            tool_map[tool_name] = ToolsetTool(
                toolset=self,
                tool_def=tool_def,
                max_retries=1,
                args_validator=TOOL_SCHEMA_VALIDATOR,
            )

        self._tools_cache = tool_map
        return tool_map

    async def call_tool(self, name: str, tool_args: dict[str, Any], ctx=None, tool=None):
        prefix = f"{self.server_name}_"
        tool_name = name[len(prefix) :] if name.startswith(prefix) else name
        result = await self._client.call_mcp_tool(
            server=self.server_name,
            name=tool_name,
            args=tool_args or {},
        )

        if self._tool_primitive is not None:
            result_str = str(result) if not isinstance(result, str) else result
            self._tool_primitive.record_call(name, tool_args or {}, result_str)

        return result


class BrokerMCPServerManager:
    """
    Manages broker-proxied MCP toolsets inside the runtime container.
    """

    def __init__(
        self,
        server_configs: dict[str, dict[str, Any]] | Iterable[str],
        *,
        tool_primitive=None,
        client=None,
    ):
        from tactus.broker.client import BrokerClient

        if isinstance(server_configs, dict):
            server_names = list(server_configs.keys())
        else:
            server_names = list(server_configs)

        self._client = client or BrokerClient.from_environment()
        if self._client is None:
            raise RuntimeError("Broker MCP toolset requires TACTUS_BROKER_SOCKET to be set")
        self.tool_primitive = tool_primitive
        self.server_toolsets = {
            name: BrokerMCPToolset(name, self._client, tool_primitive=tool_primitive)
            for name in server_names
        }

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return None

    def get_toolsets(self) -> list[Any]:
        return list(self.server_toolsets.values())

    def get_toolset_by_name(self, server_name: str):
        return self.server_toolsets.get(server_name)
