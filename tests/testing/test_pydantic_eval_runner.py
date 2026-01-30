"""Tests for Pydantic eval runner helpers."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from tactus.testing.pydantic_eval_runner import TactusPydanticEvalRunner
from tactus.testing.eval_models import (
    EvaluationConfig,
    EvalCase,
    EvaluatorConfig,
    EvaluationThresholds,
)


def _runner(tmp_path, eval_config):
    runner = object.__new__(TactusPydanticEvalRunner)
    runner.procedure_file = tmp_path / "proc.tac"
    runner.eval_config = eval_config
    runner.openai_api_key = None
    runner._procedure_source = ""
    return runner


def test_load_jsonl(tmp_path):
    path = tmp_path / "cases.jsonl"
    path.write_text('{"name": "case", "inputs": {"a": 1}}\n', encoding="utf-8")

    runner = _runner(tmp_path, EvaluationConfig(dataset=[], evaluators=[]))
    cases = runner._load_jsonl(path)

    assert len(cases) == 1
    assert cases[0].name == "case"


def test_load_json(tmp_path):
    path = tmp_path / "cases.json"
    path.write_text('[{"name": "case", "inputs": {"a": 1}}]', encoding="utf-8")

    runner = _runner(tmp_path, EvaluationConfig(dataset=[], evaluators=[]))
    cases = runner._load_json(path)

    assert len(cases) == 1
    assert cases[0].inputs["a"] == 1


def test_load_csv(tmp_path):
    path = tmp_path / "cases.csv"
    path.write_text('name,inputs\ncase,{"a": 1}\n', encoding="utf-8")

    runner = _runner(tmp_path, EvaluationConfig(dataset=[], evaluators=[]))
    cases = runner._load_csv(path)

    assert len(cases) == 1
    assert cases[0].inputs["a"] == 1


def test_load_dataset_file_errors(tmp_path):
    runner = _runner(tmp_path, EvaluationConfig(dataset=[], evaluators=[]))

    with pytest.raises(FileNotFoundError):
        runner._load_dataset_file("missing.json")

    bad = tmp_path / "cases.txt"
    bad.write_text("", encoding="utf-8")

    with pytest.raises(ValueError):
        runner._load_dataset_file(str(bad))


def test_check_thresholds():
    thresholds = EvaluationThresholds(min_success_rate=0.5, max_cost_per_run=1.0)
    eval_config = EvaluationConfig(
        dataset=[EvalCase(name="case", inputs={})],
        evaluators=[EvaluatorConfig(type="contains")],
        thresholds=thresholds,
    )
    runner = _runner(Path("."), eval_config)

    class FakeAssertion:
        def __init__(self, value):
            self.value = value

    report = SimpleNamespace(
        cases=[
            SimpleNamespace(assertions={"a": FakeAssertion(True)}, cost=0.5),
            SimpleNamespace(assertions={"a": FakeAssertion(False)}, cost=0.5),
        ]
    )

    passed, violations = runner.check_thresholds(report)

    assert passed is True
    assert violations == []


def test_extract_trace_with_session():
    eval_config = EvaluationConfig(dataset=[], evaluators=[])
    runner = _runner(Path("."), eval_config)

    class ToolCall:
        def __init__(self, tool_name, args, result):
            self.tool_name = tool_name
            self.args = args
            self.result = result

    class Message:
        def __init__(self, role, content, agent_name="agent"):
            self.role = role
            self.content = content
            self.agent_name = agent_name

    session = SimpleNamespace(
        tool_calls=[ToolCall("done", {"ok": True}, {"status": "ok"})],
        messages=[Message("assistant", "hi")],
        state_history=[{"variable": "status", "value": "ok"}],
        iteration_count=2,
    )
    runtime = SimpleNamespace(session=session, total_cost=1.2, total_tokens=10)

    trace = runner._extract_trace(runtime, duration=0.5)

    assert trace["tool_calls"][0]["name"] == "done"
    assert trace["agent_turns"][0]["message"] == "hi"
    assert trace["state_changes"] == [{"variable": "status", "value": "ok"}]
    assert trace["iterations"] == 2
    assert trace["cost"] == 1.2
    assert trace["tokens"] == 10


def test_create_evaluators_handles_errors(monkeypatch):
    eval_config = EvaluationConfig(
        dataset=[],
        evaluators=[
            EvaluatorConfig(type="contains"),
            EvaluatorConfig(type="unknown"),
        ],
    )
    runner = _runner(Path("."), eval_config)

    def fake_create_evaluator(config):
        if config.type == "unknown":
            raise ValueError("bad")
        return object()

    monkeypatch.setattr("tactus.testing.evaluators.create_evaluator", fake_create_evaluator)

    evaluators = runner._create_evaluators()

    assert len(evaluators) == 1


def test_create_dataset_expands_runs(tmp_path):
    pytest.importorskip("pydantic_evals")

    eval_config = EvaluationConfig(
        dataset=[EvalCase(name="case", inputs={"a": 1})],
        evaluators=[],
        runs=2,
    )
    runner = _runner(tmp_path, eval_config)

    dataset = runner._create_dataset()

    assert len(dataset.cases) == 2
    assert dataset.cases[0].name == "case_run1"
    assert dataset.cases[1].metadata["run_number"] == 2


def test_create_task_function_success(monkeypatch, tmp_path):
    eval_config = EvaluationConfig(dataset=[], evaluators=[])
    runner = _runner(tmp_path, eval_config)
    runner._procedure_source = "main = Procedure { function(input) return { ok = true } end }"

    class DummyRuntime:
        def __init__(self, *args, **kwargs):
            self.total_cost = 1.0
            self.total_tokens = 5
            self.session = None

        async def execute(self, source, context, format):
            return {"result": {"ok": True}}

    monkeypatch.setattr("tactus.core.runtime.TactusRuntime", DummyRuntime)

    task = runner._create_task_function()
    result = task({"x": 1})

    assert result["__output__"] == {"ok": True}
    assert result["__trace__"]["cost"] == 1.0


def test_create_task_function_error(monkeypatch, tmp_path):
    eval_config = EvaluationConfig(dataset=[], evaluators=[])
    runner = _runner(tmp_path, eval_config)
    runner._procedure_source = "main = Procedure { function(input) error('boom') end }"

    class DummyRuntime:
        def __init__(self, *args, **kwargs):
            self.total_cost = 0.0
            self.total_tokens = 0
            self.session = None

        async def execute(self, source, context, format):
            raise RuntimeError("boom")

    monkeypatch.setattr("tactus.core.runtime.TactusRuntime", DummyRuntime)

    task = runner._create_task_function()
    result = task({"x": 1})

    assert result["__output__"]["success"] is False
    assert "boom" in result["__output__"]["error"]


def test_run_evaluation_executes_dataset(monkeypatch, tmp_path):
    pytest.importorskip("pydantic_evals")

    procedure_file = tmp_path / "proc.tac"
    procedure_file.write_text("main = Procedure { function(input) return { ok = true } end }")

    eval_config = EvaluationConfig(dataset=[EvalCase(name="case", inputs={"a": 1})], evaluators=[])
    runner = TactusPydanticEvalRunner(procedure_file, eval_config)

    class FakeDataset:
        def __init__(self):
            self.called = False

        def evaluate_sync(self, task):
            self.called = True
            return {"ok": True}

    fake_dataset = FakeDataset()

    monkeypatch.setattr(runner, "_create_dataset", lambda: fake_dataset)
    monkeypatch.setattr(runner, "_create_task_function", lambda: (lambda _input: {"ok": True}))

    report = runner.run_evaluation()

    assert report == {"ok": True}
    assert fake_dataset.called is True
