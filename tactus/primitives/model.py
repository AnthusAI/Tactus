"""
Model primitive for ML inference with automatic checkpointing.
"""

import logging
from typing import Any

from tactus.core.execution_context import ExecutionContext

logger = logging.getLogger(__name__)


class ModelPrimitive:
    """
    Model primitive for ML inference operations.

    Unlike agents (conversational LLMs), models handle:
    - Classification (sentiment, intent, NER)
    - Extraction (quotes, entities, facts)
    - Embeddings (semantic search, clustering)
    - Custom ML inference (any trained model)

    Each .predict() call is automatically checkpointed for durability.
    """

    def __init__(self, model_name: str, config: dict, context: ExecutionContext | None = None):
        """
        Initialize model primitive.

        Args:
            model_name: Name of the model (for checkpointing)
            config: Model configuration dict with:
                - type: Backend type (http, pytorch, bert, sklearn, etc.)
                - Backend-specific config (endpoint, path, etc.)
            context: Execution context for checkpointing
        """
        self.model_name = model_name
        self.config = config
        self.context = context
        self.backend = self._create_backend(config)

    def _create_backend(self, config: dict):
        """
        Create appropriate backend based on model type.

        Args:
            config: Model configuration

        Returns:
            Backend instance
        """
        model_type = config.get("type")

        if model_type == "http":
            from tactus.backends.http_backend import HTTPModelBackend

            return HTTPModelBackend(
                endpoint=config["endpoint"],
                timeout=config.get("timeout", 30.0),
                headers=config.get("headers"),
            )

        elif model_type == "pytorch":
            from tactus.backends.pytorch_backend import PyTorchModelBackend

            return PyTorchModelBackend(
                path=config["path"],
                device=config.get("device", "cpu"),
                labels=config.get("labels"),
            )

        else:
            raise ValueError(
                f"Unknown model type: {model_type}. " f"Supported types: http, pytorch"
            )

    def predict(self, input_data: Any) -> Any:
        """
        Run model inference with automatic checkpointing.

        Args:
            input_data: Input to the model (format depends on backend)

        Returns:
            Model prediction result
        """
        if self.context is None:
            # No context - run directly without checkpointing
            return self.backend.predict_sync(input_data)

        # With context - checkpoint the operation

        return self.context.checkpoint(
            fn=lambda: self._execute_predict(input_data),
            operation_type="model_predict",
        )

    def _execute_predict(self, input_data: Any) -> Any:
        """
        Execute the actual prediction.

        Args:
            input_data: Input to the model

        Returns:
            Model prediction result
        """
        return self.backend.predict_sync(input_data)

    def __repr__(self) -> str:
        return f"ModelPrimitive({self.model_name}, type={self.config.get('type')})"
