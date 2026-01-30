import asyncio
import builtins
from types import SimpleNamespace

import pytest

from tactus.testing.context import TactusTestContext


def test_tool_helpers_return_defaults_without_primitives(tmp_path):
    ctx = TactusTestContext(procedure_file=tmp_path / "proc.tac")

    assert ctx.tool_call_count("tool") == 0
    assert ctx.tool_calls("tool") == []


def test_state_helpers_return_defaults_without_state(tmp_path):
    ctx = TactusTestContext(procedure_file=tmp_path / "proc.tac")

    assert ctx.state_get("missing") is None
    assert ctx.state_exists("missing") is False


def test_output_helpers_handle_missing_output(tmp_path):
    ctx = TactusTestContext(procedure_file=tmp_path / "proc.tac")

    assert ctx.output_get("key") is None
    assert ctx.output_exists("key") is False
    assert ctx.output_value() is None


def test_agent_turns_defaults_to_zero(tmp_path):
    ctx = TactusTestContext(procedure_file=tmp_path / "proc.tac")
    assert ctx.agent_turns() == 0


def test_mock_agent_response_without_when_message(tmp_path):
    ctx = TactusTestContext(procedure_file=tmp_path / "proc.tac")

    called = False

    def fake_setup_runtime():
        nonlocal called
        called = True
        ctx.runtime = None

    ctx.setup_runtime = fake_setup_runtime  # type: ignore[assignment]

    ctx.mock_agent_response("agent", "reply")

    assert called is True
    assert ctx._agent_mock_turns["agent"][0]["message"] == "reply"
    assert "when_message" not in ctx._agent_mock_turns["agent"][0]


def test_mock_agent_tool_call_resets_non_list_tool_calls(tmp_path):
    ctx = TactusTestContext(procedure_file=tmp_path / "proc.tac")
    ctx.runtime = SimpleNamespace(external_agent_mocks=None)
    ctx.set_scenario_message("ping")

    ctx.mock_agent_response("agent", "reply")
    ctx._agent_mock_turns["agent"][0]["tool_calls"] = "not-a-list"

    ctx.mock_agent_tool_call("agent", "tool", {"x": 3})

    assert ctx._agent_mock_turns["agent"][0]["tool_calls"] == [{"tool": "tool", "args": {"x": 3}}]
    assert ctx.runtime.external_agent_mocks == ctx._agent_mock_turns


def test_mock_agent_data_sets_turn_and_syncs_runtime(tmp_path):
    ctx = TactusTestContext(procedure_file=tmp_path / "proc.tac")
    ctx.runtime = SimpleNamespace(external_agent_mocks=None)

    ctx.mock_agent_data("agent", {"ok": True}, when_message="hi")

    turn = ctx._agent_mock_turns["agent"][0]
    assert turn["when_message"] == "hi"
    assert turn["data"] == {"ok": True}
    assert ctx.runtime.external_agent_mocks == ctx._agent_mock_turns


def test_run_procedure_async_returns_when_already_executed(tmp_path):
    ctx = TactusTestContext(procedure_file=tmp_path / "proc.tac")
    ctx._procedure_executed = True

    def fake_setup_runtime():
        raise AssertionError("setup_runtime should not be called")

    ctx.setup_runtime = fake_setup_runtime  # type: ignore[assignment]

    asyncio.run(ctx.run_procedure_async())


def test_capture_primitives_returns_when_runtime_missing(tmp_path):
    ctx = TactusTestContext(procedure_file=tmp_path / "proc.tac")
    ctx.runtime = SimpleNamespace(lua_sandbox=None)
    ctx._capture_primitives()
    assert ctx._primitives == {}


def test_output_helpers_handle_output_and_result_dicts(tmp_path):
    ctx = TactusTestContext(procedure_file=tmp_path / "proc.tac")
    ctx.execution_result = {"output": {"a": 1}}

    assert ctx.output_get("a") == 1
    assert ctx.output_exists("a") is True

    ctx.execution_result = {"result": {"b": 2}}
    assert ctx.output_get("b") == 2
    assert ctx.output_exists("b") is True


def test_output_helpers_ignore_non_dict_output(tmp_path):
    ctx = TactusTestContext(procedure_file=tmp_path / "proc.tac")
    ctx.execution_result = {"output": "scalar"}

    assert ctx.output_get("key") is None
    assert ctx.output_exists("key") is False


def test_stop_success_and_iterations_fallback_to_execution_result(tmp_path):
    ctx = TactusTestContext(procedure_file=tmp_path / "proc.tac")
    ctx.execution_result = {"success": True, "iterations": 4}

    assert ctx.stop_success() is True
    assert ctx.iterations() == 4


def test_agent_context_reads_from_execution_result(tmp_path):
    ctx = TactusTestContext(procedure_file=tmp_path / "proc.tac")
    ctx.execution_result = {"agent_context": "hello"}
    assert ctx.agent_context() == "hello"


def test_mock_agent_data_rejects_non_dict(tmp_path):
    ctx = TactusTestContext(procedure_file=tmp_path / "proc.tac")
    with pytest.raises(TypeError):
        ctx.mock_agent_data("agent", ["bad"])


def test_mock_tool_returns_raises_when_runtime_missing(tmp_path):
    ctx = TactusTestContext(procedure_file=tmp_path / "proc.tac")

    def fake_setup_runtime():
        ctx.runtime = None

    ctx.setup_runtime = fake_setup_runtime  # type: ignore[assignment]

    with pytest.raises(AssertionError):
        ctx.mock_tool_returns("tool", "ok")


def test_mock_tool_returns_initializes_mock_manager(tmp_path):
    ctx = TactusTestContext(procedure_file=tmp_path / "proc.tac")
    ctx.runtime = SimpleNamespace(mock_manager=None)

    ctx.mock_tool_returns("tool", {"ok": True})
    assert ctx.runtime.mock_manager is not None


def test_run_procedure_async_captures_metrics(tmp_path):
    proc = tmp_path / "proc.tac"
    proc.write_text("main = Procedure { function(input) return { ok = true } end }")
    ctx = TactusTestContext(procedure_file=proc)

    class DummyRuntime:
        def __init__(self):
            self.lua_sandbox = True
            self.tool_primitive = SimpleNamespace()
            self.state_primitive = SimpleNamespace()
            self.iterations_primitive = SimpleNamespace()
            self.stop_primitive = SimpleNamespace()

        async def execute(self, source, context, format):
            return {
                "success": True,
                "total_cost": 1.5,
                "total_tokens": 10,
                "cost_breakdown": [{"cost": 1.5}],
                "iterations": 2,
                "tools_used": ["done"],
            }

    ctx.runtime = DummyRuntime()

    asyncio.run(ctx.run_procedure_async())

    assert ctx.total_cost == 1.5
    assert ctx.total_tokens == 10
    assert ctx.cost_breakdown == [{"cost": 1.5}]
    assert ctx.tools_used == ["done"]
    assert ctx.is_running() is True


def test_capture_primitives_handles_exceptions(tmp_path):
    ctx = TactusTestContext(procedure_file=tmp_path / "proc.tac")

    class BadRuntime:
        lua_sandbox = True

        @property
        def tool_primitive(self):
            raise RuntimeError("no tool")

        @property
        def state_primitive(self):
            raise RuntimeError("no state")

        @property
        def iterations_primitive(self):
            raise RuntimeError("no iterations")

        @property
        def stop_primitive(self):
            raise RuntimeError("no stop")

    ctx.runtime = BadRuntime()
    ctx._capture_primitives()
    assert ctx._primitives == {}


def test_output_value_falls_back_on_import_error(tmp_path, monkeypatch):
    ctx = TactusTestContext(procedure_file=tmp_path / "proc.tac")
    ctx.execution_result = {"result": {"ok": True}}

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "tactus.protocols.result":
            raise ImportError("missing")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    try:
        assert ctx.output_value() == {"ok": True}
    finally:
        monkeypatch.setattr(builtins, "__import__", real_import)


def test_stop_reason_from_execution_result(tmp_path):
    ctx = TactusTestContext(procedure_file=tmp_path / "proc.tac")
    ctx.execution_result = {"stop_reason": "done"}
    assert ctx.stop_reason() == "done"


def test_output_value_returns_scalar_result(tmp_path):
    ctx = TactusTestContext(procedure_file=tmp_path / "proc.tac")
    ctx.execution_result = {"result": "ok"}
    assert ctx.output_value() == "ok"
