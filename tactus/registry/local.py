"""
Local filesystem-based model registry implementation.

Stores model metadata and artifacts in a local directory structure:
    ~/.tactus/models/
    └── {model_name}/
        ├── metadata.json          # Registry metadata
        ├── versions/
        │   ├── {version_id}.json  # Version metadata
        │   └── {version_id}/      # Artifact files
        └── tags/
            └── {tag_name}.json    # Tag pointers
"""

import json
import logging
import os
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from tactus.registry.storage import LocalStorage, ModelStorage

logger = logging.getLogger(__name__)


@dataclass
class ModelVersion:
    """Metadata for a specific model version."""

    version_id: str  # Unique version identifier
    model_name: str  # Model name
    backend_type: str  # Backend type (pytorch, http, llm, etc.)
    backend_config: Dict[str, Any]  # Backend-specific configuration
    tags: List[str]  # Tags applied to this version (champion, staging, etc.)
    metadata: Dict[str, Any]  # User-provided metadata
    created_at: float  # Unix timestamp
    artifact_path: Optional[str] = None  # Path to model artifact (if applicable)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ModelVersion":
        """Create from dictionary."""
        return cls(**data)


class LocalRegistry:
    """
    Local filesystem-based model registry.

    Implements the ModelRegistry protocol for development and small projects.
    """

    def __init__(self, registry_dir: Optional[str] = None, storage: Optional[ModelStorage] = None):
        """
        Initialize local registry.

        Args:
            registry_dir: Directory to store registry data. Defaults to ~/.tactus/models/
            storage: Storage backend for artifacts. Defaults to LocalStorage rooted in registry_dir.
        """
        if registry_dir is None:
            registry_dir = os.path.expanduser("~/.tactus/models")
        self.registry_dir = Path(registry_dir)
        self.registry_dir.mkdir(parents=True, exist_ok=True)
        self.storage = storage or LocalStorage(base_dir=self.registry_dir / "artifacts")

    def _model_dir(self, name: str) -> Path:
        """Get directory for a specific model."""
        return self.registry_dir / name

    def _versions_dir(self, name: str) -> Path:
        """Get versions directory for a model."""
        return self._model_dir(name) / "versions"

    def _tags_dir(self, name: str) -> Path:
        """Get tags directory for a model."""
        return self._model_dir(name) / "tags"

    def _version_metadata_path(self, name: str, version: str) -> Path:
        """Get path to version metadata file."""
        return self._versions_dir(name) / f"{version}.json"

    def _tag_path(self, name: str, tag: str) -> Path:
        """Get path to tag file."""
        return self._tags_dir(name) / f"{tag}.json"

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
            backend_type: Backend type (pytorch, http, llm, etc.)
            backend_config: Backend-specific configuration
            tags: Optional tags to apply
            metadata: Optional user metadata
            artifact: Optional artifact bytes to store via storage backend
            artifact_path: Pre-existing artifact location (file path or URI)
            artifact_filename: Filename to use when saving artifact bytes

        Returns:
            ModelVersion object

        Raises:
            ValueError: If version already exists
        """
        # Create directories
        self._versions_dir(name).mkdir(parents=True, exist_ok=True)
        self._tags_dir(name).mkdir(parents=True, exist_ok=True)

        # Check if version already exists
        version_path = self._version_metadata_path(name, version)
        if version_path.exists():
            raise ValueError(f"Version {version} already exists for model {name}")

        resolved_artifact_path = None
        if artifact is not None:
            storage_path = f"{name}/{version}/{artifact_filename}"
            resolved_artifact_path = self.storage.save(artifact, storage_path)
        elif artifact_path is not None:
            resolved_artifact_path = artifact_path

        # Create version metadata
        model_version = ModelVersion(
            version_id=version,
            model_name=name,
            backend_type=backend_type,
            backend_config=backend_config,
            tags=tags or [],
            metadata=metadata or {},
            created_at=time.time(),
            artifact_path=resolved_artifact_path,
        )

        # Save version metadata
        with open(version_path, "w") as f:
            json.dump(model_version.to_dict(), f, indent=2)

        # Apply tags
        for tag in tags or []:
            self._apply_tag(name, version, tag)

        logger.info(f"Registered model {name} version {version}")
        return model_version

    def resolve(self, name: str, version: Optional[str] = None) -> ModelVersion:
        """
        Resolve a model version.

        Args:
            name: Model name
            version: Version identifier or tag name. If None, uses "latest" tag.

        Returns:
            ModelVersion object

        Raises:
            ValueError: If model or version not found
        """
        if version is None:
            version = "latest"

        # Check if version is a tag
        tag_path = self._tag_path(name, version)
        if tag_path.exists():
            with open(tag_path) as f:
                tag_data = json.load(f)
                version = tag_data["version_id"]

        # Load version metadata
        version_path = self._version_metadata_path(name, version)
        if not version_path.exists():
            raise ValueError(f"Version {version} not found for model {name}")

        with open(version_path) as f:
            data = json.load(f)
            return ModelVersion.from_dict(data)

    def list_versions(self, name: str) -> List[ModelVersion]:
        """
        List all versions of a model.

        Args:
            name: Model name

        Returns:
            List of ModelVersion objects, sorted by creation time (newest first)
        """
        versions_dir = self._versions_dir(name)
        if not versions_dir.exists():
            return []

        versions = []
        for version_file in versions_dir.glob("*.json"):
            with open(version_file) as f:
                data = json.load(f)
                versions.append(ModelVersion.from_dict(data))

        # Sort by creation time, newest first
        versions.sort(key=lambda v: v.created_at, reverse=True)
        return versions

    def promote(self, name: str, version: str, tag: str) -> None:
        """
        Promote a version by applying a tag.

        If the tag already exists on another version, it will be moved.
        The previous version with this tag will be auto-tagged as "{tag}-previous".

        Args:
            name: Model name
            version: Version identifier to promote
            tag: Tag name (e.g., "champion", "staging")

        Raises:
            ValueError: If version doesn't exist
        """
        # Verify version exists
        version_path = self._version_metadata_path(name, version)
        if not version_path.exists():
            raise ValueError(f"Version {version} not found for model {name}")

        # Check if tag already exists
        tag_path = self._tag_path(name, tag)
        if tag_path.exists():
            # Save previous version with "{tag}-previous" tag
            with open(tag_path) as f:
                old_tag_data = json.load(f)
                old_version = old_tag_data["version_id"]

            # Apply "{tag}-previous" tag to old version
            previous_tag = f"{tag}-previous"
            self._apply_tag(name, old_version, previous_tag)
            logger.info(f"Tagged previous {tag} version {old_version} as {previous_tag}")

        # Apply new tag
        self._apply_tag(name, version, tag)
        logger.info(f"Promoted {name} version {version} to {tag}")

    def _apply_tag(self, name: str, version: str, tag: str) -> None:
        """Apply a tag to a version."""
        self._tags_dir(name).mkdir(parents=True, exist_ok=True)
        tag_path = self._tag_path(name, tag)
        tag_path.parent.mkdir(parents=True, exist_ok=True)

        tag_data = {
            "version_id": version,
            "tagged_at": time.time(),
        }

        with open(tag_path, "w") as f:
            json.dump(tag_data, f, indent=2)

    def log_prediction(
        self,
        model_id: str,
        input_data: Any,
        output_data: Any,
        cost: Optional[float] = None,
        latency_ms: Optional[float] = None,
    ) -> None:
        """
        Log a prediction for monitoring.

        Args:
            model_id: Model identifier (name:version)
            input_data: Input to the model
            output_data: Output from the model
            cost: Optional inference cost
            latency_ms: Optional latency in milliseconds
        """
        # For now, just log to logger
        # In the future, could write to a predictions log file
        logger.debug(f"Prediction logged for {model_id}: cost={cost}, latency_ms={latency_ms}")
