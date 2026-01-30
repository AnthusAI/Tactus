from types import SimpleNamespace

import pytest

from tactus.testing.context import TactusTestContext


def test_mock_agent_response_uses_scenario_message(tmp_path):
    ctx = TactusTestContext(procedure_file=tmp_path / "proc.tac")
    ctx.set_scenario_message("hello")

    def fake_setup_runtime():
        ctx.runtime = SimpleNamespace(external_agent_mocks=None)

    ctx.setup_runtime = fake_setup_runtime  # type: ignore[assignment]

    ctx.mock_agent_response("agent", "reply")

    assert ctx._agent_mock_turns["agent"][0]["when_message"] == "hello"
    assert ctx.runtime.external_agent_mocks == ctx._agent_mock_turns


def test_mock_agent_tool_call_appends_to_existing_turn(tmp_path):
    ctx = TactusTestContext(procedure_file=tmp_path / "proc.tac")
    ctx.set_scenario_message("hello")
    ctx.runtime = SimpleNamespace(external_agent_mocks=None)

    ctx.mock_agent_response("agent", "reply")
    ctx.mock_agent_tool_call("agent", "tool", {"x": 1})

    turn = ctx._agent_mock_turns["agent"][0]
    assert turn["when_message"] == "hello"
    assert turn["tool_calls"] == [{"tool": "tool", "args": {"x": 1}}]


def test_mock_agent_tool_call_creates_new_turn_when_needed(tmp_path):
    ctx = TactusTestContext(procedure_file=tmp_path / "proc.tac")
    ctx.runtime = SimpleNamespace(external_agent_mocks=None)

    ctx.mock_agent_tool_call("agent", "tool", {"x": 2})

    turn = ctx._agent_mock_turns["agent"][0]
    assert turn["tool_calls"] == [{"tool": "tool", "args": {"x": 2}}]


def test_mock_agent_data_requires_dict(tmp_path):
    ctx = TactusTestContext(procedure_file=tmp_path / "proc.tac")
    with pytest.raises(TypeError):
        ctx.mock_agent_data("agent", ["not", "dict"])


def test_mock_agent_tool_call_creates_turn_with_when_message(tmp_path):
    ctx = TactusTestContext(procedure_file=tmp_path / "proc.tac")
    ctx.set_scenario_message("hello")

    def fake_setup_runtime():
        ctx.runtime = SimpleNamespace(external_agent_mocks=None)

    ctx.setup_runtime = fake_setup_runtime  # type: ignore[assignment]

    ctx.mock_agent_tool_call("agent", "tool", {"x": 1})

    turn = ctx._agent_mock_turns["agent"][0]
    assert turn["when_message"] == "hello"
    assert ctx.runtime.external_agent_mocks == ctx._agent_mock_turns


def test_mock_agent_data_creates_turn_with_when_message(tmp_path):
    ctx = TactusTestContext(procedure_file=tmp_path / "proc.tac")
    ctx.set_scenario_message("ping")

    def fake_setup_runtime():
        ctx.runtime = SimpleNamespace(external_agent_mocks=None)

    ctx.setup_runtime = fake_setup_runtime  # type: ignore[assignment]

    ctx.mock_agent_data("agent", {"ok": True})

    turn = ctx._agent_mock_turns["agent"][0]
    assert turn["when_message"] == "ping"
    assert ctx.runtime.external_agent_mocks == ctx._agent_mock_turns
