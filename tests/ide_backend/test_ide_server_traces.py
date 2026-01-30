from datetime import datetime, timezone
from types import SimpleNamespace

from tactus.ide import server as ide_server


def test_list_trace_runs_empty_without_procedure(monkeypatch):
    app = ide_server.create_app()
    client = app.test_client()

    response = client.get("/api/traces/runs")

    assert response.status_code == 200
    assert response.get_json()["runs"] == []


def test_list_trace_runs_groups_by_run_id(monkeypatch, tmp_path):
    checkpoints = [
        SimpleNamespace(run_id="run1", position=1, timestamp=datetime.now(timezone.utc)),
        SimpleNamespace(run_id="run1", position=2, timestamp=datetime.now(timezone.utc)),
        SimpleNamespace(run_id="run2", position=1, timestamp=datetime.now(timezone.utc)),
    ]
    metadata = SimpleNamespace(execution_log=checkpoints)

    class DummyStorage:
        def __init__(self, storage_dir):
            self.storage_dir = storage_dir

        def load_procedure_metadata(self, _procedure):
            return metadata

    monkeypatch.setattr("tactus.adapters.file_storage.FileStorage", DummyStorage)
    monkeypatch.setattr(ide_server, "WORKSPACE_ROOT", str(tmp_path))

    app = ide_server.create_app()
    client = app.test_client()

    response = client.get("/api/traces/runs", query_string={"procedure": "proc"})
    payload = response.get_json()

    assert response.status_code == 200
    assert len(payload["runs"]) == 2


def test_get_trace_run_requires_procedure():
    app = ide_server.create_app()
    client = app.test_client()

    response = client.get("/api/traces/runs/run1")

    assert response.status_code == 400


def test_get_trace_run_not_found(monkeypatch, tmp_path):
    metadata = SimpleNamespace(execution_log=[])

    class DummyStorage:
        def __init__(self, storage_dir):
            self.storage_dir = storage_dir

        def load_procedure_metadata(self, _procedure):
            return metadata

    monkeypatch.setattr("tactus.adapters.file_storage.FileStorage", DummyStorage)
    monkeypatch.setattr(ide_server, "WORKSPACE_ROOT", str(tmp_path))

    app = ide_server.create_app()
    client = app.test_client()

    response = client.get("/api/traces/runs/run1", query_string={"procedure": "proc"})

    assert response.status_code == 404


def test_get_run_checkpoints(monkeypatch, tmp_path):
    checkpoint = SimpleNamespace(
        run_id="run1",
        position=1,
        type="agent_turn",
        timestamp=datetime.now(timezone.utc),
        source_location=SimpleNamespace(file="file.tac", line=2),
    )
    metadata = SimpleNamespace(execution_log=[checkpoint])

    class DummyStorage:
        def __init__(self, storage_dir):
            self.storage_dir = storage_dir

        def load_procedure_metadata(self, _procedure):
            return metadata

    monkeypatch.setattr("tactus.adapters.file_storage.FileStorage", DummyStorage)
    monkeypatch.setattr(ide_server, "WORKSPACE_ROOT", str(tmp_path))

    app = ide_server.create_app()
    client = app.test_client()

    response = client.get("/api/traces/runs/run1/checkpoints", query_string={"procedure": "proc"})

    assert response.status_code == 200
    assert response.get_json()["checkpoints"][0]["name"] == "agent_turn"


def test_get_checkpoint_not_found(monkeypatch, tmp_path):
    metadata = SimpleNamespace(execution_log=[])

    class DummyStorage:
        def __init__(self, storage_dir):
            self.storage_dir = storage_dir

        def load_procedure_metadata(self, _procedure):
            return metadata

    monkeypatch.setattr("tactus.adapters.file_storage.FileStorage", DummyStorage)
    monkeypatch.setattr(ide_server, "WORKSPACE_ROOT", str(tmp_path))

    app = ide_server.create_app()
    client = app.test_client()

    response = client.get("/api/traces/runs/run1/checkpoints/1", query_string={"procedure": "proc"})

    assert response.status_code == 404


def test_clear_checkpoints_removes_file(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    storage_dir = workspace / ".tac" / "storage"
    storage_dir.mkdir(parents=True)
    checkpoint_file = storage_dir / "proc.json"
    checkpoint_file.write_text("{}")

    monkeypatch.setattr(ide_server, "WORKSPACE_ROOT", str(workspace))
    app = ide_server.create_app()
    client = app.test_client()

    response = client.delete("/api/procedures/proc/checkpoints")

    assert response.status_code == 200
    assert not checkpoint_file.exists()


def test_get_run_statistics(monkeypatch, tmp_path):
    checkpoint = SimpleNamespace(
        run_id="run1",
        position=1,
        type="agent_turn",
        duration_ms=100,
        timestamp=datetime.now(timezone.utc),
        source_location=SimpleNamespace(file="file.tac", line=2),
    )
    metadata = SimpleNamespace(execution_log=[checkpoint])

    class DummyStorage:
        def __init__(self, storage_dir):
            self.storage_dir = storage_dir

        def load_procedure_metadata(self, _procedure):
            return metadata

    monkeypatch.setattr("tactus.adapters.file_storage.FileStorage", DummyStorage)
    monkeypatch.setattr(ide_server, "WORKSPACE_ROOT", str(tmp_path))

    app = ide_server.create_app()
    client = app.test_client()

    response = client.get("/api/traces/runs/run1/statistics", query_string={"procedure": "proc"})

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["total_duration_ms"] == 100
