"""
Tests for Model primitive data types.
"""

import json
from dataclasses import asdict

import pytest

from tactus.models.types import PredictionCost, PredictionResult


class TestPredictionCost:
    """Test PredictionCost data class."""

    def test_empty_cost(self):
        """Test cost with no fields set."""
        cost = PredictionCost()
        assert cost.inference_cost is None
        assert cost.compute_time_ms is None
        assert cost.tokens_in is None
        assert cost.tokens_out is None
        assert cost.total_cost is None

    def test_llm_cost(self):
        """Test cost for LLM prediction."""
        cost = PredictionCost(
            inference_cost=0.0003, compute_time_ms=250.5, tokens_in=10, tokens_out=20
        )
        assert cost.inference_cost == 0.0003
        assert cost.compute_time_ms == 250.5
        assert cost.tokens_in == 10
        assert cost.tokens_out == 20
        assert cost.total_cost == 0.0003

    def test_http_cost(self):
        """Test cost for HTTP prediction."""
        cost = PredictionCost(inference_cost=0.01, compute_time_ms=150.0)
        assert cost.inference_cost == 0.01
        assert cost.compute_time_ms == 150.0
        assert cost.tokens_in is None
        assert cost.tokens_out is None

    def test_local_model_cost(self):
        """Test cost for local model (only timing)."""
        cost = PredictionCost(compute_time_ms=50.0)
        assert cost.inference_cost is None
        assert cost.compute_time_ms == 50.0
        assert cost.total_cost is None

    def test_serialize_deserialize(self):
        """Test cost serialization and deserialization."""
        cost = PredictionCost(
            inference_cost=0.0005, compute_time_ms=300.0, tokens_in=15, tokens_out=25
        )

        # Serialize to dict
        cost_dict = asdict(cost)
        assert cost_dict["inference_cost"] == 0.0005
        assert cost_dict["tokens_in"] == 15

        # Serialize to JSON
        cost_json = json.dumps(cost_dict)
        assert "0.0005" in cost_json

        # Deserialize from dict
        restored = PredictionCost(**json.loads(cost_json))
        assert restored.inference_cost == cost.inference_cost
        assert restored.tokens_in == cost.tokens_in


class TestPredictionResult:
    """Test PredictionResult data class."""

    def test_minimal_result(self):
        """Test result with only output."""
        result = PredictionResult(output={"label": "positive"})
        assert result.output == {"label": "positive"}
        assert result.cost is None
        assert result.model_version is None
        assert result.backend_type is None

    def test_full_result(self):
        """Test result with all fields."""
        cost = PredictionCost(inference_cost=0.0003, compute_time_ms=200.0)
        result = PredictionResult(
            output={"label": "positive", "confidence": 0.95},
            cost=cost,
            model_version="v1.2.3",
            backend_type="llm",
        )

        assert result.output["label"] == "positive"
        assert result.cost.inference_cost == 0.0003
        assert result.model_version == "v1.2.3"
        assert result.backend_type == "llm"

    def test_result_with_string_output(self):
        """Test result with non-dict output."""
        result = PredictionResult(output="positive")
        assert result.output == "positive"

    def test_result_with_list_output(self):
        """Test result with list output."""
        result = PredictionResult(output=[0.1, 0.9])
        assert result.output == [0.1, 0.9]

    def test_serialize_deserialize(self):
        """Test result serialization and deserialization."""
        cost = PredictionCost(
            inference_cost=0.0004, compute_time_ms=250.0, tokens_in=12, tokens_out=18
        )
        result = PredictionResult(
            output={"label": "negative"},
            cost=cost,
            model_version="v2.0.0",
            backend_type="http",
        )

        # Serialize to dict
        result_dict = {
            "output": result.output,
            "cost": asdict(result.cost) if result.cost else None,
            "model_version": result.model_version,
            "backend_type": result.backend_type,
        }

        # Serialize to JSON
        result_json = json.dumps(result_dict)
        assert "negative" in result_json

        # Deserialize from dict
        restored_dict = json.loads(result_json)
        restored_cost = (
            PredictionCost(**restored_dict["cost"]) if restored_dict["cost"] else None
        )
        restored = PredictionResult(
            output=restored_dict["output"],
            cost=restored_cost,
            model_version=restored_dict["model_version"],
            backend_type=restored_dict["backend_type"],
        )

        assert restored.output == result.output
        assert restored.cost.inference_cost == result.cost.inference_cost
        assert restored.model_version == result.model_version
        assert restored.backend_type == result.backend_type
