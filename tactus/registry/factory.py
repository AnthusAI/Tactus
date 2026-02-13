"""
Factory for creating ModelRegistry implementations from config or environment.
"""

from __future__ import annotations

import os
from typing import Any, Optional

from tactus.registry.local import LocalRegistry
from tactus.registry.mlflow import MLflowRegistry
from tactus.registry.sagemaker import SageMakerRegistry


def create_registry(
    registry_type: Optional[str] = None,
    registry_dir: Optional[str] = None,
    tracking_uri: Optional[str] = None,
    region_name: Optional[str] = None,
    client: Any = None,
):
    """
    Create a registry based on type, falling back to environment variables.

    Environment fallbacks:
      TACTUS_REGISTRY_TYPE: local|mlflow|sagemaker
      TACTUS_REGISTRY_DIR: path for local
      TACTUS_REGISTRY_TRACKING_URI: URI for mlflow
      AWS_REGION / AWS_DEFAULT_REGION: for sagemaker
    """
    registry_type = registry_type or os.environ.get("TACTUS_REGISTRY_TYPE", "local")

    if registry_type == "mlflow":
        tracking_uri = tracking_uri or os.environ.get("TACTUS_REGISTRY_TRACKING_URI")
        return MLflowRegistry(tracking_uri=tracking_uri, client=client)

    if registry_type == "sagemaker":
        region = region_name or os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION")
        return SageMakerRegistry(region_name=region or "us-east-1", client=client)

    # Default: local
    registry_dir = registry_dir or os.environ.get("TACTUS_REGISTRY_DIR")
    return LocalRegistry(registry_dir=registry_dir)
