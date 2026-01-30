from pathlib import Path

import pytest

from tactus.testing.eval_models import EvaluationConfig, EvaluatorConfig
from tactus.testing.pydantic_eval_runner import TactusPydanticEvalRunner


def _make_runner(tmp_path: Path, evaluators=None) -> TactusPydanticEvalRunner:
    config = EvaluationConfig(dataset=[], evaluators=evaluators or [])
    return TactusPydanticEvalRunner(tmp_path / "proc.tac", config)


def test_load_dataset_file_rejects_unknown_extension(tmp_path):
    runner = _make_runner(tmp_path)
    file_path = tmp_path / "cases.txt"
    file_path.write_text("invalid")

    with pytest.raises(ValueError, match="Unsupported dataset file format"):
        runner._load_dataset_file(str(file_path))


def test_create_evaluators_skips_failures(monkeypatch, tmp_path):
    def fake_create_evaluator(config):
        if config.type == "fail":
            raise RuntimeError("boom")
        return f"ok:{config.type}"

    monkeypatch.setattr("tactus.testing.evaluators.create_evaluator", fake_create_evaluator)

    configs = [EvaluatorConfig(type="pass"), EvaluatorConfig(type="fail")]
    runner = _make_runner(tmp_path, evaluators=configs)

    evaluators = runner._create_evaluators()

    assert evaluators == ["ok:pass"]
