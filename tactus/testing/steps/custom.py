"""
Custom step manager for user-defined Lua step functions.

Supports regex pattern matching for step definitions, allowing
expressive BDD specifications with captured arguments.
"""

import logging
import re
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class CustomStepManager:
    """
    Manages custom Lua step definitions with regex pattern matching.

    Allows users to define custom steps in their procedure files
    using the Step() function with regex patterns and Lua implementations.

    Example:
        Step("a classifier with classes (.+)", function(ctx, classes)
            -- classes contains the captured group
        end)
    """

    def __init__(self, lua_sandbox=None):
        self.lua_sandbox = lua_sandbox
        self._steps: Dict[re.Pattern, Any] = {}  # compiled_pattern -> lua_function
        self._patterns: Dict[str, re.Pattern] = {}  # pattern_str -> compiled_pattern

    def register_from_lua(self, pattern: str, lua_function: Any) -> None:
        """
        Register a custom step from Lua code with regex pattern.

        Args:
            pattern: The step text pattern (regex with capture groups)
            lua_function: Lua function reference to execute
        """
        try:
            compiled = re.compile(pattern, re.IGNORECASE)
            self._steps[compiled] = lua_function
            self._patterns[pattern] = compiled
            logger.debug(f"Registered custom step pattern: {pattern}")
        except re.error as e:
            logger.error(f"Invalid regex pattern '{pattern}': {e}")
            raise ValueError(f"Invalid step pattern: {e}")

    def _match(self, step_text: str) -> Optional[Tuple[Any, tuple]]:
        """
        Find a matching pattern and return the Lua function with captured groups.

        Args:
            step_text: The step text to match

        Returns:
            Tuple of (lua_function, captured_groups) if match found, None otherwise
        """
        for pattern, lua_func in self._steps.items():
            match = pattern.match(step_text)
            if match:
                return lua_func, match.groups()
        return None

    def execute(self, step_text: str, context: Any) -> bool:
        """
        Execute custom Lua step if pattern matches.

        Args:
            step_text: The step text to match
            context: Test context object

        Returns:
            True if step was found and executed, False otherwise
        """
        result = self._match(step_text)
        if result:
            lua_func, groups = result
            try:
                # Call Lua function with context + captured groups
                lua_func(context, *groups)
                return True
            except Exception as e:
                logger.error(f"Custom step '{step_text}' failed: {e}")
                raise AssertionError(f"Custom step failed: {e}")

        return False

    def has_step(self, step_text: str) -> bool:
        """Check if any pattern matches the step text."""
        return self._match(step_text) is not None

    def get_all_patterns(self) -> list[str]:
        """Get all registered pattern strings."""
        return list(self._patterns.keys())

    def execute_by_pattern(self, pattern: str, context: Any, *args) -> bool:
        """
        Execute custom Lua step by pattern string with pre-captured args.

        This is used when the regex matching has already been done (e.g., by Behave)
        and we just need to call the Lua function with the captured groups.

        Args:
            pattern: The pattern string to look up
            context: Test context object
            *args: Captured groups from regex match

        Returns:
            True if step was found and executed, False otherwise
        """
        if pattern in self._patterns:
            compiled = self._patterns[pattern]
            lua_func = self._steps.get(compiled)
            if lua_func:
                try:
                    lua_func(context, *args)
                    return True
                except Exception as e:
                    logger.error(f"Custom step '{pattern}' failed: {e}")
                    raise AssertionError(f"Custom step failed: {e}")
        return False

    def clear(self) -> None:
        """Clear all custom steps."""
        self._steps.clear()
        self._patterns.clear()
