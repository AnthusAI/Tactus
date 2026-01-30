from types import SimpleNamespace

from tactus.ide import server as ide_server


class FakeValidator:
    def __init__(self, result):
        self._result = result

    def validate_file(self, path, mode=None):
        return self._result


def test_test_stream_no_specifications(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    file_path = workspace / "sample.tac"
    file_path.write_text("content")

    registry = SimpleNamespace(gherkin_specifications=None)
    result = SimpleNamespace(valid=True, errors=[], registry=registry)
    monkeypatch.setattr("tactus.validation.TactusValidator", lambda: FakeValidator(result))
    monkeypatch.setattr(ide_server, "TactusValidator", lambda: FakeValidator(result))

    app = ide_server.create_app(initial_workspace=str(workspace))
    client = app.test_client()

    response = client.get("/api/test/stream", query_string={"path": "sample.tac"})
    data = response.data.decode("utf-8")
    assert "No specifications found" in data


def test_evaluate_stream_no_specifications(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    file_path = workspace / "sample.tac"
    file_path.write_text("content")

    registry = SimpleNamespace(gherkin_specifications=None)
    result = SimpleNamespace(valid=True, errors=[], registry=registry)
    monkeypatch.setattr("tactus.validation.TactusValidator", lambda: FakeValidator(result))

    app = ide_server.create_app(initial_workspace=str(workspace))
    client = app.test_client()

    response = client.get("/api/evaluate/stream", query_string={"path": "sample.tac"})
    data = response.data.decode("utf-8")
    assert "No specifications found" in data


def test_pydantic_eval_stream_no_evaluations(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    file_path = workspace / "sample.tac"
    file_path.write_text("content")

    registry = SimpleNamespace(pydantic_evaluations=None)
    result = SimpleNamespace(valid=True, errors=[], registry=registry)
    monkeypatch.setattr("tactus.validation.TactusValidator", lambda: FakeValidator(result))
    monkeypatch.setattr(ide_server, "TactusValidator", lambda: FakeValidator(result))

    app = ide_server.create_app(initial_workspace=str(workspace))
    client = app.test_client()

    response = client.get("/api/pydantic-eval/stream", query_string={"path": "sample.tac"})
    data = response.data.decode("utf-8")
    assert "No evaluations found" in data
