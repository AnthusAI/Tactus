"""
Protocol definitions for model registry.
"""

from dataclasses import dataclass
from typing import Any, List, Optional, Protocol


@dataclass
class ModelVersion:
    """Metadata for a specific model version."""

    name: str  # Model name
    version: str  # Version identifier (e.g., "v1.0.0", "20240215-143022")
    backend_type: str  # Backend type (http, pytorch, llm, etc.)
    backend_config: dict  # Backend-specific configuration
    created_at: str  # ISO timestamp
    tags: List[str]  # Tags like "champion", "challenger", "staging"
    metadata: Optional[dict] = None  # Additional metadata


@dataclass
class PredictionLog:
    """Log entry for a model prediction."""

    model_id: str  # Model name:version
    timestamp: str  # ISO timestamp
    input_data: Any  # Input to the model
    output_data: Any  # Output from the model
    cost: Optional[float] = None  # Inference cost
    latency_ms: Optional[float] = None  # Latency in milliseconds


class ModelRegistry(Protocol):
    """Protocol for model registry implementations."""

    def register(
        self,
        name: str,
        version: str,
        backend_type: str,
        backend_config: dict,
        tags: Optional[List[str]] = None,
        metadata: Optional[dict] = None,
        artifact: Optional[bytes] = None,
        artifact_path: Optional[str] = None,
        artifact_filename: str = "artifact.bin",
    ) -> ModelVersion:
        """
        Register a new model version.

        Args:
            name: Model name
            version: Version identifier
            backend_type: Type of backend (http, pytorch, llm, etc.)
            backend_config: Backend configuration
            tags: Optional list of tags (e.g., ["champion"])
            metadata: Optional additional metadata
            artifact: Optional artifact bytes to persist
            artifact_path: Existing artifact URI/path to record
            artifact_filename: Filename to use when persisting bytes

        Returns:
            ModelVersion object for the registered version
        """
        ...

    def resolve(self, name: str, version: Optional[str] = None) -> ModelVersion:
        """
        Resolve a model by name and version/tag.

        Args:
            name: Model name
            version: Version identifier or tag (e.g., "v1.0.0", "champion", "latest")
                    If None, resolves to "champion" or latest version

        Returns:
            ModelVersion object

        Raises:
            KeyError: If model or version not found
        """
        ...

    def list_versions(self, name: str) -> List[ModelVersion]:
        """
        List all versions of a model.

        Args:
            name: Model name

        Returns:
            List of ModelVersion objects, sorted by creation time (newest first)
        """
        ...

    def promote(self, name: str, version: str, tag: str) -> None:
        """
        Promote a version by adding/moving a tag.

        When promoting to "champion", the previous champion is automatically
        tagged as "champion-previous" for rollback capability.

        Args:
            name: Model name
            version: Version to promote
            tag: Tag to add (e.g., "champion", "staging", "production")

        Raises:
            KeyError: If model or version not found
        """
        ...

    def log_prediction(
        self,
        model_id: str,
        input_data: Any,
        output_data: Any,
        cost: Optional[float] = None,
        latency_ms: Optional[float] = None,
    ) -> None:
        """
        Log a prediction for monitoring and analysis.

        Args:
            model_id: Model identifier (name:version)
            input_data: Input to the model
            output_data: Output from the model
            cost: Optional inference cost
            latency_ms: Optional latency in milliseconds
        """
        ...
