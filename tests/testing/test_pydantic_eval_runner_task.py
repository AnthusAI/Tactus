from tactus.testing.eval_models import EvaluationConfig
from tactus.testing.pydantic_eval_runner import TactusPydanticEvalRunner


def test_task_function_returns_error_payload(monkeypatch, tmp_path):
    class FakeRuntime:
        def __init__(self, *args, **kwargs):
            self.session = None

        async def execute(self, *args, **kwargs):
            raise RuntimeError("boom")

    monkeypatch.setattr("tactus.core.runtime.TactusRuntime", FakeRuntime)

    runner = TactusPydanticEvalRunner(
        tmp_path / "proc.tac", EvaluationConfig(dataset=[], evaluators=[])
    )
    runner._procedure_source = "Procedure { function() end }"

    task = runner._create_task_function()
    result = task({"x": 1})

    assert result["__output__"]["success"] is False
    assert "boom" in result["__output__"]["error"]
    assert "duration" in result["__trace__"]


def test_task_function_wraps_non_dict_output(monkeypatch, tmp_path):
    class FakeRuntime:
        def __init__(self, *args, **kwargs):
            self.session = None
            self.total_cost = 0.0
            self.total_tokens = 0

        async def execute(self, *args, **kwargs):
            return "ok"

    monkeypatch.setattr("tactus.core.runtime.TactusRuntime", FakeRuntime)

    runner = TactusPydanticEvalRunner(
        tmp_path / "proc.tac", EvaluationConfig(dataset=[], evaluators=[])
    )
    runner._procedure_source = "Procedure { function() end }"

    task = runner._create_task_function()
    result = task({"x": 1})

    assert result["__output__"] == "ok"


def test_task_function_preserves_dict_output_without_result(monkeypatch, tmp_path):
    class FakeRuntime:
        def __init__(self, *args, **kwargs):
            self.session = None
            self.total_cost = 0.0
            self.total_tokens = 0

        async def execute(self, *args, **kwargs):
            return {"ok": True}

    monkeypatch.setattr("tactus.core.runtime.TactusRuntime", FakeRuntime)

    runner = TactusPydanticEvalRunner(
        tmp_path / "proc.tac", EvaluationConfig(dataset=[], evaluators=[])
    )
    runner._procedure_source = "Procedure { function() end }"

    task = runner._create_task_function()
    result = task({"x": 1})

    assert result["__output__"] == {"ok": True}
