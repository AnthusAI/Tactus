"""
Tests for LocalRegistry implementation.
"""

import tempfile
from pathlib import Path

import pytest

from tactus.registry.local import LocalRegistry, ModelVersion


class TestLocalRegistry:
    """Test LocalRegistry functionality."""

    @pytest.fixture
    def temp_registry_dir(self):
        """Create a temporary registry directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def registry(self, temp_registry_dir):
        """Create a LocalRegistry instance with temporary directory."""
        return LocalRegistry(registry_dir=temp_registry_dir)

    def test_init_creates_directory(self, temp_registry_dir):
        """Test that __init__ creates the registry directory."""
        LocalRegistry(registry_dir=temp_registry_dir)
        assert Path(temp_registry_dir).exists()

    def test_register_creates_version(self, registry):
        """Test registering a new model version."""
        version = registry.register(
            name="sentiment-classifier",
            version="v1.0.0",
            backend_type="pytorch",
            backend_config={"path": "/models/sentiment.pt"},
            tags=["latest"],
            metadata={"accuracy": 0.95},
        )

        assert version.version_id == "v1.0.0"
        assert version.model_name == "sentiment-classifier"
        assert version.backend_type == "pytorch"
        assert version.backend_config == {"path": "/models/sentiment.pt"}
        assert version.tags == ["latest"]
        assert version.metadata == {"accuracy": 0.95}

    def test_register_duplicate_version_raises_error(self, registry):
        """Test that registering duplicate version raises ValueError."""
        registry.register(
            name="classifier",
            version="v1.0.0",
            backend_type="pytorch",
            backend_config={},
        )

        with pytest.raises(ValueError, match="already exists"):
            registry.register(
                name="classifier",
                version="v1.0.0",
                backend_type="pytorch",
                backend_config={},
            )

    def test_resolve_by_version_id(self, registry):
        """Test resolving a model by version ID."""
        registry.register(
            name="classifier",
            version="v1.0.0",
            backend_type="pytorch",
            backend_config={"path": "/models/model.pt"},
        )

        version = registry.resolve("classifier", "v1.0.0")
        assert version.version_id == "v1.0.0"
        assert version.backend_type == "pytorch"

    def test_resolve_by_tag(self, registry):
        """Test resolving a model by tag."""
        registry.register(
            name="classifier",
            version="v1.0.0",
            backend_type="pytorch",
            backend_config={"path": "/models/model.pt"},
            tags=["champion"],
        )

        version = registry.resolve("classifier", "champion")
        assert version.version_id == "v1.0.0"

    def test_resolve_without_version_uses_latest(self, registry):
        """Test resolving without version uses 'latest' tag."""
        registry.register(
            name="classifier",
            version="v1.0.0",
            backend_type="pytorch",
            backend_config={},
            tags=["latest"],
        )

        version = registry.resolve("classifier")
        assert version.version_id == "v1.0.0"

    def test_resolve_nonexistent_version_raises_error(self, registry):
        """Test resolving nonexistent version raises ValueError."""
        with pytest.raises(ValueError, match="not found"):
            registry.resolve("classifier", "v1.0.0")

    def test_list_versions(self, registry):
        """Test listing all versions of a model."""
        registry.register(
            name="classifier",
            version="v1.0.0",
            backend_type="pytorch",
            backend_config={},
        )
        registry.register(
            name="classifier",
            version="v1.1.0",
            backend_type="pytorch",
            backend_config={},
        )
        registry.register(
            name="classifier",
            version="v2.0.0",
            backend_type="pytorch",
            backend_config={},
        )

        versions = registry.list_versions("classifier")
        assert len(versions) == 3
        # Should be sorted by creation time, newest first
        version_ids = [v.version_id for v in versions]
        assert "v2.0.0" in version_ids
        assert "v1.1.0" in version_ids
        assert "v1.0.0" in version_ids

    def test_list_versions_nonexistent_model(self, registry):
        """Test listing versions of nonexistent model returns empty list."""
        versions = registry.list_versions("nonexistent")
        assert versions == []

    def test_promote_creates_tag(self, registry):
        """Test promoting a version creates a tag."""
        registry.register(
            name="classifier",
            version="v1.0.0",
            backend_type="pytorch",
            backend_config={},
        )

        registry.promote("classifier", "v1.0.0", "champion")

        # Should be able to resolve by tag
        version = registry.resolve("classifier", "champion")
        assert version.version_id == "v1.0.0"

    def test_promote_moves_existing_tag(self, registry):
        """Test promoting a version moves an existing tag."""
        registry.register(
            name="classifier",
            version="v1.0.0",
            backend_type="pytorch",
            backend_config={},
        )
        registry.register(
            name="classifier",
            version="v2.0.0",
            backend_type="pytorch",
            backend_config={},
        )

        # Promote v1.0.0 to champion
        registry.promote("classifier", "v1.0.0", "champion")

        # Promote v2.0.0 to champion
        registry.promote("classifier", "v2.0.0", "champion")

        # Champion should now point to v2.0.0
        version = registry.resolve("classifier", "champion")
        assert version.version_id == "v2.0.0"

        # v1.0.0 should be tagged as champion-previous
        previous = registry.resolve("classifier", "champion-previous")
        assert previous.version_id == "v1.0.0"

    def test_promote_nonexistent_version_raises_error(self, registry):
        """Test promoting nonexistent version raises ValueError."""
        with pytest.raises(ValueError, match="not found"):
            registry.promote("classifier", "v1.0.0", "champion")

    def test_log_prediction(self, registry):
        """Test logging a prediction (basic smoke test)."""
        # Should not raise any errors
        registry.log_prediction(
            model_id="classifier:v1.0.0",
            input_data={"text": "hello"},
            output_data={"label": "positive"},
            cost=0.0001,
            latency_ms=45.2,
        )


class TestModelVersion:
    """Test ModelVersion dataclass."""

    def test_to_dict(self):
        """Test converting ModelVersion to dict."""
        version = ModelVersion(
            version_id="v1.0.0",
            model_name="classifier",
            backend_type="pytorch",
            backend_config={"path": "/models/model.pt"},
            tags=["latest"],
            metadata={"accuracy": 0.95},
            created_at=1234567890.0,
        )

        data = version.to_dict()
        assert data["version_id"] == "v1.0.0"
        assert data["model_name"] == "classifier"
        assert data["backend_type"] == "pytorch"
        assert data["tags"] == ["latest"]

    def test_from_dict(self):
        """Test creating ModelVersion from dict."""
        data = {
            "version_id": "v1.0.0",
            "model_name": "classifier",
            "backend_type": "pytorch",
            "backend_config": {"path": "/models/model.pt"},
            "tags": ["latest"],
            "metadata": {"accuracy": 0.95},
            "created_at": 1234567890.0,
            "artifact_path": None,
        }

        version = ModelVersion.from_dict(data)
        assert version.version_id == "v1.0.0"
        assert version.model_name == "classifier"
        assert version.backend_type == "pytorch"
