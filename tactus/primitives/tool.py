"""
Tool Primitive - Tool call tracking, result access, and direct invocation.

Provides:
- Tool.called(name) - Check if tool was called
- Tool.last_result(name) - Get last result from named tool
- Tool.last_call(name) - Get full call info
- Tool.get(name) - Get a callable handle to an external tool (MCP, plugin)
"""

import logging
from typing import Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from tactus.primitives.tool_handle import ToolHandle

logger = logging.getLogger(__name__)


class ToolCall:
    """Represents a single tool call with arguments and result."""

    def __init__(self, name: str, args: dict[str, Any], result: Any):
        self.name = name
        self.args = args
        self.result = result
        self.timestamp = None  # Could add timestamp tracking

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for Lua access."""
        return {"name": self.name, "args": self.args, "result": self.result}

    def __repr__(self) -> str:
        return f"ToolCall({self.name}, args={self.args})"


class ToolPrimitive:
    """
    Tracks tool calls and provides access to results.

    Maintains a history of tool calls and their results, allowing
    Lua code to check what tools were used and access their outputs.

    Also supports tool lookup via __call__:
        Tool("done")({args})  -- Look up and call tool
        Tool.called("done")   -- Check if tool was called (existing)
    """

    def __init__(
        self,
        log_handler=None,
        agent_name: Optional[str] = None,
        procedure_id: Optional[str] = None,
    ):
        """Initialize tool tracking."""
        self._tool_calls: list[ToolCall] = []
        self._last_calls: dict[str, ToolCall] = {}  # name -> last call
        self.log_handler = log_handler
        self.agent_name = agent_name
        self.procedure_id = procedure_id
        self._runtime = None  # Will be set by runtime for Tool.get() support
        self._tool_registry: dict[str, "ToolHandle"] = {}  # For Tool("name") lookup
        logger.debug("ToolPrimitive initialized")

    def set_tool_registry(self, registry: dict[str, "ToolHandle"]) -> None:
        """
        Set the tool registry for Tool("name") lookup.

        Called by dsl_stubs.create_dsl_stubs() after tools are registered.

        Args:
            registry: Dict mapping tool names to ToolHandle instances
        """
        self._tool_registry = registry
        logger.debug("ToolPrimitive tool registry set with %s tools", len(registry))

    def __call__(self, tool_name: str) -> "ToolHandle":
        """
        Look up a tool by name for direct invocation.

        This makes Tool dual-purpose:
        - Tool("done")({args}) -- lookup and call
        - Tool.called("done")  -- tracking (existing method)

        Args:
            tool_name: Name of the tool to look up

        Returns:
            ToolHandle that can be called directly

        Raises:
            ValueError: If tool not found in registry

        Example (Lua):
            Tool("done")({reason = "finished"})
        """
        if tool_name not in self._tool_registry:
            available = list(self._tool_registry.keys())
            raise ValueError(f"Tool '{tool_name}' not defined. Available tools: {available}")
        return self._tool_registry[tool_name]

    def set_runtime(self, runtime) -> None:
        """
        Set runtime reference for toolset lookup.

        Called by the runtime after initialization to enable Tool.get().

        Args:
            runtime: TactusRuntime instance with toolset_registry
        """
        self._runtime = runtime
        logger.debug("ToolPrimitive connected to runtime for toolset lookup")

    def get(self, tool_name: str) -> "ToolHandle":
        """
        Get a callable handle to an external tool (MCP, plugin).

        For Lua-defined tools, use the return value of tool() instead.

        Args:
            tool_name: Name of the external tool to retrieve

        Returns:
            ToolHandle that can be called directly

        Raises:
            ValueError: If tool is not found in registry

        Example (Lua):
            local search = Tool.get("web_search")  -- MCP tool
            local result = search({query = "weather"})

            local analyze = Tool.get("analyze_sentiment")  -- Plugin tool
            local sentiment = analyze({text = "I love this!"})
        """
        from tactus.primitives.tool_handle import ToolHandle

        logger.debug("Tool.get('%s') called", tool_name)

        # Look up toolset from runtime registry
        toolset = self._get_toolset(tool_name)
        if toolset is None:
            raise ValueError(
                f"Tool '{tool_name}' not found. "
                f"Make sure it's registered as an MCP tool, plugin, or in a toolset."
            )

        # Extract the callable function from the toolset
        tool_function = self._extract_tool_function(toolset, tool_name)

        logger.debug("Tool.get('%s') returning ToolHandle", tool_name)
        return ToolHandle(tool_name, tool_function, self)

    def _get_toolset(self, name: str) -> Optional[Any]:
        """
        Look up toolset from runtime registry.

        Args:
            name: Toolset name

        Returns:
            Toolset instance or None if not found
        """
        if self._runtime is None:
            logger.warning("Tool.get() called but runtime not connected")
            return None

        if not hasattr(self._runtime, "toolset_registry"):
            logger.warning("Runtime does not have toolset_registry")
            return None

        return self._runtime.toolset_registry.get(name)

    def _extract_tool_function(self, toolset: Any, tool_name: str) -> Any:
        """
        Extract callable function from a pydantic-ai toolset.

        Handles different toolset types (FunctionToolset, MCP, etc.)

        Args:
            toolset: Pydantic-ai toolset instance
            tool_name: Name of the tool

        Returns:
            Callable function that executes the tool
        """
        # Try to get the tool function from common toolset patterns

        # Pattern 1: FunctionToolset with tools list
        if hasattr(toolset, "tools"):
            tools = toolset.tools
            if isinstance(tools, list):
                for tool in tools:
                    if hasattr(tool, "name") and tool.name == tool_name:
                        # Return the tool's function
                        if hasattr(tool, "function"):
                            return tool.function
                        elif callable(tool):
                            return tool
            # If tools is a dict
            elif isinstance(tools, dict) and tool_name in tools:
                tool = tools[tool_name]
                if hasattr(tool, "function"):
                    return tool.function
                elif callable(tool):
                    return tool

        # Pattern 2: Toolset with a single tool (like individual Lua tools)
        if hasattr(toolset, "function"):
            return toolset.function

        # Pattern 3: Toolset that is itself callable
        if callable(toolset):
            return toolset

        # Pattern 4: MCP toolset - these wrap MCP tools
        if hasattr(toolset, "_tools") or hasattr(toolset, "get_tool"):
            # Try to get the specific tool
            if hasattr(toolset, "get_tool"):
                tool = toolset.get_tool(tool_name)
                if tool:
                    return tool

            # Return a wrapper that calls through the toolset
            def mcp_wrapper(args):
                return toolset.call_tool(tool_name, args)

            return mcp_wrapper

        # Fallback: assume the toolset itself contains tool functions
        logger.warning(
            "Could not extract tool function for '%s' from toolset type %s",
            tool_name,
            type(toolset),
        )

        # Return a wrapper that attempts to call through the toolset
        def fallback_wrapper(args):
            if hasattr(toolset, "call"):
                return toolset.call(tool_name, args)
            raise RuntimeError(f"Cannot call tool '{tool_name}' - toolset type not supported")

        return fallback_wrapper

    def called(self, tool_name: str) -> bool:
        """
        Check if a tool was called at least once.

        Args:
            tool_name: Name of the tool to check

        Returns:
            True if the tool was called

        Example (Lua):
            if Tool.called("done") then
                Log.info("Done tool was called")
            end
        """
        was_called = tool_name in self._last_calls
        logger.debug("Tool.called('%s') = %s", tool_name, was_called)
        return was_called

    def last_result(self, tool_name: str) -> Any:
        """
        Get the last result from a named tool.

        Args:
            tool_name: Name of the tool

        Returns:
            Last result from the tool, or None if never called

        Example (Lua):
            local result = Tool.last_result("search")
            if result then
                Log.info("Search found: " .. result)
            end
        """
        if tool_name not in self._last_calls:
            logger.debug("Tool.last_result('%s') = None (never called)", tool_name)
            return None

        result = self._last_calls[tool_name].result
        logger.debug("Tool.last_result('%s') = %s", tool_name, result)
        return result

    def last_call(self, tool_name: str) -> Optional[dict[str, Any]]:
        """
        Get full information about the last call to a tool.

        Args:
            tool_name: Name of the tool

        Returns:
            Dictionary with 'name', 'args', 'result' or None if never called

        Example (Lua):
            local call = Tool.last_call("search")
            if call then
                Log.info("Search was called with: " .. call.args.query)
                Log.info("Result: " .. call.result)
            end
        """
        if tool_name not in self._last_calls:
            logger.debug("Tool.last_call('%s') = None (never called)", tool_name)
            return None

        call_dict = self._last_calls[tool_name].to_dict()
        logger.debug("Tool.last_call('%s') = %s", tool_name, call_dict)
        return call_dict

    def record_call(
        self,
        tool_name: str,
        args: dict[str, Any],
        result: Any,
        agent_name: Optional[str] = None,
    ) -> None:
        """
        Record a tool call (called by runtime after tool execution).

        Args:
            tool_name: Name of the tool
            args: Arguments passed to the tool
            result: Result returned by the tool
            agent_name: Optional name of agent that called the tool

        Note: This is called internally by the runtime, not from Lua
        """
        tool_call = ToolCall(tool_name, args, result)
        self._tool_calls.append(tool_call)
        self._last_calls[tool_name] = tool_call

        logger.debug(
            "Tool call recorded: %s -> %s total calls",
            tool_name,
            len(self._tool_calls),
        )

        # Emit ToolCallEvent if we have a log handler
        if self.log_handler:
            try:
                from tactus.protocols.models import ToolCallEvent

                event = ToolCallEvent(
                    agent_name=agent_name or self.agent_name or "unknown",
                    tool_name=tool_name,
                    tool_args=args,
                    tool_result=result,
                    procedure_id=self.procedure_id,
                )
                self.log_handler.log(event)
            except Exception as error:
                logger.warning("Failed to log tool call event: %s", error)

    def get_all_calls(self) -> list[ToolCall]:
        """
        Get all tool calls (for debugging/logging).

        Returns:
            List of all ToolCall objects
        """
        return self._tool_calls.copy()

    def get_call_count(self, tool_name: Optional[str] = None) -> int:
        """
        Get the number of times a tool was called.

        Args:
            tool_name: Name of tool (or None for total count)

        Returns:
            Number of calls
        """
        if tool_name is None:
            return len(self._tool_calls)

        return sum(1 for call in self._tool_calls if call.name == tool_name)

    def reset(self) -> None:
        """Reset tool tracking (mainly for testing)."""
        self._tool_calls.clear()
        self._last_calls.clear()
        logger.debug("Tool tracking reset")

    def __repr__(self) -> str:
        return f"ToolPrimitive({len(self._tool_calls)} calls)"
