"""Tests for evaluation runner metrics."""

from pathlib import Path

from tactus.testing.evaluation_runner import TactusEvaluationRunner
from tactus.testing.models import ScenarioResult, StepResult


def _scenario_result(status: str, duration: float, steps):
    return ScenarioResult(name="scenario", status=status, duration=duration, steps=steps)


def test_calculate_consistency():
    runner = TactusEvaluationRunner(Path("dummy.tac"))

    steps_a = [StepResult(keyword="Given", message="a", status="passed")]
    steps_b = [StepResult(keyword="Given", message="a", status="passed")]
    steps_c = [StepResult(keyword="Given", message="b", status="failed")]

    results = [
        _scenario_result("passed", 1.0, steps_a),
        _scenario_result("passed", 1.2, steps_b),
        _scenario_result("failed", 0.8, steps_c),
    ]

    consistency = runner._calculate_consistency(results)

    assert consistency == 2 / 3


def test_calculate_metrics_flaky():
    runner = TactusEvaluationRunner(Path("dummy.tac"))

    steps = [StepResult(keyword="Given", message="a", status="passed")]
    results = [
        _scenario_result("passed", 1.0, steps),
        _scenario_result("failed", 2.0, steps),
    ]

    metrics = runner._calculate_metrics("scenario", results)

    assert metrics.total_runs == 2
    assert metrics.passed_runs == 1
    assert metrics.failed_runs == 1
    assert metrics.is_flaky is True
