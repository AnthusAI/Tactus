"""
Tests for Model primitive cost accumulation (Phase 2.3).
"""

import pytest
from unittest.mock import MagicMock

from tactus.primitives.model import ModelPrimitive


class TestCostAccumulation:
    """Test cumulative cost tracking on model instances."""

    def test_initial_stats_are_zero(self):
        """Test that newly created model has zero statistics."""
        config = {
            "type": "http",
            "endpoint": "http://test.com/predict",
        }

        model = ModelPrimitive("test_model", config)

        assert model.total_cost == 0.0
        assert model.prediction_count == 0
        assert model.avg_latency_ms == 0.0

    def test_single_prediction_stats(self):
        """Test stats after single prediction."""
        config = {
            "type": "llm",
            "model": "openai/gpt-4o-mini",
            "system_prompt": "Classify",
        }

        model = ModelPrimitive("classifier", config)

        # Mock backend to return cost data
        mock_result = {
            "result": {"label": "positive"},
            "usage": {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20},
            "cost": {"prompt_cost": 0.0001, "completion_cost": 0.0001, "total_cost": 0.0002},
        }
        model.backend.predict_sync = MagicMock(return_value=mock_result)

        result = model.predict({"text": "Hello"})

        # Check prediction result
        assert result.output == {"label": "positive"}
        assert result.cost.inference_cost == 0.0002

        # Check accumulated stats
        assert model.prediction_count == 1
        assert model.total_cost == 0.0002
        assert model.avg_latency_ms > 0  # Should have some timing

    def test_multiple_predictions_accumulate(self):
        """Test that multiple predictions accumulate correctly."""
        config = {
            "type": "llm",
            "model": "openai/gpt-4o-mini",
            "system_prompt": "Classify",
        }

        model = ModelPrimitive("classifier", config)

        # Mock backend with different costs for each call
        mock_result1 = {
            "result": {"label": "positive"},
            "usage": {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20},
            "cost": {"prompt_cost": 0.0001, "completion_cost": 0.0001, "total_cost": 0.0002},
        }
        mock_result2 = {
            "result": {"label": "negative"},
            "usage": {"prompt_tokens": 15, "completion_tokens": 12, "total_tokens": 27},
            "cost": {"prompt_cost": 0.00015, "completion_cost": 0.00012, "total_cost": 0.00027},
        }
        mock_result3 = {
            "result": {"label": "neutral"},
            "usage": {"prompt_tokens": 12, "completion_tokens": 8, "total_tokens": 20},
            "cost": {"prompt_cost": 0.00012, "completion_cost": 0.00008, "total_cost": 0.0002},
        }

        model.backend.predict_sync = MagicMock(
            side_effect=[mock_result1, mock_result2, mock_result3]
        )

        # Make three predictions
        model.predict({"text": "Great!"})
        model.predict({"text": "Terrible!"})
        model.predict({"text": "It's okay."})

        # Check accumulated stats
        assert model.prediction_count == 3
        assert model.total_cost == pytest.approx(0.00067)  # 0.0002 + 0.00027 + 0.0002
        assert model.avg_latency_ms > 0

    def test_http_backend_accumulates_timing_only(self):
        """Test HTTP backend accumulates timing but no inference cost."""
        config = {
            "type": "http",
            "endpoint": "http://test.com/predict",
        }

        model = ModelPrimitive("http_model", config)
        model.backend.predict_sync = MagicMock(return_value={"label": "positive"})

        # Make two predictions
        model.predict({"text": "Hello"})
        model.predict({"text": "World"})

        # Check stats
        assert model.prediction_count == 2
        assert model.total_cost == 0.0  # No inference cost for HTTP
        assert model.avg_latency_ms > 0  # But timing is tracked

    def test_mixed_backend_predictions(self):
        """Test that stats accumulate correctly for different backend responses."""
        config = {
            "type": "http",
            "endpoint": "http://test.com/predict",
        }

        model = ModelPrimitive("model", config)

        # Mock backend to return different response formats
        # First: raw output (HTTP style)
        # Second: with cost data (LLM style)
        mock_result1 = {"label": "positive"}
        mock_result2 = {
            "result": {"label": "negative"},
            "usage": {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20},
            "cost": {"prompt_cost": 0.0001, "completion_cost": 0.0001, "total_cost": 0.0002},
        }

        model.backend.predict_sync = MagicMock(side_effect=[mock_result1, mock_result2])

        # Make two predictions
        result1 = model.predict({"text": "Hello"})
        result2 = model.predict({"text": "World"})

        # Check individual results
        assert result1.output == {"label": "positive"}
        assert result1.cost.inference_cost is None

        assert result2.output == {"label": "negative"}
        assert result2.cost.inference_cost == 0.0002

        # Check accumulated stats
        assert model.prediction_count == 2
        assert model.total_cost == 0.0002  # Only second had cost
        assert model.avg_latency_ms > 0

    def test_stats_persist_across_calls(self):
        """Test that stats persist and accumulate across multiple calls."""
        config = {
            "type": "llm",
            "model": "openai/gpt-4o-mini",
            "system_prompt": "Classify",
        }

        model = ModelPrimitive("classifier", config)

        mock_result = {
            "result": {"label": "positive"},
            "usage": {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20},
            "cost": {"prompt_cost": 0.0001, "completion_cost": 0.0001, "total_cost": 0.0002},
        }
        model.backend.predict_sync = MagicMock(return_value=mock_result)

        # Make predictions and check stats grow monotonically
        for i in range(1, 6):
            model.predict({"text": f"Test {i}"})
            assert model.prediction_count == i
            assert model.total_cost == pytest.approx(0.0002 * i)
            assert model.avg_latency_ms > 0
