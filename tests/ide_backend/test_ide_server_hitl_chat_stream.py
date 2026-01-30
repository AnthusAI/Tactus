import sys
from types import SimpleNamespace

from tactus.ide import server as ide_server


def test_hitl_response_routes_to_channel(monkeypatch, tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    captured = {}

    class FakeChannel:
        def handle_ide_response(self, request_id, value):
            captured["request_id"] = request_id
            captured["value"] = value

    monkeypatch.setattr("tactus.adapters.channels.sse.SSEControlChannel", FakeChannel)

    app = ide_server.create_app(initial_workspace=str(workspace))
    client = app.test_client()

    response = client.post("/api/hitl/response/req-1", json={"value": "ok"})
    assert response.get_json()["status"] == "ok"
    assert captured == {"request_id": "req-1", "value": "ok"}


def test_chat_stream_requires_message(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    app = ide_server.create_app(initial_workspace=str(workspace))
    client = app.test_client()

    response = client.post("/api/chat/stream", json={})
    assert response.status_code == 400
    assert "workspace_root and message required" in response.get_json()["error"]


def test_chat_stream_emits_events(monkeypatch, tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    class FakeAssistantService:
        def __init__(self, workspace_root, config):
            self.workspace_root = workspace_root
            self.config = config

        async def start_conversation(self, conversation_id):
            return None

        async def send_message(self, message):
            yield {"type": "message", "content": "ok"}

    fake_module = SimpleNamespace(AssistantService=FakeAssistantService)
    monkeypatch.setitem(sys.modules, "assistant_service", fake_module)

    app = ide_server.create_app(initial_workspace=str(workspace))
    client = app.test_client()

    response = client.post(
        "/api/chat/stream",
        json={"workspace_root": str(workspace), "message": "hi"},
    )
    data = response.data.decode("utf-8")
    assert "ok" in data
