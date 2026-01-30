import pytest

from tactus.dspy.agent import DSPyAgentHandle
from tactus.dspy.prediction import TactusPrediction
from tactus.dspy.config import reset_lm_configuration
from tactus.protocols.cost import CostStats, UsageStats


class DummyPrediction(dict):
    """Minimal prediction object that behaves like a DSPy Prediction."""

    pass


@pytest.fixture(autouse=True)
def reset_lm():
    reset_lm_configuration()


def make_agent(**overrides):
    params = {
        "name": "agent",
        "system_prompt": "Test",
        "model": "openai/gpt-4o-mini",
    }
    params.update(overrides)
    return DSPyAgentHandle(**params)


def test_prediction_to_value_prefers_response():
    agent = make_agent()
    prediction = DummyPrediction(response="hi")
    wrapped = TactusPrediction(prediction)

    assert agent._prediction_to_value(wrapped) == "hi"


def test_prediction_to_value_parses_json_when_schema_set():
    agent = make_agent(output_schema={"result": {"type": "object"}})
    prediction = DummyPrediction(response='{"ok": true}')
    wrapped = TactusPrediction(prediction)

    assert agent._prediction_to_value(wrapped) == {"ok": True}


def test_prediction_to_value_returns_structured_fields():
    agent = make_agent()
    prediction = DummyPrediction(a=1, b=2, tool_calls=[{"id": "x"}])
    wrapped = TactusPrediction(prediction)

    assert agent._prediction_to_value(wrapped) == {"a": 1, "b": 2}


def test_wrap_as_result_includes_usage():
    agent = make_agent()
    prediction = DummyPrediction(response="ok")
    wrapped = TactusPrediction(prediction)
    usage = UsageStats(prompt_tokens=1, completion_tokens=2, total_tokens=3)
    cost = CostStats(total_cost=0.01, prompt_cost=0.002, completion_cost=0.008)

    result = agent._wrap_as_result(wrapped, usage, cost)
    assert result.output == "ok"
    assert result.usage.total_tokens == 3
    assert result.cost_stats.total_cost == 0.01


def test_add_usage_and_cost_accumulates():
    agent = make_agent()
    agent._add_usage_and_cost(
        UsageStats(prompt_tokens=1, completion_tokens=2, total_tokens=3), CostStats(total_cost=0.1)
    )
    agent._add_usage_and_cost(
        UsageStats(prompt_tokens=4, completion_tokens=5, total_tokens=9), CostStats(total_cost=0.2)
    )

    assert agent.usage.total_tokens == 12
    assert agent.cost().total_cost == 0.30000000000000004


def test_extract_last_call_stats_handles_no_lm(monkeypatch):
    import dspy

    agent = make_agent()
    monkeypatch.setattr(dspy.settings, "lm", None)
    usage, cost = agent._extract_last_call_stats()

    assert usage.total_tokens == 0
    assert cost.total_cost == 0


def test_extract_last_call_stats_reads_lm_history(monkeypatch):
    import dspy

    agent = make_agent()
    dummy_lm = type(
        "DummyLM",
        (),
        {
            "history": [
                {
                    "usage": {"prompt_tokens": 2, "completion_tokens": 3, "total_tokens": 5},
                    "model": "openai/gpt-4o",
                }
            ]
        },
    )()
    monkeypatch.setattr(dspy.settings, "lm", dummy_lm)
    usage, cost = agent._extract_last_call_stats()

    assert usage.total_tokens == 5
    assert cost.model == "openai/gpt-4o"
