"""
Model primitive for ML inference with automatic checkpointing.
"""

import logging
import time
from typing import Any, Optional, Type

from pydantic import BaseModel, ValidationError
from tactus.core.execution_context import ExecutionContext
from tactus.models.schema import resolve_schema
from tactus.models.types import PredictionCost, PredictionResult

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
        context: Optional[ExecutionContext] = None,
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

        # Resolve input/output schemas to Pydantic models
        self.input_schema_dict = config.get("input", {})
        self.output_schema_dict = config.get("output", {})

        try:
            self.input_schema: Optional[Type[BaseModel]] = resolve_schema(
                self.input_schema_dict, f"{model_name}_Input"
            )
            self.output_schema: Optional[Type[BaseModel]] = resolve_schema(
                self.output_schema_dict, f"{model_name}_Output"
            )
        except (ImportError, AttributeError, TypeError) as e:
            raise ValueError(f"Failed to resolve schema for model '{model_name}': {e}") from e

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

        if model_type == "llm":
            from tactus.backends.llm_backend import LLMModelBackend

            return LLMModelBackend(
                model=config["model"],
                system_prompt=config.get("system_prompt", ""),
                provider=config.get("provider"),
                temperature=config.get("temperature", 0.0),
                max_tokens=config.get("max_tokens"),
                retries=config.get("retries", 3),
                retry_prompt=config.get("retry_prompt"),
                parse_direction=config.get("parse_direction", "end"),
                mock_manager=self.mock_manager,
                registry=None,  # TODO: Pass registry when available
                execution_context=None,  # Don't checkpoint internal agent turns
            )

        raise ValueError(f"Unknown model type: {model_type}. Supported types: http, pytorch, llm")

    def predict(self, input_data: Any) -> Any:
        """
        Run model inference with automatic checkpointing.

        Args:
            input_data: Input to the model (format depends on backend)

        Returns:
            Model prediction result
        """
        if self.context is None:
            # No context - run directly without checkpointing but still validate
            return self._execute_predict(input_data)

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
            Model prediction result (wrapped in PredictionResult)

        Raises:
            ValidationError: If input_data doesn't match input_schema
        """
        # Validate input if schema is defined
        if self.input_schema is not None:
            try:
                # For dict input, validate directly
                if isinstance(input_data, dict):
                    validated_input = self.input_schema(**input_data)
                    input_data = validated_input.model_dump()
                else:
                    # For non-dict, wrap in a dict with single "input" field if schema expects it
                    # Otherwise, validation will fail with clear error message
                    validated_input = self.input_schema(input=input_data)
                    input_data = validated_input.model_dump()["input"]
            except ValidationError as e:
                logger.error(
                    f"Model '{self.model_name}' input validation failed: {e}",
                    extra={"model_name": self.model_name, "input_data": input_data},
                )
                raise

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
                # Return raw mock result for backward compatibility
                return mock_result

        # Track timing
        start_time = time.perf_counter()
        result = self.backend.predict_sync(input_data)
        elapsed_ms = (time.perf_counter() - start_time) * 1000

        # Extract cost and output from backend result
        # LLM backend returns: {"result": <output>, "cost": {...}, "usage": {...}}
        # HTTP/PyTorch backends return raw output
        if isinstance(result, dict) and "result" in result and "cost" in result:
            # LLM backend format (has both "result" and "cost" keys)
            output = result["result"]
            backend_cost = result.get("cost", {})
            backend_usage = result.get("usage", {})

            # Create PredictionCost from backend data
            cost = PredictionCost(
                inference_cost=backend_cost.get("total_cost"),
                compute_time_ms=elapsed_ms,
                tokens_in=backend_usage.get("prompt_tokens"),
                tokens_out=backend_usage.get("completion_tokens"),
            )
        else:
            # HTTP/PyTorch backend format (raw output)
            output = result
            cost = PredictionCost(compute_time_ms=elapsed_ms)

        # Validate output if schema is defined
        if self.output_schema is not None:
            try:
                if isinstance(output, dict):
                    _ = self.output_schema(**output)
                else:
                    # Wrap non-dict result
                    _ = self.output_schema(output=output)
            except ValidationError as e:
                # Log warning but don't fail - backend may be external/untrusted
                logger.warning(
                    f"Model '{self.model_name}' output validation failed: {e}. "
                    f"Backend returned: {output}",
                    extra={"model_name": self.model_name, "result": output},
                )

        # Wrap in PredictionResult
        prediction_result = PredictionResult(
            output=output, cost=cost, model_version=None, backend_type=self.config.get("type")
        )

        return prediction_result

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
