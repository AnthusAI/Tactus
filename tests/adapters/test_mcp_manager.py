import pytest

from tactus.adapters.mcp_manager import MCPServerManager, substitute_env_vars


def test_substitute_env_vars_handles_nested(monkeypatch):
    monkeypatch.setenv("HOST", "example.com")

    value = substitute_env_vars(
        {"url": "https://${HOST}/api", "list": ["${HOST}", {"k": "${HOST}"}]}
    )

    assert value["url"] == "https://example.com/api"
    assert value["list"][0] == "example.com"
    assert value["list"][1]["k"] == "example.com"


def test_substitute_env_vars_passthrough():
    assert substitute_env_vars(123) == 123


@pytest.mark.asyncio
async def test_trace_callback_records_success():
    class DummyToolPrimitive:
        def __init__(self):
            self.calls = []

        def record_call(self, name, args, result):
            self.calls.append((name, args, result))

    async def next_call(tool_name, tool_args):
        return {"ok": True}

    manager = MCPServerManager({}, tool_primitive=DummyToolPrimitive())
    callback = manager._create_trace_callback("server")

    result = await callback(None, next_call, "tool", {"x": 1})

    assert result == {"ok": True}
    assert manager.tool_primitive.calls == [("tool", {"x": 1}, "{'ok': True}")]


@pytest.mark.asyncio
async def test_trace_callback_records_failure():
    class DummyToolPrimitive:
        def __init__(self):
            self.calls = []

        def record_call(self, name, args, result):
            self.calls.append((name, args, result))

    async def next_call(_tool_name, _tool_args):
        raise RuntimeError("boom")

    manager = MCPServerManager({}, tool_primitive=DummyToolPrimitive())
    callback = manager._create_trace_callback("server")

    with pytest.raises(RuntimeError):
        await callback(None, next_call, "tool", {"x": 1})

    assert manager.tool_primitive.calls == [("tool", {"x": 1}, "Error: boom")]


@pytest.mark.asyncio
async def test_manager_connects_and_registers_toolsets(monkeypatch):
    created = []

    class FakeServer:
        def __init__(self, command, args=None, env=None, cwd=None, process_tool_call=None):
            self.command = command
            self.args = args or []
            self.env = env
            self.cwd = cwd
            self.process_tool_call = process_tool_call
            created.append(self)

        def prefixed(self, _name):
            return self

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

    monkeypatch.setattr("tactus.adapters.mcp_manager.MCPServerStdio", FakeServer)

    manager = MCPServerManager({"srv": {"command": "echo", "args": ["ok"]}})
    async with manager:
        toolsets = manager.get_toolsets()
        assert len(toolsets) == 1
        assert manager.get_toolset_by_name("srv") is toolsets[0]


@pytest.mark.asyncio
async def test_manager_skips_fileno_error(monkeypatch):
    import io

    def raise_fileno(*_args, **_kwargs):
        raise io.UnsupportedOperation("fileno")

    monkeypatch.setattr("tactus.adapters.mcp_manager.MCPServerStdio", raise_fileno)

    manager = MCPServerManager({"srv": {"command": "echo"}})
    async with manager:
        assert manager.get_toolsets() == []


@pytest.mark.asyncio
async def test_manager_retries_transient_error(monkeypatch):
    calls = {"count": 0}

    class FlakyServer:
        def __init__(self, command, args=None, env=None, cwd=None, process_tool_call=None):
            calls["count"] += 1
            if calls["count"] == 1:
                raise RuntimeError("BrokenResourceError: boom")

        def prefixed(self, _name):
            return self

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

    monkeypatch.setattr("tactus.adapters.mcp_manager.MCPServerStdio", FlakyServer)

    manager = MCPServerManager({"srv": {"command": "echo"}})
    async with manager:
        assert len(manager.get_toolsets()) == 1
    assert calls["count"] >= 2


@pytest.mark.asyncio
async def test_manager_raises_on_non_transient_error(monkeypatch):
    def raise_fail(*_args, **_kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr("tactus.adapters.mcp_manager.MCPServerStdio", raise_fail)

    manager = MCPServerManager({"srv": {"command": "echo"}})
    with pytest.raises(RuntimeError):
        await manager.__aenter__()


@pytest.mark.asyncio
async def test_manager_raises_after_transient_retries(monkeypatch):
    def raise_transient(*_args, **_kwargs):
        raise RuntimeError("BrokenResourceError: boom")

    monkeypatch.setattr("tactus.adapters.mcp_manager.MCPServerStdio", raise_transient)

    manager = MCPServerManager({"srv": {"command": "echo"}})
    with pytest.raises(RuntimeError):
        await manager.__aenter__()


@pytest.mark.asyncio
async def test_trace_callback_without_tool_primitive_success():
    async def next_call(tool_name, tool_args):
        return "ok"

    manager = MCPServerManager({})
    callback = manager._create_trace_callback("server")

    result = await callback(None, next_call, "tool", {"x": 1})

    assert result == "ok"


@pytest.mark.asyncio
async def test_trace_callback_without_tool_primitive_failure():
    async def next_call(_tool_name, _tool_args):
        raise RuntimeError("boom")

    manager = MCPServerManager({})
    callback = manager._create_trace_callback("server")

    with pytest.raises(RuntimeError):
        await callback(None, next_call, "tool", {"x": 1})
