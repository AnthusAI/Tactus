"""
Tool Handle - Callable wrapper for direct tool invocation.

Provides OOP-style tool access where tool() returns a callable handle
that can be invoked directly without going through an agent.
"""

import asyncio
import logging
from typing import Any, Callable, Optional, TYPE_CHECKING

from tactus.utils.asyncio_helpers import clear_closed_event_loop

if TYPE_CHECKING:
    from tactus.primitives.tool import ToolPrimitive

logger = logging.getLogger(__name__)


class ToolHandle:
    """
    Callable wrapper around a tool for direct invocation.

    Returned by tool() for Lua-defined tools and Tool.get() for external tools.
    Can be called directly from Lua: result = handle({args})

    Example (Lua):
        local calculate_tip = tool({...}, function(args) ... end)
        local result = calculate_tip({bill_amount = 50, tip_percentage = 20})
    """

    def __init__(
        self,
        name: str,
        implementation_function: Callable,
        tool_primitive: Optional["ToolPrimitive"] = None,
        is_async: bool = False,
        record_calls: bool = True,
    ):
        """
        Initialize a tool handle.

        Args:
            name: Tool name for tracking/logging
            implementation_function: The actual function to execute
            tool_primitive: Optional ToolPrimitive for call recording
            is_async: Whether the implementation function is async (for MCP tools)
        """
        self.name = name
        self.implementation_function = implementation_function
        self.tool_primitive = tool_primitive
        self.is_async = is_async
        self.record_calls = record_calls

        logger.debug("ToolHandle created for '%s' (async=%s)", name, is_async)

    def _has_tool_primitive(self) -> bool:
        return self.tool_primitive is not None

    def _normalize_tool_arguments(self, tool_arguments: Any) -> Any:
        """
        Convert a Lua table or mapping-like input to a plain Python dict when possible.
        """
        if tool_arguments is None:
            return {}

        if hasattr(tool_arguments, "items"):
            return self._lua_table_to_dict(tool_arguments)

        return tool_arguments

    def call(self, args: dict[str, Any]) -> Any:
        """
        Execute the tool with given arguments.

        Args:
            args: Dictionary of arguments to pass to the tool

        Returns:
            Tool result

        Example (Lua):
            local result = my_tool:call({arg1 = "value"})
        """
        logger.debug("ToolHandle.call('%s') with args: %s", self.name, args)

        try:
            # Convert Lua table to Python dict if needed
            normalized_arguments = self._normalize_tool_arguments(args)

            # Execute the implementation
            if self.is_async or asyncio.iscoroutinefunction(self.implementation_function):
                result = self._run_async(normalized_arguments)
            else:
                result = self.implementation_function(normalized_arguments)

            # Record the call for tracking
            if self.tool_primitive and self.record_calls:
                self.tool_primitive.record_call(self.name, normalized_arguments, result)

            logger.debug("ToolHandle.call('%s') returned: %s", self.name, result)
            return result

        except Exception as error:
            logger.error(
                "ToolHandle.call('%s') failed: %s",
                self.name,
                error,
                exc_info=True,
            )
            raise

    def __call__(self, args: dict[str, Any]) -> Any:
        """
        Make handle callable for shorthand syntax.

        Example (Lua):
            local result = my_tool({arg1 = "value"})
        """
        return self.call(args)

    def called(self) -> bool:
        """
        Check if this tool has been called at least once.

        Returns:
            True if tool was called, False otherwise

        Example (Lua):
            if done.called() then
                Log.info("Task completed!")
            end
        """
        if not self._has_tool_primitive():
            logger.warning("ToolHandle.called('%s'): No tool_primitive attached", self.name)
            return False

        result = self.tool_primitive.called(self.name)
        logger.debug("ToolHandle.called('%s') = %s", self.name, result)
        return result

    def last_call(self) -> Optional[dict[str, Any]]:
        """
        Get the last call record for this tool.

        Returns:
            Dictionary with 'name', 'args', 'result' or None if never called

        Example (Lua):
            local call = multiply.last_call()
            if call then
                Log.info("Last multiply: " .. call.args.a .. " * " .. call.args.b)
            end
        """
        if not self._has_tool_primitive():
            logger.warning("ToolHandle.last_call('%s'): No tool_primitive attached", self.name)
            return None

        result = self.tool_primitive.last_call(self.name)
        logger.debug("ToolHandle.last_call('%s') = %s", self.name, result)
        return result

    def last_result(self) -> Any:
        """
        Get the result from the last call to this tool.

        Returns:
            Result value from last call, or None if never called

        Example (Lua):
            local answer = done.last_result()
            return { result = answer }
        """
        if not self._has_tool_primitive():
            logger.warning("ToolHandle.last_result('%s'): No tool_primitive attached", self.name)
            return None

        result = self.tool_primitive.last_result(self.name)
        logger.debug("ToolHandle.last_result('%s') = %s", self.name, result)
        return result

    def call_count(self) -> int:
        """
        Get the number of times this tool has been called.

        Returns:
            Number of calls (0 if never called)

        Example (Lua):
            local count = multiply.call_count()
            Log.info("Multiply was called " .. count .. " times")
        """
        if not self._has_tool_primitive():
            logger.warning("ToolHandle.call_count('%s'): No tool_primitive attached", self.name)
            return 0

        # Count all calls with this tool name
        count = sum(1 for call in self.tool_primitive._tool_calls if call.name == self.name)
        logger.debug("ToolHandle.call_count('%s') = %s", self.name, count)
        return count

    def reset(self) -> None:
        """
        Clear all recorded calls for this tool.

        This is useful when reusing the same tool handle in multiple sequential
        operations within a single procedure, allowing called() checks to work
        independently for each operation.

        Example (Lua):
            -- First agent uses done
            agent1()
            if done.called() then
                Log.info("Agent 1 completed")
            end

            -- Reset for second agent
            done.reset()

            -- Second agent uses done independently
            agent2()
            if done.called() then
                Log.info("Agent 2 completed")
            end
        """
        if not self._has_tool_primitive():
            logger.warning("ToolHandle.reset('%s'): No tool_primitive attached", self.name)
            return

        # Remove all calls for this tool
        self.tool_primitive._tool_calls = [
            call for call in self.tool_primitive._tool_calls if call.name != self.name
        ]
        logger.debug("ToolHandle.reset('%s'): Cleared all call records", self.name)

    def _run_async(self, args: dict[str, Any]) -> Any:
        """
        Run async function from sync context.

        Handles the complexity of running async code from Lua's sync context.
        """
        try:
            # Try to get a running event loop
            running_loop = asyncio.get_running_loop()

            # We're in an async context - use nest_asyncio if available
            try:
                import nest_asyncio

                nest_asyncio.apply(running_loop)
                return asyncio.run(self.implementation_function(args))
            except ImportError:
                # nest_asyncio not available, fall back to threading
                import threading

                async_result = {"value": None, "exception": None}

                def run_in_thread():
                    try:
                        thread_event_loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(thread_event_loop)
                        try:
                            async_result["value"] = thread_event_loop.run_until_complete(
                                self.implementation_function(args)
                            )
                        finally:
                            thread_event_loop.close()
                    except Exception as error:
                        async_result["exception"] = error

                worker_thread = threading.Thread(target=run_in_thread)
                worker_thread.start()
                worker_thread.join()

                if async_result["exception"]:
                    raise async_result["exception"]
                return async_result["value"]

        except RuntimeError:
            # No event loop running - safe to use asyncio.run()
            clear_closed_event_loop()
            return asyncio.run(self.implementation_function(args))

    def _lua_table_to_dict(self, lua_table: Any) -> Any:
        """Convert a Lua table to Python dict recursively."""
        if lua_table is None:
            return {}

        if not hasattr(lua_table, "items"):
            return lua_table

        result = {}
        for key, value in lua_table.items():
            if hasattr(value, "items"):
                result[key] = self._lua_table_to_dict(value)
            else:
                result[key] = value
        return result

    def __repr__(self) -> str:
        return f"ToolHandle('{self.name}')"
