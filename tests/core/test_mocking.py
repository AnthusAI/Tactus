"""Tests for mock manager."""

import pytest

from tactus.core.mocking import MockManager, MockConfig


def test_register_and_static_mock():
    manager = MockManager()
    manager.register_mock("tool", {"output": {"ok": True}})

    assert manager.get_mock_response("tool", {}) == {"ok": True}
    assert manager.get_mock_response("missing", {}) is None


def test_register_temporal_mock():
    manager = MockManager()
    manager.register_mock("tool", {"temporal": [1, 2]})

    assert manager.get_mock_response("tool", {}) == 1
    manager.record_call("tool", {}, 1)
    assert manager.get_mock_response("tool", {}) == 2


def test_register_conditional_mock():
    manager = MockManager()
    manager.register_mock(
        "tool",
        {"conditional_mocks": [{"when": {"query": "contains:hello"}, "return": "hit"}]},
    )

    assert manager.get_mock_response("tool", {"query": "hello world"}) == "hit"
    assert manager.get_mock_response("tool", {"query": "no"}) is None
    assert manager.get_mock_response("tool", {}) is None


def test_register_conditional_startswith_and_endswith():
    manager = MockManager()
    manager.register_mock(
        "tool",
        {
            "conditional_mocks": [
                {"when": {"query": "startswith:hi"}, "return": "start"},
                {"when": {"query": "endswith:bye"}, "return": "end"},
            ]
        },
    )

    assert manager.get_mock_response("tool", {"query": "hi there"}) == "start"
    manager.record_call("tool", {}, "start")
    assert manager.get_mock_response("tool", {"query": "say bye"}) == "end"
    assert manager.get_mock_response("tool", {"query": "no match"}) is None


def test_register_conditional_exact_and_non_string():
    manager = MockManager()
    manager.register_mock(
        "tool",
        {"conditional_mocks": [{"when": {"mode": "fast", "count": 2}, "return": "hit"}]},
    )

    assert manager.get_mock_response("tool", {"mode": "fast", "count": 2}) == "hit"
    assert manager.get_mock_response("tool", {"mode": "slow", "count": 2}) is None
    assert manager.get_mock_response("tool", {"mode": "fast", "count": 3}) is None


def test_register_error_mock():
    manager = MockManager()
    manager.register_mock("tool", {"error": "boom"})

    with pytest.raises(RuntimeError):
        manager.get_mock_response("tool", {})


def test_disable_enable_mock():
    manager = MockManager()
    manager.register_mock("tool", {"output": "ok"})

    manager.disable_mock("tool")
    assert manager.get_mock_response("tool", {}) is None

    manager.enable_mock("tool")
    assert manager.get_mock_response("tool", {}) == "ok"
    manager.enable_mock("missing")
    manager.disable_mock("missing")


def test_global_disable():
    manager = MockManager()
    manager.register_mock("tool", {"output": "ok"})

    manager.disable_mock()
    assert manager.get_mock_response("tool", {}) is None

    manager.enable_mock()
    assert manager.get_mock_response("tool", {}) == "ok"


def test_record_call_and_history():
    manager = MockManager()
    manager.record_call("tool", {"a": 1}, "ok")
    manager.record_call("tool", {"a": 2}, "ok2")

    assert manager.get_call_count("tool") == 2
    assert manager.get_call_history("tool")[0].result == "ok"

    manager.reset()
    assert manager.get_call_count("tool") == 0


def test_temporal_mock_falls_back_to_last():
    manager = MockManager()
    manager.register_mock("tool", {"temporal": [1, 2]})
    manager.call_counts["tool"] = 2

    assert manager.get_mock_response("tool", {}) == 2


def test_disabled_mock_config_returns_none():
    manager = MockManager()
    manager.register_mock("tool", MockConfig(tool_name="tool", static_result="ok", enabled=False))

    assert manager.get_mock_response("tool", {}) is None
