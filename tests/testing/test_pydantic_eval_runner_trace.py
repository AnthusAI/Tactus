from types import SimpleNamespace

from tactus.testing.eval_models import EvaluationConfig
from tactus.testing.pydantic_eval_runner import TactusPydanticEvalRunner


def test_extract_trace_from_runtime(tmp_path):
    runner = TactusPydanticEvalRunner(
        tmp_path / "proc.tac", EvaluationConfig(dataset=[], evaluators=[])
    )

    session = SimpleNamespace(
        tool_calls=[SimpleNamespace(name="tool", args={"x": 1}, result="ok")],
        messages=[SimpleNamespace(role="assistant", agent_name="agent", content="hi")],
        state_history=[{"key": "value"}],
        iteration_count=2,
    )
    runtime = SimpleNamespace(session=session, total_cost=1.0, total_tokens=10)

    trace = runner._extract_trace(runtime, duration=1.5)

    assert trace["duration"] == 1.5
    assert trace["tool_calls"] == [{"name": "tool", "args": {"x": 1}, "result": "ok"}]
    assert trace["agent_turns"] == [{"agent": "agent", "message": "hi"}]
    assert trace["state_changes"] == [{"key": "value"}]
    assert trace["iterations"] == 2
    assert trace["cost"] == 1.0
    assert trace["tokens"] == 10


def test_extract_trace_handles_missing_session_fields(tmp_path):
    runner = TactusPydanticEvalRunner(
        tmp_path / "proc.tac", EvaluationConfig(dataset=[], evaluators=[])
    )

    session = SimpleNamespace(messages=[SimpleNamespace(role="user", content="hi")])
    runtime = SimpleNamespace(session=session)

    trace = runner._extract_trace(runtime, duration=0.1)

    assert trace["tool_calls"] == []
    assert trace["agent_turns"] == []
    assert trace["state_changes"] == []
    assert trace["iterations"] == 0
    assert trace["cost"] == 0.0
    assert trace["tokens"] == 0


def test_extract_trace_handles_no_messages(tmp_path):
    runner = TactusPydanticEvalRunner(
        tmp_path / "proc.tac", EvaluationConfig(dataset=[], evaluators=[])
    )

    session = SimpleNamespace(tool_calls=[], state_history=[])
    runtime = SimpleNamespace(session=session)

    trace = runner._extract_trace(runtime, duration=0.2)

    assert trace["agent_turns"] == []
