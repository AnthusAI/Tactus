import types

import pytest
import dspy

from tactus.dspy.agent import DSPyAgentHandle
from tactus.protocols.cost import UsageStats, CostStats


def _make_agent(monkeypatch, **kwargs):
    monkeypatch.setattr(
        DSPyAgentHandle,
        "_build_module",
        lambda self: types.SimpleNamespace(module=lambda **_kw: dspy.Prediction(response="ok")),
    )
    return DSPyAgentHandle(name="agent", model="openai/gpt-4o", **kwargs)


def test_add_usage_and_cost_accumulates(monkeypatch):
    agent = _make_agent(monkeypatch)
    usage = UsageStats(prompt_tokens=1, completion_tokens=2, total_tokens=3)
    cost = CostStats(total_cost=1.2, prompt_cost=0.4, completion_cost=0.8, model="m", provider="p")

    agent._add_usage_and_cost(usage, cost)

    assert agent.usage.prompt_tokens == 1
    assert agent.usage.completion_tokens == 2
    assert agent.usage.total_tokens == 3
    assert agent.cost().total_cost == 1.2
    assert agent.cost().model == "m"
    assert agent.cost().provider == "p"


def test_extract_last_call_stats_no_history(monkeypatch):
    agent = _make_agent(monkeypatch)
    monkeypatch.setattr(dspy.settings, "lm", None)

    usage, cost = agent._extract_last_call_stats()

    assert usage.total_tokens == 0
    assert cost.total_cost == 0


def test_extract_last_call_stats_with_cost(monkeypatch):
    agent = _make_agent(monkeypatch)

    class FakeLM:
        history = [
            {
                "usage": {"prompt_tokens": 3, "completion_tokens": 1, "total_tokens": 4},
                "cost": 2.0,
                "model": "openai/gpt-4o",
            }
        ]

    monkeypatch.setattr(dspy.settings, "lm", FakeLM())

    usage, cost = agent._extract_last_call_stats()

    assert usage.total_tokens == 4
    assert cost.total_cost == 2.0
    assert cost.provider == "openai"


def test_extract_last_call_stats_uses_cost_per_token(monkeypatch):
    agent = _make_agent(monkeypatch)

    class FakeLM:
        history = [
            {
                "usage": {"prompt_tokens": 2, "completion_tokens": 2, "total_tokens": 4},
                "cost": None,
                "model": "openai/gpt-4o",
            }
        ]

    def fake_cost_per_token(*_args, **_kwargs):
        return 0.5, 0.5

    monkeypatch.setattr(dspy.settings, "lm", FakeLM())
    monkeypatch.setattr("litellm.cost_calculator.cost_per_token", fake_cost_per_token)

    usage, cost = agent._extract_last_call_stats()

    assert usage.total_tokens == 4
    assert cost.total_cost == 1.0


def test_prediction_to_value_with_schema(monkeypatch):
    agent = _make_agent(monkeypatch, output_schema={"answer": {"type": "string"}})

    class FakePrediction:
        def data(self):
            return {"response": '{"answer": "ok"}'}

        @property
        def message(self):
            return ""

    assert agent._prediction_to_value(FakePrediction()) == {"answer": "ok"}


def test_prediction_to_value_with_multiple_fields(monkeypatch):
    agent = _make_agent(monkeypatch)

    class FakePrediction:
        def data(self):
            return {"response": "ok", "score": 1}

        @property
        def message(self):
            return ""

    assert agent._prediction_to_value(FakePrediction()) == {"response": "ok", "score": 1}


def test_prediction_to_value_falls_back_to_message(monkeypatch):
    agent = _make_agent(monkeypatch)

    class FakePrediction:
        def data(self):
            return {}

        @property
        def message(self):
            return "fallback"

    assert agent._prediction_to_value(FakePrediction()) == "fallback"


def test_module_to_strategy(monkeypatch):
    agent = _make_agent(monkeypatch)
    assert agent._module_to_strategy("Predict") == "predict"

    with pytest.raises(ValueError, match="Unknown module"):
        agent._module_to_strategy("weird")
