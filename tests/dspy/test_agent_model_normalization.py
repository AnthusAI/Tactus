import types

import dspy

from tactus.dspy.agent import DSPyAgentHandle, _normalize_model_for_litellm


def test_normalize_model_for_litellm_passthrough():
    assert _normalize_model_for_litellm("openai/gpt-4o-mini", None) == "openai/gpt-4o-mini"


def test_normalize_model_for_litellm_colon_provider_separator():
    assert _normalize_model_for_litellm("openai:gpt-4o-mini", None) == "openai/gpt-4o-mini"


def test_normalize_model_for_litellm_combines_provider_and_model():
    assert _normalize_model_for_litellm("gpt-4o-mini", "openai") == "openai/gpt-4o-mini"


def test_normalize_model_for_litellm_does_not_rewrite_version_colon_when_provider_given():
    model_id = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
    assert _normalize_model_for_litellm(model_id, "bedrock") == f"bedrock/{model_id}"


def test_agent_scoped_lm_uses_normalized_model(monkeypatch):
    # Avoid actually running an LM call.
    monkeypatch.setattr(
        DSPyAgentHandle,
        "_build_module",
        lambda self: types.SimpleNamespace(module=lambda **_kw: dspy.Prediction(response="ok")),
    )

    called = {}

    def fake_create_lm(model: str, **kwargs):
        called["model"] = model
        called["kwargs"] = kwargs
        return object()

    monkeypatch.setattr("tactus.dspy.config.create_lm", fake_create_lm)

    agent = DSPyAgentHandle(
        name="agent",
        provider="openai",
        model="gpt-4o-mini",
        reasoning_effort="xhigh",
        verbosity="low",
    )
    agent({"message": "hello"})

    assert called["model"] == "openai/gpt-4o-mini"
    assert called["kwargs"]["reasoning_effort"] == "xhigh"
    assert called["kwargs"]["verbosity"] == "low"


def test_agents_do_not_inherit_previous_lm_configuration(monkeypatch):
    class FakeLM:
        def __init__(self, model: str, **kwargs):
            self.model = model
            self.kwargs = kwargs

    def fake_create_lm(model: str, **kwargs):
        return FakeLM(model, **kwargs)

    def fake_turn(_opts, _context):
        lm = dspy.settings.lm
        return dspy.Prediction(response=f"{lm.model}:{lm.kwargs.get('max_tokens')}")

    monkeypatch.setattr("tactus.dspy.config.create_lm", fake_create_lm)

    first = DSPyAgentHandle(
        name="first",
        model="openai/model-one",
        max_tokens=16,
    )
    second = DSPyAgentHandle(
        name="second",
        model="openai/model-two",
        max_tokens=220,
    )

    for agent in (first, second):
        monkeypatch.setattr(agent, "_should_stream", lambda: False)
        monkeypatch.setattr(agent, "_turn_without_streaming", fake_turn)

    first_result = first({"message": "first"})
    second_result = second({"message": "second"})

    assert first_result.response == "openai/model-one:16"
    assert second_result.response == "openai/model-two:220"
