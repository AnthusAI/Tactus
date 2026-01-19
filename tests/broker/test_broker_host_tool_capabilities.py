from __future__ import annotations

from pathlib import Path
import socket
import tempfile
from types import SimpleNamespace

import pytest

from tactus.broker.client import BrokerClient
from tactus.broker.server import BrokerServer


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


@pytest.mark.asyncio
async def test_broker_host_capabilities_lists_tools():
    with tempfile.TemporaryDirectory(dir=str(Path.cwd())) as td:
        socket_path = Path(td) / "broker.sock"

        async with BrokerServer(socket_path, openai_backend=_FakeOpenAIBackend()):
            client = BrokerClient(socket_path)
            result = await client.call_tool(name="host.capabilities", args={})

    assert "host.ping" in result["tools"]
    assert "host.echo" in result["tools"]
    assert "host.capabilities" in result["tools"]
    assert "host.version" in result["tools"]


@pytest.mark.asyncio
async def test_broker_host_version_returns_version_string():
    with tempfile.TemporaryDirectory(dir=str(Path.cwd())) as td:
        socket_path = Path(td) / "broker.sock"

        async with BrokerServer(socket_path, openai_backend=_FakeOpenAIBackend()):
            client = BrokerClient(socket_path)
            result = await client.call_tool(name="host.version", args={})

    assert isinstance(result.get("version"), str)
    assert result["version"]
