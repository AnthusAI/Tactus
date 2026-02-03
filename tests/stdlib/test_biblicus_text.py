import builtins
import os
import sys

import tactus.stdlib.biblicus.text as biblicus_text


class DummyClientConfig:
    def __init__(self, **kwargs):
        self.payload = kwargs


def test_normalize_client_config_parses_provider_prefix(monkeypatch):
    monkeypatch.setattr(
        biblicus_text,
        "_require_biblicus_text",
        lambda: {"LlmClientConfig": DummyClientConfig},
    )
    config = biblicus_text._normalize_client_config({"model": "openai/gpt-4o-mini"})
    assert config.payload["provider"] == "openai"
    assert config.payload["model"] == "gpt-4o-mini"


def test_normalize_client_config_requires_dict():
    try:
        biblicus_text._normalize_client_config("nope")
    except ValueError as exc:
        assert "client must be a table" in str(exc)
    else:
        raise AssertionError("Expected dict requirement error")


def test_normalize_client_config_requires_model(monkeypatch):
    monkeypatch.setattr(
        biblicus_text,
        "_require_biblicus_text",
        lambda: {"LlmClientConfig": DummyClientConfig},
    )
    try:
        biblicus_text._normalize_client_config({"provider": "openai"})
    except ValueError as exc:
        assert "client.model is required" in str(exc)
    else:
        raise AssertionError("Expected model requirement error")


def test_normalize_client_config_strips_explicit_provider_prefix(monkeypatch):
    monkeypatch.setattr(
        biblicus_text,
        "_require_biblicus_text",
        lambda: {"LlmClientConfig": DummyClientConfig},
    )
    config = biblicus_text._normalize_client_config(
        {"provider": "openai", "model": "openai/gpt-4o-mini"}
    )
    assert config.payload["provider"] == "openai"
    assert config.payload["model"] == "gpt-4o-mini"


def test_normalize_client_config_requires_provider(monkeypatch):
    monkeypatch.setattr(
        biblicus_text,
        "_require_biblicus_text",
        lambda: {"LlmClientConfig": DummyClientConfig},
    )
    try:
        biblicus_text._normalize_client_config({"model": "gpt-4o-mini"})
    except ValueError as exc:
        assert "client.provider is required" in str(exc)
    else:
        raise AssertionError("Expected provider requirement error")


def test_prepare_request_requires_client():
    try:
        biblicus_text._prepare_request({"text": "hello"})
    except ValueError as exc:
        assert "client is required" in str(exc)
    else:
        raise AssertionError("Expected client requirement error")


def test_prepare_request_requires_dict():
    try:
        biblicus_text._prepare_request("nope")
    except ValueError as exc:
        assert "request must be a table" in str(exc)
    else:
        raise AssertionError("Expected request type error")


def test_prepare_request_strips_mock_text_when_mock_mode_zero(monkeypatch):
    monkeypatch.setenv("TACTUS_MOCK_MODE", "0")
    monkeypatch.setattr(biblicus_text, "_normalize_client_config", lambda _c: "client")
    payload = biblicus_text._prepare_request(
        {"client": {"provider": "openai", "model": "gpt-4o-mini"}, "mock_marked_up_text": "x"}
    )
    assert "mock_marked_up_text" not in payload
    os.environ.pop("TACTUS_MOCK_MODE", None)


def test_maybe_mock_records_call(monkeypatch):
    calls = {"recorded": False}

    class DummyMockManager:
        def get_mock_response(self, _tool, _payload):
            return {"ok": True}

        def record_call(self, _tool, _payload, _response):
            calls["recorded"] = True

    import tactus.core.mocking as mocking

    monkeypatch.setattr(mocking, "get_current_mock_manager", lambda: DummyMockManager())

    assert biblicus_text._maybe_mock("tool", {"a": 1}) == {"ok": True}
    assert calls["recorded"] is True


def test_maybe_mock_handles_import_error(monkeypatch):
    import builtins

    original_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "tactus.core.mocking":
            raise ImportError("missing")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import, raising=True)
    assert biblicus_text._maybe_mock("tool", {"a": 1}) is None


def test_maybe_mock_returns_none_without_manager(monkeypatch):
    import types

    dummy_module = types.SimpleNamespace(get_current_mock_manager=lambda: None)
    monkeypatch.setitem(sys.modules, "tactus.core.mocking", dummy_module)
    assert biblicus_text._maybe_mock("tool", {"a": 1}) is None


def test_maybe_mock_returns_none_without_response(monkeypatch):
    import types

    class DummyMockManager:
        def get_mock_response(self, _tool, _payload):
            return None

    dummy_module = types.SimpleNamespace(get_current_mock_manager=lambda: DummyMockManager())
    monkeypatch.setitem(sys.modules, "tactus.core.mocking", dummy_module)
    assert biblicus_text._maybe_mock("tool", {"a": 1}) is None


def test_parse_span_helpers(monkeypatch):
    class DummySpan:
        def __init__(self, value):
            self.value = value

        def model_dump(self):
            return {"value": self.value}

    monkeypatch.setattr(
        biblicus_text,
        "_require_biblicus_text",
        lambda: {
            "parse_span_markup": lambda text: [DummySpan(text)],
            "strip_span_tags": lambda text: text.replace("<span>", "").replace("</span>", ""),
            "summarize_span_context": lambda text, indices: [text] * len(indices),
        },
    )
    assert biblicus_text.strip_span_tags("<span>hi</span>") == "hi"
    assert biblicus_text.parse_span_markup("hi") == [{"value": "hi"}]
    assert biblicus_text.summarize_span_context("hi", [0, 1]) == ["hi", "hi"]


def test_require_biblicus_text_missing(monkeypatch):
    original_import = __import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name.startswith("biblicus.text"):
            raise ModuleNotFoundError("missing")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import, raising=False)
    try:
        biblicus_text._require_biblicus_text()
    except ValueError as exc:
        assert "Biblicus text utilities are unavailable" in str(exc)
    else:
        raise AssertionError("Expected missing biblicus text error")


def test_require_biblicus_text_success(monkeypatch):
    class DummyRequest:
        pass

    class DummyConfig:
        pass

    class DummyMarkup:
        parse_span_markup = object()
        strip_span_tags = object()
        summarize_span_context = object()

    class DummyTextModels:
        TextAnnotateRequest = DummyRequest
        TextExtractRequest = DummyRequest
        TextLinkRequest = DummyRequest
        TextRedactRequest = DummyRequest
        TextSliceRequest = DummyRequest

    class DummyText:
        apply_text_annotate = object()
        apply_text_extract = object()
        apply_text_link = object()
        apply_text_redact = object()
        apply_text_slice = object()

    class DummyAIModels:
        LlmClientConfig = DummyConfig

    monkeypatch.setitem(sys.modules, "biblicus.ai.models", DummyAIModels)
    monkeypatch.setitem(sys.modules, "biblicus.text", DummyText)
    monkeypatch.setitem(sys.modules, "biblicus.text.markup", DummyMarkup)
    monkeypatch.setitem(sys.modules, "biblicus.text.models", DummyTextModels)

    result = biblicus_text._require_biblicus_text()
    assert result["LlmClientConfig"] is DummyConfig


def test_extract_calls_biblicus(monkeypatch):
    class DummyRequest:
        def __init__(self, **kwargs):
            self.payload = kwargs

    class DummyResponse:
        def model_dump(self):
            return {"ok": True}

    monkeypatch.setattr(biblicus_text, "_maybe_mock", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(biblicus_text, "_normalize_client_config", lambda _c: "client")
    monkeypatch.setattr(
        biblicus_text,
        "_require_biblicus_text",
        lambda: {
            "TextExtractRequest": DummyRequest,
            "apply_text_extract": lambda _req: DummyResponse(),
        },
    )
    result = biblicus_text.extract({"client": {"provider": "openai", "model": "gpt-4o-mini"}})
    assert result == {"ok": True}


def test_slice_calls_biblicus(monkeypatch):
    class DummyRequest:
        def __init__(self, **kwargs):
            self.payload = kwargs

    class DummyResponse:
        def model_dump(self):
            return {"ok": True}

    monkeypatch.setattr(biblicus_text, "_maybe_mock", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(biblicus_text, "_normalize_client_config", lambda _c: "client")
    monkeypatch.setattr(
        biblicus_text,
        "_require_biblicus_text",
        lambda: {
            "TextSliceRequest": DummyRequest,
            "apply_text_slice": lambda _req: DummyResponse(),
        },
    )
    result = biblicus_text.slice({"client": {"provider": "openai", "model": "gpt-4o-mini"}})
    assert result == {"ok": True}


def test_annotate_calls_biblicus(monkeypatch):
    class DummyRequest:
        def __init__(self, **kwargs):
            self.payload = kwargs

    class DummyResponse:
        def model_dump(self):
            return {"ok": True}

    monkeypatch.setattr(biblicus_text, "_maybe_mock", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(biblicus_text, "_normalize_client_config", lambda _c: "client")
    monkeypatch.setattr(
        biblicus_text,
        "_require_biblicus_text",
        lambda: {
            "TextAnnotateRequest": DummyRequest,
            "apply_text_annotate": lambda _req: DummyResponse(),
        },
    )
    result = biblicus_text.annotate({"client": {"provider": "openai", "model": "gpt-4o-mini"}})
    assert result == {"ok": True}


def test_redact_calls_biblicus(monkeypatch):
    class DummyRequest:
        def __init__(self, **kwargs):
            self.payload = kwargs

    class DummyResponse:
        def model_dump(self):
            return {"ok": True}

    monkeypatch.setattr(biblicus_text, "_maybe_mock", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(biblicus_text, "_normalize_client_config", lambda _c: "client")
    monkeypatch.setattr(
        biblicus_text,
        "_require_biblicus_text",
        lambda: {
            "TextRedactRequest": DummyRequest,
            "apply_text_redact": lambda _req: DummyResponse(),
        },
    )
    result = biblicus_text.redact({"client": {"provider": "openai", "model": "gpt-4o-mini"}})
    assert result == {"ok": True}


def test_link_calls_biblicus(monkeypatch):
    class DummyRequest:
        def __init__(self, **kwargs):
            self.payload = kwargs

    class DummyResponse:
        def model_dump(self):
            return {"ok": True}

    monkeypatch.setattr(biblicus_text, "_maybe_mock", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(biblicus_text, "_normalize_client_config", lambda _c: "client")
    monkeypatch.setattr(
        biblicus_text,
        "_require_biblicus_text",
        lambda: {
            "TextLinkRequest": DummyRequest,
            "apply_text_link": lambda _req: DummyResponse(),
        },
    )
    result = biblicus_text.link({"client": {"provider": "openai", "model": "gpt-4o-mini"}})
    assert result == {"ok": True}


def test_extract_returns_mock(monkeypatch):
    monkeypatch.setattr(biblicus_text, "_prepare_request", lambda req: req)
    monkeypatch.setattr(biblicus_text, "_maybe_mock", lambda *_args, **_kwargs: {"mock": True})
    assert biblicus_text.extract({"client": {}}) == {"mock": True}


def test_slice_returns_mock(monkeypatch):
    monkeypatch.setattr(biblicus_text, "_prepare_request", lambda req: req)
    monkeypatch.setattr(biblicus_text, "_maybe_mock", lambda *_args, **_kwargs: {"mock": True})
    assert biblicus_text.slice({"client": {}}) == {"mock": True}


def test_annotate_returns_mock(monkeypatch):
    monkeypatch.setattr(biblicus_text, "_prepare_request", lambda req: req)
    monkeypatch.setattr(biblicus_text, "_maybe_mock", lambda *_args, **_kwargs: {"mock": True})
    assert biblicus_text.annotate({"client": {}}) == {"mock": True}


def test_redact_returns_mock(monkeypatch):
    monkeypatch.setattr(biblicus_text, "_prepare_request", lambda req: req)
    monkeypatch.setattr(biblicus_text, "_maybe_mock", lambda *_args, **_kwargs: {"mock": True})
    assert biblicus_text.redact({"client": {}}) == {"mock": True}


def test_link_returns_mock(monkeypatch):
    monkeypatch.setattr(biblicus_text, "_prepare_request", lambda req: req)
    monkeypatch.setattr(biblicus_text, "_maybe_mock", lambda *_args, **_kwargs: {"mock": True})
    assert biblicus_text.link({"client": {}}) == {"mock": True}


def test_mock_marked_up_text_passes_through_in_mock_mode(monkeypatch):
    class DummyRequest:
        def __init__(self, **kwargs):
            if "mock_marked_up_text" not in kwargs:
                raise AssertionError("mock_marked_up_text should be preserved")
            self.payload = kwargs

    class DummyResponse:
        def model_dump(self):
            return {"ok": True}

    def fake_apply_text_extract(_request):
        return DummyResponse()

    monkeypatch.setenv("TACTUS_MOCK_MODE", "1")
    monkeypatch.setattr(biblicus_text, "_maybe_mock", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        biblicus_text,
        "_require_biblicus_text",
        lambda: {
            "LlmClientConfig": DummyClientConfig,
            "TextExtractRequest": DummyRequest,
            "apply_text_extract": fake_apply_text_extract,
        },
    )

    result = biblicus_text.extract(
        {
            "client": {"provider": "openai", "model": "gpt-4o-mini"},
            "text": "Alice met Bob.",
            "mock_marked_up_text": "<span>Alice</span> met <span>Bob</span>.",
        }
    )

    assert result == {"ok": True}
    os.environ.pop("TACTUS_MOCK_MODE", None)
