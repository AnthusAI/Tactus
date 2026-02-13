"""
Tests for RegistryBackend.
"""

import pytest
from unittest.mock import Mock, AsyncMock

from tactus.backends.registry_backend import RegistryBackend
from tactus.registry.local import ModelVersion


class TestRegistryBackend:
    """Test RegistryBackend functionality."""

    def test_resolve_and_predict_sync(self):
        """Test resolving from registry and making prediction."""
        # Create mock registry
        mock_registry = Mock()
        model_version = ModelVersion(
            version_id="v1.0.0",
            model_name="classifier",
            backend_type="http",
            backend_config={"endpoint": "http://example.com/predict"},
            tags=["champion"],
            metadata={},
            created_at=1234567890.0,
        )
        mock_registry.resolve.return_value = model_version

        # Create registry backend
        backend = RegistryBackend(
            registry=mock_registry,
            model_name="classifier",
            version="champion",
        )

        # Mock the resolved HTTP backend
        from unittest.mock import patch

        with patch("tactus.backends.http_backend.HTTPModelBackend") as MockHTTP:
            mock_http = Mock()
            mock_http.predict_sync.return_value = {"label": "positive"}
            MockHTTP.return_value = mock_http

            # Make prediction
            result = backend.predict_sync({"text": "hello"})

            # Verify registry was called
            mock_registry.resolve.assert_called_once_with("classifier", "champion")

            # Verify HTTP backend was created and called
            MockHTTP.assert_called_once()
            mock_http.predict_sync.assert_called_once_with({"text": "hello"})

            assert result == {"label": "positive"}
            assert backend.resolved_version_id == "v1.0.0"

    def test_resolve_uses_cache(self):
        """Test that backend resolution is cached."""
        mock_registry = Mock()
        model_version = ModelVersion(
            version_id="v1.0.0",
            model_name="classifier",
            backend_type="http",
            backend_config={"endpoint": "http://example.com"},
            tags=[],
            metadata={},
            created_at=1234567890.0,
        )
        mock_registry.resolve.return_value = model_version

        backend = RegistryBackend(
            registry=mock_registry,
            model_name="classifier",
            version="v1.0.0",
        )

        from unittest.mock import patch

        with patch("tactus.backends.http_backend.HTTPModelBackend") as MockHTTP:
            mock_http = Mock()
            mock_http.predict_sync.return_value = "result1"
            MockHTTP.return_value = mock_http

            # First prediction
            backend.predict_sync({"x": 1})

            # Second prediction
            backend.predict_sync({"x": 2})

            # Registry should only be called once (cached)
            assert mock_registry.resolve.call_count == 1

            # HTTP backend should be called twice
            assert mock_http.predict_sync.call_count == 2

    def test_fallback_when_resolution_fails(self):
        """Test using fallback config when registry resolution fails."""
        mock_registry = Mock()
        mock_registry.resolve.side_effect = ValueError("Model not found")

        fallback_config = {
            "type": "http",
            "endpoint": "http://fallback.com/predict",
        }

        backend = RegistryBackend(
            registry=mock_registry,
            model_name="classifier",
            version="champion",
            fallback_config=fallback_config,
        )

        from unittest.mock import patch

        with patch("tactus.backends.http_backend.HTTPModelBackend") as MockHTTP:
            mock_http = Mock()
            mock_http.predict_sync.return_value = {"label": "fallback"}
            MockHTTP.return_value = mock_http

            result = backend.predict_sync({"text": "test"})

            # Should use fallback
            assert result == {"label": "fallback"}
            assert backend.resolved_version_id is None

    def test_error_when_no_fallback(self):
        """Test error when resolution fails and no fallback configured."""
        mock_registry = Mock()
        mock_registry.resolve.side_effect = ValueError("Model not found")

        backend = RegistryBackend(
            registry=mock_registry,
            model_name="classifier",
            version="champion",
            fallback_config=None,
        )

        with pytest.raises(ValueError, match="Failed to resolve.*no fallback"):
            backend.predict_sync({"text": "test"})

    def test_resolve_pytorch_backend(self):
        """Test resolving PyTorch backend from registry."""
        mock_registry = Mock()
        model_version = ModelVersion(
            version_id="v2.0.0",
            model_name="classifier",
            backend_type="pytorch",
            backend_config={"path": "/models/model.pt", "device": "cuda"},
            tags=[],
            metadata={},
            created_at=1234567890.0,
        )
        mock_registry.resolve.return_value = model_version

        backend = RegistryBackend(
            registry=mock_registry,
            model_name="classifier",
            version="v2.0.0",
        )

        from unittest.mock import patch

        with patch("tactus.backends.pytorch_backend.PyTorchModelBackend") as MockPT:
            mock_pt = Mock()
            mock_pt.predict_sync.return_value = [0.1, 0.9]
            MockPT.return_value = mock_pt

            result = backend.predict_sync({"data": [1, 2, 3]})

            MockPT.assert_called_once_with(path="/models/model.pt", device="cuda", labels=None)
            assert result == [0.1, 0.9]

    def test_resolve_llm_backend(self):
        """Test resolving LLM backend from registry."""
        mock_registry = Mock()
        model_version = ModelVersion(
            version_id="v3.0.0",
            model_name="classifier",
            backend_type="llm",
            backend_config={
                "model": "openai/gpt-4o-mini",
                "system_prompt": "Classify sentiment",
                "temperature": 0.0,
            },
            tags=[],
            metadata={},
            created_at=1234567890.0,
        )
        mock_registry.resolve.return_value = model_version

        backend = RegistryBackend(
            registry=mock_registry,
            model_name="classifier",
            version="v3.0.0",
        )

        from unittest.mock import patch

        with patch("tactus.backends.llm_backend.LLMModelBackend") as MockLLM:
            mock_llm = Mock()
            mock_llm.predict_sync.return_value = {
                "result": {"label": "positive"},
                "cost": {},
                "usage": {},
            }
            MockLLM.return_value = mock_llm

            result = backend.predict_sync({"text": "test"})

            MockLLM.assert_called_once()
            assert result["result"] == {"label": "positive"}

    def test_unknown_backend_type_raises_error(self):
        """Test that unknown backend type raises error."""
        mock_registry = Mock()
        model_version = ModelVersion(
            version_id="v1.0.0",
            model_name="classifier",
            backend_type="unknown",
            backend_config={},
            tags=[],
            metadata={},
            created_at=1234567890.0,
        )
        mock_registry.resolve.return_value = model_version

        backend = RegistryBackend(
            registry=mock_registry,
            model_name="classifier",
            version="v1.0.0",
        )

        with pytest.raises(ValueError, match="Unknown backend type"):
            backend.predict_sync({"data": "test"})

    async def test_async_predict(self):
        """Test async predict using resolved backend."""
        mock_registry = Mock()
        model_version = ModelVersion(
            version_id="v1.0.0",
            model_name="classifier",
            backend_type="http",
            backend_config={"endpoint": "http://example.com"},
            tags=[],
            metadata={},
            created_at=1234567890.0,
        )
        mock_registry.resolve.return_value = model_version

        backend = RegistryBackend(
            registry=mock_registry,
            model_name="classifier",
            version="v1.0.0",
        )

        from unittest.mock import patch

        with patch("tactus.backends.http_backend.HTTPModelBackend") as MockHTTP:
            mock_http = Mock()
            mock_http.predict = AsyncMock(return_value={"label": "async_result"})
            MockHTTP.return_value = mock_http

            result = await backend.predict({"text": "async test"})

            mock_http.predict.assert_called_once_with({"text": "async test"})
            assert result == {"label": "async_result"}
