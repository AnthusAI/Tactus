import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from tactus.core.registry import ValidationMessage
from tactus.ide import server as ide_server


def test_clear_runtime_caches_warns_when_unset(caplog):
    ide_server._clear_runtime_caches_fn = None
    ide_server.clear_runtime_caches()
    assert any(
        "clear_runtime_caches called but no implementation set" in msg for msg in caplog.messages
    )


def test_clear_runtime_caches_calls_callback():
    called = []

    def _clear():
        called.append(True)

    ide_server._clear_runtime_caches_fn = _clear
    ide_server.clear_runtime_caches()
    assert called == [True]


def test_resolve_workspace_path_errors(tmp_path, monkeypatch):
    monkeypatch.setattr(ide_server, "WORKSPACE_ROOT", None)
    with pytest.raises(ValueError, match="No workspace folder selected"):
        ide_server._resolve_workspace_path("file.tac")

    monkeypatch.setattr(ide_server, "WORKSPACE_ROOT", str(tmp_path))
    with pytest.raises(ValueError, match="escapes workspace"):
        ide_server._resolve_workspace_path("../outside.tac")


def test_lsp_handler_validates_and_tracks_registry():
    handler = ide_server.TactusLSPHandler()

    errors = [ValidationMessage(level="error", message="bad", location=(2, 3))]
    warnings = [ValidationMessage(level="warning", message="warn", location=None)]
    result = SimpleNamespace(errors=errors, warnings=warnings, registry={"ok": True})

    class FakeValidator:
        def validate(self, text, mode):
            return result

    handler.validator = FakeValidator()
    diagnostics = handler.validate_document("file://test", "text")
    assert len(diagnostics) == 2
    assert handler.registries["file://test"] == {"ok": True}
    assert diagnostics[0]["range"]["start"]["line"] == 1


def test_lsp_handler_skips_missing_registry_and_diagnostics():
    handler = ide_server.TactusLSPHandler()

    result = SimpleNamespace(
        errors=[ValidationMessage(level="error", message="bad", location=None)],
        warnings=[],
        registry=None,
    )

    class FakeValidator:
        def validate(self, text, mode):
            return result

    handler.validator = FakeValidator()
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(handler, "_convert_to_diagnostic", lambda *_args, **_kwargs: None)
    diagnostics = handler.validate_document("file://test", "text")
    monkeypatch.undo()

    assert diagnostics == []
    assert "file://test" not in handler.registries


def test_lsp_handler_skips_warning_diagnostic():
    handler = ide_server.TactusLSPHandler()

    warnings = [ValidationMessage(level="warning", message="warn", location=None)]
    result = SimpleNamespace(errors=[], warnings=warnings, registry=None)

    class FakeValidator:
        def validate(self, text, mode):
            return result

    handler.validator = FakeValidator()
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(handler, "_convert_to_diagnostic", lambda *_args, **_kwargs: None)
    diagnostics = handler.validate_document("file://warn", "text")
    monkeypatch.undo()

    assert diagnostics == []


def test_lsp_handler_handles_validation_exception(caplog):
    handler = ide_server.TactusLSPHandler()

    class ErrorValidator:
        def validate(self, text, mode):
            raise RuntimeError("boom")

    handler.validator = ErrorValidator()
    diagnostics = handler.validate_document("file://test", "text")
    assert diagnostics == []
    assert any("Error validating document" in msg for msg in caplog.messages)


def test_lsp_server_initialize_and_unknown_method():
    server = ide_server.LSPServer()
    response = server.handle_message({"id": 1, "method": "initialize", "params": {}})
    assert response["result"]["serverInfo"]["name"] == "tactus-lsp-server"
    assert server.initialized is True

    error_response = server.handle_message({"id": 2, "method": "unknown", "params": {}})
    assert error_response["error"]["code"] == -32601


def test_basic_workspace_and_file_endpoints(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    sample = workspace / "sample.tac"
    sample.write_text("hello")

    app = ide_server.create_app(initial_workspace=str(workspace))
    client = app.test_client()

    response = client.get("/health")
    assert response.get_json()["status"] == "ok"

    response = client.get("/api/workspace")
    assert response.get_json()["root"] == str(workspace)

    response = client.get("/api/tree")
    data = response.get_json()
    assert any(entry["name"] == "sample.tac" for entry in data["entries"])

    response = client.get("/api/file", query_string={"path": "sample.tac"})
    payload = response.get_json()
    assert payload["content"] == "hello"

    response = client.post("/api/file", json={"path": "new/file.tac", "content": "new"})
    assert response.get_json()["success"] is True
    assert (workspace / "new" / "file.tac").read_text() == "new"

    response = client.get("/api/file")
    assert response.status_code == 400


def test_file_post_missing_and_write_error(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    app = ide_server.create_app(initial_workspace=str(workspace))
    client = app.test_client()

    response = client.post("/api/file", json={"path": "sample.tac"})
    assert response.status_code == 400

    def _write_text(_self, _content):
        raise RuntimeError("boom")

    monkeypatch.setattr(ide_server.Path, "write_text", _write_text)
    response = client.post("/api/file", json={"path": "sample.tac", "content": "data"})
    assert response.status_code == 500


def test_workspace_cwd_and_about(tmp_path):
    app = ide_server.create_app(initial_workspace=str(tmp_path))
    client = app.test_client()

    response = client.get("/api/workspace/cwd")
    assert response.get_json()["cwd"] == str(tmp_path)

    response = client.get("/api/about")
    payload = response.get_json()
    assert payload["name"] == "Tactus IDE"
    assert "version" in payload


def test_workspace_get_no_root(monkeypatch):
    monkeypatch.setattr(ide_server, "WORKSPACE_ROOT", None)
    app = ide_server.create_app()
    client = app.test_client()

    response = client.get("/api/workspace")
    assert response.get_json()["root"] is None


def test_workspace_post_errors(tmp_path, monkeypatch):
    app = ide_server.create_app(initial_workspace=str(tmp_path))
    client = app.test_client()

    response = client.post("/api/workspace", json={})
    assert response.status_code == 400

    response = client.post("/api/workspace", json={"root": str(tmp_path / "missing")})
    assert response.status_code == 404

    file_path = tmp_path / "file.txt"
    file_path.write_text("ok")
    response = client.post("/api/workspace", json={"root": str(file_path)})
    assert response.status_code == 400

    monkeypatch.setattr(
        ide_server.os, "chdir", lambda _path: (_ for _ in ()).throw(RuntimeError("boom"))
    )
    response = client.post("/api/workspace", json={"root": str(tmp_path)})
    assert response.status_code == 500


def test_workspace_post_success(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    original_cwd = Path.cwd()
    app = ide_server.create_app()
    client = app.test_client()

    try:
        response = client.post("/api/workspace", json={"root": str(workspace)})
        payload = response.get_json()
        assert payload["success"] is True
        assert payload["name"] == "workspace"
    finally:
        os.chdir(original_cwd)


def test_validate_endpoints(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    file_path = workspace / "sample.tac"
    file_path.write_text("content")

    class FakeValidator:
        def validate(self, content, mode=None):
            return SimpleNamespace(valid=True, errors=[], warnings=[])

    monkeypatch.setattr(ide_server, "TactusValidator", FakeValidator)

    app = ide_server.create_app(initial_workspace=str(workspace))
    client = app.test_client()

    response = client.post("/api/validate", json={"content": "content"})
    assert response.get_json()["valid"] is True

    response = client.get("/api/validate/stream", query_string={"path": "sample.tac"})
    assert response.mimetype == "text/event-stream"


def test_procedure_metadata_success(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    file_path = workspace / "sample.tac"
    file_path.write_text("content")

    class FakeAgent:
        def __init__(self, name):
            self.name = name
            self.provider = "openai"
            self.model = "gpt-4o"
            self.system_prompt = "prompt"
            self.tools = ["done"]

    registry = SimpleNamespace(
        description="desc",
        input_schema={"task": {"type": "string"}},
        output_schema={"result": {"type": "string"}},
        agents={"agent": FakeAgent("agent")},
        toolsets={"default": {"tools": ["search"]}},
        gherkin_specifications="Feature: Demo\nScenario: First",
        pydantic_evaluations={"dataset": [1, 2], "evaluators": ["a"], "runs": 2},
        lua_tools={"custom_tool": {}},
    )

    class FakeValidator:
        def validate_file(self, path, mode):
            return SimpleNamespace(errors=[], registry=registry)

    monkeypatch.setattr(ide_server, "TactusValidator", FakeValidator)

    app = ide_server.create_app(initial_workspace=str(workspace))
    client = app.test_client()

    response = client.get("/api/procedure/metadata", query_string={"path": "sample.tac"})
    payload = response.get_json()
    assert payload["success"] is True
    assert payload["metadata"]["description"] == "desc"
    assert payload["metadata"]["specifications"]["scenario_count"] == 1
    assert "custom_tool" in payload["metadata"]["tools"]


def test_procedure_metadata_toolsets_and_evals_variants(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    file_path = workspace / "sample.tac"
    file_path.write_text("content")

    class FakeAgent:
        def __init__(self, name):
            self.name = name
            self.provider = "openai"
            self.model = "gpt-4o"
            self.system_prompt = "prompt"
            self.tools = []

    registry = SimpleNamespace(
        description=None,
        input_schema=None,
        output_schema=None,
        agents={"agent": FakeAgent("agent")},
        toolsets={"default": "not-a-dict"},
        gherkin_specifications=None,
        pydantic_evaluations=["not-a-dict"],
        lua_tools=None,
    )

    class FakeValidator:
        def validate_file(self, path, mode):
            return SimpleNamespace(errors=[], registry=registry)

    monkeypatch.setattr(ide_server, "TactusValidator", FakeValidator)

    app = ide_server.create_app(initial_workspace=str(workspace))
    client = app.test_client()

    response = client.get("/api/procedure/metadata", query_string={"path": "sample.tac"})
    payload = response.get_json()
    assert payload["success"] is True
    assert payload["metadata"]["specifications"] is None
    assert payload["metadata"]["evaluations"]["runs"] == 1


def test_procedure_metadata_evaluations_counts(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    file_path = workspace / "sample.tac"
    file_path.write_text("content")

    class FakeAgent:
        def __init__(self, name):
            self.name = name
            self.provider = "openai"
            self.model = "gpt-4o"
            self.system_prompt = "prompt"
            self.tools = ["done"]

    registry = SimpleNamespace(
        description="desc",
        input_schema={},
        output_schema={},
        agents={"agent": FakeAgent("agent")},
        toolsets={"default": {"tools": ["search"]}, "empty": {}},
        gherkin_specifications="Feature: Demo\nScenario: A",
        pydantic_evaluations={
            "dataset": [{"x": 1}],
            "evaluators": ["a", "b"],
            "runs": 3,
            "parallel": True,
        },
        lua_tools={},
    )

    class FakeValidator:
        def validate_file(self, path, mode):
            return SimpleNamespace(errors=[], registry=registry)

    monkeypatch.setattr(ide_server, "TactusValidator", FakeValidator)

    app = ide_server.create_app(initial_workspace=str(workspace))
    client = app.test_client()

    response = client.get("/api/procedure/metadata", query_string={"path": "sample.tac"})
    payload = response.get_json()
    assert payload["metadata"]["evaluations"]["dataset_count"] == 1
    assert payload["metadata"]["evaluations"]["evaluator_count"] == 2


def test_procedure_metadata_missing_registry(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    file_path = workspace / "sample.tac"
    file_path.write_text("content")

    class FakeValidator:
        def validate_file(self, path, mode):
            return SimpleNamespace(
                errors=[ValidationMessage(level="error", message="bad", location=(1, 2))],
                registry=None,
            )

    monkeypatch.setattr(ide_server, "TactusValidator", FakeValidator)

    app = ide_server.create_app(initial_workspace=str(workspace))
    client = app.test_client()

    response = client.get("/api/procedure/metadata", query_string={"path": "sample.tac"})
    assert response.status_code == 400
    payload = response.get_json()
    assert payload["success"] is False
    assert payload["validation_errors"][0]["line"] == 1


def test_lsp_request_and_notifications(monkeypatch):
    class FakeHandler:
        def __init__(self):
            self.closed = []

        def validate_document(self, uri, text):
            return [{"message": "ok"}]

        def close_document(self, uri):
            self.closed.append(uri)

    class FakeLSPServer:
        def __init__(self):
            self.handler = FakeHandler()

        def handle_message(self, message):
            return {"jsonrpc": "2.0", "id": message.get("id"), "result": {"ok": True}}

    monkeypatch.setattr(ide_server, "LSPServer", FakeLSPServer)

    app = ide_server.create_app()
    client = app.test_client()

    response = client.post("/api/lsp", json={"id": 1, "method": "initialize", "params": {}})
    assert response.get_json()["result"]["ok"] is True

    response = client.post(
        "/api/lsp/notification",
        json={
            "method": "textDocument/didOpen",
            "params": {"textDocument": {"uri": "file://a", "text": "x"}},
        },
    )
    assert response.get_json()["diagnostics"][0]["message"] == "ok"

    response = client.post(
        "/api/lsp/notification",
        json={
            "method": "textDocument/didChange",
            "params": {"textDocument": {"uri": "file://a"}, "contentChanges": [{"text": "y"}]},
        },
    )
    assert response.get_json()["diagnostics"][0]["message"] == "ok"

    response = client.post(
        "/api/lsp/notification",
        json={"method": "textDocument/didClose", "params": {"textDocument": {"uri": "file://a"}}},
    )
    assert response.get_json()["status"] == "ok"


def test_chat_endpoints(monkeypatch, tmp_path):
    created = {}

    class FakeAssistant:
        def __init__(self, workspace_root, config):
            self.reset_called = False
            created["instance"] = self

        def process_message(self, message):
            return {"response": f"echo:{message}", "tool_calls": ["tool"]}

        def reset_conversation(self):
            self.reset_called = True

        def get_available_tools(self):
            return ["tool"]

    monkeypatch.setattr("tactus.ide.coding_assistant.CodingAssistantAgent", FakeAssistant)

    app = ide_server.create_app(initial_workspace=str(tmp_path))
    client = app.test_client()

    response = client.post("/api/chat", json={})
    assert response.status_code == 400

    response = client.post("/api/chat", json={"message": "hi"})
    payload = response.get_json()
    assert payload["success"] is True
    assert payload["response"] == "echo:hi"

    response = client.post("/api/chat/reset", json={})
    assert response.get_json()["success"] is True
    assert created["instance"].reset_called is True

    response = client.get("/api/chat/tools")
    assert response.get_json()["tools"] == ["tool"]


def test_chat_requires_workspace(monkeypatch):
    monkeypatch.setattr(ide_server, "WORKSPACE_ROOT", None)

    app = ide_server.create_app()
    client = app.test_client()

    response = client.post("/api/chat", json={"message": "hi"})
    assert response.status_code == 400


def test_trace_endpoints(tmp_path, monkeypatch):
    from datetime import datetime, timezone

    from tactus.protocols.models import CheckpointEntry, ProcedureMetadata

    now = datetime.now(timezone.utc)
    metadata = ProcedureMetadata(procedure_id="proc")
    metadata.state = {"ok": True}
    metadata.execution_log = [
        CheckpointEntry(position=0, type="agent_turn", result="a", timestamp=now, run_id="run-1"),
        CheckpointEntry(
            position=1, type="model_predict", result="b", timestamp=now, run_id="run-1"
        ),
        CheckpointEntry(position=0, type="agent_turn", result="c", timestamp=now, run_id="run-2"),
    ]

    class FakeFileStorage:
        def __init__(self, storage_dir):
            self.storage_dir = storage_dir

        def load_procedure_metadata(self, procedure_id):
            return metadata

    monkeypatch.setattr("tactus.adapters.file_storage.FileStorage", FakeFileStorage)

    storage_dir = tmp_path / ".tac" / "storage"
    events_dir = storage_dir / "events"
    events_dir.mkdir(parents=True)
    (events_dir / "run-1.json").write_text('[{"event": "ok"}]')

    app = ide_server.create_app(initial_workspace=str(tmp_path))
    client = app.test_client()

    response = client.get("/api/traces/runs", query_string={"procedure": "proc", "limit": 10})
    runs = response.get_json()["runs"]
    assert len(runs) == 2

    response = client.get("/api/traces/runs/run-1", query_string={"procedure": "proc"})
    assert response.get_json()["run_id"] == "run-1"

    response = client.get("/api/traces/runs/run-1/checkpoints", query_string={"procedure": "proc"})
    assert len(response.get_json()["checkpoints"]) == 2

    response = client.get(
        "/api/traces/runs/run-1/checkpoints/1", query_string={"procedure": "proc"}
    )
    assert response.get_json()["position"] == 1

    response = client.get("/api/traces/runs/run-1/statistics", query_string={"procedure": "proc"})
    assert response.get_json()["total_checkpoints"] == 2

    response = client.get("/api/traces/runs/run-1/events")
    assert response.get_json()["events"][0]["event"] == "ok"


def test_run_procedure_endpoint(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    file_path = workspace / "run.tac"
    file_path.write_text("content")

    class FakeCompleted:
        returncode = 0
        stdout = "ok"
        stderr = ""

    monkeypatch.setattr(ide_server.subprocess, "run", lambda *args, **kwargs: FakeCompleted())

    app = ide_server.create_app(initial_workspace=str(workspace))
    client = app.test_client()

    response = client.post("/api/run", json={"path": "run.tac"})
    payload = response.get_json()
    assert payload["success"] is True


def test_run_procedure_stream_input_errors(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    app = ide_server.create_app(initial_workspace=str(workspace))
    client = app.test_client()

    response = client.get("/api/run/stream", query_string={"inputs": "{bad"})
    assert response.status_code == 400


def test_workspace_post_validation(tmp_path):
    app = ide_server.create_app()
    client = app.test_client()

    response = client.post("/api/workspace", json={})
    assert response.status_code == 400

    response = client.post("/api/workspace", json={"root": str(tmp_path / "missing")})
    assert response.status_code == 404

    file_path = tmp_path / "not_dir.txt"
    file_path.write_text("x")
    response = client.post("/api/workspace", json={"root": str(file_path)})
    assert response.status_code == 400
