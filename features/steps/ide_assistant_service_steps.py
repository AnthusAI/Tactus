"""BDD steps for IDE assistant service."""

import asyncio
import sys
import tempfile
from contextlib import nullcontext
from pathlib import Path
from unittest import mock

from behave import given, when, then

project_root = Path(__file__).resolve().parents[2]
backend_path = project_root / "tactus-ide" / "backend"
sys.path.insert(0, str(backend_path))

from assistant_service import AssistantService  # noqa: E402


class FakeStreamResponse:
    def __init__(self, chunk: str):
        self.chunk = chunk


class FakePrediction:
    def __init__(self, answer: str):
        self.answer = answer


class FakeStreamListener:
    def __init__(self, *args, **kwargs):
        pass


class FakeStatusMessageProvider:
    def __init__(self, *args, **kwargs):
        pass


async def _collect_events(async_iter):
    events = []
    async for event in async_iter:
        events.append(event)
    return events


@given("an assistant service with a workspace")
def step_create_service(context):
    temp_dir = tempfile.TemporaryDirectory()
    context._temp_workspace = temp_dir
    context.workspace_root = temp_dir.name
    context.service = AssistantService(context.workspace_root, {"provider": "openai"})


@when('I start a conversation "{conversation_id}"')
def step_start_conversation(context, conversation_id):
    with mock.patch("tactus.dspy.config.create_lm", return_value=object()):
        with mock.patch("dspy.Tool", side_effect=lambda fn: fn):
            with mock.patch("dspy.ReAct", return_value=object()):
                context.start_result = asyncio.run(
                    context.service.start_conversation(conversation_id)
                )


@then("the conversation should be active")
def step_conversation_active(context):
    assert context.start_result["status"] == "active"


@when('I resume the conversation "{conversation_id}"')
def step_resume_conversation(context, conversation_id):
    context.resume_result = asyncio.run(context.service.resume_conversation(conversation_id))


@then("the conversation should be marked as resumed")
def step_conversation_resumed(context):
    assert context.resume_result["status"] == "resumed"


@when("I send a message without starting a conversation")
def step_send_message_without_start(context):
    context.no_start_events = asyncio.run(_collect_events(context.service.send_message("hi")))


@then("I should receive an error event")
def step_verify_error_event(context):
    assert any(event.get("type") == "error" for event in context.no_start_events)


@when('I send a message "{message}"')
def step_send_message(context, message):
    fake_streaming_module = type(
        "StreamingModule",
        (),
        {
            "StreamListener": FakeStreamListener,
            "StatusMessageProvider": FakeStatusMessageProvider,
            "StatusMessage": type("StatusMessage", (), {}),
            "StreamResponse": FakeStreamResponse,
        },
    )

    async def fake_streaming_agent(question=None):
        yield FakeStreamResponse("Hello ")
        yield FakeStreamResponse("there")
        yield FakePrediction(answer="Hello there")

    def fake_streamify(agent, stream_listeners=None, status_message_provider=None):
        return fake_streaming_agent

    with mock.patch("dspy.context", return_value=nullcontext()):
        with mock.patch("dspy.streamify", side_effect=fake_streamify):
            with mock.patch("dspy.streaming", fake_streaming_module):
                with mock.patch("dspy.Prediction", FakePrediction):
                    context.events = asyncio.run(
                        _collect_events(context.service.send_message(message))
                    )


@then("I should receive assistant output")
def step_verify_assistant_output(context):
    assert any(event.get("type") == "message" for event in context.events)
    assert context.events[-1].get("type") in {"done", "error"}


@then("the assistant history should include the exchange")
def step_verify_history(context):
    history = asyncio.run(context.service.get_history(context.service.conversation_id))
    roles = [msg["role"] for msg in history]
    assert roles.count("user") >= 1
    assert roles.count("assistant") >= 1


@when('I clear the conversation "{conversation_id}"')
def step_clear_conversation(context, conversation_id):
    asyncio.run(context.service.clear_conversation(conversation_id))


@then("the conversation history should be empty")
def step_verify_history_cleared(context):
    history = asyncio.run(context.service.get_history(context.service.conversation_id))
    assert history == []
