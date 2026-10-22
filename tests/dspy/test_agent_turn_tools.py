"""A turn's `tools` override: `tools = {}` gives the turn no tools; tool names keep only those tools."""

import types

from tactus.dspy.agent import DSPyAgentHandle

from tests.dspy.test_agent_execution import _make_agent


def _agent_with_tools(monkeypatch, *names):
    agent = _make_agent(monkeypatch, toolsets=[object()])
    tools = [types.SimpleNamespace(name=name) for name in names]
    monkeypatch.setattr(agent, "_convert_toolsets_to_dspy_tools_sync", lambda: list(tools))
    return agent


class LuaTableLike:
    def __init__(self, *items):
        self._items = dict(enumerate(items, start=1))

    def values(self):
        return self._items.values()


def test_no_override_keeps_every_tool(monkeypatch):
    agent = _agent_with_tools(monkeypatch, "fetch", "save", "done")
    assert [tool.name for tool in agent._tools_for_turn({"message": "go"})] == [
        "fetch",
        "save",
        "done",
    ]


def test_an_empty_override_gives_the_turn_no_tools(monkeypatch):
    agent = _agent_with_tools(monkeypatch, "fetch", "done")
    assert agent._tools_for_turn({"tools": LuaTableLike()}) == []
    assert agent._tools_for_turn({"tools": {}}) == []
    assert agent._tools_for_turn({"tools": []}) == []


def test_named_tools_keep_only_those_tools(monkeypatch):
    agent = _agent_with_tools(monkeypatch, "fetch", "save", "done")
    done_handle = types.SimpleNamespace(name="done")
    assert [
        tool.name for tool in agent._tools_for_turn({"tools": LuaTableLike("fetch", done_handle)})
    ] == [
        "fetch",
        "done",
    ]


def test_a_name_that_is_not_a_tool_keeps_every_tool(monkeypatch):
    agent = _agent_with_tools(monkeypatch, "fetch", "done")
    assert len(agent._tools_for_turn({"tools": ["papyrus"]})) == 2


def test_requested_tool_names_reads_lua_tables_lists_and_handles():
    assert DSPyAgentHandle._requested_tool_names(None) is None
    assert DSPyAgentHandle._requested_tool_names(
        LuaTableLike("a", types.SimpleNamespace(name="b"))
    ) == ["a", "b"]
