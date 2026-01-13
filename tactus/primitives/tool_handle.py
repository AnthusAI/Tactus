"""
Tool Handle - Callable wrapper for direct tool invocation.

Provides OOP-style tool access where tool() returns a callable handle
that can be invoked directly without going through an agent.
"""

import asyncio
import logging
from typing import Any, Callable, Dict, Optional, TYPE_CHECKING

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
        impl_fn: Callable,
        tool_primitive: Optional["ToolPrimitive"] = None,
        is_async: bool = False,
        record_calls: bool = True,
    ):
        """
        Initialize a tool handle.

        Args:
            name: Tool name for tracking/logging
            impl_fn: The actual function to execute
            tool_primitive: Optional ToolPrimitive for call recording
            is_async: Whether impl_fn is async (for MCP tools)
        """
        self.name = name
        self.impl_fn = impl_fn
        self.tool_primitive = tool_primitive
        self.is_async = is_async
        self.record_calls = record_calls

        logger.debug(f"ToolHandle created for '{name}' (async={is_async})")

    def call(self, args: Dict[str, Any]) -> Any:
        """
        Execute the tool with given arguments.

        Args:
            args: Dictionary of arguments to pass to the tool

        Returns:
            Tool result

        Example (Lua):
            local result = my_tool:call({arg1 = "value"})
        """
        logger.debug(f"ToolHandle.call('{self.name}') with args: {args}")

        try:
            # Convert Lua table to Python dict if needed
            if hasattr(args, "items"):
                args = self._lua_table_to_dict(args)

            # Execute the implementation
            if self.is_async or asyncio.iscoroutinefunction(self.impl_fn):
                result = self._run_async(args)
            else:
                result = self.impl_fn(args)

            # Record the call for tracking
            if self.tool_primitive and self.record_calls:
                self.tool_primitive.record_call(self.name, args, result)

            logger.debug(f"ToolHandle.call('{self.name}') returned: {result}")
            return result

        except Exception as e:
            logger.error(f"ToolHandle.call('{self.name}') failed: {e}", exc_info=True)
            raise

    def __call__(self, args: Dict[str, Any]) -> Any:
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
        if not self.tool_primitive:
            logger.warning(f"ToolHandle.called('{self.name}'): No tool_primitive attached")
            return False

        result = self.tool_primitive.called(self.name)
        logger.debug(f"ToolHandle.called('{self.name}') = {result}")
        return result

    def last_call(self) -> Optional[Dict[str, Any]]:
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
        if not self.tool_primitive:
            logger.warning(f"ToolHandle.last_call('{self.name}'): No tool_primitive attached")
            return None

        result = self.tool_primitive.last_call(self.name)
        logger.debug(f"ToolHandle.last_call('{self.name}') = {result}")
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
        if not self.tool_primitive:
            logger.warning(f"ToolHandle.last_result('{self.name}'): No tool_primitive attached")
            return None

        result = self.tool_primitive.last_result(self.name)
        logger.debug(f"ToolHandle.last_result('{self.name}') = {result}")
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
        if not self.tool_primitive:
            logger.warning(f"ToolHandle.call_count('{self.name}'): No tool_primitive attached")
            return 0

        # Count all calls with this tool name
        count = sum(1 for call in self.tool_primitive._tool_calls if call.name == self.name)
        logger.debug(f"ToolHandle.call_count('{self.name}') = {count}")
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
        if not self.tool_primitive:
            logger.warning(f"ToolHandle.reset('{self.name}'): No tool_primitive attached")
            return

        # Remove all calls for this tool
        self.tool_primitive._tool_calls = [
            call for call in self.tool_primitive._tool_calls if call.name != self.name
        ]
        logger.debug(f"ToolHandle.reset('{self.name}'): Cleared all call records")

    def _run_async(self, args: Dict[str, Any]) -> Any:
        """
        Run async function from sync context.

        Handles the complexity of running async code from Lua's sync context.
        """
        try:
            # Try to get a running event loop
            loop = asyncio.get_running_loop()

            # We're in an async context - use nest_asyncio if available
            try:
                import nest_asyncio

                nest_asyncio.apply(loop)
                return asyncio.run(self.impl_fn(args))
            except ImportError:
                # nest_asyncio not available, fall back to threading
                import threading

                result_container = {"value": None, "exception": None}

                def run_in_thread():
                    try:
                        new_loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(new_loop)
                        try:
                            result_container["value"] = new_loop.run_until_complete(
                                self.impl_fn(args)
                            )
                        finally:
                            new_loop.close()
                    except Exception as e:
                        result_container["exception"] = e

                thread = threading.Thread(target=run_in_thread)
                thread.start()
                thread.join()

                if result_container["exception"]:
                    raise result_container["exception"]
                return result_container["value"]

        except RuntimeError:
            # No event loop running - safe to use asyncio.run()
            return asyncio.run(self.impl_fn(args))

    def _lua_table_to_dict(self, lua_table) -> Dict[str, Any]:
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
