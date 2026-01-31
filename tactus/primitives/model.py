"""
Model primitive for ML inference with automatic checkpointing.
"""

import logging
from typing import Any, Optional

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

    def __init__(
        self,
        model_name: str,
        config: dict,
        context: ExecutionContext | None = None,
        mock_manager: Optional[Any] = None,
    ):
        """
        Initialize model primitive.

        Args:
            model_name: Name of the model (for checkpointing)
            config: Model configuration dict with:
                - type: Backend type (http, pytorch, bert, sklearn, etc.)
                - input: Optional input schema
                - output: Optional output schema
                - Backend-specific config (endpoint, path, etc.)
            context: Execution context for checkpointing
        """
        self.model_name = model_name
        self.config = config
        self.context = context
        self.mock_manager = mock_manager

        # Extract optional input/output schemas
        self.input_schema = config.get("input", {})
        self.output_schema = config.get("output", {})

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

        if model_type == "pytorch":
            from tactus.backends.pytorch_backend import PyTorchModelBackend

            return PyTorchModelBackend(
                path=config["path"],
                device=config.get("device", "cpu"),
                labels=config.get("labels"),
            )

        raise ValueError(f"Unknown model type: {model_type}. Supported types: http, pytorch")

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
        # Capture source location
        import inspect

        current_frame = inspect.currentframe()
        if current_frame and current_frame.f_back:
            caller_frame = current_frame.f_back
            source_info = {
                "file": caller_frame.f_code.co_filename,
                "line": caller_frame.f_lineno,
                "function": caller_frame.f_code.co_name,
            }
        else:
            source_info = None

        return self.context.checkpoint(
            fn=lambda: self._execute_predict(input_data),
            checkpoint_type="model_predict",
            source_info=source_info,
        )

    def _execute_predict(self, input_data: Any) -> Any:
        """
        Execute the actual prediction.

        Args:
            input_data: Input to the model

        Returns:
            Model prediction result
        """
        if self.mock_manager is not None:
            args_payload = input_data if isinstance(input_data, dict) else {"input": input_data}
            mock_result = self.mock_manager.get_mock_response(
                self.model_name,
                args_payload,
            )
            if mock_result is not None:
                # Ensure temporal mocks advance and calls are available for assertions.
                try:
                    self.mock_manager.record_call(
                        self.model_name,
                        args_payload,
                        mock_result,
                    )
                except Exception:
                    pass
                return mock_result

        return self.backend.predict_sync(input_data)

    def __call__(self, input_data: Any) -> Any:
        """
        Execute model inference using the callable interface.

        This is an alias for predict() that enables the unified callable syntax:
            result = classifier({text = "Hello"})

        Args:
            input_data: Input to the model (format depends on backend)

        Returns:
            Model prediction result
        """
        return self.predict(input_data)

    def __repr__(self) -> str:
        return f"ModelPrimitive({self.model_name}, type={self.config.get('type')})"
