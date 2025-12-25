"""
Model backend protocol for ML inference.

Defines the interface that all model backends must implement.
"""

from typing import Any, Protocol


class ModelBackend(Protocol):
    """Protocol for model inference backends."""

    async def predict(self, input_data: Any) -> Any:
        """
        Run inference on input data.

        Args:
            input_data: Input to the model (format depends on backend)

        Returns:
            Model prediction result
        """
        ...

    def predict_sync(self, input_data: Any) -> Any:
        """
        Synchronous version of predict.

        Args:
            input_data: Input to the model (format depends on backend)

        Returns:
            Model prediction result
        """
        ...
