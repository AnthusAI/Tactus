import subprocess

from tactus.ide import server as ide_server


def test_workspace_post_success_sets_root(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    recorded = {}

    def fake_chdir(path):
        recorded["cwd"] = path

    monkeypatch.setattr(ide_server, "WORKSPACE_ROOT", None)
    monkeypatch.setattr(ide_server.os, "chdir", fake_chdir)

    app = ide_server.create_app()
    client = app.test_client()

    response = client.post("/api/workspace", json={"root": str(workspace)})
    payload = response.get_json()

    assert payload["success"] is True
    assert payload["root"] == str(workspace)
    assert recorded["cwd"] == str(workspace)


def test_tree_requires_workspace(tmp_path, monkeypatch):
    monkeypatch.setattr(ide_server, "WORKSPACE_ROOT", None)
    app = ide_server.create_app()
    client = app.test_client()

    response = client.get("/api/tree")
    assert response.status_code == 400
    assert "no workspace" in response.get_json()["error"].lower()


def test_file_read_path_escape(tmp_path, monkeypatch):
    monkeypatch.setattr(ide_server, "WORKSPACE_ROOT", str(tmp_path))
    app = ide_server.create_app()
    client = app.test_client()

    response = client.get("/api/file", query_string={"path": "../outside.tac"})
    assert response.status_code == 400
    assert "escapes workspace" in response.get_json()["error"].lower()


def test_validate_stream_requires_path():
    app = ide_server.create_app()
    client = app.test_client()

    response = client.get("/api/validate/stream")
    assert response.status_code == 400
    assert "missing 'path'" in response.get_json()["error"].lower()


def test_run_procedure_timeout(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    file_path = workspace / "run.tac"
    file_path.write_text("content")

    def raise_timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=kwargs.get("args", ["tactus"]), timeout=30)

    monkeypatch.setattr(ide_server.subprocess, "run", raise_timeout)

    app = ide_server.create_app(initial_workspace=str(workspace))
    client = app.test_client()

    response = client.post("/api/run", json={"path": "run.tac"})
    assert response.status_code == 408


def test_run_stream_requires_path(tmp_path):
    app = ide_server.create_app(initial_workspace=str(tmp_path))
    client = app.test_client()

    response = client.get("/api/run/stream")
    assert response.status_code == 400
    assert "missing 'path'" in response.get_json()["error"].lower()


def test_run_stream_missing_file(tmp_path):
    app = ide_server.create_app(initial_workspace=str(tmp_path))
    client = app.test_client()

    response = client.get("/api/run/stream", query_string={"path": "missing.tac"})
    assert response.status_code == 404
    assert "file not found" in response.get_json()["error"].lower()
