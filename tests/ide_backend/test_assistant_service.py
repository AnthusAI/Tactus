from pathlib import Path
import contextlib
import sys
import types

import pytest

backend_dir = Path(__file__).resolve().parents[2] / "tactus-ide" / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from assistant_service import AssistantService  # noqa: E402


class FakeTool:
    def __init__(self, func):
        self.func = func


class FakeReAct:
    def __init__(self, signature, tools, max_iters):
        self.signature = signature
        self.tools = tools
        self.max_iters = max_iters


class FakeStatusMessage:
    def __init__(self, message):
        self.message = message


class FakeStreamResponse:
    def __init__(self, chunk):
        self.chunk = chunk


class FakePrediction:
    def __init__(self, answer=None, response=None):
        if answer is not None:
            self.answer = answer
        if response is not None:
            self.response = response


class FakeStreamListener:
    def __init__(self, signature_field_name, allow_reuse):
        self.signature_field_name = signature_field_name
        self.allow_reuse = allow_reuse


class FakeStatusMessageProvider:
    pass


def build_fake_dspy(streamify_impl, prediction_class=FakePrediction):
    streaming = types.SimpleNamespace(
        StreamListener=FakeStreamListener,
        StatusMessageProvider=FakeStatusMessageProvider,
        StatusMessage=FakeStatusMessage,
        StreamResponse=FakeStreamResponse,
    )

    return types.SimpleNamespace(
        Tool=FakeTool,
        ReAct=FakeReAct,
        Prediction=prediction_class,
        streaming=streaming,
        streamify=streamify_impl,
        context=lambda **kwargs: contextlib.nullcontext(),
    )


def build_inline_thread(monkeypatch):
    class InlineThread:
        def __init__(self, target=None, daemon=None):
            self._target = target
            self.daemon = daemon

        def start(self):
            if self._target:
                self._target()

    monkeypatch.setattr("threading.Thread", InlineThread)


@pytest.mark.asyncio
async def test_start_conversation_initializes_agent(monkeypatch, tmp_path):
    monkeypatch.setattr("assistant_service.dspy.Tool", FakeTool)
    monkeypatch.setattr("assistant_service.dspy.ReAct", FakeReAct)
    monkeypatch.setattr("tactus.dspy.config.create_lm", lambda *args, **kwargs: "lm")

    service = AssistantService(str(tmp_path), {"provider": "openai", "model": "gpt-4o"})
    result = await service.start_conversation("conv-1")

    assert result["conversation_id"] == "conv-1"
    assert service.agent is not None
    assert service.lm == "lm"


def test_set_websocket_manager():
    service = AssistantService("/tmp", {"provider": "openai", "model": "gpt-4o"})
    manager = object()

    service.set_websocket_manager(manager)

    assert service.websocket_manager is manager


@pytest.mark.asyncio
async def test_start_conversation_handles_spec_loading_and_tool_helpers(
    monkeypatch, tmp_path, caplog
):
    def fake_create_lm(model, temperature=None, max_tokens=None):
        return {
            "model": model,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

    def fake_read_text(self):
        raise OSError("no spec")

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr("assistant_service.dspy.Tool", FakeTool)
    monkeypatch.setattr("assistant_service.dspy.ReAct", FakeReAct)
    monkeypatch.setattr("tactus.dspy.config.create_lm", fake_create_lm)
    monkeypatch.setattr("pathlib.Path.read_text", fake_read_text)

    service = AssistantService(str(tmp_path), {"provider": "openai", "model": "openai/gpt-4o"})

    with caplog.at_level("WARNING"):
        await service.start_conversation("conv-2")

    assert "Could not load SPECIFICATION.md" in caplog.text
    assert "OPENAI_API_KEY not set" in caplog.text
    assert "Could not load specification" in service.system_prompt
    assert service.lm["model"] == "openai/gpt-4o"

    view_tool = service.agent.tools[0]
    search_tool = service.agent.tools[1]

    monkeypatch.setattr("assistant_service.str_replace_based_edit_tool", lambda **kwargs: "view ok")
    assert view_tool.func("view", "README.md", view_range=[1, 2]) == "view ok"

    def raise_edit(**kwargs):
        raise ValueError("bad edit")

    monkeypatch.setattr("assistant_service.str_replace_based_edit_tool", raise_edit)
    assert view_tool.func("view", "README.md") == "Error: bad edit"

    monkeypatch.setattr("assistant_service.search_files", lambda root, pattern: [])
    assert "No files found" in search_tool.func("*.tac")

    from assistant_tools import FileToolsError

    def raise_search(root, pattern):
        raise FileToolsError("no access")

    monkeypatch.setattr("assistant_service.search_files", raise_search)
    assert "Error searching files: no access" == search_tool.func("*.tac")

    monkeypatch.setattr("assistant_service.search_files", lambda root, pattern: ["a.tac", "b.tac"])
    assert "Files matching" in search_tool.func("*.tac")


@pytest.mark.asyncio
async def test_start_conversation_without_provider_prefix(monkeypatch, tmp_path):
    captured = {}

    def fake_create_lm(model, temperature=None, max_tokens=None):
        captured["model"] = model
        return "lm"

    monkeypatch.setattr("assistant_service.dspy.Tool", FakeTool)
    monkeypatch.setattr("assistant_service.dspy.ReAct", FakeReAct)
    monkeypatch.setattr("tactus.dspy.config.create_lm", fake_create_lm)

    service = AssistantService(str(tmp_path), {"provider": None, "model": "gpt-4o"})
    await service.start_conversation("conv-3")

    assert captured["model"] == "gpt-4o"


@pytest.mark.asyncio
async def test_send_message_streams_status_and_chunks(monkeypatch):
    status_message = FakeStatusMessage("tool running")
    chunk = FakeStreamResponse("Hello ")
    empty_chunk = FakeStreamResponse("")
    final = FakePrediction(answer="unused")

    def streamify_impl(agent, stream_listeners=None, status_message_provider=None):
        assert status_message_provider is not None

        tool_inputs = {"kwargs": {"path": "x" * 60}}
        assert (
            status_message_provider.tool_start_status_message(
                types.SimpleNamespace(name="read_file"), tool_inputs
            )
            == "read_file  path = " + ("x" * 47) + "..."
        )
        assert (
            status_message_provider.tool_start_status_message(
                types.SimpleNamespace(name="read_file"), {"path": "short"}
            )
            == "read_file  path = short"
        )
        assert (
            status_message_provider.tool_start_status_message(
                types.SimpleNamespace(name="read_file"), {}
            )
            == "read_file"
        )
        assert status_message_provider.tool_end_status_message({"ok": True}) is None

        async def runner(**kwargs):
            yield status_message
            yield chunk
            yield empty_chunk
            yield final

        return runner

    fake_dspy = build_fake_dspy(streamify_impl)
    monkeypatch.setitem(sys.modules, "dspy", fake_dspy)
    monkeypatch.setattr("assistant_service.dspy", fake_dspy)

    service = AssistantService("/tmp", {"provider": "openai", "model": "gpt-4o"})
    service.agent = object()
    service.lm = "lm"
    service.system_prompt = "system"
    service.message_history = [{"role": "assistant", "content": "previous"}]

    events = []
    async for event in service.send_message("hi"):
        events.append(event)

    assert events[0]["type"] == "thinking"
    assert events[1]["type"] == "status"
    assert events[2]["type"] == "message"
    assert events[-1]["type"] == "done"
    assert service.message_history[-1]["content"] == "Hello "


@pytest.mark.asyncio
async def test_send_message_fallback_filters_react_markup(monkeypatch):
    final = FakePrediction(answer="Thought: skip\nAnswer: Hello there")

    def streamify_impl(agent, stream_listeners=None, status_message_provider=None):
        async def runner(**kwargs):
            yield final

        return runner

    fake_dspy = build_fake_dspy(streamify_impl)
    monkeypatch.setitem(sys.modules, "dspy", fake_dspy)
    monkeypatch.setattr("assistant_service.dspy", fake_dspy)

    service = AssistantService("/tmp", {"provider": "openai", "model": "gpt-4o"})
    service.agent = object()
    service.lm = "lm"
    service.system_prompt = "system"

    events = []
    async for event in service.send_message("hi"):
        events.append(event)

    message_events = [event for event in events if event["type"] == "message"]
    assert message_events[0]["content"] == "skip\nHello there"
    assert service.message_history[-1]["content"] == "skip\nHello there"


@pytest.mark.asyncio
async def test_send_message_fallback_response_and_dict_branches(monkeypatch):
    def streamify_impl(agent, stream_listeners=None, status_message_provider=None):
        async def runner(**kwargs):
            yield FakePrediction(response="Answer: hi")

        return runner

    fake_dspy = build_fake_dspy(streamify_impl)
    monkeypatch.setitem(sys.modules, "dspy", fake_dspy)
    monkeypatch.setattr("assistant_service.dspy", fake_dspy)

    service = AssistantService("/tmp", {"provider": "openai", "model": "gpt-4o"})
    service.agent = object()
    service.lm = "lm"
    service.system_prompt = "system"

    events = [event async for event in service.send_message("hi")]
    message_events = [event for event in events if event["type"] == "message"]
    assert message_events[0]["content"] == "hi"

    def streamify_dict(agent, stream_listeners=None, status_message_provider=None):
        async def runner(**kwargs):
            yield {"answer": "   "}

        return runner

    fake_dspy_dict = build_fake_dspy(streamify_dict, prediction_class=dict)
    monkeypatch.setitem(sys.modules, "dspy", fake_dspy_dict)
    monkeypatch.setattr("assistant_service.dspy", fake_dspy_dict)

    service = AssistantService("/tmp", {"provider": "openai", "model": "gpt-4o"})
    service.agent = object()
    service.lm = "lm"
    service.system_prompt = "system"

    events = [event async for event in service.send_message("hi")]
    assert not [event for event in events if event["type"] == "message"]


@pytest.mark.asyncio
async def test_send_message_fallback_str_branch(monkeypatch):
    def streamify_impl(agent, stream_listeners=None, status_message_provider=None):
        async def runner(**kwargs):
            yield "Answer: raw"

        return runner

    fake_dspy = build_fake_dspy(streamify_impl, prediction_class=str)
    monkeypatch.setitem(sys.modules, "dspy", fake_dspy)
    monkeypatch.setattr("assistant_service.dspy", fake_dspy)

    service = AssistantService("/tmp", {"provider": "openai", "model": "gpt-4o"})
    service.agent = object()
    service.lm = "lm"
    service.system_prompt = "system"

    events = [event async for event in service.send_message("hi")]
    message_events = [event for event in events if event["type"] == "message"]
    assert message_events[0]["content"] == "raw"


@pytest.mark.asyncio
async def test_send_message_queue_timeout_logs_warning(monkeypatch, caplog):
    import queue as queue_module

    class TimeoutQueue:
        def __init__(self):
            self.items = []

        def put(self, item):
            self.items.append(item)

        def get(self, timeout=None):
            raise queue_module.Empty()

    def streamify_impl(agent, stream_listeners=None, status_message_provider=None):
        async def runner(**kwargs):
            yield FakePrediction(answer="Answer: hi")

        return runner

    fake_dspy = build_fake_dspy(streamify_impl)
    monkeypatch.setitem(sys.modules, "dspy", fake_dspy)
    monkeypatch.setattr("assistant_service.dspy", fake_dspy)
    monkeypatch.setattr(queue_module, "Queue", TimeoutQueue)

    service = AssistantService("/tmp", {"provider": "openai", "model": "gpt-4o"})
    service.agent = object()
    service.lm = "lm"
    service.system_prompt = "system"

    with caplog.at_level("WARNING"):
        events = [event async for event in service.send_message("hi")]

    assert any(
        "Timeout waiting for streaming chunks" in record.message for record in caplog.records
    )
    assert events[-1]["type"] == "done"


@pytest.mark.asyncio
async def test_send_message_ignores_unrecognized_chunks(monkeypatch):
    def streamify_impl(agent, stream_listeners=None, status_message_provider=None):
        async def runner(**kwargs):
            yield object()

        return runner

    fake_dspy = build_fake_dspy(streamify_impl)
    monkeypatch.setitem(sys.modules, "dspy", fake_dspy)
    monkeypatch.setattr("assistant_service.dspy", fake_dspy)

    service = AssistantService("/tmp", {"provider": "openai", "model": "gpt-4o"})
    service.agent = object()
    service.lm = "lm"
    service.system_prompt = "system"

    events = [event async for event in service.send_message("hi")]
    assert not [event for event in events if event["type"] == "message"]
    assert events[-1]["type"] == "done"


@pytest.mark.asyncio
async def test_send_message_streaming_error_returns_error(monkeypatch):
    def streamify_impl(agent, stream_listeners=None, status_message_provider=None):
        async def runner(**kwargs):
            raise RuntimeError("stream fail")
            yield  # pragma: no cover

        return runner

    fake_dspy = build_fake_dspy(streamify_impl)
    monkeypatch.setitem(sys.modules, "dspy", fake_dspy)
    monkeypatch.setattr("assistant_service.dspy", fake_dspy)

    service = AssistantService("/tmp", {"provider": "openai", "model": "gpt-4o"})
    service.agent = object()
    service.lm = "lm"
    service.system_prompt = "system"

    events = [event async for event in service.send_message("hi")]
    assert events[-1]["type"] == "error"
    assert "stream fail" in events[-1]["error"]


@pytest.mark.asyncio
async def test_send_message_outer_agent_error(monkeypatch):
    import asyncio

    def streamify_impl(agent, stream_listeners=None, status_message_provider=None):
        async def runner(**kwargs):
            yield FakePrediction(answer="Answer: hi")

        return runner

    fake_dspy = build_fake_dspy(streamify_impl)
    monkeypatch.setitem(sys.modules, "dspy", fake_dspy)
    monkeypatch.setattr("assistant_service.dspy", fake_dspy)
    monkeypatch.setattr(
        asyncio, "new_event_loop", lambda: (_ for _ in ()).throw(RuntimeError("boom"))
    )

    service = AssistantService("/tmp", {"provider": "openai", "model": "gpt-4o"})
    service.agent = object()
    service.lm = "lm"
    service.system_prompt = "system"

    events = [event async for event in service.send_message("hi")]
    assert events[-1]["type"] == "error"
    assert "boom" in events[-1]["error"]


@pytest.mark.asyncio
async def test_send_message_without_agent():
    service = AssistantService("/tmp", {"provider": "openai", "model": "gpt-4o"})
    events = []

    async for event in service.send_message("hi"):
        events.append(event)

    assert events[0]["type"] == "error"


@pytest.mark.asyncio
async def test_resume_get_history_and_clear():
    service = AssistantService("/tmp", {"provider": "openai", "model": "gpt-4o"})
    service.message_history = [{"role": "user", "content": "hi"}]

    resume = await service.resume_conversation("conv-1")
    assert resume["status"] == "resumed"

    history = await service.get_history("conv-1")
    assert history == [{"role": "user", "content": "hi"}]

    await service.clear_conversation("conv-1")
    assert service.message_history == []
