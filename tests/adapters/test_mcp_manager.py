import builtins
import io
import os

import pytest

from tactus.adapters import mcp_manager


def test_require_mcp_server_stdio_import_error(monkeypatch):
    original_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "pydantic_ai.mcp":
            raise ImportError("missing")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import, raising=True)

    with pytest.raises(RuntimeError):
        mcp_manager._require_mcp_server_stdio()


def test_substitute_env_vars():
    os.environ["TOKEN"] = "secret"
    assert mcp_manager.substitute_env_vars("${TOKEN}") == "secret"
    assert mcp_manager.substitute_env_vars({"k": "${TOKEN}"}) == {"k": "secret"}
    assert mcp_manager.substitute_env_vars(["${TOKEN}"]) == ["secret"]
    os.environ.pop("TOKEN", None)


def test_substitute_env_vars_passthrough():
    assert mcp_manager.substitute_env_vars(123) == 123


@pytest.mark.asyncio
async def test_mcp_manager_connects_and_tracks_toolsets(monkeypatch):
    class DummyServer:
        def __init__(self, **_kwargs):
            pass

        def prefixed(self, _name):
            return self

        async def __aenter__(self):
            return self

        async def __aexit__(self, _exc_type, _exc, _tb):
            return None

    monkeypatch.setattr(mcp_manager, "MCPServerStdio", DummyServer)
    manager = mcp_manager.MCPServerManager({"srv": {"command": "echo"}}, tool_primitive=None)
    async with manager:
        assert manager.get_toolsets() == [manager.get_toolset_by_name("srv")]


@pytest.mark.asyncio
async def test_mcp_manager_with_no_configs(monkeypatch):
    manager = mcp_manager.MCPServerManager({}, tool_primitive=None)
    async with manager:
        assert manager.get_toolsets() == []


@pytest.mark.asyncio
async def test_mcp_manager_handles_fileno_error(monkeypatch):
    class DummyServer:
        def __init__(self, **_kwargs):
            raise io.UnsupportedOperation("fileno")

    monkeypatch.setattr(mcp_manager, "MCPServerStdio", DummyServer)
    manager = mcp_manager.MCPServerManager({"srv": {"command": "echo"}}, tool_primitive=None)
    async with manager:
        assert manager.get_toolsets() == []


@pytest.mark.asyncio
async def test_mcp_manager_retries_transient_errors(monkeypatch):
    calls = {"count": 0}

    class DummyServer:
        def __init__(self, **_kwargs):
            calls["count"] += 1
            if calls["count"] == 1:
                raise RuntimeError("BrokenResourceError")

        def prefixed(self, _name):
            return self

        async def __aenter__(self):
            return self

        async def __aexit__(self, _exc_type, _exc, _tb):
            return None

    monkeypatch.setattr(mcp_manager, "MCPServerStdio", DummyServer)
    manager = mcp_manager.MCPServerManager({"srv": {"command": "echo"}}, tool_primitive=None)
    async with manager:
        assert calls["count"] >= 2


@pytest.mark.asyncio
async def test_mcp_manager_retries_taskgroup_errors(monkeypatch):
    calls = {"count": 0}

    class DummyServer:
        def __init__(self, **_kwargs):
            calls["count"] += 1
            if calls["count"] == 1:
                raise RuntimeError("unhandled errors in a TaskGroup")

        def prefixed(self, _name):
            return self

        async def __aenter__(self):
            return self

        async def __aexit__(self, _exc_type, _exc, _tb):
            return None

    monkeypatch.setattr(mcp_manager, "MCPServerStdio", DummyServer)
    manager = mcp_manager.MCPServerManager({"srv": {"command": "echo"}}, tool_primitive=None)
    async with manager:
        assert calls["count"] >= 2


@pytest.mark.asyncio
async def test_mcp_manager_raises_after_retries(monkeypatch):
    class DummyServer:
        def __init__(self, **_kwargs):
            raise RuntimeError("BrokenResourceError")

    monkeypatch.setattr(mcp_manager, "MCPServerStdio", DummyServer)
    manager = mcp_manager.MCPServerManager({"srv": {"command": "echo"}}, tool_primitive=None)
    with pytest.raises(RuntimeError):
        async with manager:
            pass


@pytest.mark.asyncio
async def test_mcp_manager_raises_non_transient_error(monkeypatch):
    class DummyServer:
        def __init__(self, **_kwargs):
            raise RuntimeError("boom")

    monkeypatch.setattr(mcp_manager, "MCPServerStdio", DummyServer)
    manager = mcp_manager.MCPServerManager({"srv": {"command": "echo"}}, tool_primitive=None)
    with pytest.raises(RuntimeError):
        async with manager:
            pass


@pytest.mark.asyncio
async def test_trace_callback_records_calls():
    records = []

    class DummyToolPrimitive:
        def record_call(self, name, args, result):
            records.append((name, args, result))

    manager = mcp_manager.MCPServerManager({}, tool_primitive=DummyToolPrimitive())
    callback = manager._create_trace_callback("srv")

    async def invoke_next(tool_name, tool_args):
        return "ok"

    result = await callback(None, invoke_next, "tool", {"a": 1})
    assert result == "ok"
    assert records[-1][2] == "ok"

    async def invoke_error(_tool, _args):
        raise RuntimeError("fail")

    with pytest.raises(RuntimeError):
        await callback(None, invoke_error, "tool", {"a": 2})
    assert "Error:" in records[-1][2]


@pytest.mark.asyncio
async def test_trace_callback_error_without_tool_primitive():
    manager = mcp_manager.MCPServerManager({}, tool_primitive=None)
    callback = manager._create_trace_callback("srv")

    async def invoke_error(_tool, _args):
        raise RuntimeError("fail")

    with pytest.raises(RuntimeError):
        await callback(None, invoke_error, "tool", {"a": 2})


@pytest.mark.asyncio
async def test_trace_callback_retries_transient_tool_errors():
    records = []
    calls = {"count": 0}

    class DummyToolPrimitive:
        def record_call(self, name, args, result):
            records.append((name, args, result))

    manager = mcp_manager.MCPServerManager({}, tool_primitive=DummyToolPrimitive())
    callback = manager._create_trace_callback("srv")

    async def flaky_invoke(_tool, _args):
        calls["count"] += 1
        if calls["count"] == 1:
            raise RuntimeError("unhandled errors in a TaskGroup")
        return "ok-after-retry"

    result = await callback(None, flaky_invoke, "tool", {"a": 3})
    assert result == "ok-after-retry"
    assert calls["count"] == 2
    assert records[-1][2] == "ok-after-retry"


@pytest.mark.asyncio
async def test_trace_callback_does_not_retry_non_transient_tool_errors():
    calls = {"count": 0}

    manager = mcp_manager.MCPServerManager({}, tool_primitive=None)
    callback = manager._create_trace_callback("srv")

    async def boom(_tool, _args):
        calls["count"] += 1
        raise RuntimeError("permanent failure")

    with pytest.raises(RuntimeError, match="permanent failure"):
        await callback(None, boom, "tool", {"a": 4})

    assert calls["count"] == 1
