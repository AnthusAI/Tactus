"""Tests for IDE chat server routes."""

import sys
from pathlib import Path

from flask import Flask
import pytest

backend_path = Path(__file__).resolve().parents[2] / "tactus-ide" / "backend"
sys.path.insert(0, str(backend_path))

import chat_server  # noqa: E402


class FakeService:
    def __init__(self):
        self.started = False
        self.cleared = False

    async def start_conversation(self, conversation_id):
        self.started = True
        return {"conversation_id": conversation_id, "status": "active"}

    async def send_message(self, message):
        yield {"type": "message", "content": f"echo:{message}", "role": "assistant"}
        yield {"type": "done"}

    async def get_history(self, conversation_id):
        return [{"role": "user", "content": "hi"}]

    async def resume_conversation(self, conversation_id):
        return {"conversation_id": conversation_id, "status": "resumed", "history": []}

    async def clear_conversation(self, conversation_id):
        self.cleared = True


class ErrorService(FakeService):
    async def send_message(self, message):
        raise RuntimeError("send failed")
        if False:
            yield  # pragma: no cover

    async def get_history(self, conversation_id):
        raise RuntimeError("history failed")

    async def resume_conversation(self, conversation_id):
        raise RuntimeError("resume failed")

    async def clear_conversation(self, conversation_id):
        raise RuntimeError("clear failed")


class StartErrorService(FakeService):
    async def start_conversation(self, conversation_id):
        raise RuntimeError("start failed")


@pytest.fixture
def client():
    app = Flask(__name__)
    chat_server.register_chat_routes(app)
    return app.test_client()


@pytest.fixture(autouse=True)
def clear_conversations():
    chat_server.conversations.clear()
    yield
    chat_server.conversations.clear()


def test_get_or_create_service_returns_assistant_service(monkeypatch):
    sentinel = object()

    monkeypatch.setattr(chat_server, "AssistantService", lambda workspace_root, config: sentinel)

    assert chat_server.get_or_create_service("/tmp", {}) is sentinel


def test_test_endpoint(client):
    response = client.get("/api/chat/test")

    assert response.status_code == 200
    assert response.get_json()["status"] == "ok"


def test_start_conversation_requires_workspace_root(client):
    response = client.post("/api/chat/start", json={})

    assert response.status_code == 400


def test_start_conversation_success(client, monkeypatch):
    service = FakeService()
    monkeypatch.setattr(
        chat_server, "get_or_create_service", lambda workspace_root, config: service
    )
    monkeypatch.setattr(chat_server.uuid, "uuid4", lambda: "fixed-id")

    response = client.post("/api/chat/start", json={"workspace_root": "/tmp", "config": {}})

    assert response.status_code == 200
    assert response.get_json()["conversation_id"] == "fixed-id"
    assert "fixed-id" in chat_server.conversations


def test_start_conversation_error_returns_500(client, monkeypatch):
    monkeypatch.setattr(
        chat_server, "get_or_create_service", lambda workspace_root, config: StartErrorService()
    )

    response = client.post("/api/chat/start", json={"workspace_root": "/tmp", "config": {}})

    assert response.status_code == 500


def test_send_message_requires_fields(client):
    response = client.post("/api/chat/message", json={})

    assert response.status_code == 400


def test_send_message_not_found(client):
    response = client.post(
        "/api/chat/message", json={"conversation_id": "missing", "message": "hi"}
    )

    assert response.status_code == 404


def test_send_message_success(client):
    chat_server.conversations["conv-1"] = FakeService()

    response = client.post("/api/chat/message", json={"conversation_id": "conv-1", "message": "hi"})

    assert response.status_code == 200
    events = response.get_json()["events"]
    assert events[0]["content"] == "echo:hi"


def test_send_message_error_returns_500(client):
    chat_server.conversations["conv-1"] = ErrorService()

    response = client.post("/api/chat/message", json={"conversation_id": "conv-1", "message": "hi"})

    assert response.status_code == 500


def test_stream_message_requires_fields(client):
    response = client.post("/api/chat/stream", json={})

    assert response.status_code == 400


def test_stream_message_success(client, monkeypatch):
    service = FakeService()
    monkeypatch.setattr(
        chat_server, "get_or_create_service", lambda workspace_root, config: service
    )
    monkeypatch.setattr(chat_server.uuid, "uuid4", lambda: "stream-id")

    response = client.post(
        "/api/chat/stream",
        json={"workspace_root": "/tmp", "message": "hi", "config": {}},
    )

    body = response.get_data(as_text=True)
    assert "type" in body
    assert "thinking" in body
    assert "echo:hi" in body


def test_stream_message_generator_error_returns_error_event(client, monkeypatch):
    service = StartErrorService()
    monkeypatch.setattr(
        chat_server, "get_or_create_service", lambda workspace_root, config: service
    )

    response = client.post(
        "/api/chat/stream",
        json={"workspace_root": "/tmp", "message": "hi", "config": {}},
    )

    body = response.get_data(as_text=True)
    assert "error" in body
    assert "start failed" in body


def test_stream_message_outer_error_returns_500(client, monkeypatch):
    monkeypatch.setattr(
        chat_server.uuid, "uuid4", lambda: (_ for _ in ()).throw(RuntimeError("boom"))
    )

    response = client.post(
        "/api/chat/stream",
        json={"workspace_root": "/tmp", "message": "hi", "config": {}},
    )

    assert response.status_code == 500


def test_get_history_not_found(client):
    response = client.get("/api/chat/history/missing")

    assert response.status_code == 404


def test_get_history_success(client):
    chat_server.conversations["conv-1"] = FakeService()

    response = client.get("/api/chat/history/conv-1")

    assert response.status_code == 200
    assert response.get_json()["history"]


def test_get_history_error_returns_500(client):
    chat_server.conversations["conv-1"] = ErrorService()

    response = client.get("/api/chat/history/conv-1")

    assert response.status_code == 500


def test_resume_requires_workspace_root(client):
    response = client.post("/api/chat/resume/conv-1", json={})

    assert response.status_code == 400


def test_resume_success(client, monkeypatch):
    service = FakeService()
    monkeypatch.setattr(
        chat_server, "get_or_create_service", lambda workspace_root, config: service
    )

    response = client.post("/api/chat/resume/conv-1", json={"workspace_root": "/tmp"})

    assert response.status_code == 200
    assert response.get_json()["status"] == "resumed"
    assert "conv-1" in chat_server.conversations


def test_resume_error_returns_500(client, monkeypatch):
    service = ErrorService()
    monkeypatch.setattr(
        chat_server, "get_or_create_service", lambda workspace_root, config: service
    )

    response = client.post("/api/chat/resume/conv-1", json={"workspace_root": "/tmp"})

    assert response.status_code == 500


def test_clear_not_found(client):
    response = client.delete("/api/chat/missing")

    assert response.status_code == 404


def test_clear_success(client):
    chat_server.conversations["conv-1"] = FakeService()

    response = client.delete("/api/chat/conv-1")

    assert response.status_code == 200
    assert "conv-1" not in chat_server.conversations


def test_clear_error_returns_500(client):
    chat_server.conversations["conv-1"] = ErrorService()

    response = client.delete("/api/chat/conv-1")

    assert response.status_code == 500


def test_register_chat_routes_error_raises(monkeypatch):
    class BadApp:
        def register_blueprint(self, bp):
            raise RuntimeError("nope")

    with pytest.raises(RuntimeError):
        chat_server.register_chat_routes(BadApp())
