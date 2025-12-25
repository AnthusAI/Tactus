"""
State Primitive - Mutable state management for procedures.

Provides:
- State.get(key, default) - Get state value
- State.set(key, value) - Set state value
- State.increment(key, amount) - Increment numeric value
- State.append(key, value) - Append to list
- State.all() - Get all state as table
"""

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


class StatePrimitive:
    """
    Manages mutable state for procedure execution.

    State is preserved across agent turns and can be used to track
    progress, accumulate results, and coordinate between agents.
    """

    def __init__(self, state_schema: Dict[str, Any] = None):
        """
        Initialize state storage.

        Args:
            state_schema: Optional state schema with field definitions and defaults
        """
        self._state: Dict[str, Any] = {}
        self._schema: Dict[str, Any] = state_schema or {}

        # Initialize state with defaults from schema
        for key, field_def in self._schema.items():
            if isinstance(field_def, dict) and "default" in field_def:
                self._state[key] = field_def["default"]

        logger.debug(f"StatePrimitive initialized with {len(self._schema)} schema fields")

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a value from state.

        Args:
            key: State key to retrieve
            default: Default value if key not found

        Returns:
            Stored value or default

        Example (Lua):
            local count = State.get("hypothesis_count", 0)
        """
        value = self._state.get(key, default)
        logger.debug(f"State.get('{key}') = {value}")
        return value

    def set(self, key: str, value: Any) -> None:
        """
        Set a value in state.

        Args:
            key: State key to set
            value: Value to store

        Example (Lua):
            State.set("current_phase", "exploration")
        """
        # Validate against schema if present
        if key in self._schema:
            field_def = self._schema[key]
            if isinstance(field_def, dict) and "type" in field_def:
                expected_type = field_def["type"]
                if not self._validate_type(value, expected_type):
                    logger.warning(
                        f"State.set('{key}'): value type {type(value).__name__} "
                        f"does not match schema type {expected_type}"
                    )

        self._state[key] = value
        logger.debug(f"State.set('{key}', {value})")

    def increment(self, key: str, amount: float = 1) -> float:
        """
        Increment a numeric value in state.

        Args:
            key: State key to increment
            amount: Amount to increment by (default 1)

        Returns:
            New value after increment

        Example (Lua):
            State.increment("hypotheses_filed")
            State.increment("score", 10)
        """
        current = self._state.get(key, 0)

        # Ensure numeric
        if not isinstance(current, (int, float)):
            logger.warning(f"State.increment: '{key}' is not numeric, resetting to 0")
            current = 0

        new_value = current + amount
        self._state[key] = new_value

        logger.debug(f"State.increment('{key}', {amount}) = {new_value}")
        return new_value

    def append(self, key: str, value: Any) -> None:
        """
        Append a value to a list in state.

        Args:
            key: State key (will be created as list if doesn't exist)
            value: Value to append

        Example (Lua):
            State.append("nodes_created", node_id)
        """
        if key not in self._state:
            self._state[key] = []
        elif not isinstance(self._state[key], list):
            logger.warning(f"State.append: '{key}' is not a list, converting")
            self._state[key] = [self._state[key]]

        self._state[key].append(value)
        logger.debug(f"State.append('{key}', {value}) -> list length: {len(self._state[key])}")

    def all(self) -> Dict[str, Any]:
        """
        Get all state as a dictionary.

        Returns:
            Complete state dictionary

        Example (Lua):
            local state = State.all()
            for k, v in pairs(state) do
                print(k, v)
            end
        """
        logger.debug(f"State.all() returning {len(self._state)} keys")
        return self._state.copy()

    def clear(self) -> None:
        """Clear all state (mainly for testing)."""
        self._state.clear()
        logger.debug("State.clear() - all state cleared")

    def _validate_type(self, value: Any, expected_type: str) -> bool:
        """
        Validate value against expected type from schema.

        Args:
            value: Value to validate
            expected_type: Expected type string (string, number, boolean, array, object)

        Returns:
            True if value matches expected type, False otherwise
        """
        type_mapping = {
            "string": str,
            "number": (int, float),
            "boolean": bool,
            "array": list,
            "object": dict,
        }

        expected_python_type = type_mapping.get(expected_type)
        if expected_python_type is None:
            logger.warning(f"Unknown type in schema: {expected_type}")
            return True  # Allow unknown types

        return isinstance(value, expected_python_type)

    def __repr__(self) -> str:
        return f"StatePrimitive({len(self._state)} keys)"
