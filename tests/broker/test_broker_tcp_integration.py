import socket
from types import SimpleNamespace

import pytest

import dspy
from litellm import ModelResponseStream

from tactus.broker.client import BrokerClient
from tactus.broker.server import TcpBrokerServer
from tactus.dspy.broker_lm import BrokeredLM


def _tcp_listen_supported() -> bool:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(("127.0.0.1", 0))
        s.listen(1)
        s.close()
        return True
    except OSError:
        return False


if not _tcp_listen_supported():
    pytest.skip("TCP listen not permitted in this environment", allow_module_level=True)


class _FakeOpenAIBackend:
    async def chat(
        self,
        *,
        model: str,
        messages: list[dict],
        temperature: float | None = None,
        max_tokens: int | None = None,
        tools: list[dict] | None = None,
        tool_choice: dict | str | None = None,
        stream: bool,
        **kwargs,
    ):
        if stream:

            async def gen():
                for token in ["he", "llo"]:
                    yield SimpleNamespace(
                        choices=[SimpleNamespace(delta=SimpleNamespace(content=token))]
                    )

            return gen()

        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="hello"))])


class _FakeSendStream:
    def __init__(self):
        self.items: list[object] = []

    async def send(self, item: object) -> None:
        self.items.append(item)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_tcp_broker_events_emit_round_trip():
    received: list[dict] = []

    async with TcpBrokerServer(
        host="127.0.0.1",
        port=0,
        openai_backend=_FakeOpenAIBackend(),
        event_handler=received.append,
    ) as server:
        assert server.bound_port is not None
        client = BrokerClient(f"tcp://127.0.0.1:{server.bound_port}")
        await client.emit_event({"kind": "test", "value": 1})

    assert received == [{"kind": "test", "value": 1}]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_tcp_brokered_lm_non_streaming(monkeypatch: pytest.MonkeyPatch):
    async with TcpBrokerServer(
        host="127.0.0.1", port=0, openai_backend=_FakeOpenAIBackend()
    ) as server:
        assert server.bound_port is not None
        monkeypatch.setenv("TACTUS_BROKER_SOCKET", f"tcp://127.0.0.1:{server.bound_port}")

        lm = BrokeredLM("openai/gpt-4o-mini")
        resp = await lm.aforward(messages=[{"role": "user", "content": "hi"}])

    assert resp.choices[0].message.content == "hello"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_tcp_brokered_lm_streaming_sends_model_response_stream_chunks(
    monkeypatch: pytest.MonkeyPatch,
):
    async with TcpBrokerServer(
        host="127.0.0.1", port=0, openai_backend=_FakeOpenAIBackend()
    ) as server:
        assert server.bound_port is not None
        monkeypatch.setenv("TACTUS_BROKER_SOCKET", f"tcp://127.0.0.1:{server.bound_port}")

        lm = BrokeredLM("openai/gpt-4o-mini")
        send_stream = _FakeSendStream()

        with dspy.settings.context(send_stream=send_stream):
            resp = await lm.aforward(messages=[{"role": "user", "content": "hi"}])

    chunks = [i for i in send_stream.items if isinstance(i, ModelResponseStream)]
    assert "".join(c.choices[0].delta.content for c in chunks) == "hello"
    assert resp.choices[0].message.content == "hello"
