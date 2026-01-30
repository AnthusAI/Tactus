from types import SimpleNamespace

import pytest

import dspy
from tactus.dspy import config as dspy_config


def test_configure_lm_requires_model():
    with pytest.raises(ValueError, match="model is required"):
        dspy_config.configure_lm("")


def test_configure_lm_rejects_invalid_format():
    with pytest.raises(ValueError, match="Invalid model format"):
        dspy_config.configure_lm("gpt-4o")


def test_configure_lm_uses_broker_when_env_set(monkeypatch):
    monkeypatch.setenv("TACTUS_BROKER_SOCKET", "/tmp/broker.sock")
    captured = {}

    class FakeBrokeredLM:
        def __init__(self, model, **kwargs):
            captured["model"] = model
            captured["kwargs"] = kwargs

    class FakeAdapter:
        def __init__(self, use_native_function_calling=False):
            self.use_native_function_calling = use_native_function_calling

    monkeypatch.setattr("tactus.dspy.broker_lm.BrokeredLM", FakeBrokeredLM)
    monkeypatch.setattr("dspy.adapters.chat_adapter.ChatAdapter", FakeAdapter)

    def fake_configure(*, lm=None, adapter=None):
        captured["configured_lm"] = lm
        captured["adapter"] = adapter

    monkeypatch.setattr(dspy, "configure", fake_configure)

    lm = dspy_config.configure_lm("openai/gpt-4o", api_key="secret")
    assert captured["model"] == "openai/gpt-4o"
    assert "api_key" not in captured["kwargs"]
    assert lm is captured["configured_lm"]
    assert captured["adapter"].use_native_function_calling is True


def test_create_lm_rejects_invalid_format():
    with pytest.raises(ValueError, match="Invalid model format"):
        dspy_config.create_lm("gpt-4o")


def test_create_lm_allows_unknown_provider_with_slash(monkeypatch):
    captured = {}

    class FakeLM:
        def __init__(self, model, **kwargs):
            captured["model"] = model
            captured["kwargs"] = kwargs

    monkeypatch.setattr(dspy, "LM", FakeLM)

    lm = dspy_config.create_lm("custom/foo", temperature=0.1)

    assert lm is not None
    assert captured["model"] == "custom/foo"


def test_reset_lm_configuration_clears_global(monkeypatch):
    dspy_config._current_lm = SimpleNamespace()
    called = {}

    def fake_configure(*, lm=None, adapter=None):
        called["lm"] = lm

    monkeypatch.setattr(dspy, "configure", fake_configure)

    dspy_config.reset_lm_configuration()
    assert dspy_config._current_lm is None
    assert called["lm"] is None
