import builtins
import json

import pytest

from tactus.stdlib.core.validation import (
    validate_output,
    _calculate_similarity,
    _find_best_fuzzy_match,
    _generate_suggestions,
)


def test_validate_output_classification_strict_and_fuzzy():
    result = validate_output("Yes", valid_values=["Yes", "No"], strict=True)
    assert result["valid"] is True
    assert result["value"] == "Yes"

    result = validate_output("Yess", valid_values=["Yes", "No"], strict=False)
    assert result["valid"] is True

    result = validate_output("yse", valid_values=["Yes", "No"], strict=False)
    assert result["valid"] is True
    assert result["value"] == "Yes"


def test_validate_output_handles_empty_output():
    result = validate_output("", valid_values=["Yes", "No"])
    assert result["valid"] is False
    assert result["error"] == "Empty output"


def test_validate_output_handles_prefix_and_fuzzy_miss():
    result = validate_output("Yes - because", valid_values=["Yes", "No"])
    assert result["valid"] is True
    assert result["value"] == "Yes"

    result = validate_output("Maybe", valid_values=["Yes", "No"], strict=False)
    assert result["valid"] is False
    assert result["suggestions"]


def test_validate_output_strict_skips_fuzzy():
    result = validate_output("Maybe", valid_values=["Yes", "No"], strict=True)
    assert result["valid"] is False
    assert result["suggestions"]


def test_validate_output_schema_and_json_errors():
    schema = {"type": "object", "properties": {"name": {"type": "string"}}}
    result = validate_output(json.dumps({"name": "Ada"}), schema=schema)
    assert result["valid"] is True

    result = validate_output("{bad", schema=schema)
    assert result["valid"] is False
    assert "Invalid JSON" in result["error"]


def test_validate_output_without_rules():
    result = validate_output("freeform")
    assert result["valid"] is True
    assert result["value"] == "freeform"


def test_similarity_helpers():
    assert _calculate_similarity("", "x") == 0.0
    assert _calculate_similarity("a", "a") == 1.0
    assert _calculate_similarity("hello", "ell") == 0.85
    match = _find_best_fuzzy_match("yes", ["yes", "no"])
    assert match["value"] == "yes"
    suggestions = _generate_suggestions("yess", ["yes", "no"])
    assert any("Valid options" in s for s in suggestions)

    assert _find_best_fuzzy_match("hi", []) is None


def test_generate_suggestions_includes_best_match():
    suggestions = _generate_suggestions("yess", ["yes"])
    assert any("Did you mean" in s for s in suggestions)


def test_generate_suggestions_without_close_match():
    suggestions = _generate_suggestions("zzz", ["yes"])
    assert any("Valid options" in s for s in suggestions)
    assert all("Did you mean" not in s for s in suggestions)


def test_validate_schema_validation_error():
    pytest.importorskip("jsonschema")
    schema = {"type": "object", "properties": {"count": {"type": "number"}}}
    result = validate_output(json.dumps({"count": "bad"}), schema=schema)
    assert result["valid"] is False
    assert "Schema validation failed" in result["error"]


def test_validate_schema_handles_missing_jsonschema(monkeypatch):
    schema = {"type": "object"}

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "jsonschema":
            raise ImportError("missing")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    result = validate_output(json.dumps({"ok": True}), schema=schema)
    assert result["valid"] is True
