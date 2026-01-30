from pathlib import Path

import pytest

from tactus.testing.models import ScenarioResult, StepResult
from tactus.testing.test_runner import TactusTestRunner
from tactus.testing.models import ParsedFeature


def test_build_feature_result_requires_parsed_feature(tmp_path):
    runner = TactusTestRunner(Path(tmp_path / "proc.tac"))
    with pytest.raises(RuntimeError):
        runner._build_feature_result([])


def test_build_test_result_sorts_unique_tools(tmp_path):
    runner = TactusTestRunner(Path(tmp_path / "proc.tac"))
    runner.parsed_feature = type(
        "Feature",
        (),
        {"name": "Feature", "description": "", "tags": []},
    )()

    scenario = ScenarioResult(
        name="Scenario",
        status="passed",
        duration=1.0,
        steps=[StepResult(keyword="Given", message="x", status="passed")],
        tools_used=["b", "a"],
    )
    feature_results = [runner._build_feature_result([scenario])]

    result = runner._build_test_result(feature_results)

    assert result.unique_tools_used == ["a", "b"]


def test_setup_registers_custom_steps(tmp_path, monkeypatch):
    runner = TactusTestRunner(Path(tmp_path / "proc.tac"))
    parsed = ParsedFeature(name="Feature", scenarios=[])

    monkeypatch.setattr(
        "tactus.testing.test_runner.GherkinParser.parse",
        lambda _self, _text: parsed,
    )
    monkeypatch.setattr(
        "tactus.testing.test_runner.setup_behave_directory", lambda *args, **kwargs: tmp_path
    )

    captured = {}

    def fake_register(pattern, lua_func):
        captured["pattern"] = pattern
        captured["lua_func"] = lua_func

    runner.custom_steps.register_from_lua = fake_register

    runner.setup("Feature: X", custom_steps_dict={"Given foo": "func"})

    assert runner.parsed_feature is parsed
    assert runner.work_dir == tmp_path
    assert runner.generated_step_file is not None
    assert captured["pattern"] == "Given foo"


def test_setup_without_custom_steps(tmp_path, monkeypatch):
    runner = TactusTestRunner(Path(tmp_path / "proc.tac"))
    parsed = ParsedFeature(name="Feature", scenarios=[])

    monkeypatch.setattr(
        "tactus.testing.test_runner.GherkinParser.parse",
        lambda _self, _text: parsed,
    )
    monkeypatch.setattr(
        "tactus.testing.test_runner.setup_behave_directory", lambda *args, **kwargs: tmp_path
    )

    runner.setup("Feature: X")

    assert runner.parsed_feature is parsed


def test_cleanup_handles_missing_behave_registry(tmp_path, monkeypatch):
    runner = TactusTestRunner(Path(tmp_path / "proc.tac"))
    runner.work_dir = tmp_path / "work"
    runner.work_dir.mkdir()

    import builtins

    original_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "behave.step_registry":
            raise ImportError("no behave")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    runner.cleanup()

    assert not runner.work_dir.exists()


def test_cleanup_skips_missing_work_dir(tmp_path):
    runner = TactusTestRunner(Path(tmp_path / "proc.tac"))
    runner.work_dir = tmp_path / "missing"

    runner.cleanup()

    assert not runner.work_dir.exists()
