from pathlib import Path
import socket
import tempfile
from types import SimpleNamespace

import pytest

import dspy
from litellm import ModelResponseStream

from tactus.broker.client import BrokerClient
from tactus.broker.server import BrokerServer
from tactus.dspy.broker_lm import BrokeredLM


def _uds_supported() -> bool:
    try:
        with tempfile.TemporaryDirectory(dir=str(Path.cwd())) as td:
            path = Path(td) / "probe.sock"
            s = socket.socket(socket.AF_UNIX)
            s.bind(str(path))
            s.close()
        return True
    except OSError:
        return False


if not _uds_supported():
    pytest.skip("AF_UNIX sockets not permitted in this environment", allow_module_level=True)


class _FakeOpenAIBackend:
    async def chat(
        self,
        *,
        model: str,
        messages: list[dict],
        temperature: float | None = None,
        max_tokens: int | None = None,
        stream: bool,
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
async def test_broker_events_emit_round_trip():
    received: list[dict] = []
    with tempfile.TemporaryDirectory(dir=str(Path.cwd())) as td:
        socket_path = Path(td) / "broker.sock"

        async with BrokerServer(
            socket_path, openai_backend=_FakeOpenAIBackend(), event_handler=received.append
        ):
            client = BrokerClient(socket_path)
            await client.emit_event({"kind": "test", "value": 1})

    assert received == [{"kind": "test", "value": 1}]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_brokered_lm_non_streaming(monkeypatch: pytest.MonkeyPatch):
    with tempfile.TemporaryDirectory(dir=str(Path.cwd())) as td:
        socket_path = Path(td) / "broker.sock"
        monkeypatch.setenv("TACTUS_BROKER_SOCKET", str(socket_path))

        async with BrokerServer(socket_path, openai_backend=_FakeOpenAIBackend()):
            lm = BrokeredLM("openai/gpt-4o-mini")
            resp = await lm.aforward(messages=[{"role": "user", "content": "hi"}])

    assert resp.choices[0].message.content == "hello"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_brokered_lm_streaming_sends_model_response_stream_chunks(
    monkeypatch: pytest.MonkeyPatch,
):
    with tempfile.TemporaryDirectory(dir=str(Path.cwd())) as td:
        socket_path = Path(td) / "broker.sock"
        monkeypatch.setenv("TACTUS_BROKER_SOCKET", str(socket_path))

        async with BrokerServer(socket_path, openai_backend=_FakeOpenAIBackend()):
            lm = BrokeredLM("openai/gpt-4o-mini")
            send_stream = _FakeSendStream()

            with dspy.settings.context(send_stream=send_stream):
                resp = await lm.aforward(messages=[{"role": "user", "content": "hi"}])

        chunks = [i for i in send_stream.items if isinstance(i, ModelResponseStream)]
        assert "".join(c.choices[0].delta.content for c in chunks) == "hello"
        assert resp.choices[0].message.content == "hello"
