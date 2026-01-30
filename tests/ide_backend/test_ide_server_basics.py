import tactus
from tactus.ide import server as ide_server


def test_health_endpoint():
    app = ide_server.create_app()
    client = app.test_client()

    response = client.get("/health")

    assert response.status_code == 200
    assert response.get_json()["status"] == "ok"


def test_about_endpoint_includes_version():
    app = ide_server.create_app()
    client = app.test_client()

    response = client.get("/api/about")
    payload = response.get_json()

    assert payload["version"] == tactus.__version__
    assert payload["name"] == "Tactus IDE"


def test_clear_runtime_caches_calls_callback(monkeypatch):
    called = {}

    def fake_clear():
        called["ok"] = True

    monkeypatch.setattr(ide_server, "_clear_runtime_caches_fn", fake_clear)

    ide_server.clear_runtime_caches()

    assert called["ok"] is True


def test_clear_runtime_caches_warns_without_callback(monkeypatch, caplog):
    monkeypatch.setattr(ide_server, "_clear_runtime_caches_fn", None)

    with caplog.at_level("WARNING"):
        ide_server.clear_runtime_caches()

    assert "clear_runtime_caches called" in caplog.text


def test_workspace_get_empty_returns_none(monkeypatch):
    monkeypatch.setattr(ide_server, "WORKSPACE_ROOT", None)
    app = ide_server.create_app()
    client = app.test_client()

    response = client.get("/api/workspace")
    payload = response.get_json()

    assert payload["root"] is None
    assert payload["name"] is None


def test_workspace_post_missing_root():
    app = ide_server.create_app()
    client = app.test_client()

    response = client.post("/api/workspace", json={})

    assert response.status_code == 400
    assert "missing" in response.get_json()["error"].lower()


def test_workspace_post_invalid_path(tmp_path):
    app = ide_server.create_app()
    client = app.test_client()

    response = client.post("/api/workspace", json={"root": str(tmp_path / "missing")})

    assert response.status_code == 404


def test_workspace_post_rejects_file(tmp_path):
    file_path = tmp_path / "file.txt"
    file_path.write_text("data")
    app = ide_server.create_app()
    client = app.test_client()

    response = client.post("/api/workspace", json={"root": str(file_path)})

    assert response.status_code == 400
    assert "directory" in response.get_json()["error"].lower()


def test_tree_and_file_operations(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "folder").mkdir()
    (workspace / "file.txt").write_text("hello")

    monkeypatch.setattr(ide_server, "WORKSPACE_ROOT", str(workspace))
    app = ide_server.create_app()
    client = app.test_client()

    tree = client.get("/api/tree")
    assert tree.status_code == 200
    assert tree.get_json()["entries"]

    missing = client.get("/api/file", query_string={"path": "missing.txt"})
    assert missing.status_code == 404

    not_file = client.get("/api/file", query_string={"path": "folder"})
    assert not_file.status_code == 400

    file_resp = client.get("/api/file", query_string={"path": "file.txt"})
    assert file_resp.status_code == 200
    assert file_resp.get_json()["content"] == "hello"

    write_resp = client.post("/api/file", json={"path": "new.txt", "content": "new"})
    assert write_resp.status_code == 200
    assert (workspace / "new.txt").read_text() == "new"
