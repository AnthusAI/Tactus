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

    def test_llm_backend_passes_gpt5_controls_to_agent(self, monkeypatch):
        """Test LLM backend forwards runtime GPT-5 controls to its internal agent."""
        captured = {}

        class FakeAgent:
            def __init__(self, **kwargs):
                captured.update(kwargs)

        monkeypatch.setattr("tactus.backends.llm_backend.DSPyAgentHandle", FakeAgent)

        backend = LLMModelBackend(
            model="openai/gpt-5-mini",
            system_prompt="Classify sentiment",
            reasoning_effort="minimal",
            verbosity="high",
        )

        assert backend.reasoning_effort == "minimal"
        assert backend.verbosity == "high"
        assert captured["reasoning_effort"] == "minimal"
        assert captured["verbosity"] == "high"

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

        assert result["result"] == {"response": '{"label": "positive", "confidence": 0.95}'}
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

        assert result["result"] == {
            "response": '{"label": "positive"} This is because the text expresses happiness.'
        }

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

        assert result["result"] == {
            "response": 'Let me analyze this text. The sentiment is clearly positive. {"label": "positive"}'
        }

    def test_llm_backend_retry_on_invalid_response(self):
        """Test LLM backend returns raw response text without JSON retries/parsing."""
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

        assert result["result"] == {"response": "Not JSON at all"}
        assert backend._agent.call_count == 1

    def test_llm_backend_fails_after_max_retries(self):
        """Test LLM backend surfaces raw response when content is not JSON."""
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
        result = backend.predict_sync({"text": "Test"})

        assert result["result"] == {"response": "Not JSON"}
        assert backend._agent.call_count == 1

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

    def test_model_primitive_passes_runtime_gpt5_controls_to_llm_backend(self):
        """Test Model primitive forwards runtime GPT-5 controls to type='llm' backend."""
        config = {
            "type": "llm",
            "model": "openai/gpt-5-mini",
            "system_prompt": "Classify sentiment",
            "input": {"text": "string"},
            "output": {"label": "string", "confidence": "float"},
        }

        model = ModelPrimitive(
            "sentiment_classifier",
            config,
            reasoning_effort="xhigh",
            verbosity="low",
        )

        assert model.backend.reasoning_effort == "xhigh"
        assert model.backend.verbosity == "low"

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

    async def test_llm_backend_async_predict(self):
        """Test LLM backend async predict() wrapper."""
        backend = LLMModelBackend(
            model="openai/gpt-4o-mini",
            system_prompt="Classify sentiment",
        )

        # Mock the predict_sync method
        mock_result = {
            "result": {"label": "positive"},
            "usage": {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20},
            "cost": {"prompt_cost": 0.0001, "completion_cost": 0.0001, "total_cost": 0.0002},
        }
        backend.predict_sync = MagicMock(return_value=mock_result)

        # Call async predict
        result = await backend.predict({"text": "Great!"})

        assert result["result"] == {"label": "positive"}
        backend.predict_sync.assert_called_once_with({"text": "Great!"})

    def test_llm_backend_non_dict_input(self):
        """Test LLM backend with non-dict input (str branch)."""
        backend = LLMModelBackend(
            model="openai/gpt-4o-mini",
            system_prompt="Classify sentiment",
        )

        # Mock the internal agent's __call__ method
        mock_result = TactusResult(
            output={"response": '{"label": "positive"}'},
            usage=UsageStats(prompt_tokens=10, completion_tokens=10, total_tokens=20),
            cost_stats=CostStats(prompt_cost=0.0001, completion_cost=0.0001, total_cost=0.0002),
        )
        backend._agent = MagicMock(return_value=mock_result)

        # Pass string input instead of dict
        result = backend.predict_sync("Hello world")

        # Should convert to string and pass to agent
        backend._agent.assert_called_once()
        call_args = backend._agent.call_args[0][0]
        assert call_args["message"] == "Hello world"
        assert result["result"] == {"response": '{"label": "positive"}'}

    def test_llm_backend_string_output_from_agent(self):
        """Test LLM backend when agent_result.output is string instead of dict."""
        backend = LLMModelBackend(
            model="openai/gpt-4o-mini",
            system_prompt="Classify sentiment",
        )

        # Mock the internal agent to return string output
        mock_result = TactusResult(
            output='{"label": "negative"}',  # String instead of dict
            usage=UsageStats(prompt_tokens=10, completion_tokens=10, total_tokens=20),
            cost_stats=CostStats(prompt_cost=0.0001, completion_cost=0.0001, total_cost=0.0002),
        )
        backend._agent = MagicMock(return_value=mock_result)

        result = backend.predict_sync({"text": "Bad product"})

        assert result["result"] == {"response": '{"label": "negative"}'}

    def test_llm_backend_parse_error_start_no_json(self):
        """Test LLM backend returns raw text when no JSON is present."""
        backend = LLMModelBackend(
            model="openai/gpt-4o-mini",
            system_prompt="Classify",
            parse_direction="start",
            retries=0,  # No retries to test error path
        )

        # Mock response with no valid JSON at start
        mock_result = TactusResult(
            output={"response": "This text does not start with JSON"},
            usage=UsageStats(prompt_tokens=10, completion_tokens=10, total_tokens=20),
            cost_stats=CostStats(prompt_cost=0.0001, completion_cost=0.0001, total_cost=0.0002),
        )
        backend._agent = MagicMock(return_value=mock_result)
        result = backend.predict_sync({"text": "Test"})

        assert result["result"] == {"response": "This text does not start with JSON"}

    def test_llm_backend_parse_error_start_invalid_json(self):
        """Test LLM backend returns raw text when JSON-looking content is invalid."""
        backend = LLMModelBackend(
            model="openai/gpt-4o-mini",
            system_prompt="Classify",
            parse_direction="start",
            retries=0,
        )

        # Mock response with invalid JSON at start
        mock_result = TactusResult(
            output={"response": "{invalid json here}"},
            usage=UsageStats(prompt_tokens=10, completion_tokens=10, total_tokens=20),
            cost_stats=CostStats(prompt_cost=0.0001, completion_cost=0.0001, total_cost=0.0002),
        )
        backend._agent = MagicMock(return_value=mock_result)
        result = backend.predict_sync({"text": "Test"})

        assert result["result"] == {"response": "{invalid json here}"}

    def test_llm_backend_parse_error_end_no_json(self):
        """Test LLM backend returns raw text when response does not end with JSON."""
        backend = LLMModelBackend(
            model="openai/gpt-4o-mini",
            system_prompt="Classify",
            parse_direction="end",
            retries=0,
        )

        # Mock response with no valid JSON at end
        mock_result = TactusResult(
            output={"response": "This text does not end with JSON at all"},
            usage=UsageStats(prompt_tokens=10, completion_tokens=10, total_tokens=20),
            cost_stats=CostStats(prompt_cost=0.0001, completion_cost=0.0001, total_cost=0.0002),
        )
        backend._agent = MagicMock(return_value=mock_result)
        result = backend.predict_sync({"text": "Test"})

        assert result["result"] == {"response": "This text does not end with JSON at all"}

    def test_llm_backend_parse_error_end_invalid_json(self):
        """Test LLM backend returns raw text for invalid JSON fragments."""
        backend = LLMModelBackend(
            model="openai/gpt-4o-mini",
            system_prompt="Classify",
            parse_direction="end",
            retries=0,
        )

        # Mock response that ends with } but has invalid JSON throughout
        mock_result = TactusResult(
            output={"response": "Some reasoning text {invalid json here}"},
            usage=UsageStats(prompt_tokens=10, completion_tokens=10, total_tokens=20),
            cost_stats=CostStats(prompt_cost=0.0001, completion_cost=0.0001, total_cost=0.0002),
        )
        backend._agent = MagicMock(return_value=mock_result)
        result = backend.predict_sync({"text": "Test"})

        assert result["result"] == {"response": "Some reasoning text {invalid json here}"}

    def test_llm_backend_agent_exception_propagates(self):
        """Test that exceptions from agent propagate correctly."""
        backend = LLMModelBackend(
            model="openai/gpt-4o-mini",
            system_prompt="Classify",
            retries=1,
        )

        # Mock agent to raise a non-JSON exception
        backend._agent = MagicMock(side_effect=RuntimeError("Agent failed"))

        with pytest.raises(RuntimeError, match="Agent failed"):
            backend.predict_sync({"text": "Test"})
