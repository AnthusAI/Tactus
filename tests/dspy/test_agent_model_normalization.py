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


def test_agent_auto_config_uses_normalized_model(monkeypatch):
    # Avoid actually running an LM call.
    monkeypatch.setattr(
        DSPyAgentHandle,
        "_build_module",
        lambda self: types.SimpleNamespace(module=lambda **_kw: dspy.Prediction(response="ok")),
    )

    # Force the agent to attempt auto-config.
    monkeypatch.setattr("tactus.dspy.config.get_current_lm", lambda: None)

    called = {}

    def fake_configure_lm(model: str, **kwargs):
        called["model"] = model
        called["kwargs"] = kwargs
        return None

    monkeypatch.setattr("tactus.dspy.config.configure_lm", fake_configure_lm)

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
