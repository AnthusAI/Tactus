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


def create_prediction(**kwargs: Any) -> TactusPrediction:
    """
    Create a new TactusPrediction directly.

    This is useful for creating prediction objects manually,
    e.g., in tests or when constructing results programmatically.

    Args:
        **kwargs: Field values for the prediction

    Returns:
        A TactusPrediction instance
    """
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
