import json
from pathlib import Path

import pytest

from tactus.testing.eval_models import EvaluationConfig, EvalCase
from tactus.testing.pydantic_eval_runner import TactusPydanticEvalRunner


def _make_runner(tmp_path: Path) -> TactusPydanticEvalRunner:
    config = EvaluationConfig(dataset=[], evaluators=[])
    return TactusPydanticEvalRunner(tmp_path / "proc.tac", config)


def test_load_jsonl_valid(tmp_path):
    runner = _make_runner(tmp_path)
    file_path = tmp_path / "cases.jsonl"
    file_path.write_text(
        "\n".join(
            [
                json.dumps({"name": "case1", "inputs": {"x": 1}}),
                "",
                json.dumps({"name": "case2", "inputs": {"y": 2}}),
            ]
        )
    )

    cases = runner._load_jsonl(file_path)

    assert cases == [
        EvalCase(name="case1", inputs={"x": 1}),
        EvalCase(name="case2", inputs={"y": 2}),
    ]


def test_load_jsonl_invalid_line(tmp_path):
    runner = _make_runner(tmp_path)
    file_path = tmp_path / "cases.jsonl"
    file_path.write_text('{"name": "case1", "inputs": {"x": 1}}\n{bad json}')

    with pytest.raises(ValueError, match="Invalid JSON"):
        runner._load_jsonl(file_path)


def test_load_json_valid_array(tmp_path):
    runner = _make_runner(tmp_path)
    file_path = tmp_path / "cases.json"
    file_path.write_text(json.dumps([{"name": "case1", "inputs": {"x": 1}}]))

    cases = runner._load_json(file_path)

    assert cases == [EvalCase(name="case1", inputs={"x": 1})]


def test_load_json_rejects_non_array(tmp_path):
    runner = _make_runner(tmp_path)
    file_path = tmp_path / "cases.json"
    file_path.write_text(json.dumps({"name": "case1", "inputs": {"x": 1}}))

    with pytest.raises(ValueError, match="array of cases"):
        runner._load_json(file_path)


def test_load_csv_valid(tmp_path):
    runner = _make_runner(tmp_path)
    file_path = tmp_path / "cases.csv"
    file_path.write_text(
        "name,inputs,expected_output,metadata\n"
        'case1,"{""x"": 1}","{""y"": 2}","{""tag"": ""t""}"\n'
    )

    cases = runner._load_csv(file_path)

    assert cases == [
        EvalCase(name="case1", inputs={"x": 1}, expected_output={"y": 2}, metadata={"tag": "t"})
    ]


def test_load_dataset_file_resolves_relative(tmp_path):
    runner = _make_runner(tmp_path)
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    file_path = data_dir / "cases.json"
    file_path.write_text(json.dumps([{"name": "case1", "inputs": {"x": 1}}]))

    cases = runner._load_dataset_file("data/cases.json")

    assert cases == [EvalCase(name="case1", inputs={"x": 1})]


def test_load_dataset_file_handles_csv(tmp_path):
    runner = _make_runner(tmp_path)
    file_path = tmp_path / "cases.csv"
    file_path.write_text('name,inputs\ncase1,{"x": 1}\n')

    cases = runner._load_dataset_file(str(file_path))

    assert cases == [EvalCase(name="case1", inputs={"x": 1})]


def test_load_dataset_file_handles_jsonl(tmp_path):
    runner = _make_runner(tmp_path)
    file_path = tmp_path / "cases.jsonl"
    file_path.write_text(json.dumps({"name": "case1", "inputs": {"x": 1}}))

    cases = runner._load_dataset_file(str(file_path))

    assert cases == [EvalCase(name="case1", inputs={"x": 1})]


def test_load_csv_rejects_missing_name_column(tmp_path):
    runner = _make_runner(tmp_path)
    file_path = tmp_path / "cases.csv"
    file_path.write_text('inputs\n"{}"\n')

    with pytest.raises(ValueError, match="name"):
        runner._load_csv(file_path)


def test_load_csv_rejects_bad_json(tmp_path):
    runner = _make_runner(tmp_path)
    file_path = tmp_path / "cases.csv"
    file_path.write_text("name,inputs\ncase1,not-json\n")

    with pytest.raises(ValueError, match="Invalid JSON"):
        runner._load_csv(file_path)
