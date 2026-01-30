"""Tests for ExtractPrimitive and ExtractHandle."""

import sys
from types import SimpleNamespace

import pytest

from tactus.stdlib.core.models import ExtractorResult
from tactus.stdlib.extract.primitive import (
    ExtractHandle,
    ExtractPrimitive,
    ExtractorFactory,
)


class FakeExtractor:
    def __init__(self):
        self.fields = {"name": "string"}
        self.total_calls = 2
        self.total_retries = 1
        self._agent = "agent"

    def extract(self, text):
        return ExtractorResult(fields={"name": text})

    def reset(self):
        self.total_calls = 0
        self.total_retries = 0


class FakeLuaTable:
    def __init__(self, items):
        self._items = items

    def items(self):
        return self._items.items()


@pytest.fixture
def primitive():
    return ExtractPrimitive(agent_factory=lambda *args, **kwargs: None)


def test_extract_primitive_requires_fields(primitive):
    with pytest.raises(ValueError):
        primitive({"prompt": "extract"})


def test_extract_primitive_requires_prompt(primitive):
    with pytest.raises(ValueError):
        primitive({"fields": {"name": "string"}})


def test_extract_handle_calls_extractor(primitive, monkeypatch):
    fake = FakeExtractor()
    monkeypatch.setattr(primitive, "_create_extractor", lambda config: fake)

    handle = primitive({"fields": {"name": "string"}, "prompt": "extract"})

    assert isinstance(handle, ExtractHandle)
    result = handle({"text": "Ada"})
    assert result.fields["name"] == "Ada"


def test_extract_primitive_one_shot_returns_lua_dict(primitive, monkeypatch):
    fake = FakeExtractor()
    monkeypatch.setattr(primitive, "_create_extractor", lambda config: fake)

    output = primitive({"fields": {"name": "string"}, "prompt": "extract", "input": "Ada"})

    assert output["name"] == "Ada"
    assert output["_validation_errors"] == []


def test_extract_handle_properties_and_reset(monkeypatch):
    fake = FakeExtractor()
    handle = ExtractHandle(fake)

    assert handle.total_calls == 2
    assert handle.total_retries == 1

    handle.reset()
    assert handle.total_calls == 0
    assert handle.total_retries == 0
    assert repr(handle) == f"ExtractHandle(extractor={fake})"


def test_lua_to_python_converts_table(monkeypatch, primitive):
    fake_lupa = SimpleNamespace(
        lua_type=lambda value: "table" if isinstance(value, FakeLuaTable) else "string"
    )
    sys.modules["lupa"] = fake_lupa
    try:
        lua_table = FakeLuaTable({1: "a", 2: "b"})
        assert primitive._lua_to_python(lua_table) == ["a", "b"]

        lua_table = FakeLuaTable({"key": "value"})
        assert primitive._lua_to_python(lua_table) == {"key": "value"}
    finally:
        sys.modules.pop("lupa", None)


def test_to_lua_table_uses_converter(monkeypatch, primitive):
    primitive.lua_table_from = lambda value: {"wrapped": value}

    assert primitive._to_lua_table({"a": 1}) == {"wrapped": {"a": 1}}
    assert primitive._to_lua_table([1, 2]) == [1, 2]


def test_lua_to_python_handles_import_error(monkeypatch, primitive):
    sys.modules["lupa"] = SimpleNamespace()
    try:
        input_value = {"a": 1}
        assert primitive._lua_to_python(input_value) == input_value
    finally:
        sys.modules.pop("lupa", None)


def test_lua_to_python_handles_non_table_value(primitive):
    assert primitive._lua_to_python("hello") == "hello"
    assert primitive._lua_to_python(None) is None


def test_lua_to_python_handles_mixed_keys(primitive, monkeypatch):
    fake_lupa = SimpleNamespace(
        lua_type=lambda value: "table" if isinstance(value, FakeLuaTable) else "string"
    )
    sys.modules["lupa"] = fake_lupa
    try:
        lua_table = FakeLuaTable({1: "a", "b": "c"})
        assert primitive._lua_to_python(lua_table) == {1: "a", "b": "c"}
    finally:
        sys.modules.pop("lupa", None)


def test_to_lua_table_returns_value_when_no_converter(primitive):
    assert primitive._to_lua_table({"a": 1}) == {"a": 1}


def test_create_extractor_uses_factory_for_custom_method(primitive, monkeypatch):
    class CustomExtractor:
        def __init__(self, config=None, **kwargs):
            self.config = config or {}
            self.kwargs = kwargs

        def extract(self, text):
            return ExtractorResult(fields={"text": text})

        def reset(self):
            return None

    ExtractorFactory.register("custom_test", CustomExtractor)
    config = {"method": "custom_test", "fields": {"name": "string"}, "prompt": "extract"}
    extractor = primitive._create_extractor(config)
    assert isinstance(extractor, CustomExtractor)


def test_create_extractor_uses_llm_method():
    primitive = ExtractPrimitive(agent_factory=lambda *args, **kwargs: None)
    config = {"fields": {"name": "string"}, "prompt": "extract", "method": "llm"}
    extractor = primitive._create_extractor(config)
    assert extractor.fields == {"name": "string"}
