from pathlib import Path
from types import SimpleNamespace

from tactus.testing.evaluation_runner import TactusEvaluationRunner
from tactus.testing.models import ScenarioResult, StepResult


def test_calculate_consistency_empty_results(tmp_path):
    runner = TactusEvaluationRunner(Path(tmp_path / "proc.tac"))
    assert runner._calculate_consistency([]) == 0.0


def test_calculate_metrics_and_flakiness(tmp_path):
    runner = TactusEvaluationRunner(Path(tmp_path / "proc.tac"))

    steps_pass = [
        StepResult(keyword="Given", message="x", status="passed"),
        StepResult(keyword="Then", message="y", status="passed"),
    ]
    steps_fail = [
        StepResult(keyword="Given", message="x", status="passed"),
        StepResult(keyword="Then", message="y", status="failed"),
    ]

    results = [
        ScenarioResult(name="s", status="passed", duration=1.0, steps=steps_pass),
        ScenarioResult(name="s", status="failed", duration=3.0, steps=steps_fail),
        ScenarioResult(name="s", status="passed", duration=2.0, steps=steps_pass),
    ]

    eval_result = runner._calculate_metrics("s", results)

    assert eval_result.total_runs == 3
    assert eval_result.passed_runs == 2
    assert eval_result.failed_runs == 1
    assert eval_result.success_rate == 2 / 3
    assert eval_result.mean_duration == 2.0
    assert eval_result.median_duration == 2.0
    assert eval_result.is_flaky is True
    assert 0.0 < eval_result.consistency_score < 1.0


def test_evaluate_all_parallel_uses_pool(monkeypatch, tmp_path):
    runner = TactusEvaluationRunner(Path(tmp_path / "proc.tac"))
    runner.work_dir = tmp_path
    runner.parsed_feature = SimpleNamespace(scenarios=[SimpleNamespace(name="scenario")])

    def fake_run(scenario_name, work_dir, iteration):
        return ScenarioResult(name=scenario_name, status="passed", duration=0.1, steps=[])

    runner._run_single_iteration = staticmethod(fake_run)

    class FakePool:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def starmap(self, func, args):
            return [func(*arg) for arg in args]

    class FakeCtx:
        def Pool(self, processes):
            return FakePool()

    monkeypatch.setattr(
        "tactus.testing.evaluation_runner.multiprocessing.get_context", lambda _: FakeCtx()
    )

    results = runner.evaluate_all(runs=2, parallel=True)
    assert results[0].total_runs == 2


def test_evaluate_scenario_non_parallel(monkeypatch, tmp_path):
    runner = TactusEvaluationRunner(Path(tmp_path / "proc.tac"))
    runner.work_dir = tmp_path

    def fake_run(scenario_name, work_dir, iteration):
        return ScenarioResult(name=scenario_name, status="passed", duration=0.1, steps=[])

    runner._run_single_iteration = staticmethod(fake_run)

    result = runner.evaluate_scenario("scenario", runs=2, parallel=False)
    assert result.total_runs == 2


def test_run_single_iteration_sets_iteration(monkeypatch):
    def fake_run(_name, _work_dir):
        return ScenarioResult(name="scenario", status="passed", duration=0.1, steps=[])

    monkeypatch.setattr(
        "tactus.testing.test_runner.TactusTestRunner._run_single_scenario", fake_run
    )
    result = TactusEvaluationRunner._run_single_iteration("scenario", ".", 3)
    assert result.iteration == 3
