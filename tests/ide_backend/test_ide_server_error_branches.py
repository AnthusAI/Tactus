from pathlib import Path
from types import SimpleNamespace

from tactus.ide import server as ide_server


def test_lsp_validate_document_records_registry_and_warnings():
    handler = ide_server.TactusLSPHandler()

    class FakeValidator:
        def validate(self, _text, _mode):
            return SimpleNamespace(
                registry={"ok": True},
                errors=[SimpleNamespace(message="bad", location=(1, 1))],
                warnings=[SimpleNamespace(message="warn", location=(2, 1))],
            )

    handler.validator = FakeValidator()

    diagnostics = handler.validate_document("file://demo", "content")
    assert handler.registries["file://demo"] == {"ok": True}
    assert len(diagnostics) == 2


def test_lsp_validate_document_handles_exception():
    handler = ide_server.TactusLSPHandler()

    class FakeValidator:
        def validate(self, _text, _mode):
            raise RuntimeError("boom")

    handler.validator = FakeValidator()
    diagnostics = handler.validate_document("file://demo", "content")
    assert diagnostics == []


def test_tree_path_not_found_and_not_dir(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    file_path = workspace / "file.txt"
    file_path.write_text("data")

    monkeypatch.setattr(ide_server, "WORKSPACE_ROOT", str(workspace))
    app = ide_server.create_app()
    client = app.test_client()

    response = client.get("/api/tree", query_string={"path": "missing"})
    assert response.status_code == 404

    response = client.get("/api/tree", query_string={"path": "file.txt"})
    assert response.status_code == 400


def test_tree_operations_handles_exception(tmp_path, monkeypatch):
    monkeypatch.setattr(ide_server, "WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setattr(ide_server, "_resolve_workspace_path", lambda _path: (_ for _ in ()).throw(RuntimeError("boom")))
    app = ide_server.create_app()
    client = app.test_client()

    response = client.get("/api/tree")
    assert response.status_code == 500


def test_tree_operations_handles_value_error(tmp_path, monkeypatch):
    monkeypatch.setattr(ide_server, "WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setattr(ide_server, "_resolve_workspace_path", lambda _path: (_ for _ in ()).throw(ValueError("bad")))
    app = ide_server.create_app()
    client = app.test_client()

    response = client.get("/api/tree")
    assert response.status_code == 400


def test_file_operations_missing_params(tmp_path, monkeypatch):
    monkeypatch.setattr(ide_server, "WORKSPACE_ROOT", str(tmp_path))
    app = ide_server.create_app()
    client = app.test_client()

    response = client.get("/api/file")
    assert response.status_code == 400

    response = client.post("/api/file", json={"path": "file.txt"})
    assert response.status_code == 400


def test_file_operations_read_error(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    file_path = workspace / "file.txt"
    file_path.write_text("data")

    monkeypatch.setattr(ide_server, "WORKSPACE_ROOT", str(workspace))
    monkeypatch.setattr(Path, "read_text", lambda _self: (_ for _ in ()).throw(RuntimeError("boom")))
    app = ide_server.create_app()
    client = app.test_client()

    response = client.get("/api/file", query_string={"path": "file.txt"})
    assert response.status_code == 500


def test_file_operations_write_error(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    monkeypatch.setattr(ide_server, "WORKSPACE_ROOT", str(workspace))
    monkeypatch.setattr(Path, "write_text", lambda _self, _content: (_ for _ in ()).throw(RuntimeError("boom")))
    app = ide_server.create_app()
    client = app.test_client()

    response = client.post("/api/file", json={"path": "file.txt", "content": "data"})
    assert response.status_code == 500


def test_file_operations_write_value_error(tmp_path, monkeypatch):
    monkeypatch.setattr(ide_server, "WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setattr(ide_server, "_resolve_workspace_path", lambda _path: (_ for _ in ()).throw(ValueError("bad")))
    app = ide_server.create_app()
    client = app.test_client()

    response = client.post("/api/file", json={"path": "file.txt", "content": "data"})
    assert response.status_code == 400


def test_workspace_post_handles_exception(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    monkeypatch.setattr(ide_server.os, "chdir", lambda _path: (_ for _ in ()).throw(RuntimeError("boom")))
    app = ide_server.create_app()
    client = app.test_client()

    response = client.post("/api/workspace", json={"root": str(workspace)})
    assert response.status_code == 500


def test_run_procedure_without_workspace_returns_error(monkeypatch):
    monkeypatch.setattr(ide_server, "WORKSPACE_ROOT", None)
    app = ide_server.create_app()
    client = app.test_client()

    response = client.post("/api/run", json={"path": "demo.tac"})
    assert response.status_code == 400


def test_chat_message_handles_exception(monkeypatch):
    class DummyAssistant:
        def __init__(self, *_args, **_kwargs):
            pass

        def process_message(self, _message):
            raise RuntimeError("boom")

    class DummyConfigManager:
        def _load_from_environment(self):
            return {}

        def _get_user_config_paths(self):
            return []

        def _deep_merge(self, base, _other):
            return base

    monkeypatch.setattr(ide_server, "WORKSPACE_ROOT", "/tmp/workspace")
    monkeypatch.setattr("tactus.ide.coding_assistant.CodingAssistantAgent", DummyAssistant)
    monkeypatch.setattr("tactus.core.config_manager.ConfigManager", DummyConfigManager)

    app = ide_server.create_app()
    client = app.test_client()

    response = client.post("/api/chat", json={"message": "hi"})
    assert response.status_code == 500


def test_validate_requires_content():
    app = ide_server.create_app()
    client = app.test_client()

    response = client.post("/api/validate", json={})
    assert response.status_code == 400


def test_validate_handles_exception(monkeypatch):
    class DummyValidator:
        def validate(self, _content):
            raise RuntimeError("boom")

    monkeypatch.setattr(ide_server, "TactusValidator", DummyValidator)
    app = ide_server.create_app()
    client = app.test_client()

    response = client.post("/api/validate", json={"content": "demo"})
    assert response.status_code == 500


def test_validate_stream_missing_file(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.setattr(ide_server, "WORKSPACE_ROOT", str(workspace))

    app = ide_server.create_app()
    client = app.test_client()

    response = client.get("/api/validate/stream", query_string={"path": "missing.tac"})
    assert response.status_code == 404


def test_validate_stream_emits_error_event(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    file_path = workspace / "proc.tac"
    file_path.write_text("content")

    class DummyValidator:
        def validate(self, _content):
            raise RuntimeError("boom")

    monkeypatch.setattr(ide_server, "WORKSPACE_ROOT", str(workspace))
    monkeypatch.setattr(ide_server, "TactusValidator", DummyValidator)

    app = ide_server.create_app()
    client = app.test_client()

    response = client.get("/api/validate/stream", query_string={"path": "proc.tac"})
    data = response.get_data(as_text=True)

    assert "\"lifecycle_stage\": \"error\"" in data


def test_validate_stream_handles_value_error(tmp_path, monkeypatch):
    monkeypatch.setattr(ide_server, "WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setattr(ide_server, "_resolve_workspace_path", lambda _path: (_ for _ in ()).throw(ValueError("bad")))

    app = ide_server.create_app()
    client = app.test_client()

    response = client.get("/api/validate/stream", query_string={"path": "proc.tac"})
    assert response.status_code == 400


def test_validate_stream_handles_exception(tmp_path, monkeypatch):
    monkeypatch.setattr(ide_server, "WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setattr(ide_server, "_resolve_workspace_path", lambda _path: (_ for _ in ()).throw(RuntimeError("boom")))

    app = ide_server.create_app()
    client = app.test_client()

    response = client.get("/api/validate/stream", query_string={"path": "proc.tac"})
    assert response.status_code == 500


def test_run_procedure_missing_file(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.setattr(ide_server, "WORKSPACE_ROOT", str(workspace))

    app = ide_server.create_app()
    client = app.test_client()

    response = client.post("/api/run", json={"path": "missing.tac"})
    assert response.status_code == 404


def test_run_procedure_missing_path(tmp_path, monkeypatch):
    monkeypatch.setattr(ide_server, "WORKSPACE_ROOT", str(tmp_path))
    app = ide_server.create_app()
    client = app.test_client()

    response = client.post("/api/run", json={})
    assert response.status_code == 400


def test_run_procedure_handles_exception(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    file_path = workspace / "proc.tac"
    file_path.write_text("content")

    monkeypatch.setattr(ide_server, "WORKSPACE_ROOT", str(workspace))
    monkeypatch.setattr(ide_server.subprocess, "run", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("boom")))

    app = ide_server.create_app()
    client = app.test_client()

    response = client.post("/api/run", json={"path": "proc.tac"})
    assert response.status_code == 500


def test_run_procedure_writes_content(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    class FakeCompleted:
        returncode = 0
        stdout = "ok"
        stderr = ""

    monkeypatch.setattr(ide_server, "WORKSPACE_ROOT", str(workspace))
    monkeypatch.setattr(ide_server.subprocess, "run", lambda *args, **kwargs: FakeCompleted())

    app = ide_server.create_app()
    client = app.test_client()

    response = client.post("/api/run", json={"path": "proc.tac", "content": "data"})
    assert response.status_code == 200
    assert (workspace / "proc.tac").read_text() == "data"


def test_procedure_metadata_file_not_found(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.setattr(ide_server, "WORKSPACE_ROOT", str(workspace))

    app = ide_server.create_app()
    client = app.test_client()

    response = client.get("/api/procedure/metadata", query_string={"path": "missing.tac"})
    assert response.status_code == 404


def test_procedure_metadata_handles_exception(tmp_path, monkeypatch):
    monkeypatch.setattr(ide_server, "WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setattr(ide_server, "_resolve_workspace_path", lambda _path: (_ for _ in ()).throw(RuntimeError("boom")))
    app = ide_server.create_app()
    client = app.test_client()

    response = client.get("/api/procedure/metadata", query_string={"path": "proc.tac"})
    assert response.status_code == 500


def test_list_trace_runs_handles_exception(monkeypatch, tmp_path):
    class DummyStorage:
        def __init__(self, storage_dir):
            self.storage_dir = storage_dir

        def load_procedure_metadata(self, _procedure):
            raise RuntimeError("boom")

    monkeypatch.setattr("tactus.adapters.file_storage.FileStorage", DummyStorage)
    monkeypatch.setattr(ide_server, "WORKSPACE_ROOT", str(tmp_path))

    app = ide_server.create_app()
    client = app.test_client()

    response = client.get("/api/traces/runs", query_string={"procedure": "proc"})
    assert response.status_code == 500
