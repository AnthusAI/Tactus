"""
DSPy Prediction integration for Tactus.

This module provides the Prediction primitive that maps to DSPy Prediction,
representing the output of DSPy Module calls with convenient access methods.
"""

from typing import Any, Dict

import dspy


class TactusPrediction:
    """
    A Tactus wrapper around DSPy Prediction.

    This class provides a convenient API for accessing prediction results
    from DSPy Modules. It wraps the native DSPy Prediction while adding
    Tactus-specific convenience methods.

    Attributes are accessible directly:
        result = module(question="What is 2+2?")
        print(result.answer)  # Access output field

    Example usage in Lua:
        local result = qa_module({ question = "What is 2+2?" })

        -- Access output fields
        print(result.answer)

        -- Get all output values as a table
        local data = result.data()

        -- Check if prediction has a specific field
        if result.has("reasoning") then
            print(result.reasoning)
        end
    """

    def __init__(self, dspy_prediction: dspy.Prediction):
        """
        Initialize a TactusPrediction from a DSPy Prediction.

        Args:
            dspy_prediction: The DSPy Prediction object to wrap
        """
        self._prediction = dspy_prediction

    def __getattr__(self, name: str) -> Any:
        """
        Access prediction fields as attributes.

        Delegates to the underlying DSPy Prediction.
        """
        if name.startswith("_"):
            raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")
        return getattr(self._prediction, name)

    def data(self) -> Dict[str, Any]:
        """
        Get all prediction data as a dictionary.

        Returns:
            Dict containing all output fields and their values
        """
        return dict(self._prediction)

    def has(self, field_name: str) -> bool:
        """
        Check if the prediction has a specific field.

        Args:
            field_name: The field to check for

        Returns:
            True if the field exists in the prediction
        """
        return hasattr(self._prediction, field_name)

    def get(self, field_name: str, default: Any = None) -> Any:
        """
        Get a field value with a default if not present.

        Args:
            field_name: The field to get
            default: Default value if field doesn't exist

        Returns:
            The field value or default
        """
        return getattr(self._prediction, field_name, default)

    def to_dspy(self) -> dspy.Prediction:
        """
        Get the underlying DSPy Prediction.

        Returns:
            The wrapped dspy.Prediction object
        """
        return self._prediction

    @classmethod
    def from_dspy(cls, prediction: dspy.Prediction) -> "TactusPrediction":
        """
        Create a TactusPrediction from a DSPy Prediction.

        Args:
            prediction: A dspy.Prediction instance

        Returns:
            A TactusPrediction instance
        """
        return cls(prediction)

    @property
    def message(self) -> str:
        """
        Get the message content from the prediction.

        This is a convenience property that tries common field names
        for message content. Useful for accessing agent responses.

        Returns:
            The message content, or empty string if not found

        Priority order:
            1. response (most common for agent responses)
            2. text
            3. answer
            4. content
            5. output
            6. First string field found
            7. Empty string if nothing found
        """
        # Try common field names in priority order
        for field in ["response", "text", "answer", "content", "output"]:
            value = getattr(self._prediction, field, None)
            if value is not None and isinstance(value, str):
                return value

        # Fall back to first string value found
        for key in dir(self._prediction):
            if not key.startswith("_"):
                value = getattr(self._prediction, key, None)
                if value is not None and isinstance(value, str):
                    return value

        return ""


def validate_field_name(field_name: str) -> bool:
    """
    Validate prediction field name.

    Args:
        field_name: Field name to validate

    Returns:
        True if field name is valid, False otherwise
    """
    import re

    # Field names must start with a letter or underscore, followed by
    # optional letters, digits, or underscores
    return re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", field_name) is not None


def validate_field_type(field_name: str, value: Any, schema: Dict[str, Any] = None) -> bool:
    """
    Validate prediction field type.

    Args:
        field_name: Name of the field
        value: Value to validate
        schema: Optional type schema

    Returns:
        True if field type is valid, False otherwise
    """
    # Default type validation if no schema provided
    if schema is None:
        return True

    type_mapping = {
        "str": str,
        "int": int,
        "float": float,
        "bool": bool,
        "list": list,
    }

    field_type = schema.get("fields", {}).get(field_name, {}).get("type")
    if field_type:
        expected_type = type_mapping.get(field_type)
        return isinstance(value, expected_type) if expected_type else False

    return True


def create_prediction(**kwargs: Any) -> TactusPrediction:
    """
    Create a new TactusPrediction directly.

    This is useful for creating prediction objects manually,
    e.g., in tests or when constructing results programmatically.

    Args:
        **kwargs: Field values for the prediction

    Returns:
        A TactusPrediction instance

    Raises:
        ValueError: For invalid field names or missing required fields
    """
    # Validate field names
    for field in kwargs.keys():
        if not validate_field_name(field):
            raise ValueError(f"Invalid field name: {field}")

    # Optional schema validation (can be injected via special key)
    schema = kwargs.pop("__schema__", {}) if "__schema__" in kwargs else {}

    # Validate required fields
    required_fields = schema.get("required", [])
    for field in required_fields:
        if field not in kwargs:
            raise ValueError(f"Required field missing: {field}")

    # Validate field types
    for field, value in kwargs.items():
        if not validate_field_type(field, value, schema):
            expected_type = schema.get("fields", {}).get(field, {}).get("type")
            raise TypeError(
                f"Field {field} type mismatch. Expected {expected_type}, got {type(value).__name__}"
            )

    # Create and return the Prediction
    return TactusPrediction(dspy.Prediction(**kwargs))


def wrap_prediction(dspy_prediction: dspy.Prediction) -> TactusPrediction:
    """
    Wrap a DSPy Prediction in a TactusPrediction.

    Args:
        dspy_prediction: The DSPy Prediction to wrap

    Returns:
        A TactusPrediction instance
    """
    return TactusPrediction(dspy_prediction)
