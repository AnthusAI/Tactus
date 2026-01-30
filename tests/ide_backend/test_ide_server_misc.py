import json
from pathlib import Path
from types import SimpleNamespace

from tactus.ide import server as ide_server


def test_workspace_cwd_uses_workspace_root(monkeypatch, tmp_path):
    monkeypatch.setattr(ide_server, "WORKSPACE_ROOT", str(tmp_path))
    app = ide_server.create_app()
    client = app.test_client()

    response = client.get("/api/workspace/cwd")
    assert response.get_json()["cwd"] == str(tmp_path)


def test_workspace_cwd_defaults_to_current_dir(monkeypatch, tmp_path):
    monkeypatch.setattr(ide_server, "WORKSPACE_ROOT", None)
    monkeypatch.setattr(Path, "cwd", lambda: tmp_path)
    app = ide_server.create_app()
    client = app.test_client()

    response = client.get("/api/workspace/cwd")
    assert response.get_json()["cwd"] == str(tmp_path)


def test_lsp_notification_did_change_and_close(monkeypatch):
    captured = {"changed": None, "closed": None}

    class DummyHandler:
        def validate_document(self, uri, text):
            captured["changed"] = (uri, text)
            return []

        def close_document(self, uri):
            captured["closed"] = uri

    class DummyServer:
        def __init__(self):
            self.handler = DummyHandler()

    monkeypatch.setattr(ide_server, "LSPServer", lambda: DummyServer())
    app = ide_server.create_app()
    client = app.test_client()

    response = client.post(
        "/api/lsp/notification",
        json={
            "method": "textDocument/didChange",
            "params": {
                "textDocument": {"uri": "file://demo"},
                "contentChanges": [{"text": "updated"}],
            },
        },
    )
    assert response.status_code == 200
    assert captured["changed"] == ("file://demo", "updated")

    response = client.post(
        "/api/lsp/notification",
        json={"method": "textDocument/didClose", "params": {"textDocument": {"uri": "file://demo"}}},
    )
    assert response.status_code == 200
    assert captured["closed"] == "file://demo"


def test_hitl_stream_emits_connection_event(monkeypatch):
    class FakeChannel:
        async def get_next_event(self):
            return None

    monkeypatch.setattr("tactus.adapters.channels.sse.SSEControlChannel", FakeChannel)
    app = ide_server.create_app()
    client = app.test_client()

    response = client.get("/api/hitl/stream")
    chunk = next(response.response).decode("utf-8")
    assert "\"type\": \"connection\"" in chunk


def test_chat_reset_without_assistant(monkeypatch):
    monkeypatch.setattr(ide_server, "WORKSPACE_ROOT", None)
    app = ide_server.create_app()
    client = app.test_client()

    response = client.post("/api/chat/reset")
    assert response.status_code == 400
    assert "Assistant not initialized" in response.get_json()["error"]


def test_chat_message_requires_message(monkeypatch):
    monkeypatch.setattr(ide_server, "WORKSPACE_ROOT", "/tmp/workspace")
    app = ide_server.create_app()
    client = app.test_client()

    response = client.post("/api/chat", json={})
    assert response.status_code == 400
    assert "missing 'message'" in response.get_json()["error"].lower()


def test_chat_tools_handles_exception(monkeypatch):
    class BoomAssistant:
        def __init__(self, *_args, **_kwargs):
            raise RuntimeError("boom")

    class DummyConfigManager:
        def _load_from_environment(self):
            return {}

        def _get_user_config_paths(self):
            return []

        def _deep_merge(self, base, _other):
            return base

    monkeypatch.setattr(ide_server, "WORKSPACE_ROOT", "/tmp/workspace")
    monkeypatch.setattr("tactus.ide.coding_assistant.CodingAssistantAgent", BoomAssistant)
    monkeypatch.setattr("tactus.core.config_manager.ConfigManager", DummyConfigManager)

    app = ide_server.create_app()
    client = app.test_client()

    response = client.get("/api/chat/tools")
    assert response.status_code == 500
    assert "boom" in response.get_json()["error"]


def test_run_events_not_found(monkeypatch, tmp_path):
    monkeypatch.setattr(ide_server, "WORKSPACE_ROOT", str(tmp_path))
    app = ide_server.create_app()
    client = app.test_client()

    response = client.get("/api/traces/runs/unknown/events")
    assert response.status_code == 404


def test_frontend_static_serving(tmp_path):
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir()
    (dist_dir / "index.html").write_text("index")
    (dist_dir / "app.js").write_text("console.log('ok')")

    app = ide_server.create_app(frontend_dist_dir=str(dist_dir))
    client = app.test_client()

    root_response = client.get("/")
    assert root_response.get_data(as_text=True) == "index"

    asset_response = client.get("/app.js")
    assert "console.log" in asset_response.get_data(as_text=True)

    with app.test_request_context("/route"):
        response = app.view_functions["serve_static_or_frontend"]("route")
        response.direct_passthrough = False
        assert response.get_data(as_text=True) == "index"

    with app.test_request_context("/api/unknown"):
        response = app.view_functions["serve_static_or_frontend"]("api/unknown")
        assert response[1] == 404
