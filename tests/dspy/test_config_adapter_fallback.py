import sys
import types

from tactus.dspy import config as dspy_config


def test_configure_llm_adapter_fallback(monkeypatch):
    created = {"fallback": False}

    class DummyAdapter:
        def __init__(self, *args, **kwargs):
            if "use_native_function_calling" in kwargs:
                raise TypeError("unsupported")
            created["fallback"] = True

    dummy_chat_adapter = types.SimpleNamespace(ChatAdapter=DummyAdapter)
    monkeypatch.setitem(sys.modules, "dspy.adapters.chat_adapter", dummy_chat_adapter)

    dummy_dspy = types.SimpleNamespace(
        configure=lambda **_kwargs: None,
        LM=lambda *_args, **_kwargs: "lm",
    )

    monkeypatch.setattr(dspy_config, "dspy", dummy_dspy)
    dspy_config.configure_lm("openai/gpt-4o-mini")
    assert created["fallback"] is True
