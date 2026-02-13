"""
Tests for HTTP backend cost tracking (Phase 2.4).
"""

import pytest
from unittest.mock import MagicMock, patch

from tactus.backends.http_backend import HTTPModelBackend
from tactus.primitives.model import ModelPrimitive


class TestHTTPBackendCost:
    """Test HTTP backend with cost_per_call configuration."""

    def test_http_backend_without_cost(self):
        """Test HTTP backend without cost tracking returns raw output."""
        backend = HTTPModelBackend(endpoint="http://test.com/predict")

        # Mock httpx client
        with patch("httpx.Client") as mock_client:
            mock_response = MagicMock()
            mock_response.json.return_value = {"label": "positive"}
            mock_client.return_value.__enter__.return_value.post.return_value = mock_response

            result = backend.predict_sync({"text": "Hello"})

            assert result == {"label": "positive"}

    def test_http_backend_with_cost(self):
        """Test HTTP backend with cost_per_call wraps result with cost."""
        backend = HTTPModelBackend(
            endpoint="http://test.com/predict", cost_per_call=0.01
        )

        # Mock httpx client
        with patch("httpx.Client") as mock_client:
            mock_response = MagicMock()
            mock_response.json.return_value = {"label": "positive"}
            mock_client.return_value.__enter__.return_value.post.return_value = mock_response

            result = backend.predict_sync({"text": "Hello"})

            # Result should be wrapped with cost
            assert result["result"] == {"label": "positive"}
            assert result["cost"]["total_cost"] == 0.01
            assert result["usage"]["total_tokens"] == 0

    def test_model_primitive_with_http_cost(self):
        """Test Model primitive with HTTP backend cost tracking."""
        config = {
            "type": "http",
            "endpoint": "http://test.com/predict",
            "cost_per_call": 0.005,
        }

        model = ModelPrimitive("http_model", config)

        # Mock backend
        mock_result = {
            "result": {"label": "positive"},
            "cost": {"total_cost": 0.005, "prompt_cost": 0.005, "completion_cost": 0.0},
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        }
        model.backend.predict_sync = MagicMock(return_value=mock_result)

        result = model.predict({"text": "Hello"})

        # Check result
        assert result.output == {"label": "positive"}
        assert result.cost.inference_cost == 0.005
        assert result.backend_type == "http"

    def test_http_cost_accumulates_across_calls(self):
        """Test HTTP backend cost accumulates correctly."""
        config = {
            "type": "http",
            "endpoint": "http://test.com/predict",
            "cost_per_call": 0.01,
        }

        model = ModelPrimitive("http_model", config)

        # Mock backend to return wrapped result
        mock_result = {
            "result": {"label": "positive"},
            "cost": {"total_cost": 0.01, "prompt_cost": 0.01, "completion_cost": 0.0},
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        }
        model.backend.predict_sync = MagicMock(return_value=mock_result)

        # Make 5 predictions
        for i in range(5):
            model.predict({"text": f"Test {i}"})

        # Check accumulated stats
        assert model.prediction_count == 5
        assert model.total_cost == pytest.approx(0.05)  # 5 * 0.01
        assert model.avg_latency_ms > 0

    def test_http_backend_cost_zero(self):
        """Test HTTP backend with zero cost."""
        backend = HTTPModelBackend(
            endpoint="http://test.com/predict", cost_per_call=0.0
        )

        # Mock httpx client
        with patch("httpx.Client") as mock_client:
            mock_response = MagicMock()
            mock_response.json.return_value = {"label": "positive"}
            mock_client.return_value.__enter__.return_value.post.return_value = mock_response

            result = backend.predict_sync({"text": "Hello"})

            # Result should be wrapped even with zero cost
            assert result["result"] == {"label": "positive"}
            assert result["cost"]["total_cost"] == 0.0

    def test_http_backend_cost_formats_match_llm(self):
        """Test HTTP backend cost format matches LLM backend format."""
        backend = HTTPModelBackend(
            endpoint="http://test.com/predict", cost_per_call=0.02
        )

        # Mock httpx client
        with patch("httpx.Client") as mock_client:
            mock_response = MagicMock()
            mock_response.json.return_value = {"score": 0.95}
            mock_client.return_value.__enter__.return_value.post.return_value = mock_response

            result = backend.predict_sync({"text": "Test"})

            # Check format matches LLM backend expectations
            assert "result" in result
            assert "cost" in result
            assert "usage" in result
            assert "total_cost" in result["cost"]
            assert "prompt_cost" in result["cost"]
            assert "completion_cost" in result["cost"]
            assert "prompt_tokens" in result["usage"]
            assert "completion_tokens" in result["usage"]
            assert "total_tokens" in result["usage"]

    def test_model_primitive_without_http_cost(self):
        """Test Model primitive with HTTP backend without cost tracking."""
        config = {
            "type": "http",
            "endpoint": "http://test.com/predict",
            # No cost_per_call specified
        }

        model = ModelPrimitive("http_model", config)

        # Mock backend to return raw result
        model.backend.predict_sync = MagicMock(return_value={"label": "negative"})

        result = model.predict({"text": "Bad"})

        # Check result
        assert result.output == {"label": "negative"}
        assert result.cost.inference_cost is None  # No cost tracking
        assert result.cost.compute_time_ms > 0  # But timing is still tracked

        # Make multiple predictions
        for i in range(3):
            model.predict({"text": f"Test {i}"})

        # Total cost should remain 0 (no per-call cost)
        assert model.total_cost == 0.0
        assert model.prediction_count == 4  # 1 + 3
