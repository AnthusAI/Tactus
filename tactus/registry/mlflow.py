"""MLflow-backed model registry implementation."""

from __future__ import annotations

import logging
from typing import Any, List, Optional

try:  # Optional dependency
    from mlflow.tracking import MlflowClient
except ImportError:  # pragma: no cover - handled in code paths without mlflow
    MlflowClient = None  # type: ignore

from tactus.registry.local import ModelVersion

logger = logging.getLogger(__name__)


def _get_client(tracking_uri: Optional[str] = None, client: Any = None):
    if client:
        return client
    if MlflowClient is None:
        raise ImportError("mlflow is not installed. Install with: pip install mlflow")
    return MlflowClient(tracking_uri)


class MLflowRegistry:
    """Minimal MLflow registry adapter implementing ModelRegistry protocol."""

    def __init__(self, tracking_uri: Optional[str] = None, client: Any = None):
        self.client = _get_client(tracking_uri, client)

    # ------------------------------------------------------------------
    # Core operations
    # ------------------------------------------------------------------
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
        """Register a new model version in MLflow."""

        source = artifact_path or backend_config.get("path") or backend_config.get("source", "")
        run_id = backend_config.get("run_id")

        mv = self.client.create_model_version(name=name, source=source, run_id=run_id)
        mv_version = getattr(mv, "version", None)
        if mv_version is None and isinstance(mv, dict):
            mv_version = mv.get("version")
        mv_version = str(mv_version)

        # Apply tags
        for tag in tags or []:
            try:
                self.client.set_model_version_tag(name, mv_version, tag_key="tag", tag_value=tag)
            except TypeError:
                # Fallback to newer signature: key/value
                self.client.set_model_version_tag(name, mv_version, key="tag", value=tag)

        model_version = ModelVersion(
            version_id=mv_version,
            model_name=name,
            backend_type=backend_type,
            backend_config=backend_config,
            tags=tags or [],
            metadata=metadata or {},
            created_at=getattr(mv, "creation_timestamp", 0) or 0,
            artifact_path=source,
        )
        return model_version

    def resolve(self, name: str, version: Optional[str] = None) -> ModelVersion:
        if version is None or version == "latest":
            versions = self.list_versions(name)
            if not versions:
                raise ValueError(f"No versions found for model {name}")
            return versions[0]

        # Attempt tag resolution via search
        tagged = [v for v in self.list_versions(name) if version in (v.tags or [])]
        if tagged:
            return tagged[0]

        mv = self.client.get_model_version(name, version)
        return ModelVersion(
            version_id=str(getattr(mv, "version", mv.get("version"))),
            model_name=name,
            backend_type=(
                mv.tags.get("backend_type", "unknown") if getattr(mv, "tags", None) else "unknown"
            ),
            backend_config={},
            tags=list(getattr(mv, "tags", {}).values()) if getattr(mv, "tags", None) else [],
            metadata={},
            created_at=getattr(mv, "creation_timestamp", 0) or 0,
            artifact_path=(
                getattr(mv, "source", None) or mv.get("source") if isinstance(mv, dict) else None
            ),
        )

    def list_versions(self, name: str) -> List[ModelVersion]:
        versions: List[ModelVersion] = []
        search_res = self.client.search_model_versions(f"name = '{name}'")
        for mv in search_res:
            version_id = getattr(mv, "version", None)
            if version_id is None and isinstance(mv, dict):
                version_id = mv.get("version")
            tags = getattr(mv, "tags", {}) or {}
            artifact_path = getattr(mv, "source", None)
            if artifact_path is None and isinstance(mv, dict):
                artifact_path = mv.get("source")

            versions.append(
                ModelVersion(
                    version_id=str(version_id),
                    model_name=name,
                    backend_type=(
                        tags.get("backend_type", "unknown") if isinstance(tags, dict) else "unknown"
                    ),
                    backend_config={},
                    tags=list(tags.values()) if isinstance(tags, dict) else [],
                    metadata={},
                    created_at=getattr(mv, "creation_timestamp", 0) or 0,
                    artifact_path=artifact_path,
                )
            )

        versions.sort(key=lambda v: float(v.created_at), reverse=True)
        return versions

    def promote(self, name: str, version: str, tag: str) -> None:
        # Remove existing tag
        existing = [v for v in self.list_versions(name) if tag in v.tags]
        for v in existing:
            try:
                self.client.delete_model_version_tag(name, v.version_id, "tag")
            except Exception:
                pass
            try:
                self.client.set_model_version_tag(
                    name, v.version_id, key="tag", value=f"{tag}-previous"
                )
            except Exception:
                pass

        # Apply new tag
        try:
            self.client.set_model_version_tag(name, version, key="tag", value=tag)
        except TypeError:
            self.client.set_model_version_tag(name, version, tag_key="tag", tag_value=tag)

    def log_prediction(
        self,
        model_id: str,
        input_data: Any,
        output_data: Any,
        cost: Optional[float] = None,
        latency_ms: Optional[float] = None,
    ) -> None:
        # Not implemented for MLflow adapter; could log to MLflow tracking in future
        logger.debug("MLflowRegistry.log_prediction noop", extra={"model_id": model_id})
