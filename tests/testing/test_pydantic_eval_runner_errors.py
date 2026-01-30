from pathlib import Path

import pytest

from tactus.testing.eval_models import EvaluationConfig
from tactus.testing.pydantic_eval_runner import TactusPydanticEvalRunner


def test_load_dataset_file_missing_raises(tmp_path: Path):
    config = EvaluationConfig(dataset=[], evaluators=[])
    runner = TactusPydanticEvalRunner(tmp_path / "proc.tac", config)

    with pytest.raises(FileNotFoundError):
        runner._load_dataset_file("missing.json")


def test_load_dataset_file_resolves_relative_path(tmp_path: Path):
    dataset_file = tmp_path / "cases.json"
    dataset_file.write_text('[{"name": "case", "inputs": {"x": 1}}]')

    config = EvaluationConfig(dataset=[], evaluators=[])
    runner = TactusPydanticEvalRunner(tmp_path / "proc.tac", config)

    cases = runner._load_dataset_file("cases.json")

    assert len(cases) == 1
    assert cases[0].name == "case"


def test_load_jsonl_invalid_json_raises(tmp_path: Path):
    dataset_file = tmp_path / "cases.jsonl"
    dataset_file.write_text('{"name": "case"\n', encoding="utf-8")

    config = EvaluationConfig(dataset=[], evaluators=[])
    runner = TactusPydanticEvalRunner(tmp_path / "proc.tac", config)

    with pytest.raises(ValueError, match="Invalid JSON"):
        runner._load_jsonl(dataset_file)


def test_load_jsonl_invalid_case_raises(tmp_path: Path):
    dataset_file = tmp_path / "cases.jsonl"
    dataset_file.write_text('{"inputs": {"x": 1}}\n', encoding="utf-8")

    config = EvaluationConfig(dataset=[], evaluators=[])
    runner = TactusPydanticEvalRunner(tmp_path / "proc.tac", config)

    with pytest.raises(ValueError, match="Invalid case data"):
        runner._load_jsonl(dataset_file)


def test_load_json_requires_array(tmp_path: Path):
    dataset_file = tmp_path / "cases.json"
    dataset_file.write_text('{"name": "case"}', encoding="utf-8")

    config = EvaluationConfig(dataset=[], evaluators=[])
    runner = TactusPydanticEvalRunner(tmp_path / "proc.tac", config)

    with pytest.raises(ValueError, match="array of cases"):
        runner._load_json(dataset_file)


def test_load_json_invalid_case_raises(tmp_path: Path):
    dataset_file = tmp_path / "cases.json"
    dataset_file.write_text('[{"inputs": {"x": 1}}]', encoding="utf-8")

    config = EvaluationConfig(dataset=[], evaluators=[])
    runner = TactusPydanticEvalRunner(tmp_path / "proc.tac", config)

    with pytest.raises(ValueError, match="Invalid case data"):
        runner._load_json(dataset_file)


def test_load_csv_missing_columns_raise(tmp_path: Path):
    dataset_file = tmp_path / "cases.csv"
    dataset_file.write_text('inputs\n{"x": 1}\n', encoding="utf-8")

    config = EvaluationConfig(dataset=[], evaluators=[])
    runner = TactusPydanticEvalRunner(tmp_path / "proc.tac", config)

    with pytest.raises(ValueError, match="name"):
        runner._load_csv(dataset_file)

    dataset_file.write_text("name\ncase\n", encoding="utf-8")
    with pytest.raises(ValueError, match="inputs"):
        runner._load_csv(dataset_file)


def test_load_csv_invalid_row_raises_value_error(tmp_path: Path, monkeypatch):
    dataset_file = tmp_path / "cases.csv"
    dataset_file.write_text("name,inputs\ncase,boom\n", encoding="utf-8")

    config = EvaluationConfig(dataset=[], evaluators=[])
    runner = TactusPydanticEvalRunner(tmp_path / "proc.tac", config)

    import json

    def fake_loads(value):
        if value == "boom":
            raise TypeError("bad inputs")
        return json.loads(value)

    monkeypatch.setattr(json, "loads", fake_loads)

    with pytest.raises(ValueError, match="Invalid case data"):
        runner._load_csv(dataset_file)
