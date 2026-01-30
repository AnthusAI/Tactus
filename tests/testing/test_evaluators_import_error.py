import builtins
import importlib
import importlib.util
import sys


def test_evaluators_import_error_defines_fallback():
    import tactus.testing.evaluators as evaluators

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name.startswith("pydantic_evals"):
            raise ImportError("missing")
        return real_import(name, *args, **kwargs)

    spec = importlib.util.spec_from_file_location(
        "tactus.testing.evaluators_missing", evaluators.__file__
    )
    module = importlib.util.module_from_spec(spec)
    try:
        builtins.__import__ = fake_import
        spec.loader.exec_module(module)
    finally:
        builtins.__import__ = real_import

    assert module.PYDANTIC_EVALS_AVAILABLE is False
    assert hasattr(module, "Evaluator")
    assert hasattr(module, "EvaluatorContext")


def test_evaluators_import_error_reloads_module():
    import tactus.testing.evaluators as evaluators
    import tactus.testing as testing_pkg

    real_import = builtins.__import__
    original_module = sys.modules.get("tactus.testing.evaluators")

    def fake_import(name, *args, **kwargs):
        if name.startswith("pydantic_evals"):
            raise ImportError("missing")
        return real_import(name, *args, **kwargs)

    try:
        builtins.__import__ = fake_import
        sys.modules.pop("tactus.testing.evaluators", None)
        reloaded = importlib.import_module("tactus.testing.evaluators")
    finally:
        builtins.__import__ = real_import
        if original_module is not None:
            sys.modules["tactus.testing.evaluators"] = original_module
            testing_pkg.evaluators = original_module

    assert reloaded is not evaluators
    assert reloaded.PYDANTIC_EVALS_AVAILABLE is False
