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
