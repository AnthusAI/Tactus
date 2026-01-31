import sys
from types import SimpleNamespace

from tactus.ide import server as ide_server


def test_test_stream_missing_path():
    app = ide_server.create_app()
    client = app.test_client()

    response = client.get("/api/test/stream")
    assert response.status_code == 400


def test_test_stream_value_error(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    file_path = workspace / "sample.tac"
    file_path.write_text("content")

    monkeypatch.setattr(ide_server, "WORKSPACE_ROOT", str(workspace))
    monkeypatch.setattr(
        ide_server,
        "_resolve_workspace_path",
        lambda _path: (_ for _ in ()).throw(ValueError("bad")),
    )

    app = ide_server.create_app()
    client = app.test_client()

    response = client.get("/api/test/stream", query_string={"path": "sample.tac"})
    assert response.status_code == 400


def test_test_stream_file_not_found(tmp_path, monkeypatch):
    monkeypatch.setattr(ide_server, "WORKSPACE_ROOT", str(tmp_path))
    app = ide_server.create_app()
    client = app.test_client()

    response = client.get("/api/test/stream", query_string={"path": "missing.tac"})
    assert response.status_code == 404


def test_test_stream_validation_failed(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    file_path = workspace / "sample.tac"
    file_path.write_text("content")

    result = SimpleNamespace(valid=False, errors=[SimpleNamespace(message="bad", level="error")])

    class DummyValidator:
        def validate_file(self, _path):
            return result

    monkeypatch.setattr(ide_server, "WORKSPACE_ROOT", str(workspace))
    monkeypatch.setattr("tactus.validation.TactusValidator", lambda: DummyValidator())

    app = ide_server.create_app()
    client = app.test_client()

    response = client.get("/api/test/stream", query_string={"path": "sample.tac"})
    data = response.data.decode("utf-8")
    assert "Validation failed" in data


def test_test_stream_behave_reset_failure(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    file_path = workspace / "sample.tac"
    file_path.write_text("content")

    registry = SimpleNamespace(gherkin_specifications="Feature: Demo\nScenario: One\n")
    result = SimpleNamespace(valid=True, errors=[], registry=registry)

    class DummyValidator:
        def validate_file(self, _path):
            return result

    class DummyRunner:
        def __init__(self, *_args, **_kwargs):
            pass

        def setup(self, _specs):
            return None

        def run_tests(self, parallel=False):
            raise RuntimeError("boom")

        def cleanup(self):
            return None

    class DummyParser:
        def parse(self, _specs):
            return SimpleNamespace(scenarios=[])

    class BrokenRegistry:
        @property
        def registry(self):
            raise RuntimeError("boom")

    fake_behave = SimpleNamespace(step_registry=BrokenRegistry())
    monkeypatch.setitem(sys.modules, "behave", fake_behave)

    monkeypatch.setattr(ide_server, "WORKSPACE_ROOT", str(workspace))
    monkeypatch.setattr("tactus.validation.TactusValidator", lambda: DummyValidator())
    monkeypatch.setattr("tactus.testing.TactusTestRunner", DummyRunner)
    monkeypatch.setattr("tactus.testing.GherkinParser", DummyParser)

    app = ide_server.create_app()
    client = app.test_client()

    response = client.get("/api/test/stream", query_string={"path": "sample.tac"})
    data = response.data.decode("utf-8")
    assert '"lifecycle_stage": "error"' in data


def test_evaluate_stream_missing_path():
    app = ide_server.create_app()
    client = app.test_client()

    response = client.get("/api/evaluate/stream")
    assert response.status_code == 400


def test_evaluate_stream_file_not_found(tmp_path, monkeypatch):
    monkeypatch.setattr(ide_server, "WORKSPACE_ROOT", str(tmp_path))
    app = ide_server.create_app()
    client = app.test_client()

    response = client.get("/api/evaluate/stream", query_string={"path": "missing.tac"})
    assert response.status_code == 404


def test_evaluate_stream_validation_failed(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    file_path = workspace / "sample.tac"
    file_path.write_text("content")

    result = SimpleNamespace(valid=False, errors=[SimpleNamespace(message="bad", level="error")])

    class DummyValidator:
        def validate_file(self, _path):
            return result

    monkeypatch.setattr(ide_server, "WORKSPACE_ROOT", str(workspace))
    monkeypatch.setattr("tactus.validation.TactusValidator", lambda: DummyValidator())

    app = ide_server.create_app()
    client = app.test_client()

    response = client.get("/api/evaluate/stream", query_string={"path": "sample.tac"})
    data = response.data.decode("utf-8")
    assert "Validation failed" in data


def test_test_stream_setup_exception(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    file_path = workspace / "sample.tac"
    file_path.write_text("content")

    monkeypatch.setattr(ide_server, "WORKSPACE_ROOT", str(workspace))
    monkeypatch.setattr(
        "tactus.validation.TactusValidator",
        lambda: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    app = ide_server.create_app()
    client = app.test_client()

    response = client.get("/api/test/stream", query_string={"path": "sample.tac"})
    data = response.data.decode("utf-8")
    assert '"lifecycle_stage": "error"' in data


def test_evaluate_stream_setup_exception(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    file_path = workspace / "sample.tac"
    file_path.write_text("content")

    monkeypatch.setattr(ide_server, "WORKSPACE_ROOT", str(workspace))
    monkeypatch.setattr(
        "tactus.validation.TactusValidator",
        lambda: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    app = ide_server.create_app()
    client = app.test_client()

    response = client.get("/api/evaluate/stream", query_string={"path": "sample.tac"})
    data = response.data.decode("utf-8")
    assert '"lifecycle_stage": "error"' in data


def test_evaluate_stream_value_error(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    file_path = workspace / "sample.tac"
    file_path.write_text("content")

    monkeypatch.setattr(ide_server, "WORKSPACE_ROOT", str(workspace))
    monkeypatch.setattr(
        ide_server,
        "_resolve_workspace_path",
        lambda _path: (_ for _ in ()).throw(ValueError("bad")),
    )

    app = ide_server.create_app()
    client = app.test_client()

    response = client.get("/api/evaluate/stream", query_string={"path": "sample.tac"})
    assert response.status_code == 400


def test_evaluate_stream_unexpected_error(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    file_path = workspace / "sample.tac"
    file_path.write_text("content")

    monkeypatch.setattr(ide_server, "WORKSPACE_ROOT", str(workspace))
    monkeypatch.setattr(
        ide_server,
        "_resolve_workspace_path",
        lambda _path: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    app = ide_server.create_app()
    client = app.test_client()

    response = client.get("/api/evaluate/stream", query_string={"path": "sample.tac"})
    assert response.status_code == 500


def test_evaluate_stream_runner_error(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    file_path = workspace / "sample.tac"
    file_path.write_text("content")

    registry = SimpleNamespace(gherkin_specifications="Feature: Demo\nScenario: One\n")
    result = SimpleNamespace(valid=True, errors=[], registry=registry)

    class DummyValidator:
        def validate_file(self, _path):
            return result

    class DummyRunner:
        def __init__(self, *_args, **_kwargs):
            pass

        def setup(self, _specs):
            return None

        def evaluate_all(self, runs=1, parallel=True):
            raise RuntimeError("boom")

        def cleanup(self):
            return None

    class DummyParser:
        def parse(self, _specs):
            return SimpleNamespace(scenarios=[])

    monkeypatch.setattr(ide_server, "WORKSPACE_ROOT", str(workspace))
    monkeypatch.setattr("tactus.validation.TactusValidator", lambda: DummyValidator())
    monkeypatch.setattr("tactus.testing.TactusEvaluationRunner", DummyRunner)
    monkeypatch.setattr("tactus.testing.GherkinParser", DummyParser)

    app = ide_server.create_app()
    client = app.test_client()

    response = client.get("/api/evaluate/stream", query_string={"path": "sample.tac"})
    data = response.data.decode("utf-8")
    assert '"lifecycle_stage": "error"' in data


def test_pydantic_eval_stream_validation_failed(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    file_path = workspace / "eval.tac"
    file_path.write_text("content")

    result = SimpleNamespace(valid=False, errors=[SimpleNamespace(message="bad")], registry=None)

    class DummyValidator:
        def validate_file(self, _path):
            return result

    monkeypatch.setattr(ide_server, "WORKSPACE_ROOT", str(workspace))
    monkeypatch.setattr(ide_server, "TactusValidator", lambda: DummyValidator())

    app = ide_server.create_app()
    client = app.test_client()

    response = client.get("/api/pydantic-eval/stream", query_string={"path": "eval.tac"})
    data = response.data.decode("utf-8")
    assert '"lifecycle_stage": "error"' in data


def test_pydantic_eval_stream_runner_error(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    file_path = workspace / "eval.tac"
    file_path.write_text("content")

    registry = SimpleNamespace(pydantic_evaluations={"dataset": [], "evaluators": []})
    result = SimpleNamespace(valid=True, errors=[], registry=registry)

    class DummyValidator:
        def validate_file(self, _path):
            return result

    class DummyRunner:
        def __init__(self, **_kwargs):
            pass

        def run_evaluation(self):
            raise RuntimeError("boom")

        def check_thresholds(self, _report):
            return True, []

    class EvalCase:
        def __init__(self, **_kwargs):
            pass

    class EvaluatorConfig:
        def __init__(self, **_kwargs):
            pass

    class EvaluationConfig:
        def __init__(self, **_kwargs):
            pass

    monkeypatch.setattr(ide_server, "WORKSPACE_ROOT", str(workspace))
    monkeypatch.setattr(ide_server, "TactusValidator", lambda: DummyValidator())
    monkeypatch.setattr("tactus.testing.pydantic_eval_runner.TactusPydanticEvalRunner", DummyRunner)
    monkeypatch.setattr("tactus.testing.eval_models.EvalCase", EvalCase)
    monkeypatch.setattr("tactus.testing.eval_models.EvaluatorConfig", EvaluatorConfig)
    monkeypatch.setattr("tactus.testing.eval_models.EvaluationConfig", EvaluationConfig)

    app = ide_server.create_app()
    client = app.test_client()

    response = client.get("/api/pydantic-eval/stream", query_string={"path": "eval.tac"})
    data = response.data.decode("utf-8")
    assert '"lifecycle_stage": "error"' in data


def test_pydantic_eval_stream_missing_path():
    app = ide_server.create_app()
    client = app.test_client()

    response = client.get("/api/pydantic-eval/stream")
    assert response.status_code == 400


def test_pydantic_eval_stream_file_not_found(tmp_path, monkeypatch):
    monkeypatch.setattr(ide_server, "WORKSPACE_ROOT", str(tmp_path))
    app = ide_server.create_app()
    client = app.test_client()

    response = client.get("/api/pydantic-eval/stream", query_string={"path": "missing.tac"})
    assert response.status_code == 404


def test_pydantic_eval_stream_import_error(tmp_path, monkeypatch):
    import builtins

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    file_path = workspace / "eval.tac"
    file_path.write_text("content")

    class DummyValidator:
        def validate_file(self, _path):
            return SimpleNamespace(
                valid=True,
                errors=[],
                registry=SimpleNamespace(pydantic_evaluations={"dataset": [], "evaluators": []}),
            )

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "tactus.testing.pydantic_eval_runner":
            raise ImportError("boom")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    monkeypatch.setattr(ide_server, "WORKSPACE_ROOT", str(workspace))
    monkeypatch.setattr(ide_server, "TactusValidator", lambda: DummyValidator())

    app = ide_server.create_app()
    client = app.test_client()

    response = client.get("/api/pydantic-eval/stream", query_string={"path": "eval.tac"})
    data = response.data.decode("utf-8")
    assert "pydantic_evals not installed" in data
