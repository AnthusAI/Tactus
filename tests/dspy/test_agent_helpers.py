from types import SimpleNamespace

import dspy
import pytest

from tactus.dspy.agent import DSPyAgentHandle
from tactus.dspy.prediction import TactusPrediction
from tactus.protocols.cost import CostStats, UsageStats


@pytest.fixture
def agent():
    return DSPyAgentHandle(name="tester")


def test_add_usage_and_cost_accumulates(agent):
    usage = UsageStats(prompt_tokens=2, completion_tokens=3, total_tokens=5)
    cost = CostStats(total_cost=0.05, prompt_cost=0.02, completion_cost=0.03, model="m")

    agent._add_usage_and_cost(usage, cost)

    assert agent.usage.total_tokens == 5
    assert agent.cost().total_cost == 0.05
    assert agent.cost().model == "m"


def test_extract_last_call_stats_empty_history(monkeypatch, agent):
    monkeypatch.setattr(dspy.settings, "lm", None)

    usage, cost = agent._extract_last_call_stats()

    assert usage.total_tokens == 0
    assert cost.total_cost == 0.0


def test_extract_last_call_stats_from_history(monkeypatch, agent):
    last_call = {
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        "model": "openai/gpt-4o",
        "cost": 0.30,
    }
    fake_lm = SimpleNamespace(history=[last_call])
    monkeypatch.setattr(dspy.settings, "lm", fake_lm)

    usage, cost = agent._extract_last_call_stats()

    assert usage.prompt_tokens == 10
    assert usage.total_tokens == 15
    assert cost.total_cost == 0.30
    assert cost.provider == "openai"


def test_module_to_strategy(agent):
    assert agent._module_to_strategy("Predict") == "predict"
    assert agent._module_to_strategy("ChainOfThought") == "chain_of_thought"
    assert agent._module_to_strategy("Raw") == "raw"

    with pytest.raises(ValueError):
        agent._module_to_strategy("Nope")


def test_prediction_to_value_json(agent):
    prediction = dspy.Prediction(response='{"a": 1}')
    wrapped = TactusPrediction(prediction)

    assert agent._prediction_to_value(wrapped) == {"a": 1}


def test_prediction_to_value_multi_field(agent):
    prediction = dspy.Prediction(response="hi", extra="value")
    wrapped = TactusPrediction(prediction)

    assert agent._prediction_to_value(wrapped) == {"response": "hi", "extra": "value"}


def test_wrap_as_result(agent):
    prediction = dspy.Prediction(response="hello")
    wrapped = TactusPrediction(prediction)
    usage = UsageStats(prompt_tokens=1, completion_tokens=1, total_tokens=2)
    cost = CostStats(total_cost=0.01)

    result = agent._wrap_as_result(wrapped, usage, cost)

    assert result.output == "hello"
    assert result.usage.total_tokens == 2
    assert result.cost_stats.total_cost == 0.01


def test_should_stream_respects_log_handler():
    handler = SimpleNamespace(supports_streaming=False)
    agent = DSPyAgentHandle(name="stream", log_handler=handler)

    assert agent._should_stream() is False

    handler.supports_streaming = True
    agent.disable_streaming = True
    assert agent._should_stream() is False


def test_wrap_mock_response_records_tool_calls():
    class DummyToolPrimitive:
        def __init__(self):
            self.calls = []

        def record_call(self, tool_name, tool_args, result, agent_name=None):
            self.calls.append((tool_name, tool_args, result, agent_name))

    agent = DSPyAgentHandle(
        name="mock",
        output_schema={"field": {"type": "string"}},
        initial_message="hi",
    )
    agent._tool_primitive = DummyToolPrimitive()
    agent._turn_count = 1

    result = agent._wrap_mock_response(
        {
            "response": "done",
            "tool_calls": [{"tool": "done", "args": {"reason": "ok"}}],
            "data": {"field": "value"},
        },
        opts={},
    )

    assert result.output == "value"
    assert agent._tool_primitive.calls[0][0] == "done"


def test_get_mock_response_with_temporal_turns():
    temporal = [
        {"when_message": "first", "message": "one", "tool_calls": []},
        {"message": "two", "tool_calls": []},
    ]
    mock_config = SimpleNamespace(
        message="default",
        tool_calls=[],
        data={},
        temporal=temporal,
    )
    registry = SimpleNamespace(agent_mocks={"agent": mock_config})

    agent = DSPyAgentHandle(name="agent", registry=registry)
    agent._turn_count = 1

    result = agent._get_mock_response({"message": "first"})

    assert result.output == "one"
