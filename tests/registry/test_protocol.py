"""
Tests for ModelRegistry protocol (Phase 3.1).
"""

from datetime import datetime
from typing import Any, List, Optional

import pytest

from tactus.registry.protocol import ModelRegistry, ModelVersion, PredictionLog


class MockRegistry:
    """Mock implementation of ModelRegistry protocol for testing."""

    def __init__(self):
        """Initialize mock registry."""
        self.versions: dict[str, List[ModelVersion]] = {}
        self.predictions: List[PredictionLog] = []

    def register(
        self,
        name: str,
        version: str,
        backend_type: str,
        backend_config: dict,
        tags: Optional[List[str]] = None,
        metadata: Optional[dict] = None,
    ) -> ModelVersion:
        """Register a new model version."""
        model_version = ModelVersion(
            name=name,
            version=version,
            backend_type=backend_type,
            backend_config=backend_config,
            created_at=datetime.now().isoformat(),
            tags=tags or [],
            metadata=metadata,
        )

        if name not in self.versions:
            self.versions[name] = []
        self.versions[name].append(model_version)

        return model_version

    def resolve(self, name: str, version: Optional[str] = None) -> ModelVersion:
        """Resolve a model by name and version/tag."""
        if name not in self.versions:
            raise KeyError(f"Model not found: {name}")

        versions = self.versions[name]

        # If no version specified, try champion tag or latest
        if version is None:
            # Try to find champion
            for v in versions:
                if "champion" in v.tags:
                    return v
            # Fall back to latest
            return versions[-1]

        # Check if version is a tag
        for v in versions:
            if version in v.tags:
                return v

        # Check if version matches version string
        for v in versions:
            if v.version == version:
                return v

        raise KeyError(f"Version not found: {name}:{version}")

    def list_versions(self, name: str) -> List[ModelVersion]:
        """List all versions of a model."""
        if name not in self.versions:
            return []
        # Return newest first
        return list(reversed(self.versions[name]))

    def promote(self, name: str, version: str, tag: str) -> None:
        """Promote a version by adding/moving a tag."""
        if name not in self.versions:
            raise KeyError(f"Model not found: {name}")

        target_version = None
        for v in self.versions[name]:
            if v.version == version:
                target_version = v
                break

        if target_version is None:
            raise KeyError(f"Version not found: {name}:{version}")

        # Handle champion promotion
        if tag == "champion":
            # Find current champion and demote to champion-previous
            for v in self.versions[name]:
                if "champion" in v.tags:
                    v.tags.remove("champion")
                    if "champion-previous" not in v.tags:
                        v.tags.append("champion-previous")

        # Remove tag from other versions
        for v in self.versions[name]:
            if tag in v.tags and v != target_version:
                v.tags.remove(tag)

        # Add tag to target
        if tag not in target_version.tags:
            target_version.tags.append(tag)

    def log_prediction(
        self,
        model_id: str,
        input_data: Any,
        output_data: Any,
        cost: Optional[float] = None,
        latency_ms: Optional[float] = None,
    ) -> None:
        """Log a prediction."""
        log = PredictionLog(
            model_id=model_id,
            timestamp=datetime.now().isoformat(),
            input_data=input_data,
            output_data=output_data,
            cost=cost,
            latency_ms=latency_ms,
        )
        self.predictions.append(log)


class TestModelRegistryProtocol:
    """Test that ModelRegistry protocol is implementable."""

    def test_protocol_is_implementable(self):
        """Test that a class can implement ModelRegistry protocol."""
        registry = MockRegistry()

        # Verify it has all required methods
        assert hasattr(registry, "register")
        assert hasattr(registry, "resolve")
        assert hasattr(registry, "list_versions")
        assert hasattr(registry, "promote")
        assert hasattr(registry, "log_prediction")

    def test_register_model(self):
        """Test registering a model version."""
        registry = MockRegistry()

        version = registry.register(
            name="sentiment_classifier",
            version="v1.0.0",
            backend_type="http",
            backend_config={"endpoint": "http://test.com/predict"},
            tags=["production"],
            metadata={"author": "test", "accuracy": 0.95},
        )

        assert version.name == "sentiment_classifier"
        assert version.version == "v1.0.0"
        assert version.backend_type == "http"
        assert "production" in version.tags
        assert version.metadata["accuracy"] == 0.95

    def test_resolve_by_version(self):
        """Test resolving model by version string."""
        registry = MockRegistry()

        registry.register(
            name="classifier",
            version="v1.0.0",
            backend_type="http",
            backend_config={"endpoint": "http://v1.com"},
        )

        registry.register(
            name="classifier",
            version="v2.0.0",
            backend_type="http",
            backend_config={"endpoint": "http://v2.com"},
        )

        result = registry.resolve("classifier", "v1.0.0")
        assert result.version == "v1.0.0"
        assert result.backend_config["endpoint"] == "http://v1.com"

    def test_resolve_by_tag(self):
        """Test resolving model by tag."""
        registry = MockRegistry()

        registry.register(
            name="classifier",
            version="v1.0.0",
            backend_type="http",
            backend_config={"endpoint": "http://v1.com"},
            tags=["champion"],
        )

        result = registry.resolve("classifier", "champion")
        assert result.version == "v1.0.0"

    def test_resolve_default_to_champion(self):
        """Test resolving without version defaults to champion."""
        registry = MockRegistry()

        registry.register(
            name="classifier",
            version="v1.0.0",
            backend_type="http",
            backend_config={},
        )

        registry.register(
            name="classifier",
            version="v2.0.0",
            backend_type="http",
            backend_config={},
            tags=["champion"],
        )

        result = registry.resolve("classifier")
        assert result.version == "v2.0.0"

    def test_list_versions(self):
        """Test listing all versions of a model."""
        registry = MockRegistry()

        registry.register("classifier", "v1.0.0", "http", {})
        registry.register("classifier", "v2.0.0", "http", {})
        registry.register("classifier", "v3.0.0", "http", {})

        versions = registry.list_versions("classifier")
        assert len(versions) == 3
        # Should be newest first
        assert versions[0].version == "v3.0.0"
        assert versions[1].version == "v2.0.0"
        assert versions[2].version == "v1.0.0"

    def test_promote_to_champion(self):
        """Test promoting a version to champion."""
        registry = MockRegistry()

        registry.register("classifier", "v1.0.0", "http", {}, tags=["champion"])
        registry.register("classifier", "v2.0.0", "http", {})

        # Promote v2.0.0 to champion
        registry.promote("classifier", "v2.0.0", "champion")

        # v2.0.0 should be champion
        v2 = registry.resolve("classifier", "v2.0.0")
        assert "champion" in v2.tags

        # v1.0.0 should be champion-previous
        v1 = registry.resolve("classifier", "v1.0.0")
        assert "champion" not in v1.tags
        assert "champion-previous" in v1.tags

    def test_log_prediction(self):
        """Test logging predictions."""
        registry = MockRegistry()

        registry.log_prediction(
            model_id="classifier:v1.0.0",
            input_data={"text": "Hello"},
            output_data={"label": "greeting"},
            cost=0.001,
            latency_ms=50.5,
        )

        assert len(registry.predictions) == 1
        log = registry.predictions[0]
        assert log.model_id == "classifier:v1.0.0"
        assert log.input_data == {"text": "Hello"}
        assert log.output_data == {"label": "greeting"}
        assert log.cost == 0.001
        assert log.latency_ms == 50.5

    def test_resolve_nonexistent_model(self):
        """Test resolving nonexistent model raises KeyError."""
        registry = MockRegistry()

        with pytest.raises(KeyError, match="Model not found"):
            registry.resolve("nonexistent")

    def test_promote_nonexistent_version(self):
        """Test promoting nonexistent version raises KeyError."""
        registry = MockRegistry()

        registry.register("classifier", "v1.0.0", "http", {})

        with pytest.raises(KeyError, match="Version not found"):
            registry.promote("classifier", "v99.0.0", "champion")
