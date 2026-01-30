"""Tests for evaluation helper evaluators."""

from types import SimpleNamespace

import pytest

from tactus.testing import evaluators
from tactus.testing.eval_models import EvaluatorConfig


def _ctx(output=None, expected=None, metadata=None):
    return SimpleNamespace(output=output, expected_output=expected, metadata=metadata or {})


def test_contains_field_evaluator():
    config = EvaluatorConfig(type="contains", field="text", value="Hello")
    evaluator = evaluators._create_contains_evaluator(config)

    assert evaluator.evaluate(_ctx({"text": "Hello world"})) is True
    assert evaluator.evaluate(_ctx({"text": "Nope"})) is False


def test_contains_evaluator_requires_value():
    config = EvaluatorConfig(type="contains", value=None)
    with pytest.raises(ValueError):
        evaluators._create_contains_evaluator(config)


def test_contains_any_evaluator():
    config = EvaluatorConfig(type="contains_any", value=["a", "b"])
    evaluator = evaluators._create_contains_any_evaluator(config)

    assert evaluator.evaluate(_ctx("has b")) is True
    assert evaluator.evaluate(_ctx("none")) is False

    config = EvaluatorConfig(type="contains_any", check_expected="choices")
    evaluator = evaluators._create_contains_any_evaluator(config)
    ctx = _ctx("b value", expected={"choices": ["a", "b"]})

    assert evaluator.evaluate(ctx) is True


def test_equals_expected_field_evaluator():
    config = EvaluatorConfig(type="equals_expected", field="score")
    evaluator = evaluators._create_equals_expected_evaluator(config)

    assert evaluator.evaluate(_ctx({"score": 1}, expected={"score": 1})) is True
    assert evaluator.evaluate(_ctx({"score": 2}, expected={"score": 1})) is False
    assert evaluator.evaluate(_ctx({"score": 2}, expected=None)) is True
    assert evaluator.evaluate(_ctx("nope", expected={"score": 2})) is False


def test_min_and_max_length_evaluators():
    min_eval = evaluators._create_min_length_evaluator(EvaluatorConfig(type="min_length", value=3))
    max_eval = evaluators._create_max_length_evaluator(EvaluatorConfig(type="max_length", value=3))

    assert min_eval.evaluate(_ctx("hey")) is True
    assert min_eval.evaluate(_ctx("hi")) is False
    assert max_eval.evaluate(_ctx("hey")) is True
    assert max_eval.evaluate(_ctx("hello")) is False

    field_min = evaluators._create_min_length_evaluator(
        EvaluatorConfig(type="min_length", field="items", value=2)
    )
    field_max = evaluators._create_max_length_evaluator(
        EvaluatorConfig(type="max_length", field="items", value=2)
    )

    assert field_min.evaluate(_ctx({"items": [1, 2]})) is True
    assert field_max.evaluate(_ctx({"items": [1, 2, 3]})) is False


def test_max_iterations_cost_tokens():
    iterations_eval = evaluators._create_max_iterations_evaluator(
        EvaluatorConfig(type="max_iterations", value=3)
    )
    cost_eval = evaluators._create_max_cost_evaluator(EvaluatorConfig(type="max_cost", value=1.0))
    tokens_eval = evaluators._create_max_tokens_evaluator(
        EvaluatorConfig(type="max_tokens", value=5)
    )

    assert iterations_eval.evaluate(_ctx(metadata={"iterations": 2})) is True
    assert iterations_eval.evaluate(_ctx(metadata={"iterations": 4})) is False
    assert cost_eval.evaluate(_ctx(metadata={"total_cost": 0.5})) is True
    assert cost_eval.evaluate(_ctx(metadata={"total_cost": 2.0})) is False
    assert tokens_eval.evaluate(_ctx(metadata={"total_tokens": 4})) is True
    assert tokens_eval.evaluate(_ctx(metadata={"total_tokens": 9})) is False

    assert iterations_eval.evaluate(_ctx(output={"iterations": 2})) is True
    assert cost_eval.evaluate(_ctx(output={"total_cost": 0.5})) is True
    assert tokens_eval.evaluate(_ctx(output={"total_tokens": 4})) is True


def test_trace_based_evaluators():
    tool_eval = evaluators._create_tool_called_evaluator(
        EvaluatorConfig(type="tool_called", value="done")
    )
    state_eval = evaluators._create_state_check_evaluator(
        EvaluatorConfig(type="state_check", field="status", value="ok")
    )
    turns_eval = evaluators._create_agent_turns_evaluator(
        EvaluatorConfig(type="agent_turns", field="agent")
    )

    trace = {
        "tool_calls": [{"name": "done"}],
        "state_changes": [{"variable": "status", "value": "ok"}],
        "agent_turns": [{"agent": "agent"}],
    }
    ctx = _ctx(output={"__trace__": trace})

    assert tool_eval.evaluate(ctx) is True
    assert state_eval.evaluate(ctx) is True
    assert turns_eval.evaluate(ctx) is True

    tool_eval = evaluators._create_tool_called_evaluator(
        EvaluatorConfig(type="tool_called", value="done", min_value=2)
    )
    trace = {"tool_calls": [{"name": "done"}]}
    ctx = _ctx(output={"__trace__": trace})
    assert tool_eval.evaluate(ctx) is False

    state_eval = evaluators._create_state_check_evaluator(
        EvaluatorConfig(type="state_check", field="missing", value="x")
    )
    assert state_eval.evaluate(ctx) is False

    turns_eval = evaluators._create_agent_turns_evaluator(
        EvaluatorConfig(type="agent_turns", field="agent", max_value=0)
    )
    trace = {"agent_turns": [{"agent": "agent"}]}
    ctx = _ctx(output={"__trace__": trace})
    assert turns_eval.evaluate(ctx) is False


def test_regex_and_range_evaluators():
    regex_eval = evaluators._create_regex_evaluator(EvaluatorConfig(type="regex", value=r"^hi"))
    range_eval = evaluators._create_range_evaluator(
        EvaluatorConfig(type="range", min_value=1, max_value=3)
    )

    assert regex_eval.evaluate(_ctx("hi there")) is True
    assert regex_eval.evaluate(_ctx("no")) is False
    assert range_eval.evaluate(_ctx(2)) is True
    assert range_eval.evaluate(_ctx(4)) is False

    regex_eval = evaluators._create_regex_evaluator(
        EvaluatorConfig(type="regex", field="text", value="Hi", case_sensitive=False)
    )
    assert regex_eval.evaluate(_ctx({"text": "hi"})) is True

    range_eval = evaluators._create_range_evaluator(
        EvaluatorConfig(type="range", value={"min": 1, "max": 2})
    )
    assert range_eval.evaluate(_ctx(0)) is False
    assert range_eval.evaluate(_ctx("nope")) is False


def test_json_schema_evaluator_optional():
    evaluator = evaluators._create_json_schema_evaluator(
        EvaluatorConfig(type="json_schema", value={"type": "object"})
    )

    ctx = _ctx({"a": 1})
    try:
        result = evaluator.evaluate(ctx)
    except Exception:
        pytest.fail("JSON schema evaluator should not raise")
    else:
        assert result in {True, False}


def test_trace_helpers_get_trace_from_metadata():
    evaluator = evaluators.TraceAwareEvaluator()
    ctx = _ctx(output={"__output__": {"x": 2}}, metadata={"trace": {"x": 1}})

    assert evaluator.get_trace(ctx) == {"x": 1}
    assert evaluator.get_output(ctx) == {"x": 2}


def test_create_evaluator_unknown_type():
    with pytest.raises(ValueError):
        evaluators.create_evaluator(EvaluatorConfig(type="nope"))
