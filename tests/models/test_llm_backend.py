"""
Tests for LLM model backend.
"""

import pytest
from unittest.mock import MagicMock

from tactus.backends.llm_backend import LLMModelBackend
from tactus.primitives.model import ModelPrimitive
from tactus.protocols.cost import CostStats, UsageStats
from tactus.protocols.result import TactusResult


class TestLLMModelBackend:
    """Test LLM model backend functionality."""

    def test_llm_backend_initialization(self):
        """Test LLM backend initializes correctly."""
        backend = LLMModelBackend(
            model="openai/gpt-4o-mini",
            system_prompt="Classify sentiment as positive or negative",
            temperature=0.0,
        )

        assert backend.model == "openai/gpt-4o-mini"
        assert backend.system_prompt == "Classify sentiment as positive or negative"
        assert backend.temperature == 0.0
        assert backend.retries == 3
        assert backend.parse_direction == "end"

    def test_llm_backend_predict_success(self):
        """Test LLM backend successfully predicts with valid response."""
        backend = LLMModelBackend(
            model="openai/gpt-4o-mini",
            system_prompt="Classify sentiment",
        )

        # Mock the internal agent's __call__ method
        mock_result = TactusResult(
            output={"response": '{"label": "positive", "confidence": 0.95}'},
            usage=UsageStats(prompt_tokens=10, completion_tokens=20, total_tokens=30),
            cost_stats=CostStats(prompt_cost=0.0001, completion_cost=0.0002, total_cost=0.0003),
        )
        backend._agent = MagicMock(return_value=mock_result)

        result = backend.predict_sync({"text": "I love this!"})

        assert result["result"] == {"label": "positive", "confidence": 0.95}
        assert result["usage"]["prompt_tokens"] == 10
        assert result["usage"]["completion_tokens"] == 20
        assert result["cost"]["total_cost"] == 0.0003

    def test_llm_backend_parse_direction_start(self):
        """Test LLM backend parses from start for fine-tuned models."""
        backend = LLMModelBackend(
            model="openai/gpt-4o-mini",
            system_prompt="Classify",
            parse_direction="start",
        )

        # Mock response with JSON at start, followed by reasoning
        mock_result = TactusResult(
            output={
                "response": '{"label": "positive"} This is because the text expresses happiness.'
            },
            usage=UsageStats(prompt_tokens=10, completion_tokens=20, total_tokens=30),
            cost_stats=CostStats(prompt_cost=0.0001, completion_cost=0.0002, total_cost=0.0003),
        )
        backend._agent = MagicMock(return_value=mock_result)

        result = backend.predict_sync({"text": "Great!"})

        assert result["result"] == {"label": "positive"}

    def test_llm_backend_parse_direction_end(self):
        """Test LLM backend parses from end for chain-of-thought."""
        backend = LLMModelBackend(
            model="openai/gpt-4o-mini",
            system_prompt="Classify",
            parse_direction="end",
        )

        # Mock response with reasoning followed by JSON
        mock_result = TactusResult(
            output={
                "response": 'Let me analyze this text. The sentiment is clearly positive. {"label": "positive"}'
            },
            usage=UsageStats(prompt_tokens=10, completion_tokens=30, total_tokens=40),
            cost_stats=CostStats(prompt_cost=0.0001, completion_cost=0.0003, total_cost=0.0004),
        )
        backend._agent = MagicMock(return_value=mock_result)

        result = backend.predict_sync({"text": "Amazing!"})

        assert result["result"] == {"label": "positive"}

    def test_llm_backend_retry_on_invalid_response(self):
        """Test LLM backend retries on invalid response."""
        backend = LLMModelBackend(
            model="openai/gpt-4o-mini",
            system_prompt="Classify",
            retries=2,
        )

        # First call returns invalid JSON, second returns valid
        invalid_result = TactusResult(
            output={"response": "Not JSON at all"},
            usage=UsageStats(prompt_tokens=10, completion_tokens=5, total_tokens=15),
            cost_stats=CostStats(prompt_cost=0.0001, completion_cost=0.00005, total_cost=0.00015),
        )
        valid_result = TactusResult(
            output={"response": '{"label": "positive"}'},
            usage=UsageStats(prompt_tokens=10, completion_tokens=10, total_tokens=20),
            cost_stats=CostStats(prompt_cost=0.0001, completion_cost=0.0001, total_cost=0.0002),
        )

        backend._agent = MagicMock(side_effect=[invalid_result, valid_result])

        result = backend.predict_sync({"text": "Good"})

        assert result["result"] == {"label": "positive"}
        assert backend._agent.call_count == 2

    def test_llm_backend_fails_after_max_retries(self):
        """Test LLM backend fails after exhausting retries."""
        backend = LLMModelBackend(
            model="openai/gpt-4o-mini",
            system_prompt="Classify",
            retries=2,
        )

        # All calls return invalid JSON
        invalid_result = TactusResult(
            output={"response": "Not JSON"},
            usage=UsageStats(prompt_tokens=10, completion_tokens=5, total_tokens=15),
            cost_stats=CostStats(prompt_cost=0.0001, completion_cost=0.00005, total_cost=0.00015),
        )

        backend._agent = MagicMock(return_value=invalid_result)

        with pytest.raises(ValueError, match="failed to produce valid output after"):
            backend.predict_sync({"text": "Test"})

        # Should call retries + 1 times
        assert backend._agent.call_count == 3

    def test_llm_backend_cost_tracking(self):
        """Test LLM backend tracks cumulative costs."""
        backend = LLMModelBackend(
            model="openai/gpt-4o-mini",
            system_prompt="Classify",
        )

        mock_result1 = TactusResult(
            output={"response": '{"label": "positive"}'},
            usage=UsageStats(prompt_tokens=10, completion_tokens=10, total_tokens=20),
            cost_stats=CostStats(prompt_cost=0.0001, completion_cost=0.0001, total_cost=0.0002),
        )
        mock_result2 = TactusResult(
            output={"response": '{"label": "negative"}'},
            usage=UsageStats(prompt_tokens=15, completion_tokens=12, total_tokens=27),
            cost_stats=CostStats(prompt_cost=0.00015, completion_cost=0.00012, total_cost=0.00027),
        )

        backend._agent = MagicMock(side_effect=[mock_result1, mock_result2])

        backend.predict_sync({"text": "Great!"})
        backend.predict_sync({"text": "Terrible!"})

        # Check cumulative stats
        assert backend.usage.prompt_tokens == 25
        assert backend.usage.completion_tokens == 22
        assert backend.usage.total_tokens == 47
        assert backend.cost.total_cost == pytest.approx(0.00047)


class TestModelPrimitiveLLMBackend:
    """Test Model primitive with LLM backend."""

    def test_model_primitive_creates_llm_backend(self):
        """Test Model primitive creates LLM backend for type='llm'."""
        config = {
            "type": "llm",
            "model": "openai/gpt-4o-mini",
            "system_prompt": "Classify sentiment",
            "input": {"text": "string"},
            "output": {"label": "string", "confidence": "float"},
        }

        model = ModelPrimitive("sentiment_classifier", config)

        assert isinstance(model.backend, LLMModelBackend)
        assert model.backend.model == "openai/gpt-4o-mini"

    def test_model_primitive_llm_predict(self):
        """Test Model primitive predict with LLM backend."""
        config = {
            "type": "llm",
            "model": "openai/gpt-4o-mini",
            "system_prompt": "Classify sentiment",
            "input": {"text": "string"},
            "output": {"label": "string"},
        }

        model = ModelPrimitive("classifier", config)

        # Mock the backend
        mock_result = {
            "result": {"label": "positive"},
            "usage": {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20},
            "cost": {"prompt_cost": 0.0001, "completion_cost": 0.0001, "total_cost": 0.0002},
        }
        model.backend.predict_sync = MagicMock(return_value=mock_result)

        result = model.predict({"text": "I love this!"})

        # Model returns PredictionResult wrapping the output
        assert result.output == {"label": "positive"}
        assert result.cost.tokens_in == 10
        assert result.cost.tokens_out == 10
        assert result.cost.inference_cost == 0.0002
        assert result.backend_type == "llm"

        # Test dict-like access for backward compatibility
        assert result["output"] == {"label": "positive"}
        assert result["label"] == "positive"  # Nested access

    def test_model_primitive_llm_input_validation(self):
        """Test Model primitive validates input before LLM backend call."""
        config = {
            "type": "llm",
            "model": "openai/gpt-4o-mini",
            "system_prompt": "Classify",
            "input": {"text": "string", "lang": "string"},
        }

        model = ModelPrimitive("classifier", config)
        model.backend.predict_sync = MagicMock()

        # Missing required field should fail validation before backend call
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            model.predict({"text": "Hello"})  # Missing 'lang'

        model.backend.predict_sync.assert_not_called()
