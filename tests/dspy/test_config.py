"""Tests for DSPy config utilities."""

import pytest

from tactus.dspy import config as dspy_config


def test_configure_lm_invalid_model():
    with pytest.raises(ValueError):
        dspy_config.configure_lm("gpt-4o")


def test_ensure_lm_configured_raises():
    dspy_config.reset_lm_configuration()

    with pytest.raises(RuntimeError):
        dspy_config.ensure_lm_configured()


def test_create_lm_invalid_model():
    with pytest.raises(ValueError):
        dspy_config.create_lm("")


def test_get_current_lm_after_config(monkeypatch):
    dspy_config.reset_lm_configuration()

    class FakeLM:
        pass

    def fake_configure(*args, **kwargs):
        return None

    monkeypatch.setattr(dspy_config.dspy, "LM", lambda *args, **kwargs: FakeLM())
    monkeypatch.setattr(dspy_config.dspy, "configure", fake_configure)

    lm = dspy_config.configure_lm("openai/gpt-4o")

    assert isinstance(lm, FakeLM)
    assert dspy_config.get_current_lm() is lm


def test_configure_lm_uses_brokered_lm(monkeypatch):
    dspy_config.reset_lm_configuration()

    class FakeLM:
        def __init__(self, model, **kwargs):
            self.model = model
            self.kwargs = kwargs

    monkeypatch.setenv("TACTUS_BROKER_SOCKET", "sock")
    monkeypatch.setattr("tactus.dspy.broker_lm.BrokeredLM", FakeLM)
    monkeypatch.setattr(dspy_config.dspy, "configure", lambda **_kwargs: None)

    lm = dspy_config.configure_lm("openai/gpt-4o", api_key="secret", api_base="http://x")

    assert isinstance(lm, FakeLM)
    assert "api_key" not in lm.kwargs
    assert "api_base" not in lm.kwargs


def test_configure_lm_passes_lm_kwargs(monkeypatch):
    dspy_config.reset_lm_configuration()

    captured = {}

    class FakeLM:
        def __init__(self, model, **kwargs):
            captured["model"] = model
            captured["kwargs"] = kwargs

    monkeypatch.delenv("TACTUS_BROKER_SOCKET", raising=False)
    monkeypatch.setattr(dspy_config.dspy, "LM", FakeLM)
    monkeypatch.setattr(dspy_config.dspy, "configure", lambda **_kwargs: None)

    dspy_config.configure_lm(
        "openai/gpt-4o",
        api_key="key",
        api_base="http://base",
        temperature=0.2,
        max_tokens=123,
        model_type="responses",
    )

    assert captured["model"] == "openai/gpt-4o"
    assert captured["kwargs"]["temperature"] == 0.2
    assert captured["kwargs"]["max_tokens"] == 123
    assert captured["kwargs"]["model_type"] == "responses"
    assert captured["kwargs"]["api_key"] == "key"
    assert captured["kwargs"]["api_base"] == "http://base"


def test_reset_lm_configuration_clears_state(monkeypatch):
    class FakeLM:
        pass

    dspy_config._current_lm = FakeLM()
    monkeypatch.setattr(dspy_config.dspy, "configure", lambda **kwargs: kwargs)

    dspy_config.reset_lm_configuration()

    assert dspy_config.get_current_lm() is None


def test_ensure_lm_configured_returns_current():
    class FakeLM:
        pass

    lm = FakeLM()
    dspy_config._current_lm = lm

    assert dspy_config.ensure_lm_configured() is lm


def test_create_lm_passes_kwargs(monkeypatch):
    captured = {}

    class FakeLM:
        def __init__(self, model, **kwargs):
            captured["model"] = model
            captured["kwargs"] = kwargs

    monkeypatch.setattr(dspy_config.dspy, "LM", FakeLM)

    lm = dspy_config.create_lm(
        "openai/gpt-4o",
        api_key="key",
        api_base="http://base",
        temperature=0.1,
        max_tokens=55,
        model_type="responses",
        extra="value",
    )

    assert lm is not None
    assert captured["kwargs"]["api_key"] == "key"
    assert captured["kwargs"]["api_base"] == "http://base"
    assert captured["kwargs"]["temperature"] == 0.1
    assert captured["kwargs"]["max_tokens"] == 55
    assert captured["kwargs"]["model_type"] == "responses"
    assert captured["kwargs"]["extra"] == "value"


def test_create_lm_omits_optional_fields_when_none(monkeypatch):
    captured = {}

    class FakeLM:
        def __init__(self, model, **kwargs):
            captured["model"] = model
            captured["kwargs"] = kwargs

    monkeypatch.setattr(dspy_config.dspy, "LM", FakeLM)

    dspy_config.create_lm("openai/gpt-4o", temperature=0.3, max_tokens=None)

    assert captured["model"] == "openai/gpt-4o"
    assert captured["kwargs"]["temperature"] == 0.3
    assert "api_key" not in captured["kwargs"]
    assert "api_base" not in captured["kwargs"]
    assert "max_tokens" not in captured["kwargs"]
    assert "model_type" not in captured["kwargs"]
