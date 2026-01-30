"""Tests for mock agent primitives."""

from types import SimpleNamespace

import pytest

from tactus.testing.mock_agent import MockAgentPrimitive, MockAgentResult


class FakeToolPrimitive:
    def __init__(self, should_fail=False):
        self.calls = []
        self.should_fail = should_fail

    def record_call(self, tool_name, args):
        self.calls.append((tool_name, args))
        if self.should_fail:
            raise RuntimeError("boom")
        return {"status": "ok", "tool": tool_name}


def _mock_config(message="done", tool_calls=None, data=None, usage=None, temporal=None):
    return SimpleNamespace(
        message=message,
        tool_calls=tool_calls or [],
        data=data or {},
        usage=usage or {},
        temporal=temporal or [],
    )


def test_mock_agent_requires_config():
    agent = MockAgentPrimitive("agent", tool_primitive=None, registry=None)

    with pytest.raises(ValueError):
        agent.turn()


def test_mock_agent_executes_tool_calls():
    tool = FakeToolPrimitive()
    config = _mock_config(tool_calls=[{"tool": "done", "args": {"ok": True}}])
    registry = SimpleNamespace(agent_mocks={"agent": config})

    agent = MockAgentPrimitive("agent", tool_primitive=tool, registry=registry)
    result = agent.turn({"message": "hi"})

    assert result.message == "done"
    assert result.tool_calls[0]["result"]["tool"] == "done"
    assert tool.calls == [("done", {"ok": True})]
    assert result.data["response"] == "done"
    assert result.usage["total_tokens"] == 0
    assert len(result.new_messages()) == 2


def test_mock_agent_temporal_turn_by_message():
    tool = FakeToolPrimitive()
    temporal = [
        {"when_message": "first", "message": "one", "tool_calls": []},
        {"when_message": "second", "message": "two", "tool_calls": []},
    ]
    config = _mock_config(message="default", temporal=temporal)
    registry = SimpleNamespace(agent_mocks={"agent": config})

    agent = MockAgentPrimitive("agent", tool_primitive=tool, registry=registry)
    result = agent.turn({"message": "second"})

    assert result.message == "two"


def test_mock_agent_temporal_turn_by_index():
    tool = FakeToolPrimitive()
    temporal = [
        {"message": "one", "tool_calls": []},
        {"message": "two", "tool_calls": []},
    ]
    config = _mock_config(message="default", temporal=temporal)
    registry = SimpleNamespace(agent_mocks={"agent": config})

    agent = MockAgentPrimitive("agent", tool_primitive=tool, registry=registry)
    agent.turn()
    result = agent.turn()

    assert result.message == "two"


def test_mock_agent_tool_call_errors_are_handled():
    tool = FakeToolPrimitive(should_fail=True)
    config = _mock_config(tool_calls=[{"tool": "done", "args": {}}])
    registry = SimpleNamespace(agent_mocks={"agent": config})

    agent = MockAgentPrimitive("agent", tool_primitive=tool, registry=registry)
    result = agent.turn()

    assert result.tool_calls[0]["result"]["status"] == "ok"


def test_mock_agent_result_lua_conversion():
    result = MockAgentResult(
        message="hi", new_messages=[{"role": "user"}], lua_table_from=lambda x: ["ok"]
    )

    assert result.new_messages() == ["ok"]
