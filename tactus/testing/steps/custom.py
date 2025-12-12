"""
Custom step manager for user-defined Lua step functions.
"""

import logging
from typing import Any, Dict


logger = logging.getLogger(__name__)


class CustomStepManager:
    """
    Manages custom Lua step definitions.

    Allows users to define custom steps in their procedure files
    using the step() function with Lua implementations.
    """

    def __init__(self, lua_sandbox=None):
        self.lua_sandbox = lua_sandbox
        self.custom_steps: Dict[str, Any] = {}

    def register_from_lua(self, step_text: str, lua_function: Any) -> None:
        """
        Register a custom step from Lua code.

        Args:
            step_text: The step text pattern (exact match)
            lua_function: Lua function reference to execute
        """
        self.custom_steps[step_text] = lua_function
        logger.debug(f"Registered custom step: {step_text}")

    def execute(self, step_text: str, context: Any) -> bool:
        """
        Execute custom Lua step if it exists.

        Args:
            step_text: The step text to match
            context: Test context object

        Returns:
            True if step was found and executed, False otherwise
        """
        if step_text in self.custom_steps:
            lua_func = self.custom_steps[step_text]
            try:
                # Call Lua function with context
                # The Lua function should perform assertions
                lua_func(context)
                return True
            except Exception as e:
                logger.error(f"Custom step '{step_text}' failed: {e}")
                raise AssertionError(f"Custom step failed: {e}")

        return False

    def has_step(self, step_text: str) -> bool:
        """Check if custom step exists."""
        return step_text in self.custom_steps

    def get_all_steps(self) -> list[str]:
        """Get all registered custom step texts."""
        return list(self.custom_steps.keys())

    def clear(self) -> None:
        """Clear all custom steps."""
        self.custom_steps.clear()
