"""
Step primitive for checkpointed operations.

Provides checkpoint() for creating explicit checkpoints in procedures.
"""

from typing import Any, Callable
import logging

logger = logging.getLogger(__name__)


class StepPrimitive:
    """
    Step primitive for checkpointing operations.

    Example usage:
        local metrics = checkpoint(function()
            return some_evaluation_function({
                model_id = input.model_id,
                version = "champion"
            })
        end)

    On first execution: runs the function and caches result at current position
    On replay: returns cached result from execution log
    """

    def __init__(self, execution_context):
        """
        Initialize Step primitive.

        Args:
            execution_context: ExecutionContext instance for checkpoint operations
        """
        self.execution_context = execution_context

    def checkpoint(self, fn: Callable[[], Any], lua_source_info=None) -> Any:
        """
        Execute function with position-based checkpointing.

        Args:
            fn: Function to execute (must be deterministic)
            lua_source_info: Optional dict with Lua source location {file, line, function}

        Returns:
            Result of fn() on first execution, cached result on replay
        """
        logger.debug("checkpoint() at position %s", self.execution_context.next_position())

        # Prioritize Lua source info over Python stack inspection
        if lua_source_info:
            # Convert Lua table to dict if needed (lupa might pass a LuaTable object)
            try:
                if hasattr(lua_source_info, "items"):
                    # It's already dict-like
                    lua_dict = dict(lua_source_info.items())
                else:
                    # Try to convert if it's a LuaTable
                    lua_dict = dict(lua_source_info)
            except Exception:
                # Fallback - treat as dict
                lua_dict = lua_source_info if isinstance(lua_source_info, dict) else {}

            # Use source info from Lua debug.getinfo
            source_info = {
                "file": self.execution_context.current_tac_file or lua_dict.get("file", "unknown"),
                "line": lua_dict.get("line", 0),
                "function": lua_dict.get("function", "unknown"),
            }
            logger.debug("Using Lua source info: %s", source_info)
        else:
            # Fallback to Python stack inspection (for backward compatibility)
            import inspect

            current_frame = inspect.currentframe()
            if current_frame and current_frame.f_back:
                caller_frame = current_frame.f_back
                source_info = {
                    "file": caller_frame.f_code.co_filename,
                    "line": caller_frame.f_lineno,
                    "function": caller_frame.f_code.co_name,
                }
            else:
                source_info = None

        try:
            result = self.execution_context.checkpoint(
                fn, "explicit_checkpoint", source_info=source_info
            )
            logger.debug("checkpoint() completed successfully")
            return result
        except Exception as error:
            logger.error("checkpoint() failed: %s", error)
            raise


class CheckpointPrimitive:
    """
    Checkpoint management primitive.

    Provides checkpoint clearing operations for testing.
    """

    def __init__(self, execution_context):
        """
        Initialize Checkpoint primitive.

        Args:
            execution_context: ExecutionContext instance
        """
        self.execution_context = execution_context

    def _coerce_position(self, position: Any) -> int:
        """
        Coerce a Lua/Python value into a checkpoint position (int).

        Lua commonly passes numbers as int/float and may pass strings; accept both.
        """
        if isinstance(position, bool):
            raise TypeError("Checkpoint position must be a number (bool is not allowed)")

        if isinstance(position, int):
            return position

        if isinstance(position, float) and position.is_integer():
            return int(position)

        if isinstance(position, str):
            stripped = position.strip()
            if stripped.isdigit() or (stripped.startswith("-") and stripped[1:].isdigit()):
                return int(stripped)
            raise TypeError(f"Checkpoint position must be an integer (got string {position!r})")

        raise TypeError(f"Checkpoint position must be an integer (got {type(position).__name__})")

    def clear_all(self) -> None:
        """
        Clear all checkpoints. Restarts procedure from beginning.

        Example:
            Checkpoint.clear_all()
        """
        logger.info("Clearing all checkpoints")
        self.execution_context.checkpoint_clear_all()

    def clear_after(self, position: int) -> None:
        """
        Clear checkpoint at position and all subsequent ones.

        Args:
            position: Checkpoint position to clear from

        Example:
            Checkpoint.clear_after(3)  -- Clear checkpoint 3 and beyond
        """
        logger.info("Clearing checkpoints after position %s", position)
        self.execution_context.checkpoint_clear_after(position)

    def next_position(self) -> int:
        """
        Get the next checkpoint position.

        Returns:
            Next position in execution log

        Example:
            local pos = Checkpoint.next_position()
            print("Next checkpoint will be at position: " .. pos)
        """
        return self.execution_context.next_position()

    def exists(self, position: Any) -> bool:
        """
        Check if a checkpoint exists at the given position.

        Args:
            position: Checkpoint position (0-indexed)

        Returns:
            True if an entry exists at that position, else False
        """
        coerced = self._coerce_position(position)
        metadata = getattr(self.execution_context, "metadata", None)
        if metadata is None or not hasattr(metadata, "execution_log"):
            raise RuntimeError("ExecutionContext does not expose checkpoint metadata")
        return 0 <= coerced < len(metadata.execution_log)

    def get(self, position: Any) -> Any:
        """
        Get the cached value from a checkpoint without advancing replay.

        Args:
            position: Checkpoint position (0-indexed)

        Returns:
            Cached result at that position, or None (Lua nil) if not present
        """
        coerced = self._coerce_position(position)
        metadata = getattr(self.execution_context, "metadata", None)
        if metadata is None or not hasattr(metadata, "execution_log"):
            raise RuntimeError("ExecutionContext does not expose checkpoint metadata")
        if coerced < 0 or coerced >= len(metadata.execution_log):
            return None
        return metadata.execution_log[coerced].result
