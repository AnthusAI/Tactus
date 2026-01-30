import os
import sys
from types import SimpleNamespace

import pytest

from tactus.broker import server as broker_server


def test_json_dumps_compact():
    payload = {"a": 1, "b": {"c": 2}}
    output = broker_server._json_dumps(payload)
    assert output == '{"a":1,"b":{"c":2}}'


def test_flatten_exceptions_handles_groups():
    try:
        raise ExceptionGroup(
            "top",
            [
                ValueError("first"),
                ExceptionGroup("nested", [RuntimeError("second")]),
            ],
        )
    except ExceptionGroup as exc:
        leaves = broker_server._flatten_exceptions(exc)

    assert [type(e) for e in leaves] == [ValueError, RuntimeError]


def test_host_tool_registry_default_tools():
    registry = broker_server.HostToolRegistry.default()
    assert registry.call("host.ping", {"ok": True})["ok"] is True
    assert registry.call("host.echo", {"value": 1})["echo"] == {"value": 1}

    with pytest.raises(KeyError):
        registry.call("host.nope", {})


@pytest.mark.asyncio
async def test_openai_chat_backend_uses_litellm(monkeypatch):
    captured = {}

    class DummyMessage:
        tool_calls = [{"id": "tool"}]

    class DummyChoice:
        finish_reason = "stop"
        message = DummyMessage()

    class DummyResult:
        choices = [DummyChoice()]

    async def acompletion(**kwargs):
        captured.update(kwargs)
        return DummyResult()

    fake_litellm = SimpleNamespace(acompletion=acompletion)
    monkeypatch.setitem(sys.modules, "litellm", fake_litellm)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    backend = broker_server.OpenAIChatBackend(api_key="secret")
    await backend.chat(
        model="gpt-4o",
        messages=[{"role": "user", "content": "hi"}],
        temperature=0.2,
        max_tokens=5,
        stream=False,
        tools=[{"name": "tool"}],
        tool_choice="auto",
    )

    assert captured["model"] == "gpt-4o"
    assert captured["temperature"] == 0.2
    assert captured["max_tokens"] == 5
    assert captured["tools"][0]["name"] == "tool"
    assert captured["tool_choice"] == "auto"
    assert os.environ["OPENAI_API_KEY"] == "secret"
