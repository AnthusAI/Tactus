"""SageMaker-backed model registry implementation (stub for future expansion)."""

from __future__ import annotations

import logging
from typing import Any, List, Optional

import boto3
from botocore.exceptions import ClientError

from tactus.registry.local import ModelVersion

logger = logging.getLogger(__name__)


class SageMakerRegistry:
    """Minimal SageMaker Model Registry adapter implementing ModelRegistry protocol."""

    def __init__(self, region_name: str = "us-east-1", client: Any = None):
        self.client = client or boto3.client("sagemaker", region_name=region_name)

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
        artifact_filename: str = "model.tar.gz",
    ) -> ModelVersion:
        # Simplified: record as a model package (placeholder)
        model_package_name = f"{name}-{version}"
        try:
            self.client.create_model_package(
                ModelPackageName=model_package_name,
                InferenceSpecification={
                    "Containers": [
                        {
                            "Image": backend_config.get("image", ""),
                            "ModelDataUrl": artifact_path or backend_config.get("path", ""),
                        }
                    ],
                    "SupportedContentTypes": ["application/json"],
                    "SupportedResponseMIMETypes": ["application/json"],
                },
            )
        except ClientError as e:
            raise ValueError(f"Failed to register model in SageMaker: {e}") from e

        return ModelVersion(
            version_id=version,
            model_name=name,
            backend_type=backend_type,
            backend_config=backend_config,
            tags=tags or [],
            metadata=metadata or {},
            created_at=0.0,
            artifact_path=artifact_path,
        )

    def resolve(self, name: str, version: Optional[str] = None) -> ModelVersion:
        if version is None:
            version = "latest"

        # Placeholder resolution using list
        versions = self.list_versions(name)
        for v in versions:
            if v.version_id == version or version in v.tags:
                return v
        raise ValueError(f"Version {version} not found for model {name}")

    def list_versions(self, name: str) -> List[ModelVersion]:
        # Simplified placeholder implementation (would call list_model_packages)
        try:
            res = self.client.list_model_packages(NameContains=name)
            versions = []
            for pkg in res.get("ModelPackageSummaryList", []):
                versions.append(
                    ModelVersion(
                        version_id=pkg.get("ModelPackageVersion", "unknown"),
                        model_name=name,
                        backend_type="sagemaker",
                        backend_config={},
                        tags=[],
                        metadata={},
                        created_at=pkg.get("CreationTime", 0),
                        artifact_path=None,
                    )
                )
            versions.sort(key=lambda v: float(v.created_at), reverse=True)
            return versions
        except ClientError as e:
            raise ValueError(f"Failed to list models in SageMaker: {e}") from e

    def promote(self, name: str, version: str, tag: str) -> None:
        # No-op placeholder; real impl would update model package group aliases
        logger.info("SageMakerRegistry promote stub: %s %s -> %s", name, version, tag)

    def log_prediction(
        self,
        model_id: str,
        input_data: Any,
        output_data: Any,
        cost: Optional[float] = None,
        latency_ms: Optional[float] = None,
    ) -> None:
        logger.debug("SageMakerRegistry log_prediction noop", extra={"model_id": model_id})
