from tactus.protocols.result import TactusResult
from tactus.testing.context import TactusTestContext


def test_tool_called_falls_back_to_execution_result(tmp_path):
    ctx = TactusTestContext(procedure_file=tmp_path / "proc.tac")
    ctx.execution_result = {"tools_used": ["tool"]}
    assert ctx.tool_called("tool") is True


def test_stop_reason_falls_back_to_execution_result(tmp_path):
    ctx = TactusTestContext(procedure_file=tmp_path / "proc.tac")
    ctx.execution_result = {"stop_reason": "complete"}
    assert ctx.stop_reason() == "complete"


def test_output_value_handles_tactus_result(tmp_path):
    ctx = TactusTestContext(procedure_file=tmp_path / "proc.tac")
    ctx.execution_result = {"result": TactusResult(output={"ok": True})}
    assert ctx.output_value() == {"ok": True}
