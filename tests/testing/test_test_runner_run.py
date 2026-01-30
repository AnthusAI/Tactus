import json
import shutil
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest

from tactus.testing.models import ParsedFeature, ParsedScenario, ScenarioResult, StepResult
from tactus.testing import test_runner
from tactus.testing.test_runner import TactusTestRunner


def test_runner_requires_behave(tmp_path, monkeypatch):
    monkeypatch.setattr(test_runner, "BEHAVE_AVAILABLE", False)
    with pytest.raises(ImportError):
        TactusTestRunner(Path(tmp_path / "proc.tac"))


def test_run_tests_requires_setup(tmp_path):
    runner = TactusTestRunner(Path(tmp_path / "proc.tac"))
    with pytest.raises(RuntimeError):
        runner.run_tests()


def test_run_tests_filters_scenarios(tmp_path):
    runner = TactusTestRunner(Path(tmp_path / "proc.tac"))
    runner.parsed_feature = ParsedFeature(
        name="Feature",
        scenarios=[ParsedScenario(name="A"), ParsedScenario(name="B")],
    )
    runner.work_dir = tmp_path

    with pytest.raises(ValueError):
        runner.run_tests(parallel=False, scenario_filter="Missing")


def test_run_tests_filters_scenarios_success(tmp_path):
    runner = TactusTestRunner(Path(tmp_path / "proc.tac"))
    runner.parsed_feature = ParsedFeature(
        name="Feature",
        scenarios=[ParsedScenario(name="A"), ParsedScenario(name="B")],
    )
    runner.work_dir = tmp_path

    def fake_run_single(name, _work_dir):
        return ScenarioResult(
            name=name,
            status="passed",
            duration=1.0,
            steps=[StepResult(keyword="Given", message="x", status="passed")],
        )

    runner._run_single_scenario = staticmethod(fake_run_single)  # type: ignore[assignment]

    result = runner.run_tests(parallel=False, scenario_filter="B")

    assert result.total_scenarios == 1


def test_run_tests_runs_sequentially(tmp_path):
    runner = TactusTestRunner(Path(tmp_path / "proc.tac"))
    runner.parsed_feature = ParsedFeature(
        name="Feature",
        scenarios=[ParsedScenario(name="A"), ParsedScenario(name="B")],
    )
    runner.work_dir = tmp_path

    def fake_run_single(name, _work_dir):
        return ScenarioResult(
            name=name,
            status="passed",
            duration=1.0,
            steps=[StepResult(keyword="Given", message="x", status="passed")],
        )

    runner._run_single_scenario = staticmethod(fake_run_single)  # type: ignore[assignment]

    result = runner.run_tests(parallel=False)

    assert result.total_scenarios == 2
    assert result.passed_scenarios == 2


def test_run_tests_runs_in_parallel(tmp_path, monkeypatch):
    runner = TactusTestRunner(Path(tmp_path / "proc.tac"))
    runner.parsed_feature = ParsedFeature(
        name="Feature",
        scenarios=[ParsedScenario(name="A"), ParsedScenario(name="B")],
    )
    runner.work_dir = tmp_path

    collected = {}

    class FakePool:
        def __init__(self, processes=None):
            collected["processes"] = processes

        def __enter__(self):
            return self

        def __exit__(self, _exc_type, _exc, _tb):
            return False

        def starmap(self, func, args):
            collected["called_with"] = args
            return [
                ScenarioResult(
                    name=name,
                    status="passed",
                    duration=1.0,
                    steps=[StepResult(keyword="Given", message="x", status="passed")],
                )
                for name, _work_dir in args
            ]

    class FakeContext:
        def Pool(self, processes=None):
            return FakePool(processes=processes)

    monkeypatch.setattr(test_runner.multiprocessing, "get_context", lambda _method: FakeContext())

    result = runner.run_tests(parallel=True)

    assert result.total_scenarios == 2
    assert collected["called_with"]


def test_run_single_scenario_raises_on_error_returncode(tmp_path, monkeypatch):
    def fake_run(*_args, **_kwargs):
        return SimpleNamespace(returncode=2, stdout="out", stderr="err")

    monkeypatch.setattr(test_runner.subprocess, "run", fake_run)
    monkeypatch.setenv("PYTHONPATH", "x")

    with pytest.raises(RuntimeError):
        TactusTestRunner._run_single_scenario("Scenario", str(tmp_path))


def test_run_single_scenario_raises_when_results_missing(tmp_path, monkeypatch):
    def fake_run(*_args, **_kwargs):
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr(test_runner.subprocess, "run", fake_run)

    class FakeUUID:
        hex = "deadbeef"

    monkeypatch.setattr(uuid, "uuid4", lambda: FakeUUID())

    with pytest.raises(RuntimeError):
        TactusTestRunner._run_single_scenario("Scenario", str(tmp_path))


def test_run_single_scenario_raises_when_results_empty(tmp_path, monkeypatch):
    def fake_run(*_args, **_kwargs):
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr(test_runner.subprocess, "run", fake_run)

    class FakeUUID:
        hex = "feedface"

    monkeypatch.setattr(uuid, "uuid4", lambda: FakeUUID())
    results_file = tmp_path / "results_feedface.json"
    results_file.write_text("")

    with pytest.raises(RuntimeError):
        TactusTestRunner._run_single_scenario("Scenario", str(tmp_path))


def test_run_single_scenario_parses_json_results(tmp_path, monkeypatch):
    def fake_run(*_args, **_kwargs):
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr(test_runner.subprocess, "run", fake_run)

    class FakeUUID:
        hex = "abc12345"

    monkeypatch.setattr(uuid, "uuid4", lambda: FakeUUID())

    results_file = tmp_path / "results_abc12345.json"
    payload = [
        {
            "elements": [
                {
                    "name": "Scenario",
                    "status": "passed",
                    "steps": [],
                    "tags": [],
                }
            ]
        }
    ]
    results_file.write_text(json.dumps(payload))

    result = TactusTestRunner._run_single_scenario("Scenario", str(tmp_path))

    assert result.name == "Scenario"
    assert result.status == "passed"
    assert not results_file.exists()


def test_run_single_scenario_parses_multi_json(tmp_path, monkeypatch):
    def fake_run(*_args, **_kwargs):
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr(test_runner.subprocess, "run", fake_run)

    class FakeUUID:
        hex = "beaded"

    monkeypatch.setattr(uuid, "uuid4", lambda: FakeUUID())

    results_file = tmp_path / "results_beaded.json"
    line1 = json.dumps([{"elements": [{"name": "Other", "status": "passed", "steps": []}]}])
    line2 = json.dumps({"elements": [{"name": "Scenario", "status": "passed", "steps": []}]})
    results_file.write_text(f"{line1}\n{line2}\n")

    result = TactusTestRunner._run_single_scenario("Scenario", str(tmp_path))

    assert result.name == "Scenario"


def test_run_single_scenario_ignores_blank_lines(tmp_path, monkeypatch):
    def fake_run(*_args, **_kwargs):
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr(test_runner.subprocess, "run", fake_run)

    class FakeUUID:
        hex = "blankln"

    monkeypatch.setattr(uuid, "uuid4", lambda: FakeUUID())

    results_file = tmp_path / "results_blankln.json"
    line1 = json.dumps([{"elements": [{"name": "Other", "status": "passed", "steps": []}]}])
    line2 = ""
    line3 = json.dumps({"elements": [{"name": "Scenario", "status": "passed", "steps": []}]})
    results_file.write_text(f"{line1}\n{line2}\n{line3}\n")

    result = TactusTestRunner._run_single_scenario("Scenario", str(tmp_path))

    assert result.name == "Scenario"


def test_run_single_scenario_skips_invalid_json_lines(tmp_path, monkeypatch):
    def fake_run(*_args, **_kwargs):
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr(test_runner.subprocess, "run", fake_run)

    class FakeUUID:
        hex = "badline"

    monkeypatch.setattr(uuid, "uuid4", lambda: FakeUUID())

    results_file = tmp_path / "results_badline.json"
    line1 = json.dumps([{"elements": [{"name": "Other", "status": "passed", "steps": []}]}])
    line2 = "{not json}"
    line3 = json.dumps({"elements": [{"name": "Scenario", "status": "passed", "steps": []}]})
    results_file.write_text(f"{line1}\n{line2}\n{line3}\n")

    result = TactusTestRunner._run_single_scenario("Scenario", str(tmp_path))

    assert result.name == "Scenario"


def test_run_single_scenario_handles_results_cleanup_error(tmp_path, monkeypatch):
    def fake_run(*_args, **_kwargs):
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr(test_runner.subprocess, "run", fake_run)

    class FakeUUID:
        hex = "cleanup"

    monkeypatch.setattr(uuid, "uuid4", lambda: FakeUUID())

    results_file = tmp_path / "results_cleanup.json"
    payload = [{"elements": [{"name": "Scenario", "status": "passed", "steps": []}]}]
    results_file.write_text(json.dumps(payload))

    def boom_unlink(_self):
        raise OSError("unlink failed")

    monkeypatch.setattr(Path, "unlink", boom_unlink)

    result = TactusTestRunner._run_single_scenario("Scenario", str(tmp_path))

    assert result.name == "Scenario"


def test_run_single_scenario_raises_when_scenario_missing(tmp_path, monkeypatch):
    def fake_run(*_args, **_kwargs):
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr(test_runner.subprocess, "run", fake_run)

    class FakeUUID:
        hex = "noscn"

    monkeypatch.setattr(uuid, "uuid4", lambda: FakeUUID())

    results_file = tmp_path / "results_noscn.json"
    payload = [{"elements": [{"name": "Other", "status": "passed", "steps": []}]}]
    results_file.write_text(json.dumps(payload))

    with pytest.raises(RuntimeError, match="Scenario 'Scenario' not found"):
        TactusTestRunner._run_single_scenario("Scenario", str(tmp_path))


def test_run_single_scenario_timeout(tmp_path, monkeypatch):
    def fake_run(*_args, **_kwargs):
        raise test_runner.subprocess.TimeoutExpired(cmd="behave", timeout=1)

    monkeypatch.setattr(test_runner.subprocess, "run", fake_run)

    with pytest.raises(RuntimeError, match="timed out"):
        TactusTestRunner._run_single_scenario("Scenario", str(tmp_path))


def test_cleanup_removes_modules_and_work_dir(tmp_path, monkeypatch):
    runner = TactusTestRunner(Path(tmp_path / "proc.tac"))
    runner.work_dir = tmp_path / "work"
    runner.work_dir.mkdir()
    step_file = runner.work_dir / "steps" / "tactus_steps_abcd1234.py"
    step_file.parent.mkdir()
    step_file.write_text("x = 1")
    runner.generated_step_file = step_file

    import sys

    sys.modules["steps.tactus_steps_abcd1234"] = SimpleNamespace()
    sys.modules["tactus_steps_abcd1234"] = SimpleNamespace()

    runner.cleanup()

    assert not runner.work_dir.exists()


def test_cleanup_warns_on_rmtree_error(tmp_path, monkeypatch):
    runner = TactusTestRunner(Path(tmp_path / "proc.tac"))
    runner.work_dir = tmp_path / "work"
    runner.work_dir.mkdir()

    def fail_rmtree(_path):
        raise OSError("nope")

    monkeypatch.setattr(shutil, "rmtree", fail_rmtree)

    runner.cleanup()
