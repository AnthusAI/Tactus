from types import SimpleNamespace

from tactus.ide import server as ide_server


def test_validate_endpoint_reports_errors(monkeypatch):
    class DummyValidator:
        def validate(self, _content):
            return SimpleNamespace(
                valid=False,
                errors=[SimpleNamespace(message="bad", location=(1, 2), level="error")],
                warnings=[],
            )

    monkeypatch.setattr(ide_server, "TactusValidator", DummyValidator)
    app = ide_server.create_app()
    client = app.test_client()

    response = client.post("/api/validate", json={"content": "name('x')"})
    payload = response.get_json()

    assert payload["valid"] is False
    assert payload["errors"][0]["message"] == "bad"


def test_validate_stream_success(monkeypatch, tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    file_path = workspace / "proc.tac"
    file_path.write_text("name('x')")

    class DummyValidator:
        def validate(self, _content):
            return SimpleNamespace(valid=True, errors=[], warnings=[])

    monkeypatch.setattr(ide_server, "WORKSPACE_ROOT", str(workspace))
    monkeypatch.setattr(ide_server, "TactusValidator", DummyValidator)

    app = ide_server.create_app()
    client = app.test_client()

    response = client.get("/api/validate/stream", query_string={"path": "proc.tac"})
    body = response.get_data(as_text=True)

    assert "validation" in body
    assert "data:" in body
