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


class FakeStatePrimitive:
    def __init__(self, initial=None):
        self.values = dict(initial or {})

    def get(self, key):
        return self.values.get(key)

    def set(self, key, value):
        self.values[key] = value


def test_inject_pending_steering_adds_system_message_and_watermark(monkeypatch):
    calls = []

    class FakeChatRecorder:
        def get_steering_messages(self, **kwargs):
            calls.append(kwargs)
            return {
                "watermark": "2026-05-05T12:01:00Z",
                "messages": [
                    {
                        "created_at": "2026-05-05T12:00:00Z",
                        "content": "Focus on retry behavior.",
                    }
                ],
            }

    agent = _make_agent(monkeypatch, chat_recorder=FakeChatRecorder())
    agent._state_primitive = FakeStatePrimitive(
        {"procedure_steering_watermark:agent": "2026-05-05T11:59:00Z"}
    )

    agent._inject_pending_steering()

    assert calls == [
        {
            "after": "2026-05-05T11:59:00Z",
            "agent_name": "agent",
            "limit": 20,
        }
    ]
    assert agent._state_primitive.get("procedure_steering_watermark:agent") == (
        "2026-05-05T12:01:00Z"
    )
    history = agent.get_history()
    assert len(history) == 1
    assert history[0]["role"] == "system"
    assert "USER STEERING RECEIVED MID-RUN" in history[0]["content"]
    assert "Focus on retry behavior." in history[0]["content"]


def test_inject_pending_steering_updates_empty_watermark_without_history(monkeypatch):
    class FakeChatRecorder:
        def get_steering_messages(self, **_kwargs):
            return {"watermark": "2026-05-05T12:02:00Z", "messages": []}

    agent = _make_agent(monkeypatch, chat_recorder=FakeChatRecorder())
    agent._state_primitive = FakeStatePrimitive()

    agent._inject_pending_steering()

    assert agent.get_history() == []
    assert agent._state_primitive.get("procedure_steering_watermark:agent") == (
        "2026-05-05T12:02:00Z"
    )


def test_agent_with_steering_disabled_does_not_query_chat_recorder(monkeypatch):
    calls = []

    class FakeChatRecorder:
        def get_steering_messages(self, **kwargs):
            calls.append(kwargs)
            return {"watermark": "", "messages": []}

    agent = _make_agent(
        monkeypatch,
        chat_recorder=FakeChatRecorder(),
        steering_enabled=False,
    )
    agent._state_primitive = FakeStatePrimitive()

    agent._inject_pending_steering()

    assert calls == []
    assert agent.get_history() == []


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


def test_agent_request_timeout_is_part_of_scoped_lm_configuration(monkeypatch):
    agent = _make_agent(monkeypatch, request_timeout=37)

    model, kwargs = agent._agent_lm_config()

    assert model == "openai/gpt-4o"
    assert kwargs["request_timeout"] == 37


def test_agent_uses_prewarmed_lm_and_adapter(monkeypatch):
    agent = _make_agent(monkeypatch, request_timeout=37)
    warmed_lm = object()
    warmed_adapter = object()

    monkeypatch.setattr(
        "tactus.dspy.config.prewarm_lm",
        lambda model, **kwargs: types.SimpleNamespace(lm=warmed_lm, adapter=warmed_adapter),
    )

    assert agent.prewarm().lm is warmed_lm
    context = agent._dspy_lm_context()
    assert context is not None


def test_non_streaming_turn_emits_supported_lifecycle_events(monkeypatch):
    events = []
    agent = _make_agent(
        monkeypatch,
        disable_streaming=True,
        lifecycle_hooks=[events.append],
    )

    agent({"message": "hello"})

    phases = [event.phase for event in events]
    assert phases == [
        "agent_preparation_started",
        "agent_preparation_completed",
        "lm_initialization_started",
        "lm_initialization_completed",
        "provider_request_started",
        "provider_request_completed",
    ]
    request_started = next(event for event in events if event.phase == "provider_request_started")
    assert request_started.prompt_context["user_message"] == "hello"
