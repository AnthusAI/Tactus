"""BDD steps for IDE chat API."""

import sys
from pathlib import Path
from unittest import mock

from behave import given, when, then
from flask import Flask

project_root = Path(__file__).resolve().parents[2]
backend_path = project_root / "tactus-ide" / "backend"
sys.path.insert(0, str(backend_path))

import chat_server  # noqa: E402


class FakeService:
    def __init__(self, workspace_root, config):
        self.workspace_root = workspace_root
        self.config = config
        self.history = []

    async def start_conversation(self, conversation_id):
        return {
            "conversation_id": conversation_id,
            "workspace_root": self.workspace_root,
            "status": "active",
        }

    async def send_message(self, message):
        self.history.append({"role": "user", "content": message})
        yield {"type": "message", "content": "ok", "role": "assistant"}
        self.history.append({"role": "assistant", "content": "ok"})
        yield {"type": "done"}

    async def get_history(self, conversation_id):
        return self.history

    async def resume_conversation(self, conversation_id):
        return {
            "conversation_id": conversation_id,
            "status": "resumed",
            "history": self.history,
        }

    async def clear_conversation(self, conversation_id):
        self.history = []


@given("a chat API client")
def step_create_client(context):
    app = Flask("tactus_ide_tests", root_path=str(project_root))
    chat_server.register_chat_routes(app)
    context.app = app
    context.client = app.test_client()
    chat_server.conversations.clear()


@when("I start a chat conversation")
def step_start_chat(context):
    with mock.patch.object(
        chat_server, "get_or_create_service", return_value=FakeService("/tmp", {})
    ):
        with mock.patch("chat_server.uuid.uuid4", return_value="test-conv"):
            response = context.client.post(
                "/api/chat/start",
                json={"workspace_root": "/tmp", "config": {}},
            )
    context.start_response = response
    context.conversation_id = response.get_json().get("conversation_id")


@then("the chat start response should be active")
def step_verify_start(context):
    payload = context.start_response.get_json()
    assert payload["status"] == "active"


@when("I ping the chat test endpoint")
def step_ping_test(context):
    context.test_response = context.client.get("/api/chat/test")


@then("the chat test response should be ok")
def step_verify_test(context):
    payload = context.test_response.get_json()
    assert payload["status"] == "ok"


@when('I send a chat message "{message}"')
def step_send_message(context, message):
    # Seed a fake service for this conversation
    chat_server.conversations[context.conversation_id] = FakeService("/tmp", {})
    response = context.client.post(
        "/api/chat/message",
        json={"conversation_id": context.conversation_id, "message": message},
    )
    context.message_response = response


@then("the chat response should include events")
def step_verify_events(context):
    payload = context.message_response.get_json()
    assert isinstance(payload.get("events"), list)
    assert payload["events"]


@when("I request the chat history")
def step_request_history(context):
    response = context.client.get(f"/api/chat/history/{context.conversation_id}")
    context.history_response = response


@then("the chat history should include the message")
def step_verify_history(context):
    payload = context.history_response.get_json()
    history = payload.get("history", [])
    assert any(msg.get("role") == "user" for msg in history)


@when("I resume a chat conversation")
def step_resume_chat(context):
    with mock.patch.object(
        chat_server, "get_or_create_service", return_value=FakeService("/tmp", {})
    ):
        response = context.client.post(
            "/api/chat/resume/test-resume",
            json={"workspace_root": "/tmp", "config": {}},
        )
    context.resume_response = response
    context.conversation_id = "test-resume"


@then("the chat resume response should be active")
def step_verify_resume(context):
    payload = context.resume_response.get_json()
    assert payload["status"] == "resumed"


@when("I clear the chat conversation")
def step_clear_chat(context):
    chat_server.conversations[context.conversation_id] = FakeService("/tmp", {})
    response = context.client.delete(f"/api/chat/{context.conversation_id}")
    context.clear_response = response


@then("the chat should be removed")
def step_verify_clear(context):
    payload = context.clear_response.get_json()
    assert payload["status"] == "cleared"


@when('I stream a chat message "{message}"')
def step_stream_chat(context, message):
    with mock.patch.object(
        chat_server, "get_or_create_service", return_value=FakeService("/tmp", {})
    ):
        with mock.patch("chat_server.uuid.uuid4", return_value="stream-conv"):
            response = context.client.post(
                "/api/chat/stream",
                json={"workspace_root": "/tmp", "message": message, "config": {}},
            )
    context.stream_response = response


@then("the stream response should be event-stream")
def step_verify_stream(context):
    assert context.stream_response.mimetype == "text/event-stream"


@when("I start a chat conversation without a workspace")
def step_start_chat_missing_workspace(context):
    response = context.client.post("/api/chat/start", json={"config": {}})
    context.error_response = response


@when("I send a chat message without a conversation id")
def step_send_message_missing_conversation(context):
    response = context.client.post("/api/chat/message", json={"message": "Hi"})
    context.error_response = response


@when("I request history for an unknown conversation")
def step_request_history_unknown(context):
    response = context.client.get("/api/chat/history/unknown")
    context.error_response = response


@when("I clear an unknown conversation")
def step_clear_unknown(context):
    response = context.client.delete("/api/chat/unknown")
    context.error_response = response


@when("I stream a chat message without a workspace")
def step_stream_missing_workspace(context):
    response = context.client.post("/api/chat/stream", json={"message": "Hi", "config": {}})
    context.error_response = response


@then('the chat error should mention "{message}"')
def step_verify_chat_error(context, message):
    payload = context.error_response.get_json()
    assert message in payload.get("error", "")
