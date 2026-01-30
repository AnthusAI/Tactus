import sys

from tactus.testing.eval_models import EvaluatorConfig
from tactus.testing import evaluators


class DummyCtx:
    def __init__(self, output=None, expected_output=None, metadata=None):
        self.output = output
        self.expected_output = expected_output
        self.metadata = metadata or {}


def test_tool_called_evaluator_counts_calls(monkeypatch):
    monkeypatch.setattr(evaluators, "PYDANTIC_EVALS_AVAILABLE", True)
    cfg = EvaluatorConfig(type="tool_called", value="ping", min_value=2)
    evaluator = evaluators.create_evaluator(cfg)

    ctx = DummyCtx(metadata={"trace": {"tool_calls": [{"name": "ping"}, {"name": "ping"}]}})
    assert evaluator.evaluate(ctx) is True


def test_state_check_evaluator_matches_latest_value(monkeypatch):
    monkeypatch.setattr(evaluators, "PYDANTIC_EVALS_AVAILABLE", True)
    cfg = EvaluatorConfig(type="state_check", field="status", value="done")
    evaluator = evaluators.create_evaluator(cfg)

    ctx = DummyCtx(
        metadata={
            "trace": {
                "state_changes": [
                    {"variable": "status", "value": "pending"},
                    {"variable": "status", "value": "done"},
                ]
            }
        }
    )
    assert evaluator.evaluate(ctx) is True


def test_agent_turns_evaluator_filters_agent(monkeypatch):
    monkeypatch.setattr(evaluators, "PYDANTIC_EVALS_AVAILABLE", True)
    cfg = EvaluatorConfig(type="agent_turns", field="agent", min_value=1)
    evaluator = evaluators.create_evaluator(cfg)
    evaluator.agent_name = "alpha"

    ctx = DummyCtx(metadata={"trace": {"agent_turns": [{"agent": "alpha"}, {"agent": "beta"}]}})
    assert evaluator.evaluate(ctx) is True


def test_regex_evaluator_matches_output(monkeypatch):
    monkeypatch.setattr(evaluators, "PYDANTIC_EVALS_AVAILABLE", True)
    cfg = EvaluatorConfig(type="regex", pattern="hello")
    evaluator = evaluators.create_evaluator(cfg)

    ctx = DummyCtx(output="hello world")
    assert evaluator.evaluate(ctx) is True


def test_trace_helpers_fall_back_to_output_trace():
    evaluator = evaluators.TraceAwareEvaluator()
    ctx = DummyCtx(output={"__trace__": {"step": "ok"}}, metadata={"trace": {}})

    assert evaluator.get_trace(ctx) == {"step": "ok"}


def test_contains_field_evaluator_handles_non_dict_output():
    evaluator = evaluators._create_contains_evaluator(
        EvaluatorConfig(type="contains", field="text", value="hi")
    )

    ctx = DummyCtx(output="hi there")
    assert evaluator.evaluate(ctx) is True


def test_state_check_ignores_non_dict_changes():
    evaluator = evaluators._create_state_check_evaluator(
        EvaluatorConfig(type="state_check", field="status", value="ok")
    )
    ctx = DummyCtx(output={"__trace__": {"state_changes": ["oops"]}})

    assert evaluator.evaluate(ctx) is False


def test_agent_turns_filtered_min_turns_fails():
    evaluator = evaluators._create_agent_turns_evaluator(
        EvaluatorConfig(type="agent_turns", field="alpha", min_value=2)
    )
    evaluator.agent_name = "alpha"
    ctx = DummyCtx(output={"__trace__": {"agent_turns": [{"agent": "alpha"}]}})

    assert evaluator.evaluate(ctx) is False


def test_agent_turns_without_agent_filter_counts_all():
    evaluator = evaluators._create_agent_turns_evaluator(
        EvaluatorConfig(type="agent_turns", field=None, min_value=2)
    )
    evaluator.agent_name = None
    ctx = DummyCtx(output={"__trace__": {"agent_turns": [{"agent": "a"}, {"agent": "b"}]}})

    assert evaluator.evaluate(ctx) is True


def test_json_schema_evaluator_uses_field_output(monkeypatch):
    class FakeValidationError(Exception):
        pass

    def fake_validate(instance, schema):
        assert instance == {"a": 1}
        assert schema == {"type": "object"}

    fake_module = type(
        "FakeJsonschema",
        (),
        {"validate": staticmethod(fake_validate), "ValidationError": FakeValidationError},
    )()

    monkeypatch.setitem(sys.modules, "jsonschema", fake_module)

    evaluator = evaluators._create_json_schema_evaluator(
        EvaluatorConfig(type="json_schema", field="data", value={"type": "object"})
    )
    ctx = DummyCtx(output={"data": {"a": 1}})

    assert evaluator.evaluate(ctx) is True
