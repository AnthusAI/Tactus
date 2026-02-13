"""
Registry backend for Model primitive.

Resolves model versions from a registry and delegates to the appropriate backend.
"""

import logging
from typing import Any, Optional

from tactus.backends.model_backend import ModelBackend
from tactus.registry.storage import resolve_path

logger = logging.getLogger(__name__)


class RegistryBackend(ModelBackend):
    """
    Backend that resolves models from a registry.

    This is a wrapper backend that:
    1. Resolves the model version from the registry
    2. Creates the appropriate backend based on registry metadata
    3. Delegates predict() calls to the resolved backend
    """

    def __init__(
        self,
        registry: Any,  # ModelRegistry protocol
        model_name: str,
        version: Optional[str] = None,
        fallback_config: Optional[dict] = None,
    ):
        """
        Initialize registry backend.

        Args:
            registry: ModelRegistry implementation
            model_name: Name of the model in the registry
            version: Version identifier or tag (e.g., "champion", "v1.0.0")
            fallback_config: Optional fallback configuration if resolution fails
        """
        self.registry = registry
        self.model_name = model_name
        self.version = version
        self.fallback_config = fallback_config
        self._resolved_backend: Optional[ModelBackend] = None
        self._resolved_version_id: Optional[str] = None

    def _resolve_backend(self) -> ModelBackend:
        """
        Resolve the backend from the registry.

        Returns:
            Resolved ModelBackend instance

        Raises:
            ValueError: If resolution fails and no fallback is configured
        """
        if self._resolved_backend is not None:
            return self._resolved_backend

        try:
            # Resolve from registry
            model_version = self.registry.resolve(self.model_name, self.version)
            self._resolved_version_id = model_version.version_id

            logger.info(
                f"Resolved {self.model_name}:{self.version or 'latest'} "
                f"to version {model_version.version_id}"
            )

            # Create backend from registry metadata
            backend = self._create_backend_from_version(model_version)
            self._resolved_backend = backend
            return backend

        except ValueError as e:
            # Resolution failed
            if self.fallback_config is not None:
                logger.warning(
                    f"Failed to resolve {self.model_name}:{self.version} from registry: {e}. "
                    f"Using fallback configuration."
                )
                backend = self._create_backend_from_config(self.fallback_config)
                self._resolved_backend = backend
                return backend
            else:
                raise ValueError(
                    f"Failed to resolve {self.model_name}:{self.version} from registry "
                    f"and no fallback configured: {e}"
                ) from e

    def _create_backend_from_version(self, model_version: Any) -> ModelBackend:
        """Create a backend from ModelVersion metadata."""
        backend_type = model_version.backend_type
        backend_config = dict(model_version.backend_config)

        # Prefer stored artifact path if present
        if getattr(model_version, "artifact_path", None) and "path" not in backend_config:
            backend_config["path"] = model_version.artifact_path

        return self._create_backend_from_config(
            {"type": backend_type, **backend_config}
        )

    def _create_backend_from_config(self, config: dict) -> ModelBackend:
        """Create a backend from configuration dict."""
        backend_type = config.get("type")

        if backend_type == "http":
            from tactus.backends.http_backend import HTTPModelBackend

            return HTTPModelBackend(
                endpoint=config["endpoint"],
                timeout=config.get("timeout", 30.0),
                headers=config.get("headers"),
                cost_per_call=config.get("cost_per_call"),
            )

        elif backend_type == "pytorch":
            from tactus.backends.pytorch_backend import PyTorchModelBackend

            path = config["path"]
            resolved_path = resolve_path(
                path,
                cache_dir=config.get("cache_dir"),
                client=config.get("s3_client"),
            )

            return PyTorchModelBackend(
                path=resolved_path,
                device=config.get("device", "cpu"),
                labels=config.get("labels"),
            )

        elif backend_type == "llm":
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
            )

        else:
            raise ValueError(f"Unknown backend type: {backend_type}")

    def predict_sync(self, input_data: Any) -> Any:
        """
        Synchronous prediction using resolved backend.

        Args:
            input_data: Input to the model

        Returns:
            Model prediction result
        """
        backend = self._resolve_backend()
        return backend.predict_sync(input_data)

    async def predict(self, input_data: Any) -> Any:
        """
        Asynchronous prediction using resolved backend.

        Args:
            input_data: Input to the model

        Returns:
            Model prediction result
        """
        backend = self._resolve_backend()
        return await backend.predict(input_data)

    @property
    def resolved_version_id(self) -> Optional[str]:
        """Return the resolved version ID, if resolved."""
        return self._resolved_version_id
