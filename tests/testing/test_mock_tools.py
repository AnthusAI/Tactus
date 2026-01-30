"""Tests for mock tool registry and primitive."""

import pytest

from tactus.testing.mock_tools import MockToolRegistry, MockedToolPrimitive, create_default_mocks


def test_mock_tool_registry_register_and_get():
    registry = MockToolRegistry()
    registry.register("tool", {"ok": True})

    assert registry.has_mock("tool") is True
    assert registry.get_response("tool", {}) == {"ok": True}


def test_mock_tool_registry_callable():
    registry = MockToolRegistry()
    registry.register("tool", lambda args: {"value": args["x"]})

    assert registry.get_response("tool", {"x": 2}) == {"value": 2}


def test_mock_tool_registry_missing_raises():
    registry = MockToolRegistry()

    with pytest.raises(ValueError):
        registry.get_response("missing", {})


def test_mock_tool_registry_clear():
    registry = MockToolRegistry()
    registry.register("tool", {"ok": True})

    registry.clear()

    assert registry.has_mock("tool") is False


def test_mocked_tool_primitive_records_calls():
    registry = MockToolRegistry()
    registry.register("tool", {"ok": True})

    primitive = MockedToolPrimitive(registry)
    result = primitive.record_call("tool", {"a": 1})

    assert result == {"ok": True}
    assert primitive.last_call("tool")["args"] == {"a": 1}


def test_mocked_tool_primitive_default_response():
    registry = MockToolRegistry()
    primitive = MockedToolPrimitive(registry)

    result = primitive.record_call("unknown", {})

    assert result["status"] == "ok"


def test_create_default_mocks():
    defaults = create_default_mocks()

    assert "done" in defaults
    assert "search" in defaults
