from pathlib import Path

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


def test_workspace_post_missing_root(monkeypatch):
    monkeypatch.setattr(ide_server, "WORKSPACE_ROOT", None)
    app = ide_server.create_app()
    client = app.test_client()

    response = client.post("/api/workspace", json={})
    assert response.status_code == 400


def test_workspace_get_returns_root(monkeypatch, tmp_path):
    monkeypatch.setattr(ide_server, "WORKSPACE_ROOT", str(tmp_path))
    app = ide_server.create_app()
    client = app.test_client()

    response = client.get("/api/workspace")
    payload = response.get_json()
    assert payload["root"] == str(tmp_path)


def test_workspace_get_without_root(monkeypatch):
    monkeypatch.setattr(ide_server, "WORKSPACE_ROOT", None)
    app = ide_server.create_app()
    client = app.test_client()

    response = client.get("/api/workspace")
    payload = response.get_json()
    assert payload["root"] is None


def test_workspace_post_sets_root(monkeypatch, tmp_path):
    import os

    monkeypatch.setattr(ide_server, "WORKSPACE_ROOT", None)
    app = ide_server.create_app()
    client = app.test_client()

    original_cwd = os.getcwd()
    response = client.post("/api/workspace", json={"root": str(tmp_path)})
    assert response.status_code == 200
    assert response.get_json()["root"] == str(tmp_path)
    os.chdir(original_cwd)


def test_file_post_missing_fields(monkeypatch, tmp_path):
    monkeypatch.setattr(ide_server, "WORKSPACE_ROOT", str(tmp_path))
    app = ide_server.create_app()
    client = app.test_client()

    response = client.post("/api/file", json={"path": "demo.txt"})
    assert response.status_code == 400


def test_file_post_writes_content(monkeypatch, tmp_path):
    monkeypatch.setattr(ide_server, "WORKSPACE_ROOT", str(tmp_path))
    app = ide_server.create_app()
    client = app.test_client()

    response = client.post("/api/file", json={"path": "demo.txt", "content": "hi"})
    assert response.status_code == 200
    assert (tmp_path / "demo.txt").read_text() == "hi"


def test_file_get_reads_content(monkeypatch, tmp_path):
    (tmp_path / "demo.txt").write_text("hello")
    monkeypatch.setattr(ide_server, "WORKSPACE_ROOT", str(tmp_path))
    app = ide_server.create_app()
    client = app.test_client()

    response = client.get("/api/file", query_string={"path": "demo.txt"})
    payload = response.get_json()
    assert payload["content"] == "hello"


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
        json={
            "method": "textDocument/didClose",
            "params": {"textDocument": {"uri": "file://demo"}},
        },
    )
    assert response.status_code == 200
    assert captured["closed"] == "file://demo"


def test_lsp_notification_did_open_missing_text(monkeypatch):
    class DummyHandler:
        def validate_document(self, _uri, _text):
            raise AssertionError("should not be called")

        def close_document(self, _uri):
            return None

    class DummyServer:
        def __init__(self):
            self.handler = DummyHandler()

    monkeypatch.setattr(ide_server, "LSPServer", lambda: DummyServer())
    app = ide_server.create_app()
    client = app.test_client()

    response = client.post(
        "/api/lsp/notification",
        json={"method": "textDocument/didOpen", "params": {"textDocument": {"uri": "file://demo"}}},
    )
    assert response.status_code == 200


def test_lsp_notification_did_change_missing_changes(monkeypatch):
    class DummyHandler:
        def validate_document(self, _uri, _text):
            raise AssertionError("should not be called")

        def close_document(self, _uri):
            return None

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
            "params": {"textDocument": {"uri": "file://demo"}, "contentChanges": []},
        },
    )
    assert response.status_code == 200


def test_lsp_notification_did_change_missing_text(monkeypatch):
    class DummyHandler:
        def validate_document(self, _uri, _text):
            raise AssertionError("should not be called")

        def close_document(self, _uri):
            return None

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
                "contentChanges": [{"text": None}],
            },
        },
    )
    assert response.status_code == 200


def test_lsp_notification_did_close_missing_uri(monkeypatch):
    class DummyHandler:
        def validate_document(self, _uri, _text):
            return []

        def close_document(self, _uri):
            raise AssertionError("should not be called")

    class DummyServer:
        def __init__(self):
            self.handler = DummyHandler()

    monkeypatch.setattr(ide_server, "LSPServer", lambda: DummyServer())
    app = ide_server.create_app()
    client = app.test_client()

    response = client.post(
        "/api/lsp/notification",
        json={"method": "textDocument/didClose", "params": {"textDocument": {}}},
    )
    assert response.status_code == 200


def test_lsp_notification_returns_diagnostics(monkeypatch):
    class DummyHandler:
        def validate_document(self, _uri, _text):
            return [{"message": "bad"}]

        def close_document(self, _uri):
            return None

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

    payload = response.get_json()
    assert payload["diagnostics"][0]["message"] == "bad"


def test_hitl_stream_emits_connection_event(monkeypatch):
    class FakeChannel:
        async def get_next_event(self):
            return None

    monkeypatch.setattr("tactus.adapters.channels.sse.SSEControlChannel", FakeChannel)
    app = ide_server.create_app()
    client = app.test_client()

    response = client.get("/api/hitl/stream")
    first_chunk = next(response.response).decode("utf-8")
    second_chunk = next(response.response).decode("utf-8")
    assert '"type": "connection"' in first_chunk
    assert ": keepalive" in second_chunk


def test_hitl_stream_keepalive_sleeps(monkeypatch):
    class FakeChannel:
        async def get_next_event(self):
            return None

    slept = {}

    def fake_sleep(seconds):
        slept["seconds"] = seconds

    monkeypatch.setattr("tactus.adapters.channels.sse.SSEControlChannel", FakeChannel)
    monkeypatch.setattr(ide_server.time, "sleep", fake_sleep)
    app = ide_server.create_app()
    client = app.test_client()

    response = client.get("/api/hitl/stream")
    _ = next(response.response)
    _ = next(response.response)
    try:
        _ = next(response.response)
    except StopIteration:
        pass

    assert slept["seconds"] == 1


def test_hitl_stream_emits_event(monkeypatch):
    class FakeChannel:
        def __init__(self):
            self._sent = False

        async def get_next_event(self):
            if not self._sent:
                self._sent = True
                return {"type": "hitl.request"}
            return None

    monkeypatch.setattr("tactus.adapters.channels.sse.SSEControlChannel", FakeChannel)
    app = ide_server.create_app()
    client = app.test_client()

    response = client.get("/api/hitl/stream")
    _ = next(response.response)
    event_chunk = next(response.response).decode("utf-8")
    assert '"type": "hitl.request"' in event_chunk


def test_hitl_stream_handles_exception(monkeypatch):
    class FakeChannel:
        async def get_next_event(self):
            raise RuntimeError("boom")

    monkeypatch.setattr("tactus.adapters.channels.sse.SSEControlChannel", FakeChannel)
    app = ide_server.create_app()
    client = app.test_client()

    response = client.get("/api/hitl/stream")
    _ = next(response.response)
    try:
        next(response.response)
    except StopIteration:
        pass


def test_hitl_response_pending_request(monkeypatch):
    event_flag = {"set": False}

    class FakeEvent:
        def set(self):
            event_flag["set"] = True

    pending = {
        "response": {"value": None, "timed_out": True, "channel_id": None},
        "event": FakeEvent(),
    }

    app = ide_server.create_app()
    client = app.test_client()

    pending_requests = None
    hitl_response = app.view_functions["hitl_response"]
    for cell in hitl_response.__closure__ or []:
        if isinstance(cell.cell_contents, dict):
            pending_requests = cell.cell_contents
            break

    pending_requests["req-1"] = pending

    response = client.post("/api/hitl/response/req-1", json={"value": "ok"})
    payload = response.get_json()

    assert payload["status"] == "ok"
    assert pending["response"]["value"] == "ok"
    assert pending["response"]["timed_out"] is False
    assert pending["response"]["channel_id"] == "sse"
    assert event_flag["set"] is True

    pending_requests.clear()


def test_hitl_response_handles_exception(monkeypatch):
    app = ide_server.create_app()
    client = app.test_client()

    pending_requests = None
    hitl_response = app.view_functions["hitl_response"]
    for cell in hitl_response.__closure__ or []:
        if isinstance(cell.cell_contents, dict):
            pending_requests = cell.cell_contents
            break

    pending_requests["req-2"] = {"response": {}, "event": None}

    response = client.post("/api/hitl/response/req-2", json={"value": "ok"})
    assert response.status_code == 400


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


def test_chat_tools_merges_user_config(monkeypatch, tmp_path):
    config_path = tmp_path / "config.yml"
    config_path.write_text("ok")

    class DummyAssistant:
        def __init__(self, _root, config):
            self.config = config

        def get_available_tools(self):
            return []

    class DummyConfigManager:
        def _load_from_environment(self):
            return {"base": True}

        def _get_user_config_paths(self):
            return [config_path]

        def _load_yaml_file(self, _path):
            return {"user": True}

        def _deep_merge(self, base, other):
            base.update(other)
            return base

    monkeypatch.setattr(ide_server, "WORKSPACE_ROOT", "/tmp/workspace")
    monkeypatch.setattr("tactus.ide.coding_assistant.CodingAssistantAgent", DummyAssistant)
    monkeypatch.setattr("tactus.core.config_manager.ConfigManager", DummyConfigManager)

    app = ide_server.create_app()
    client = app.test_client()

    response = client.get("/api/chat/tools")
    assert response.status_code == 200


def test_chat_reset_handles_exception(monkeypatch):
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

    response = client.post("/api/chat/reset")
    assert response.status_code == 500
    assert "boom" in response.get_json()["error"]


def test_chat_stream_emits_error_event(monkeypatch):
    import sys
    from types import SimpleNamespace

    class FakeService:
        def __init__(self, *_args, **_kwargs):
            pass

        async def start_conversation(self, _conversation_id):
            raise RuntimeError("boom")

        async def send_message(self, _message):
            yield {"type": "message", "content": "ok"}

    sys.modules["assistant_service"] = SimpleNamespace(AssistantService=FakeService)

    monkeypatch.setattr(ide_server, "WORKSPACE_ROOT", "/tmp/workspace")
    app = ide_server.create_app()
    client = app.test_client()

    response = client.post(
        "/api/chat/stream",
        json={"workspace_root": "/tmp/workspace", "message": "hi"},
    )
    chunk = next(response.response).decode("utf-8")
    assert '"type": "error"' in chunk


def test_chat_stream_import_error(monkeypatch):
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "assistant_service":
            raise ImportError("boom")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    monkeypatch.setattr(ide_server, "WORKSPACE_ROOT", "/tmp/workspace")
    app = ide_server.create_app()
    client = app.test_client()

    response = client.post(
        "/api/chat/stream",
        json={"workspace_root": "/tmp/workspace", "message": "hi"},
    )
    assert response.status_code == 500


def test_clear_runtime_caches_clears_assistant(monkeypatch):
    class DummyAssistant:
        def __init__(self, *_args, **_kwargs):
            pass

        def get_available_tools(self):
            return []

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

    response = client.get("/api/chat/tools")
    assert response.status_code == 200

    ide_server.clear_runtime_caches()


def test_chat_tools_user_config_empty(monkeypatch, tmp_path):
    class DummyAssistant:
        def __init__(self, *_args, **_kwargs):
            pass

        def get_available_tools(self):
            return []

    class DummyConfigManager:
        def __init__(self):
            self.merges = 0

        def _load_from_environment(self):
            return {}

        def _get_user_config_paths(self):
            return [tmp_path / "config.yml"]

        def _load_yaml_file(self, _path):
            return {}

        def _deep_merge(self, base, _other):
            self.merges += 1
            return base

    config_manager = DummyConfigManager()

    monkeypatch.setattr(ide_server, "WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setattr("tactus.ide.coding_assistant.CodingAssistantAgent", DummyAssistant)
    monkeypatch.setattr("tactus.core.config_manager.ConfigManager", lambda: config_manager)

    app = ide_server.create_app()
    client = app.test_client()

    response = client.get("/api/chat/tools")
    assert response.status_code == 200


def test_chat_tools_user_config_merges(monkeypatch, tmp_path):
    class DummyAssistant:
        def __init__(self, *_args, **_kwargs):
            pass

        def get_available_tools(self):
            return []

    class DummyConfigManager:
        def __init__(self):
            self.merges = 0

        def _load_from_environment(self):
            return {"base": True}

        def _get_user_config_paths(self):
            return [tmp_path / "config.yml"]

        def _load_yaml_file(self, _path):
            return {"user": True}

        def _deep_merge(self, base, _other):
            self.merges += 1
            base.update(_other)
            return base

    config_manager = DummyConfigManager()

    (tmp_path / "config.yml").write_text("user: true")

    monkeypatch.setattr(ide_server, "WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setattr("tactus.ide.coding_assistant.CodingAssistantAgent", DummyAssistant)
    monkeypatch.setattr("tactus.core.config_manager.ConfigManager", lambda: config_manager)

    app = ide_server.create_app()
    client = app.test_client()

    response = client.get("/api/chat/tools")
    assert response.status_code == 200
    assert config_manager.merges == 1


def test_chat_assistant_skips_empty_user_config_and_clears_cache(monkeypatch, tmp_path):
    monkeypatch.setattr(ide_server, "WORKSPACE_ROOT", str(tmp_path))

    merge_calls = {"count": 0}

    class DummyAssistant:
        def __init__(self, _root, _config):
            self.calls = 0

        def process_message(self, _message):
            return {"response": "ok"}

    class DummyConfigManager:
        def _load_from_environment(self):
            return {}

        def _get_user_config_paths(self):
            return [tmp_path / "user.yml"]

        def _load_yaml_file(self, _path):
            return {}

        def _deep_merge(self, _base, _over):
            merge_calls["count"] += 1
            return _base

    monkeypatch.setattr("tactus.ide.coding_assistant.CodingAssistantAgent", DummyAssistant)
    monkeypatch.setattr("tactus.core.config_manager.ConfigManager", DummyConfigManager)

    app = ide_server.create_app(initial_workspace=str(tmp_path))
    client = app.test_client()

    response = client.post("/api/chat", json={"message": "hi"})
    assert response.status_code == 200

    assert merge_calls["count"] == 0
    ide_server._clear_runtime_caches_fn()


def test_chat_assistant_user_config_exists_but_empty(monkeypatch, tmp_path):
    monkeypatch.setattr(ide_server, "WORKSPACE_ROOT", str(tmp_path))

    merge_calls = {"count": 0}

    class DummyAssistant:
        def __init__(self, _root, _config):
            pass

        def process_message(self, _message):
            return {"response": "ok"}

    class DummyConfigManager:
        def _load_from_environment(self):
            return {"base": True}

        def _get_user_config_paths(self):
            return [tmp_path / "user.yml"]

        def _load_yaml_file(self, _path):
            return {}

        def _deep_merge(self, _base, _over):
            merge_calls["count"] += 1
            return {"merged": True}

    (tmp_path / "user.yml").write_text("empty: true")

    monkeypatch.setattr("tactus.ide.coding_assistant.CodingAssistantAgent", DummyAssistant)
    monkeypatch.setattr("tactus.core.config_manager.ConfigManager", DummyConfigManager)

    app = ide_server.create_app(initial_workspace=str(tmp_path))
    client = app.test_client()

    response = client.post("/api/chat", json={"message": "hi"})
    assert response.status_code == 200
    assert merge_calls["count"] == 0
    ide_server._clear_runtime_caches_fn()


def test_lsp_notification_unknown_method_returns_ok(monkeypatch):
    class DummyHandler:
        def validate_document(self, _uri, _text):
            raise AssertionError("should not be called")

        def close_document(self, _uri):
            raise AssertionError("should not be called")

    class DummyServer:
        def __init__(self):
            self.handler = DummyHandler()

    monkeypatch.setattr(ide_server, "LSPServer", lambda: DummyServer())
    app = ide_server.create_app()
    client = app.test_client()

    response = client.post(
        "/api/lsp/notification",
        json={"method": "workspace/unknown", "params": {}},
    )
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


def test_clear_runtime_caches_no_assistant(monkeypatch, tmp_path):
    class DummyAssistant:
        def __init__(self, _root, _config):
            pass

        def process_message(self, _message):
            return {"response": "ok"}

    class DummyConfigManager:
        def _load_from_environment(self):
            return {}

        def _get_user_config_paths(self):
            return []

        def _load_yaml_file(self, _path):
            return {}

        def _deep_merge(self, base, _other):
            return base

    monkeypatch.setattr(ide_server, "WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setattr("tactus.ide.coding_assistant.CodingAssistantAgent", DummyAssistant)
    monkeypatch.setattr("tactus.core.config_manager.ConfigManager", DummyConfigManager)
    app = ide_server.create_app(initial_workspace=str(tmp_path))
    client = app.test_client()

    response = client.post("/api/chat", json={"message": "hi"})
    assert response.status_code == 200

    ide_server._clear_runtime_caches_fn()
    ide_server._clear_runtime_caches_fn()


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

    with app.test_request_context("/app.js"):
        response = app.view_functions["serve_static_or_frontend"]("app.js")
        response.direct_passthrough = False
        assert "console.log" in response.get_data(as_text=True)

    with app.test_request_context("/api/unknown"):
        response = app.view_functions["serve_static_or_frontend"]("api/unknown")
        assert response[1] == 404


def test_main_sets_initial_workspace(monkeypatch, tmp_path):
    captured = {}

    class DummyApp:
        def run(self, **_kwargs):
            captured["ran"] = True

    def fake_create_app(*_args, **kwargs):
        captured["initial_workspace"] = kwargs.get("initial_workspace")
        return DummyApp()

    monkeypatch.setenv("TACTUS_IDE_WORKSPACE", str(tmp_path))
    monkeypatch.setenv("TACTUS_IDE_PORT", "5001")
    monkeypatch.setattr(ide_server, "create_app", fake_create_app)

    ide_server.main()

    assert captured["initial_workspace"] == str(tmp_path)


def test_main_without_workspace_env(monkeypatch):
    class DummyApp:
        def __init__(self):
            self.called = None

        def run(self, host=None, port=None, debug=None, threaded=None, use_reloader=None):
            self.called = {
                "host": host,
                "port": port,
                "debug": debug,
                "threaded": threaded,
                "use_reloader": use_reloader,
            }

    dummy_app = DummyApp()

    monkeypatch.delenv("TACTUS_IDE_WORKSPACE", raising=False)
    monkeypatch.setenv("TACTUS_IDE_PORT", "5001")
    monkeypatch.setattr(ide_server, "create_app", lambda initial_workspace=None: dummy_app)

    ide_server.main()

    assert dummy_app.called["port"] == 5001


def test_workspace_operations_unsupported_method():
    app = ide_server.create_app()
    with app.test_request_context("/api/workspace", method="PUT"):
        response = app.view_functions["workspace_operations"]()
        assert response is None


def test_file_operations_unsupported_method(tmp_path, monkeypatch):
    monkeypatch.setattr(ide_server, "WORKSPACE_ROOT", str(tmp_path))
    app = ide_server.create_app()
    with app.test_request_context("/api/file", method="PUT"):
        response = app.view_functions["file_operations"]()
        assert response is None


def test_main_uses_env_configuration(monkeypatch):
    class DummyApp:
        def __init__(self):
            self.called = None

        def run(self, host=None, port=None, debug=None, threaded=None, use_reloader=None):
            self.called = {
                "host": host,
                "port": port,
                "debug": debug,
                "threaded": threaded,
                "use_reloader": use_reloader,
            }

    dummy_app = DummyApp()

    monkeypatch.setenv("TACTUS_IDE_HOST", "0.0.0.0")
    monkeypatch.setenv("TACTUS_IDE_PORT", "5050")
    monkeypatch.setenv("TACTUS_IDE_WORKSPACE", "/tmp/workspace")
    monkeypatch.setattr(ide_server, "create_app", lambda initial_workspace=None: dummy_app)

    ide_server.main()
    assert dummy_app.called["host"] == "0.0.0.0"
    assert dummy_app.called["port"] == 5050


def test_main_invalid_port_raises(monkeypatch):
    monkeypatch.setenv("TACTUS_IDE_PORT", "bad")
    monkeypatch.setattr(ide_server, "create_app", lambda initial_workspace=None: None)

    try:
        ide_server.main()
    except SystemExit as exc:
        assert "Invalid TACTUS_IDE_PORT" in str(exc)
