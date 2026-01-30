import pytest

from tactus.primitives.host import HostPrimitive


def test_host_call_delegates_to_broker_client():
    class _FakeBrokerClient:
        async def call_tool(self, *, name: str, args: dict):
            return {"name": name, "args": args, "ok": True}

    host = HostPrimitive(client=_FakeBrokerClient())
    result = host.call("host.ping", {"x": 1})

    assert result == {"name": "host.ping", "args": {"x": 1}, "ok": True}


def test_host_call_falls_back_to_inproc_registry(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("TACTUS_BROKER_SOCKET", raising=False)

    host = HostPrimitive()
    result = host.call("host.ping", {"x": 1})

    assert result == {"ok": True, "echo": {"x": 1}}


def test_host_call_raises_on_disallowed_tool(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("TACTUS_BROKER_SOCKET", raising=False)

    host = HostPrimitive()

    with pytest.raises(RuntimeError, match="Tool not allowlisted"):
        host.call("host.nope", {})


def test_host_call_rejects_empty_name():
    class _FakeBrokerClient:
        async def call_tool(self, *, name: str, args: dict):
            return {"name": name, "args": args}

    host = HostPrimitive(client=_FakeBrokerClient())

    with pytest.raises(ValueError, match="non-empty tool name"):
        host.call("", {})


def test_host_call_rejects_non_object_args():
    class _FakeBrokerClient:
        async def call_tool(self, *, name: str, args: dict):
            return {"name": name, "args": args}

    host = HostPrimitive(client=_FakeBrokerClient())

    with pytest.raises(ValueError, match="args must be an object"):
        host.call("host.ping", ["nope"])


def test_host_call_requires_broker_socket_when_no_registry():
    host = HostPrimitive(client=None)
    host._registry = None

    with pytest.raises(RuntimeError, match="TACTUS_BROKER_SOCKET"):
        host.call("host.ping", {})


def test_host_lua_to_python_converts_tables():
    host = HostPrimitive(client=None)

    class FakeTable:
        def items(self):
            return [("a", 1), ("b", [2, (3,)])]

    assert host._lua_to_python(FakeTable()) == {"a": 1, "b": [2, [3]]}


def test_host_lua_to_python_handles_none():
    host = HostPrimitive(client=None)
    assert host._lua_to_python(None) is None


@pytest.mark.asyncio
async def test_host_run_coro_with_running_loop():
    host = HostPrimitive(client=None)

    async def get_value():
        return "ok"

    assert host._run_coro(get_value()) == "ok"


@pytest.mark.asyncio
async def test_host_run_coro_thread_exception():
    host = HostPrimitive(client=None)

    async def get_value():
        raise ValueError("boom")

    with pytest.raises(ValueError, match="boom"):
        host._run_coro(get_value())
