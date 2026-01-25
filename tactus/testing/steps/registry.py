"""
Step registry for pattern matching and execution.
"""

import re
import logging
from typing import Callable, Dict, Optional, Pattern, Tuple

logger = logging.getLogger(__name__)


class StepRegistry:
    """
    Registry of step definitions with regex pattern matching.

    Matches step text against registered patterns and executes
    the corresponding step functions.
    """

    def __init__(self):
        self._steps: Dict[Pattern, Callable] = {}
        self._step_patterns: Dict[str, Pattern] = {}  # pattern_str -> compiled pattern

    def register(self, pattern: str, func: Callable, step_type: str = "any") -> None:
        """
        Register a step with regex pattern.

        Args:
            pattern: Regex pattern to match step text
            func: Function to execute when pattern matches
            step_type: Type of step (given, when, then, any)
        """
        try:
            compiled = re.compile(pattern, re.IGNORECASE)
            self._steps[compiled] = func
            self._step_patterns[pattern] = compiled
            logger.debug(f"Registered step pattern: {pattern}")
        except re.error as e:
            logger.error(f"Invalid regex pattern '{pattern}': {e}")
            raise ValueError(f"Invalid step pattern: {e}")

    def match(self, step_text: str) -> Optional[Tuple[Callable, dict]]:
        """
        Find matching step function for given step text.

        Args:
            step_text: The step text to match

        Returns:
            Tuple of (function, match_groups) or None if no match
        """
        for pattern, func in self._steps.items():
            match = pattern.match(step_text)
            if match:
                # Return function and captured groups as dict
                return func, match.groupdict()

        return None

    def get_all_patterns(self) -> list[str]:
        """Get all registered pattern strings."""
        return list(self._step_patterns.keys())

    def clear(self) -> None:
        """Clear all registered steps."""
        self._steps.clear()
        self._step_patterns.clear()
