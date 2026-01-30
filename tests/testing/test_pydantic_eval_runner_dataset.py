from pathlib import Path

from tactus.testing.eval_models import EvaluationConfig, EvalCase, EvaluatorConfig
from tactus.testing.pydantic_eval_runner import TactusPydanticEvalRunner


def test_create_dataset_duplicates_cases_for_runs(monkeypatch, tmp_path: Path):
    eval_config = EvaluationConfig(
        dataset=[EvalCase(name="case", inputs={"x": 1})],
        evaluators=[EvaluatorConfig(type="contains")],
        runs=2,
    )
    runner = TactusPydanticEvalRunner(tmp_path / "proc.tac", eval_config)

    monkeypatch.setattr(runner, "_create_evaluators", lambda: [])

    dataset = runner._create_dataset()

    assert [case.name for case in dataset.cases] == ["case_run1", "case_run2"]
    assert dataset.name is None


def test_create_dataset_uses_case_name_for_single_run(monkeypatch, tmp_path: Path):
    eval_config = EvaluationConfig(
        dataset=[EvalCase(name="case", inputs={"x": 1})],
        evaluators=[],
        runs=1,
    )
    runner = TactusPydanticEvalRunner(tmp_path / "proc.tac", eval_config)

    monkeypatch.setattr(runner, "_create_evaluators", lambda: [])

    dataset = runner._create_dataset()

    assert [case.name for case in dataset.cases] == ["case"]


def test_create_dataset_loads_cases_from_file(monkeypatch, tmp_path: Path):
    dataset_file = tmp_path / "cases.jsonl"
    dataset_file.write_text('{"name": "file_case", "inputs": {"x": 2}}\n')

    eval_config = EvaluationConfig(
        dataset=[],
        evaluators=[],
        dataset_file=str(dataset_file),
    )
    runner = TactusPydanticEvalRunner(tmp_path / "proc.tac", eval_config)

    monkeypatch.setattr(runner, "_create_evaluators", lambda: [])

    dataset = runner._create_dataset()

    assert [case.name for case in dataset.cases] == ["file_case"]
