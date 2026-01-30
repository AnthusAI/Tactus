"""Tests for evaluation models."""

from tactus.testing.eval_models import (
    EvalCase,
    EvaluatorConfig,
    EvaluationConfig,
    EvaluationThresholds,
    EvaluationResultSummary,
)


def test_eval_case_defaults():
    case = EvalCase(name="case", inputs={"a": 1})
    assert case.expected_output is None
    assert case.metadata == {}


def test_evaluator_config_defaults():
    config = EvaluatorConfig(type="contains", field="output", value="ok")
    assert config.include_expected is False
    assert config.case_sensitive is True


def test_evaluation_config_defaults():
    case = EvalCase(name="case", inputs={"a": 1})
    evaluator = EvaluatorConfig(type="exact_match", field="output", value="ok")
    config = EvaluationConfig(dataset=[case], evaluators=[evaluator])

    assert config.runs == 1
    assert config.parallel is True
    assert config.thresholds is None


def test_evaluation_thresholds_fields():
    thresholds = EvaluationThresholds(min_success_rate=0.9, max_cost_per_run=1.5)
    assert thresholds.min_success_rate == 0.9
    assert thresholds.max_cost_per_run == 1.5


def test_evaluation_result_summary_defaults():
    summary = EvaluationResultSummary(total_cases=2, passed_cases=2, failed_cases=0)
    assert summary.total_cost == 0.0
    assert summary.total_tokens == 0
    assert summary.total_duration == 0.0
    assert summary.case_results == []
