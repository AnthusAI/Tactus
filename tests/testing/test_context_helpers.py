from types import SimpleNamespace

from tactus.testing.context import TactusTestContext


class DummyToolCall:
    def __init__(self, name, args, result):
        self.name = name
        self.args = args
        self.result = result


def test_tool_helpers_with_primitives(tmp_path):
    ctx = TactusTestContext(procedure_file=tmp_path / "proc.tac")
    ctx._primitives["tool"] = SimpleNamespace(
        called=lambda name: name == "ping",
        _tool_calls=[DummyToolCall("ping", {"x": 1}, {"ok": True})],
    )

    assert ctx.tool_called("ping") is True
    assert ctx.tool_call_count("ping") == 1
    assert ctx.tool_calls("ping") == [{"tool": "ping", "args": {"x": 1}, "result": {"ok": True}}]


def test_state_helpers_with_primitives(tmp_path):
    ctx = TactusTestContext(procedure_file=tmp_path / "proc.tac")
    ctx._primitives["state"] = SimpleNamespace(
        _state={"key": "value"},
        get=lambda key: {"key": "value"}.get(key),
    )

    assert ctx.state_exists("key") is True
    assert ctx.state_get("key") == "value"


def test_output_helpers_use_output_and_result(tmp_path):
    ctx = TactusTestContext(procedure_file=tmp_path / "proc.tac")
    ctx.execution_result = {"output": {"a": 1}}

    assert ctx.output_get("a") == 1
    assert ctx.output_exists("a") is True
    assert ctx.output_value() == {"a": 1}

    ctx.execution_result = {"result": {"b": 2}}
    assert ctx.output_get("b") == 2
    assert ctx.output_exists("b") is True
    assert ctx.output_value() == {"b": 2}


def test_stop_and_iteration_helpers(tmp_path):
    ctx = TactusTestContext(procedure_file=tmp_path / "proc.tac")
    ctx._primitives["stop"] = SimpleNamespace(_reason="done")
    ctx._primitives["iterations"] = SimpleNamespace(_count=3)
    ctx.execution_result = {"success": True, "iterations": 2, "agent_turns": 4}

    assert ctx.stop_success() is True
    assert ctx.stop_reason() == "done"
    assert ctx.iterations() == 3
    assert ctx.agent_turns() == 4


def test_params_and_context_helpers(tmp_path):
    ctx = TactusTestContext(procedure_file=tmp_path / "proc.tac")
    ctx.set_input("task", "run")
    ctx.execution_result = {"agent_context": "context"}

    assert ctx.get_params() == {"task": "run"}
    assert ctx.agent_context() == "context"


def test_scenario_message_helpers(tmp_path):
    ctx = TactusTestContext(procedure_file=tmp_path / "proc.tac")
    ctx.set_scenario_message("hello")
    assert ctx.get_scenario_message() == "hello"
