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
from typing import Any

logger = logging.getLogger(__name__)


class StatePrimitive:
    """
    Manages mutable state for procedure execution.

    State is preserved across agent turns and can be used to track
    progress, accumulate results, and coordinate between agents.
    """

    def __init__(self, state_schema: dict[str, Any] | None = None):
        """
        Initialize state storage.

        Args:
            state_schema: Optional state schema with field definitions and defaults
        """
        self._state_values: dict[str, Any] = {}
        self._state = self._state_values
        self._schema_definitions: dict[str, Any] = state_schema or {}

        # Initialize state with defaults from schema
        for state_key, schema_field_definition in self._schema_definitions.items():
            if isinstance(schema_field_definition, dict) and "default" in schema_field_definition:
                self._state_values[state_key] = schema_field_definition["default"]

        logger.debug(
            "StatePrimitive initialized with %s schema fields",
            len(self._schema_definitions),
        )

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
        stored_value = self._state_values.get(key, default)
        logger.debug("State.get('%s') = %s", key, stored_value)
        return stored_value

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
        if key in self._schema_definitions:
            schema_field_definition = self._schema_definitions[key]
            if isinstance(schema_field_definition, dict) and "type" in schema_field_definition:
                expected_type = schema_field_definition["type"]
                if not self._is_value_matching_schema_type(value, expected_type):
                    logger.warning(
                        "State.set('%s'): value type %s does not match schema type %s",
                        key,
                        type(value).__name__,
                        expected_type,
                    )

        self._state_values[key] = value
        logger.debug("State.set('%s', %s)", key, value)

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
        current_value = self._state_values.get(key, 0)

        # Ensure numeric
        if not isinstance(current_value, (int, float)):
            logger.warning("State.increment: '%s' is not numeric, resetting to 0", key)
            current_value = 0

        new_value = current_value + amount
        self._state_values[key] = new_value

        logger.debug("State.increment('%s', %s) = %s", key, amount, new_value)
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
        if key not in self._state_values:
            self._state_values[key] = []
        elif not isinstance(self._state_values[key], list):
            logger.warning("State.append: '%s' is not a list, converting", key)
            self._state_values[key] = [self._state_values[key]]

        self._state_values[key].append(value)
        logger.debug(
            "State.append('%s', %s) -> list length: %s",
            key,
            value,
            len(self._state_values[key]),
        )

    def all(self) -> dict[str, Any]:
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
        logger.debug("State.all() returning %s keys", len(self._state_values))
        return self._state_values.copy()

    def clear(self) -> None:
        """Clear all state (mainly for testing)."""
        self._state_values.clear()
        logger.debug("State.clear() - all state cleared")

    def _is_value_matching_schema_type(self, value: Any, expected_type: str) -> bool:
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
            logger.warning("Unknown type in schema: %s", expected_type)
            return True  # Allow unknown types

        return isinstance(value, expected_python_type)

    def __repr__(self) -> str:
        return f"StatePrimitive({len(self._state_values)} keys)"
