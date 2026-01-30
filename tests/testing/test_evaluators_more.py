import builtins
import pytest

from tactus.testing import evaluators
from tactus.testing.eval_models import EvaluatorConfig


class DummyCtx:
    def __init__(self, output=None, expected_output=None):
        self.output = output
        self.expected_output = expected_output
        self.metadata = {}


def test_contains_any_evaluator_passes(monkeypatch):
    monkeypatch.setattr(evaluators, "PYDANTIC_EVALS_AVAILABLE", True)
    cfg = EvaluatorConfig(type="contains_any", value=["a", "b"])
    evaluator = evaluators.create_evaluator(cfg)

    assert evaluator.evaluate(DummyCtx(output="hello b")) is True


def test_min_length_evaluator(monkeypatch):
    monkeypatch.setattr(evaluators, "PYDANTIC_EVALS_AVAILABLE", True)
    cfg = EvaluatorConfig(type="min_length", value=3)
    evaluator = evaluators.create_evaluator(cfg)

    assert evaluator.evaluate(DummyCtx(output="abcd")) is True


def test_contains_any_evaluator_missing_values_returns_false():
    evaluator = evaluators._create_contains_any_evaluator(EvaluatorConfig(type="contains_any"))
    assert evaluator.evaluate(DummyCtx(output="anything")) is False


def test_equals_expected_default_evaluator_matches():
    evaluator = evaluators._create_equals_expected_evaluator(
        EvaluatorConfig(type="equals_expected")
    )
    ctx = DummyCtx(output={"a": 1}, expected_output={"a": 1})
    assert evaluator.evaluate(ctx) is True


def test_is_instance_evaluator_requires_value():
    with pytest.raises(ValueError):
        evaluators._create_is_instance_evaluator(EvaluatorConfig(type="is_instance"))


def test_llm_judge_requires_rubric():
    with pytest.raises(ValueError):
        evaluators._create_llm_judge_evaluator(EvaluatorConfig(type="llm_judge"))


def test_min_length_uses_expected_override():
    evaluator = evaluators._create_min_length_evaluator(
        EvaluatorConfig(type="min_length", check_expected="limit", value=1)
    )
    ctx = DummyCtx(output="ok", expected_output={"limit": 3})
    assert evaluator.evaluate(ctx) is False


def test_max_length_handles_list_output():
    evaluator = evaluators._create_max_length_evaluator(EvaluatorConfig(type="max_length", value=2))
    assert evaluator.evaluate(DummyCtx(output=[1, 2, 3])) is False


def test_max_iterations_cost_tokens_fallback_true():
    iterations_eval = evaluators._create_max_iterations_evaluator(
        EvaluatorConfig(type="max_iterations", value=1)
    )
    cost_eval = evaluators._create_max_cost_evaluator(EvaluatorConfig(type="max_cost", value=1.0))
    tokens_eval = evaluators._create_max_tokens_evaluator(
        EvaluatorConfig(type="max_tokens", value=1)
    )

    ctx = DummyCtx(output="no metadata")
    assert iterations_eval.evaluate(ctx) is True
    assert cost_eval.evaluate(ctx) is True
    assert tokens_eval.evaluate(ctx) is True


def test_tool_called_respects_max_calls():
    evaluator = evaluators._create_tool_called_evaluator(
        EvaluatorConfig(type="tool_called", value="ping", max_value=1)
    )
    ctx = DummyCtx(output={"__trace__": {"tool_calls": [{"name": "ping"}, {"name": "ping"}]}})
    assert evaluator.evaluate(ctx) is False


def test_agent_turns_respects_max_value_and_filter():
    evaluator = evaluators._create_agent_turns_evaluator(
        EvaluatorConfig(type="agent_turns", field="agent", max_value=1)
    )
    ctx = DummyCtx(output={"__trace__": {"agent_turns": [{"agent": "agent"}, {"agent": "agent"}]}})
    assert evaluator.evaluate(ctx) is False


def test_json_schema_evaluator_handles_missing_dependency(monkeypatch):
    evaluator = evaluators._create_json_schema_evaluator(
        EvaluatorConfig(type="json_schema", value={"type": "object"})
    )

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "jsonschema":
            raise ImportError("missing")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    assert evaluator.evaluate(DummyCtx(output={"a": 1})) is True


def test_range_evaluator_field_from_dict():
    evaluator = evaluators._create_range_evaluator(
        EvaluatorConfig(type="range", field="value", min_value=1, max_value=2)
    )
    assert evaluator.evaluate(DummyCtx(output={"value": 1.5})) is True


def test_create_evaluator_covers_all_types(monkeypatch):
    monkeypatch.setattr(evaluators, "PYDANTIC_EVALS_AVAILABLE", True)

    configs = [
        EvaluatorConfig(type="contains", value="hi"),
        EvaluatorConfig(type="contains_any", value=["a"]),
        EvaluatorConfig(type="equals_expected"),
        EvaluatorConfig(type="exact_match"),
        EvaluatorConfig(type="is_instance", value="str"),
        EvaluatorConfig(type="llm_judge", rubric="score"),
        EvaluatorConfig(type="min_length", value=1),
        EvaluatorConfig(type="max_length", value=1),
        EvaluatorConfig(type="max_iterations", value=1),
        EvaluatorConfig(type="max_cost", value=1.0),
        EvaluatorConfig(type="max_tokens", value=1),
        EvaluatorConfig(type="tool_called", value="done"),
        EvaluatorConfig(type="state_check", field="status", value="ok"),
        EvaluatorConfig(type="agent_turns", field="agent"),
        EvaluatorConfig(type="regex", value="hi"),
        EvaluatorConfig(type="json_schema", value={"type": "object"}),
        EvaluatorConfig(type="range", min_value=1, max_value=2),
    ]

    for config in configs:
        evaluator = evaluators.create_evaluator(config)
        assert hasattr(evaluator, "evaluate")


def test_trace_helpers_return_defaults():
    evaluator = evaluators.TraceAwareEvaluator()
    ctx = DummyCtx(output="raw", expected_output=None)
    assert evaluator.get_trace(ctx) == {}
    assert evaluator.get_output(ctx) == "raw"


def test_contains_evaluator_case_insensitive_field():
    evaluator = evaluators._create_contains_evaluator(
        EvaluatorConfig(type="contains", field="text", value="HELLO")
    )
    evaluator.case_sensitive = False
    assert evaluator.evaluate(DummyCtx(output={"text": "hello"})) is True


def test_contains_any_uses_field_output():
    evaluator = evaluators._create_contains_any_evaluator(
        EvaluatorConfig(type="contains_any", field="text", value=["yes"])
    )
    assert evaluator.evaluate(DummyCtx(output={"text": "yes"})) is True


def test_json_schema_evaluator_validation_failure():
    evaluator = evaluators._create_json_schema_evaluator(
        EvaluatorConfig(type="json_schema", value={"type": "integer"})
    )
    assert evaluator.evaluate(DummyCtx(output="nope")) is False
