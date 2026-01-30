from types import SimpleNamespace

from tactus.testing.eval_models import EvaluationConfig, EvaluationThresholds
from tactus.testing.pydantic_eval_runner import TactusPydanticEvalRunner


def test_check_thresholds_passes_when_disabled(tmp_path):
    runner = TactusPydanticEvalRunner(
        tmp_path / "proc.tac", EvaluationConfig(dataset=[], evaluators=[])
    )
    passed, violations = runner.check_thresholds(SimpleNamespace(cases=[]))

    assert passed is True
    assert violations == []


def test_check_thresholds_reports_low_success_rate(tmp_path):
    thresholds = EvaluationThresholds(min_success_rate=1.0)
    runner = TactusPydanticEvalRunner(
        tmp_path / "proc.tac",
        EvaluationConfig(dataset=[], evaluators=[], thresholds=thresholds),
    )

    passing = SimpleNamespace(assertions={"ok": SimpleNamespace(value=True)})
    failing = SimpleNamespace(assertions={"ok": SimpleNamespace(value=False)})
    report = SimpleNamespace(cases=[passing, failing], averages=lambda: None)

    passed, violations = runner.check_thresholds(report)

    assert passed is False
    assert any("Success rate" in v for v in violations)


def test_check_thresholds_reports_cost_duration_tokens(tmp_path):
    thresholds = EvaluationThresholds(max_cost_per_run=0.5, max_duration=1.0, max_tokens_per_run=5)
    runner = TactusPydanticEvalRunner(
        tmp_path / "proc.tac",
        EvaluationConfig(dataset=[], evaluators=[], thresholds=thresholds),
    )

    case = SimpleNamespace(
        assertions={"ok": SimpleNamespace(value=True)},
        cost=1.0,
        task_duration=2.0,
        tokens=10,
    )
    report = SimpleNamespace(cases=[case], averages=lambda: None)

    passed, violations = runner.check_thresholds(report)

    assert passed is False
    assert any("Average cost" in v for v in violations)
    assert any("Average duration" in v for v in violations)
    assert any("Average tokens" in v for v in violations)


def test_check_thresholds_handles_empty_report_with_thresholds(tmp_path):
    thresholds = EvaluationThresholds(min_success_rate=0.5)
    runner = TactusPydanticEvalRunner(
        tmp_path / "proc.tac",
        EvaluationConfig(dataset=[], evaluators=[], thresholds=thresholds),
    )

    passed, violations = runner.check_thresholds(SimpleNamespace(cases=[]))

    assert passed is True
    assert violations == []


def test_check_thresholds_ignores_missing_case_metrics(tmp_path):
    thresholds = EvaluationThresholds(max_cost_per_run=0.1, max_duration=0.1, max_tokens_per_run=1)
    runner = TactusPydanticEvalRunner(
        tmp_path / "proc.tac",
        EvaluationConfig(dataset=[], evaluators=[], thresholds=thresholds),
    )

    report = SimpleNamespace(
        cases=[SimpleNamespace(assertions={"ok": SimpleNamespace(value=True)})]
    )

    passed, violations = runner.check_thresholds(report)

    assert passed is True
    assert violations == []
