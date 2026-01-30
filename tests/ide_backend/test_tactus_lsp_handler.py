from types import SimpleNamespace
import sys
from pathlib import Path

from tactus.core.registry import ValidationMessage

BACKEND_PATH = Path(__file__).resolve().parents[2] / "tactus-ide" / "backend"
sys.path.insert(0, str(BACKEND_PATH))
from tactus_lsp_handler import TactusLSPHandler  # noqa: E402


def test_validate_document_records_registry_and_diagnostics(monkeypatch):
    handler = TactusLSPHandler()

    registry = SimpleNamespace(agents={}, parameters={}, outputs={})
    result = SimpleNamespace(
        errors=[ValidationMessage(level="error", message="bad", location=(2, 3))],
        warnings=[ValidationMessage(level="warning", message="warn", location=None)],
        registry=registry,
    )

    def fake_validate(_text, _mode):
        return result

    handler.validator.validate = fake_validate

    diagnostics = handler.validate_document("file://test.tac", "content")

    assert handler.registries["file://test.tac"] == registry
    assert diagnostics[0]["message"] == "bad"
    assert diagnostics[0]["severity"] == 1
    assert diagnostics[1]["severity"] == 2


def test_validate_document_without_registry_keeps_existing_entries():
    handler = TactusLSPHandler()
    handler.registries["file://existing.tac"] = object()

    result = SimpleNamespace(errors=[], warnings=[], registry=None)

    def fake_validate(_text, _mode):
        return result

    handler.validator.validate = fake_validate

    diagnostics = handler.validate_document("file://no-registry.tac", "content")

    assert diagnostics == []
    assert "file://no-registry.tac" not in handler.registries
    assert "file://existing.tac" in handler.registries


def test_validate_document_handles_exceptions(monkeypatch):
    handler = TactusLSPHandler()

    def fake_validate(_text, _mode):
        raise RuntimeError("boom")

    handler.validator.validate = fake_validate

    diagnostics = handler.validate_document("file://err.tac", "content")

    assert diagnostics == []


def test_validate_document_skips_null_diagnostics():
    handler = TactusLSPHandler()
    result = SimpleNamespace(
        errors=[ValidationMessage(level="error", message="bad", location=(1, 1))],
        warnings=[ValidationMessage(level="warning", message="warn", location=(1, 1))],
        registry=None,
    )

    def fake_validate(_text, _mode):
        return result

    handler.validator.validate = fake_validate
    handler._convert_to_diagnostic = lambda *_args, **_kwargs: None

    diagnostics = handler.validate_document("file://null.tac", "content")

    assert diagnostics == []


def test_completions_and_hover_include_registry_data():
    handler = TactusLSPHandler()
    registry = SimpleNamespace(
        agents={"agentA": SimpleNamespace(provider="openai", model="gpt")},
        parameters={
            "paramA": SimpleNamespace(parameter_type=SimpleNamespace(value="string"), default="x")
        },
        outputs={
            "outA": SimpleNamespace(field_type=SimpleNamespace(value="string"), required=True)
        },
    )
    handler.registries["file://test.tac"] = registry

    completions = handler.get_completions("file://test.tac", {"line": 0, "character": 0})
    assert any(item["label"] == "agentA" for item in completions)

    hover = handler.get_hover("file://test.tac", {"line": 0, "character": 0})
    assert "Agents" in hover["contents"]["value"]
    assert "Parameters" in hover["contents"]["value"]
    assert "Outputs" in hover["contents"]["value"]


def test_completions_without_registry_returns_dsl_entries():
    handler = TactusLSPHandler()

    completions = handler.get_completions("file://missing.tac", {"line": 0, "character": 0})

    labels = {item["label"] for item in completions}
    assert {"name", "agent", "parameter", "output", "procedure"}.issubset(labels)


def test_hover_returns_none_for_missing_or_empty_registry():
    handler = TactusLSPHandler()

    assert handler.get_hover("file://missing.tac", {"line": 0, "character": 0}) is None

    empty_registry = SimpleNamespace(agents={}, parameters={}, outputs={})
    handler.registries["file://empty.tac"] = empty_registry

    assert handler.get_hover("file://empty.tac", {"line": 0, "character": 0}) is None


def test_signature_help_returns_templates():
    handler = TactusLSPHandler()

    signature = handler.get_signature_help("file://test.tac", {"line": 0, "character": 0})

    assert signature["activeSignature"] == 0
    assert len(signature["signatures"]) >= 2


def test_close_document_removes_cache():
    handler = TactusLSPHandler()
    handler.documents["file://test.tac"] = "content"
    handler.registries["file://test.tac"] = object()

    handler.close_document("file://test.tac")

    assert "file://test.tac" not in handler.documents
    assert "file://test.tac" not in handler.registries


def test_convert_to_diagnostic_handles_missing_location_and_unknown_severity():
    handler = TactusLSPHandler()
    message = ValidationMessage(level="error", message="info", location=None)

    diagnostic = handler._convert_to_diagnostic(message, "Unknown")

    assert diagnostic["severity"] == 1
    assert diagnostic["range"]["start"] == {"line": 0, "character": 0}
