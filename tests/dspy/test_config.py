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
        reasoning_effort="high",
        verbosity="low",
    )

    assert captured["model"] == "openai/gpt-4o"
    assert captured["kwargs"]["temperature"] == 0.2
    assert captured["kwargs"]["max_tokens"] == 123
    assert captured["kwargs"]["model_type"] == "responses"
    assert captured["kwargs"]["api_key"] == "key"
    assert captured["kwargs"]["api_base"] == "http://base"
    assert captured["kwargs"]["reasoning_effort"] == "high"
    assert captured["kwargs"]["text"]["verbosity"] == "low"


def test_configure_lm_passes_chat_mode_gpt5_controls(monkeypatch):
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
        "openai/gpt-5-mini",
        model_type="chat",
        reasoning_effort="xhigh",
        verbosity="medium",
    )

    assert captured["kwargs"]["reasoning_effort"] == "xhigh"
    assert captured["kwargs"]["verbosity"] == "medium"


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
        reasoning_effort="minimal",
        verbosity="high",
        text={"format": {"type": "text"}},
        extra="value",
    )

    assert lm is not None
    assert captured["kwargs"]["api_key"] == "key"
    assert captured["kwargs"]["api_base"] == "http://base"
    assert captured["kwargs"]["temperature"] == 0.1
    assert captured["kwargs"]["max_tokens"] == 55
    assert captured["kwargs"]["model_type"] == "responses"
    assert captured["kwargs"]["reasoning_effort"] == "minimal"
    assert captured["kwargs"]["text"] == {
        "format": {"type": "text"},
        "verbosity": "high",
    }
    assert captured["kwargs"]["extra"] == "value"


def test_create_lm_maps_request_timeout_to_provider_timeout(monkeypatch):
    captured = {}

    class FakeLM:
        def __init__(self, model, **kwargs):
            captured["model"] = model
            captured["kwargs"] = kwargs

    monkeypatch.setattr(dspy_config.dspy, "LM", FakeLM)

    dspy_config.create_lm("openai/gpt-4o", request_timeout=19)

    assert captured["kwargs"]["timeout"] == 19
    assert "request_timeout" not in captured["kwargs"]


def test_create_lm_uses_brokered_lm(monkeypatch):
    captured = {}

    class FakeLM:
        def __init__(self, model, **kwargs):
            captured["model"] = model
            captured["kwargs"] = kwargs

    monkeypatch.setenv("TACTUS_BROKER_SOCKET", "sock")
    monkeypatch.setattr("tactus.dspy.broker_lm.BrokeredLM", FakeLM)

    lm = dspy_config.create_lm("openai/gpt-4o", api_key="secret", api_base="http://x")

    assert lm is not None
    assert captured["model"] == "openai/gpt-4o"
    assert "api_key" not in captured["kwargs"]
    assert "api_base" not in captured["kwargs"]


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
    assert "reasoning_effort" not in captured["kwargs"]
    assert "verbosity" not in captured["kwargs"]
    assert "text" not in captured["kwargs"]


def test_prewarm_lm_initializes_client_and_adapter_without_provider_request(monkeypatch):
    created = []
    adapter = object()

    class FakeLM:
        def __init__(self, model, **kwargs):
            created.append((model, kwargs))

        def __call__(self, *_args, **_kwargs):  # pragma: no cover - must not run
            raise AssertionError("prewarm must not make a provider request")

    monkeypatch.setattr(dspy_config.dspy, "LM", FakeLM)
    monkeypatch.setattr(dspy_config, "create_adapter", lambda: adapter)
    dspy_config.reset_prewarmed_lms()

    warmed = dspy_config.prewarm_lm(
        "openai/gpt-5-mini",
        request_timeout=42,
        model_type="responses",
    )

    assert created == [
        (
            "openai/gpt-5-mini",
            {"cache": False, "timeout": 42, "model_type": "responses"},
        )
    ]
    assert warmed.lm is dspy_config.get_prewarmed_lm(
        "openai/gpt-5-mini",
        request_timeout=42,
        model_type="responses",
    )
    assert warmed.adapter is adapter
    dspy_config.reset_prewarmed_lms()


@pytest.mark.parametrize("reasoning_effort", ["", "max", "extreme"])
def test_configure_lm_rejects_invalid_reasoning_effort(reasoning_effort):
    with pytest.raises(ValueError, match="reasoning_effort"):
        dspy_config.configure_lm("openai/gpt-5-mini", reasoning_effort=reasoning_effort)


@pytest.mark.parametrize("verbosity", ["", "minimal", "verbose"])
def test_create_lm_rejects_invalid_verbosity(verbosity):
    with pytest.raises(ValueError, match="verbosity"):
        dspy_config.create_lm("openai/gpt-5-mini", verbosity=verbosity)
