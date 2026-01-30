import builtins
import importlib.util
from pathlib import Path


def test_eval_runner_import_error_sets_flag():
    import tactus.testing.pydantic_eval_runner as eval_runner

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name.startswith("pydantic_evals"):
            raise ImportError("missing")
        return real_import(name, *args, **kwargs)

    spec = importlib.util.spec_from_file_location(
        "tactus.testing.pydantic_eval_runner_missing", eval_runner.__file__
    )
    module = importlib.util.module_from_spec(spec)
    try:
        builtins.__import__ = fake_import
        spec.loader.exec_module(module)
    finally:
        builtins.__import__ = real_import

    assert module.PYDANTIC_EVALS_AVAILABLE is False
    try:
        module.TactusPydanticEvalRunner(
            Path("proc.tac"), module.EvaluationConfig(dataset=[], evaluators=[])
        )
    except ImportError as exc:
        assert "pydantic_evals" in str(exc)
