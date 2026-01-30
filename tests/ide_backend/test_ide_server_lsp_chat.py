from tactus.ide import server as ide_server


def test_chat_tools_and_reset(monkeypatch):
    class DummyAssistant:
        def __init__(self, *_args, **_kwargs):
            self.reset_called = False

        def get_available_tools(self):
            return ["tool"]

        def reset_conversation(self):
            self.reset_called = True

    class DummyConfigManager:
        def _load_from_environment(self):
            return {}

        def _get_user_config_paths(self):
            return []

        def _deep_merge(self, base, _other):
            return base

    monkeypatch.setattr("tactus.ide.coding_assistant.CodingAssistantAgent", DummyAssistant)
    monkeypatch.setattr("tactus.core.config_manager.ConfigManager", DummyConfigManager)
    monkeypatch.setattr(ide_server, "WORKSPACE_ROOT", "/tmp/workspace")
    app = ide_server.create_app()
    client = app.test_client()

    tools_resp = client.get("/api/chat/tools")
    assert tools_resp.status_code == 200
    assert tools_resp.get_json()["tools"] == ["tool"]

    reset_resp = client.post("/api/chat/reset")
    assert reset_resp.status_code == 200
    assert reset_resp.get_json()["success"] is True


def test_chat_message_success(monkeypatch):
    class DummyAssistant:
        def __init__(self, *_args, **_kwargs):
            pass

        def process_message(self, message):
            return {"response": f"echo:{message}", "tool_calls": []}

    class DummyConfigManager:
        def _load_from_environment(self):
            return {}

        def _get_user_config_paths(self):
            return []

        def _deep_merge(self, base, _other):
            return base

    monkeypatch.setattr("tactus.ide.coding_assistant.CodingAssistantAgent", DummyAssistant)
    monkeypatch.setattr("tactus.core.config_manager.ConfigManager", DummyConfigManager)
    monkeypatch.setattr(ide_server, "WORKSPACE_ROOT", "/tmp/workspace")

    app = ide_server.create_app()
    client = app.test_client()

    response = client.post("/api/chat", json={"message": "hi"})

    assert response.status_code == 200
    assert response.get_json()["response"] == "echo:hi"


def test_chat_message_requires_workspace(monkeypatch):
    monkeypatch.setattr(ide_server, "WORKSPACE_ROOT", None)
    app = ide_server.create_app()
    client = app.test_client()

    response = client.post("/api/chat", json={"message": "hi"})

    assert response.status_code == 400
    assert "workspace" in response.get_json()["error"].lower()


def test_chat_tools_requires_assistant(monkeypatch):
    monkeypatch.setattr(ide_server, "WORKSPACE_ROOT", None)
    app = ide_server.create_app()
    client = app.test_client()

    response = client.get("/api/chat/tools")

    assert response.status_code == 400
    assert "Assistant not initialized" in response.get_json()["error"]


def test_lsp_request_returns_result(monkeypatch):
    class DummyLsp:
        def handle_message(self, _message):
            return {"jsonrpc": "2.0", "id": 1, "result": {"ok": True}}

    monkeypatch.setattr(ide_server, "LSPServer", lambda: DummyLsp())
    app = ide_server.create_app()
    client = app.test_client()

    response = client.post("/api/lsp", json={"id": 1, "method": "initialize"})

    assert response.status_code == 200
    assert response.get_json()["result"]["ok"] is True


def test_lsp_notification_returns_diagnostics(monkeypatch):
    class DummyHandler:
        def validate_document(self, _uri, _text):
            return [{"message": "bad"}]

        def close_document(self, _uri):
            return None

    class DummyLsp:
        def __init__(self):
            self.handler = DummyHandler()

    monkeypatch.setattr(ide_server, "LSPServer", lambda: DummyLsp())
    app = ide_server.create_app()
    client = app.test_client()

    response = client.post(
        "/api/lsp/notification",
        json={
            "method": "textDocument/didOpen",
            "params": {"textDocument": {"uri": "u", "text": "x"}},
        },
    )

    assert response.status_code == 200
    assert response.get_json()["diagnostics"][0]["message"] == "bad"
