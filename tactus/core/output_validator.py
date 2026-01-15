"""
Output Schema Validator for Lua DSL Procedures

Validates that Lua workflow return values match the declared output schema.
Enables type safety and composability for sub-agent workflows.
"""

import logging
from typing import Any, Optional, List

logger = logging.getLogger(__name__)


class OutputValidationError(Exception):
    """Raised when workflow output doesn't match schema."""

    pass


class OutputValidator:
    """
    Validates procedure output against declared schema.

    Supports:
    - Type checking (string, number, boolean, object, array)
    - Required field validation
    - Nested object validation
    - Clear error messages
    """

    # Type mapping from YAML to Python
    TYPE_MAP = {
        "string": str,
        "number": (int, float),
        "boolean": bool,
        "object": dict,
        "array": list,
    }

    @classmethod
    def _is_scalar_schema(cls, schema: Any) -> bool:
        return (
            isinstance(schema, dict)
            and "type" in schema
            and isinstance(schema.get("type"), str)
            and schema.get("type") in cls.TYPE_MAP
        )

    def __init__(self, output_schema: Optional[Any] = None):
        """
        Initialize validator with output schema.

        Args:
            output_schema: Dict of output field definitions
                Example:
                {
                    'limerick': {
                        'type': 'string',
                        'required': True,
                        'description': 'The generated limerick'
                    },
                    'node_id': {
                        'type': 'string',
                        'required': False
                    }
                }
        """
        self.schema = output_schema or {}

        if self._is_scalar_schema(self.schema):
            logger.debug("OutputValidator initialized with scalar output schema")
        else:
            try:
                field_count = len(self.schema)
            except TypeError:
                field_count = 0
            logger.debug(f"OutputValidator initialized with {field_count} output fields")

    def validate(self, output: Any) -> Any:
        """
        Validate workflow output against schema.

        Args:
            output: The return value from Lua workflow

        Returns:
            Validated output dict

        Raises:
            OutputValidationError: If validation fails
        """
        # If a procedure returns a Result wrapper, validate its `.output` payload
        # while preserving the wrapper (so callers can still access usage/cost/etc.).
        from tactus.protocols.result import TactusResult

        wrapped_result: TactusResult | None = output if isinstance(output, TactusResult) else None
        if wrapped_result is not None:
            output = wrapped_result.output

        # If no schema defined, accept any output
        if not self.schema:
            logger.debug("No output schema defined, skipping validation")
            if isinstance(output, dict):
                validated_payload = output
            elif hasattr(output, "items"):
                # Lua table - convert to dict
                validated_payload = dict(output.items())
            else:
                validated_payload = output

            if wrapped_result is not None:
                return wrapped_result.model_copy(update={"output": validated_payload})
            return validated_payload

        # Scalar output schema: `output = field.string{...}` etc.
        if self._is_scalar_schema(self.schema):
            # Lua tables are not valid scalar outputs.
            if hasattr(output, "items") and not isinstance(output, dict):
                output = dict(output.items())

            is_required = self.schema.get("required", False)
            if output is None and not is_required:
                return None

            expected_type = self.schema.get("type")
            if expected_type and not self._check_type(output, expected_type):
                raise OutputValidationError(
                    f"Output should be {expected_type}, got {type(output).__name__}"
                )

            if "enum" in self.schema and self.schema["enum"]:
                allowed_values = self.schema["enum"]
                if output not in allowed_values:
                    raise OutputValidationError(
                        f"Output has invalid value '{output}'. Allowed values: {allowed_values}"
                    )

            validated_payload = output
            if wrapped_result is not None:
                return wrapped_result.model_copy(update={"output": validated_payload})
            return validated_payload

        # Convert Lua tables to dicts recursively
        if hasattr(output, "items") or isinstance(output, dict):
            logger.debug("Converting Lua tables to Python dicts recursively")
            output = self._convert_lua_tables(output)

        # Output must be a dict/table
        if not isinstance(output, dict):
            raise OutputValidationError(
                f"Output must be an object/table, got {type(output).__name__}"
            )

        errors = []
        validated_output = {}

        # Check required fields and validate types
        for field_name, field_def in self.schema.items():
            if not isinstance(field_def, dict) or "type" not in field_def:
                errors.append(
                    f"Field '{field_name}' uses old type syntax. "
                    f"Use field.{field_def.get('type', 'string')}{{}} instead."
                )
                continue
            is_required = bool(field_def.get("required", False))

            if is_required and field_name not in output:
                errors.append(f"Required field '{field_name}' is missing")
                continue

            # Skip validation if field not present and not required
            if field_name not in output:
                continue

            value = output[field_name]

            # Type checking
            expected_type = field_def.get("type")
            if expected_type:
                if not self._check_type(value, expected_type):
                    actual_type = type(value).__name__
                    errors.append(
                        f"Field '{field_name}' should be {expected_type}, got {actual_type}"
                    )

            # Enum validation
            if "enum" in field_def and field_def["enum"]:
                allowed_values = field_def["enum"]
                if value not in allowed_values:
                    errors.append(
                        f"Field '{field_name}' has invalid value '{value}'. "
                        f"Allowed values: {allowed_values}"
                    )

            # Add to validated output (only declared fields)
            validated_output[field_name] = value

        # Filter undeclared fields (only return declared fields)
        for field_name in output:
            if field_name not in self.schema:
                logger.debug(f"Filtering undeclared field '{field_name}' from output")

        if errors:
            error_msg = "Output validation failed:\n  " + "\n  ".join(errors)
            raise OutputValidationError(error_msg)

        logger.info(f"Output validation passed for {len(validated_output)} fields")
        if wrapped_result is not None:
            return wrapped_result.model_copy(update={"output": validated_output})
        return validated_output

    def _check_type(self, value: Any, expected_type: str) -> bool:
        """
        Check if value matches expected type.

        Args:
            value: The value to check
            expected_type: Expected type string ('string', 'number', etc.)

        Returns:
            True if type matches
        """
        if value is None:
            # None is acceptable for optional fields
            return True

        python_type = self.TYPE_MAP.get(expected_type)
        if not python_type:
            logger.warning(f"Unknown type '{expected_type}', skipping validation")
            return True

        # Handle Lua tables as dicts/arrays
        if expected_type in ("object", "array"):
            if hasattr(value, "items") or hasattr(value, "__iter__"):
                return True

        return isinstance(value, python_type)

    def _convert_lua_tables(self, obj: Any) -> Any:
        """
        Recursively convert Lua tables to Python dicts/lists.

        Args:
            obj: Object to convert

        Returns:
            Converted object
        """
        # Handle Lua tables (have .items() method)
        if hasattr(obj, "items") and not isinstance(obj, dict):
            return {k: self._convert_lua_tables(v) for k, v in obj.items()}

        # Handle lists
        elif isinstance(obj, (list, tuple)):
            return [self._convert_lua_tables(item) for item in obj]

        # Handle dicts
        elif isinstance(obj, dict):
            return {k: self._convert_lua_tables(v) for k, v in obj.items()}

        # Return as-is for primitives
        else:
            return obj

    def get_field_description(self, field_name: str) -> Optional[str]:
        """Get description for an output field."""
        if field_name in self.schema:
            field_def = self.schema[field_name]
            if isinstance(field_def, dict):
                return field_def.get("description")
        return None

    def get_required_fields(self) -> List[str]:
        """Get list of required output fields."""
        from tactus.core.dsl_stubs import FieldDefinition

        return [
            name
            for name, def_ in self.schema.items()
            if isinstance(def_, FieldDefinition) and def_.get("required", False)
        ]

    def get_optional_fields(self) -> List[str]:
        """Get list of optional output fields."""
        from tactus.core.dsl_stubs import FieldDefinition

        return [
            name
            for name, def_ in self.schema.items()
            if isinstance(def_, FieldDefinition) and not def_.get("required", False)
        ]
