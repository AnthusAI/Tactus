import builtins
from types import SimpleNamespace
import importlib
import sys

import pytest

from tactus.testing.gherkin_parser import parse_gherkin, GherkinParser


def test_parse_gherkin_valid_feature():
    gherkin_text = """Feature: Sample

  Scenario: First
    Given a precondition
    Then a result
"""
    feature = parse_gherkin(gherkin_text)
    assert feature is not None
    assert feature.name == "Sample"
    assert feature.scenarios[0].name == "First"


def test_parse_gherkin_invalid_returns_none():
    assert parse_gherkin("") is None


def test_parser_rejects_missing_feature():
    parser = GherkinParser()
    try:
        parser.parse("Scenario: orphan")
    except ValueError as exc:
        assert "Invalid Gherkin syntax" in str(exc)


def test_parser_requires_gherkin_dependency(monkeypatch):
    import tactus.testing.gherkin_parser as gherkin_parser

    monkeypatch.setattr(gherkin_parser, "GHERKIN_AVAILABLE", False)

    with pytest.raises(ImportError):
        gherkin_parser.GherkinParser()


def test_parse_handles_document_without_feature(monkeypatch):
    parser = GherkinParser()
    parser.parser = SimpleNamespace(parse=lambda _scanner: {})

    with pytest.raises(ValueError):
        parser.parse("Feature: Missing")


def test_gherkin_import_error_path(monkeypatch):
    import tactus.testing.gherkin_parser as original_module

    original_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name.startswith("gherkin"):
            raise ImportError("missing gherkin")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    sys.modules.pop("tactus.testing.gherkin_parser", None)

    reloaded = importlib.import_module("tactus.testing.gherkin_parser")
    assert reloaded.GHERKIN_AVAILABLE is False

    with pytest.raises(ImportError):
        reloaded.GherkinParser()

    monkeypatch.setattr(builtins, "__import__", original_import)
    sys.modules["tactus.testing.gherkin_parser"] = original_module


def test_convert_to_pydantic_ignores_non_scenario_children():
    parser = GherkinParser()

    document = {
        "feature": {
            "name": "Sample",
            "description": "",
            "tags": [],
            "location": {"line": 1},
            "children": [{"rule": {"name": "Ignored"}}],
        }
    }

    feature = parser._convert_to_pydantic(document)

    assert feature.scenarios == []
