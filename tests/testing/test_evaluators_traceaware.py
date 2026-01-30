import pytest

from tactus.testing import evaluators


class DummyContext:
    def __init__(self, output=None, metadata=None):
        self.output = output
        self.metadata = metadata or {}


def test_trace_aware_evaluator_get_trace_prefers_metadata():
    evaluator = evaluators.TraceAwareEvaluator()
    ctx = DummyContext(
        output={"__trace__": {"from": "output"}}, metadata={"trace": {"from": "meta"}}
    )
    assert evaluator.get_trace(ctx) == {"from": "meta"}


def test_trace_aware_evaluator_get_trace_from_output():
    evaluator = evaluators.TraceAwareEvaluator()
    ctx = DummyContext(output={"__trace__": {"from": "output"}})
    assert evaluator.get_trace(ctx) == {"from": "output"}


def test_trace_aware_evaluator_get_output_unwraps():
    evaluator = evaluators.TraceAwareEvaluator()
    ctx = DummyContext(output={"__output__": {"value": 1}})
    assert evaluator.get_output(ctx) == {"value": 1}


def test_create_evaluator_rejects_unknown_type(monkeypatch):
    monkeypatch.setattr(evaluators, "PYDANTIC_EVALS_AVAILABLE", True)

    config = type("Cfg", (), {"type": "unknown", "params": {}, "metadata": {}})()
    with pytest.raises(ValueError):
        evaluators.create_evaluator(config)


def test_create_evaluator_requires_pydantic_evals(monkeypatch):
    monkeypatch.setattr(evaluators, "PYDANTIC_EVALS_AVAILABLE", False)

    config = type("Cfg", (), {"type": "contains", "params": {}, "metadata": {}})()
    with pytest.raises(ImportError):
        evaluators.create_evaluator(config)
