import os

from tactus.registry.factory import create_registry
from tactus.registry.local import LocalRegistry
from tactus.registry.mlflow import MLflowRegistry
from tactus.registry.sagemaker import SageMakerRegistry


def test_factory_defaults_to_local(monkeypatch):
    monkeypatch.delenv("TACTUS_REGISTRY_TYPE", raising=False)
    registry = create_registry()
    assert isinstance(registry, LocalRegistry)


def test_factory_env_mlflow(monkeypatch):
    monkeypatch.setenv("TACTUS_REGISTRY_TYPE", "mlflow")
    monkeypatch.setenv("TACTUS_REGISTRY_TRACKING_URI", "http://mlflow:5000")
    registry = create_registry()
    assert isinstance(registry, MLflowRegistry)


def test_factory_env_sagemaker(monkeypatch):
    monkeypatch.setenv("TACTUS_REGISTRY_TYPE", "sagemaker")
    monkeypatch.setenv("AWS_REGION", "us-west-2")
    registry = create_registry()
    assert isinstance(registry, SageMakerRegistry)
