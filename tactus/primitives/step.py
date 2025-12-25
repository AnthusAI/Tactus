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

    def checkpoint(self, fn: Callable[[], Any]) -> Any:
        """
        Execute function with position-based checkpointing.

        Args:
            fn: Function to execute (must be deterministic)

        Returns:
            Result of fn() on first execution, cached result on replay
        """
        logger.debug(f"checkpoint() at position {self.execution_context.next_position()}")

        try:
            result = self.execution_context.checkpoint(fn, "explicit_checkpoint")
            logger.debug("checkpoint() completed successfully")
            return result
        except Exception as e:
            logger.error(f"checkpoint() failed: {e}")
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
        logger.info(f"Clearing checkpoints after position {position}")
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
