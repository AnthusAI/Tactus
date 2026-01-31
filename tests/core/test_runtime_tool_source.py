import builtins
import sys
from types import ModuleType

import pytest

from tactus.core.runtime import TactusRuntime


class DummyTool:
    def __init__(self, func, name):
        self.func = func
        self.name = name


class DummyToolset:
    def __init__(self, tools):
        self.tools = tools


class DummyToolPrimitive:
    def __init__(self):
        self.calls = []

    def record_call(self, name, kwargs, result):
        self.calls.append((name, kwargs, result))


class DummyMockManager:
    def __init__(self, response=None):
        self.response = response
        self.calls = []

    def get_mock_response(self, name, kwargs):
        return self.response

    def record_call(self, name, kwargs, result):
        self.calls.append((name, kwargs, result))


class ToggleMockManager:
    def __init__(self, response=None):
        self.response = response
        self.calls = []
        self._bool_calls = 0

    def __bool__(self):
        self._bool_calls += 1
        return self._bool_calls == 1

    def get_mock_response(self, name, kwargs):
        return self.response

    def record_call(self, name, kwargs, result):
        self.calls.append((name, kwargs, result))


class DummyHostPrimitive:
    def __init__(self):
        self.calls = []

    def call(self, name, kwargs):
        self.calls.append((name, kwargs))
        return {"ok": True, "name": name}


@pytest.mark.asyncio
async def test_resolve_tool_source_file_missing(tmp_path):
    runtime = TactusRuntime(procedure_id="proc", hitl_handler=object())
    runtime.source_file_path = str(tmp_path / "main.tac")

    result = await runtime._resolve_tool_source("tool", "./missing.tac")

    assert result is None


@pytest.mark.asyncio
async def test_resolve_tool_source_file_wrong_suffix(tmp_path):
    runtime = TactusRuntime(procedure_id="proc", hitl_handler=object())
    file_path = tmp_path / "tool.txt"
    file_path.write_text("content")

    result = await runtime._resolve_tool_source("tool", str(file_path))

    assert result is None


@pytest.mark.asyncio
async def test_resolve_tool_source_file_loads_and_returns_none(tmp_path):
    runtime = TactusRuntime(procedure_id="proc", hitl_handler=object())
    runtime.source_file_path = str(tmp_path / "main.tac")

    tool_file = tmp_path / "tool.tac"
    tool_file.write_text("tool content")

    class DummyLuaRuntime:
        def __init__(self):
            self.executed = []

        def execute(self, content):
            self.executed.append(content)

    runtime.sandbox = type("Sandbox", (), {"runtime": DummyLuaRuntime()})()

    result = await runtime._resolve_tool_source("tool", str(tool_file))

    assert result is None


@pytest.mark.asyncio
async def test_resolve_tool_source_file_read_error(monkeypatch, tmp_path):
    runtime = TactusRuntime(procedure_id="proc", hitl_handler=object())
    runtime.source_file_path = str(tmp_path / "main.tac")

    tool_file = tmp_path / "tool.tac"
    tool_file.write_text("tool content")

    runtime.sandbox = type("Sandbox", (), {"runtime": object()})()

    def fake_open(*args, **kwargs):
        raise OSError("read failed")

    monkeypatch.setattr("builtins.open", fake_open)

    result = await runtime._resolve_tool_source("tool", str(tool_file))

    assert result is None


@pytest.mark.asyncio
async def test_resolve_tool_source_mcp_missing():
    runtime = TactusRuntime(procedure_id="proc", hitl_handler=object())
    runtime.toolset_registry = {}

    result = await runtime._resolve_tool_source("tool", "mcp.missing")

    assert result is None


@pytest.mark.asyncio
async def test_resolve_tool_source_mcp_found():
    runtime = TactusRuntime(procedure_id="proc", hitl_handler=object())
    toolset = DummyToolset([DummyTool(lambda: None, "noop")])
    runtime.toolset_registry = {"server": toolset}

    result = await runtime._resolve_tool_source("tool", "mcp.server")

    assert result is toolset


@pytest.mark.asyncio
async def test_resolve_tool_source_plugin_invalid_format():
    runtime = TactusRuntime(procedure_id="proc", hitl_handler=object())

    result = await runtime._resolve_tool_source("tool", "plugin.badformat")

    assert result is None


@pytest.mark.asyncio
async def test_resolve_tool_source_plugin_module_missing():
    runtime = TactusRuntime(procedure_id="proc", hitl_handler=object())

    result = await runtime._resolve_tool_source("tool", "plugin.missing.module")

    assert result is None


@pytest.mark.asyncio
async def test_resolve_tool_source_plugin_function_missing(monkeypatch):
    runtime = TactusRuntime(procedure_id="proc", hitl_handler=object())
    module = ModuleType("sample_plugin")
    monkeypatch.setitem(sys.modules, "sample_plugin", module)

    result = await runtime._resolve_tool_source("tool", "plugin.sample_plugin.missing")

    assert result is None


@pytest.mark.asyncio
async def test_resolve_tool_source_plugin_tool_error(monkeypatch):
    runtime = TactusRuntime(procedure_id="proc", hitl_handler=object())

    module = ModuleType("sample_plugin_error")
    module.do_it = lambda value: {"ok": value}
    monkeypatch.setitem(sys.modules, "sample_plugin_error", module)

    class BoomTool:
        def __init__(self, *args, **kwargs):
            raise RuntimeError("boom")

    monkeypatch.setattr("pydantic_ai.toolsets.FunctionToolset", DummyToolset)
    monkeypatch.setattr("pydantic_ai.Tool", BoomTool)

    toolset = await runtime._resolve_tool_source("my_tool", "plugin.sample_plugin_error.do_it")
    assert toolset is None


@pytest.mark.asyncio
async def test_resolve_tool_source_plugin_success(monkeypatch):
    runtime = TactusRuntime(procedure_id="proc", hitl_handler=object())
    runtime.tool_primitive = DummyToolPrimitive()
    runtime.mock_manager = DummyMockManager(response=None)

    module = ModuleType("sample_plugin_success")
    module.do_it = lambda value: {"ok": value}
    monkeypatch.setitem(sys.modules, "sample_plugin_success", module)

    monkeypatch.setattr("pydantic_ai.toolsets.FunctionToolset", DummyToolset)
    monkeypatch.setattr("pydantic_ai.Tool", DummyTool)

    toolset = await runtime._resolve_tool_source("my_tool", "plugin.sample_plugin_success.do_it")

    assert toolset.tools[0].name == "my_tool"
    result = toolset.tools[0].func(value=2)
    assert result == {"ok": 2}
    assert runtime.tool_primitive.calls[0][0] == "my_tool"


@pytest.mark.asyncio
async def test_resolve_tool_source_plugin_no_tracking(monkeypatch):
    runtime = TactusRuntime(procedure_id="proc", hitl_handler=object())
    runtime.tool_primitive = None
    runtime.mock_manager = None

    module = ModuleType("sample_plugin_no_track")
    module.do_it = lambda value: {"ok": value}
    monkeypatch.setitem(sys.modules, "sample_plugin_no_track", module)

    monkeypatch.setattr("pydantic_ai.toolsets.FunctionToolset", DummyToolset)
    monkeypatch.setattr("pydantic_ai.Tool", DummyTool)

    toolset = await runtime._resolve_tool_source("my_tool", "plugin.sample_plugin_no_track.do_it")

    result = toolset.tools[0].func(value=5)
    assert result == {"ok": 5}


@pytest.mark.asyncio
async def test_resolve_tool_source_plugin_mock_response(monkeypatch):
    runtime = TactusRuntime(procedure_id="proc", hitl_handler=object())
    runtime.tool_primitive = DummyToolPrimitive()
    runtime.mock_manager = DummyMockManager(response={"mock": True})

    module = ModuleType("sample_plugin_mock")
    module.do_it = lambda value: {"ok": value}
    monkeypatch.setitem(sys.modules, "sample_plugin_mock", module)

    monkeypatch.setattr("pydantic_ai.toolsets.FunctionToolset", DummyToolset)
    monkeypatch.setattr("pydantic_ai.Tool", DummyTool)

    toolset = await runtime._resolve_tool_source("my_tool", "plugin.sample_plugin_mock.do_it")

    result = toolset.tools[0].func(value=7)
    assert result == {"mock": True}
    assert runtime.tool_primitive.calls[0][0] == "my_tool"
    assert runtime.mock_manager.calls[0][0] == "my_tool"


@pytest.mark.asyncio
async def test_resolve_tool_source_plugin_mock_response_without_tracking(monkeypatch):
    runtime = TactusRuntime(procedure_id="proc", hitl_handler=object())
    runtime.tool_primitive = None
    runtime.mock_manager = ToggleMockManager(response={"mock": True})

    module = ModuleType("sample_plugin_mock_toggle")
    module.do_it = lambda value: {"ok": value}
    monkeypatch.setitem(sys.modules, "sample_plugin_mock_toggle", module)

    monkeypatch.setattr("pydantic_ai.toolsets.FunctionToolset", DummyToolset)
    monkeypatch.setattr("pydantic_ai.Tool", DummyTool)

    toolset = await runtime._resolve_tool_source(
        "my_tool", "plugin.sample_plugin_mock_toggle.do_it"
    )

    result = toolset.tools[0].func(value=7)
    assert result == {"mock": True}


@pytest.mark.asyncio
async def test_resolve_tool_source_cli_mock_response(monkeypatch):
    runtime = TactusRuntime(procedure_id="proc", hitl_handler=object())
    runtime.tool_primitive = DummyToolPrimitive()
    runtime.mock_manager = DummyMockManager(response={"mock": True})

    monkeypatch.setattr("pydantic_ai.toolsets.FunctionToolset", DummyToolset)
    monkeypatch.setattr("pydantic_ai.Tool", DummyTool)

    toolset = await runtime._resolve_tool_source("cli_tool", "cli.echo")

    result = toolset.tools[0].func(message="hi")
    assert result == {"mock": True}
    assert runtime.tool_primitive.calls[0][0] == "cli_tool"
    assert runtime.mock_manager.calls[0][0] == "cli_tool"


@pytest.mark.asyncio
async def test_resolve_tool_source_cli_mock_response_without_tracking(monkeypatch):
    runtime = TactusRuntime(procedure_id="proc", hitl_handler=object())
    runtime.tool_primitive = None
    runtime.mock_manager = ToggleMockManager(response={"mock": True})

    monkeypatch.setattr("pydantic_ai.toolsets.FunctionToolset", DummyToolset)
    monkeypatch.setattr("pydantic_ai.Tool", DummyTool)

    toolset = await runtime._resolve_tool_source("cli_tool", "cli.echo")

    result = toolset.tools[0].func(message="hi")
    assert result == {"mock": True}


@pytest.mark.asyncio
async def test_resolve_tool_source_cli_mock_response_without_tool_primitive(monkeypatch):
    runtime = TactusRuntime(procedure_id="proc", hitl_handler=object())
    runtime.tool_primitive = None
    runtime.mock_manager = DummyMockManager(response={"mock": True})

    monkeypatch.setattr("pydantic_ai.toolsets.FunctionToolset", DummyToolset)
    monkeypatch.setattr("pydantic_ai.Tool", DummyTool)

    toolset = await runtime._resolve_tool_source("cli_tool", "cli.echo")

    result = toolset.tools[0].func(message="hi")
    assert result == {"mock": True}


@pytest.mark.asyncio
async def test_resolve_tool_source_cli_success_json(monkeypatch):
    import subprocess

    runtime = TactusRuntime(procedure_id="proc", hitl_handler=object())
    runtime.tool_primitive = DummyToolPrimitive()
    runtime.mock_manager = None

    class DummyResult:
        def __init__(self):
            self.stdout = '{"ok": true}'
            self.stderr = ""
            self.returncode = 0

    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: DummyResult())
    monkeypatch.setattr("pydantic_ai.toolsets.FunctionToolset", DummyToolset)
    monkeypatch.setattr("pydantic_ai.Tool", DummyTool)

    toolset = await runtime._resolve_tool_source("cli_tool", "cli.echo")

    result = toolset.tools[0].func(flag=True, count=2, args=["one", "two"])
    assert result["success"] is True
    assert result["json"] == {"ok": True}


@pytest.mark.asyncio
async def test_resolve_tool_source_cli_builds_flags(monkeypatch):
    import subprocess

    runtime = TactusRuntime(procedure_id="proc", hitl_handler=object())
    runtime.tool_primitive = None
    runtime.mock_manager = None

    captured = {}

    class DummyResult:
        def __init__(self):
            self.stdout = "ok"
            self.stderr = ""
            self.returncode = 0

    def fake_run(cmd, **_kwargs):
        captured["cmd"] = cmd
        return DummyResult()

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr("pydantic_ai.toolsets.FunctionToolset", DummyToolset)
    monkeypatch.setattr("pydantic_ai.Tool", DummyTool)

    toolset = await runtime._resolve_tool_source("cli_tool", "cli.echo")
    toolset.tools[0].func(verbose=False, file=None, args=["one"])

    assert captured["cmd"] == ["echo", "one"]


@pytest.mark.asyncio
async def test_resolve_tool_source_cli_mock_manager_falls_through(monkeypatch):
    import subprocess

    runtime = TactusRuntime(procedure_id="proc", hitl_handler=object())
    runtime.tool_primitive = DummyToolPrimitive()
    runtime.mock_manager = DummyMockManager(response=None)

    class DummyResult:
        def __init__(self):
            self.stdout = "ok"
            self.stderr = ""
            self.returncode = 0

    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: DummyResult())
    monkeypatch.setattr("pydantic_ai.toolsets.FunctionToolset", DummyToolset)
    monkeypatch.setattr("pydantic_ai.Tool", DummyTool)

    toolset = await runtime._resolve_tool_source("cli_tool", "cli.echo")

    result = toolset.tools[0].func()
    assert result["success"] is True


@pytest.mark.asyncio
async def test_resolve_tool_source_cli_timeout(monkeypatch):
    import subprocess

    runtime = TactusRuntime(procedure_id="proc", hitl_handler=object())
    runtime.tool_primitive = DummyToolPrimitive()

    def raise_timeout(*_args, **_kwargs):
        raise subprocess.TimeoutExpired(cmd=["cli"], timeout=30)

    monkeypatch.setattr(subprocess, "run", raise_timeout)
    monkeypatch.setattr("pydantic_ai.toolsets.FunctionToolset", DummyToolset)
    monkeypatch.setattr("pydantic_ai.Tool", DummyTool)

    toolset = await runtime._resolve_tool_source("cli_tool", "cli.echo")

    result = toolset.tools[0].func()
    assert result["success"] is False
    assert "timed out" in result["error"]


@pytest.mark.asyncio
async def test_resolve_tool_source_cli_timeout_without_tool_primitive(monkeypatch):
    import subprocess

    runtime = TactusRuntime(procedure_id="proc", hitl_handler=object())
    runtime.tool_primitive = None

    def raise_timeout(*_args, **_kwargs):
        raise subprocess.TimeoutExpired(cmd=["cli"], timeout=30)

    monkeypatch.setattr(subprocess, "run", raise_timeout)
    monkeypatch.setattr("pydantic_ai.toolsets.FunctionToolset", DummyToolset)
    monkeypatch.setattr("pydantic_ai.Tool", DummyTool)

    toolset = await runtime._resolve_tool_source("cli_tool", "cli.echo")
    result = toolset.tools[0].func()
    assert result["success"] is False


@pytest.mark.asyncio
async def test_resolve_tool_source_cli_error(monkeypatch):
    import subprocess

    runtime = TactusRuntime(procedure_id="proc", hitl_handler=object())
    runtime.tool_primitive = DummyToolPrimitive()

    def raise_error(*_args, **_kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(subprocess, "run", raise_error)
    monkeypatch.setattr("pydantic_ai.toolsets.FunctionToolset", DummyToolset)
    monkeypatch.setattr("pydantic_ai.Tool", DummyTool)

    toolset = await runtime._resolve_tool_source("cli_tool", "cli.echo")

    result = toolset.tools[0].func()
    assert result["success"] is False


@pytest.mark.asyncio
async def test_resolve_tool_source_cli_error_without_tool_primitive(monkeypatch):
    import subprocess

    runtime = TactusRuntime(procedure_id="proc", hitl_handler=object())
    runtime.tool_primitive = None

    def raise_error(*_args, **_kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(subprocess, "run", raise_error)
    monkeypatch.setattr("pydantic_ai.toolsets.FunctionToolset", DummyToolset)
    monkeypatch.setattr("pydantic_ai.Tool", DummyTool)

    toolset = await runtime._resolve_tool_source("cli_tool", "cli.echo")
    result = toolset.tools[0].func()
    assert result["success"] is False
    assert "boom" in result["error"]


@pytest.mark.asyncio
async def test_resolve_tool_source_cli_json_decode_error(monkeypatch):
    import subprocess

    runtime = TactusRuntime(procedure_id="proc", hitl_handler=object())
    runtime.tool_primitive = DummyToolPrimitive()

    class DummyResult:
        def __init__(self):
            self.stdout = "{bad json"
            self.stderr = ""
            self.returncode = 0

    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: DummyResult())
    monkeypatch.setattr("pydantic_ai.toolsets.FunctionToolset", DummyToolset)
    monkeypatch.setattr("pydantic_ai.Tool", DummyTool)

    toolset = await runtime._resolve_tool_source("cli_tool", "cli.echo")

    result = toolset.tools[0].func()
    assert result["success"] is True
    assert "json" not in result


@pytest.mark.asyncio
async def test_resolve_tool_source_cli_wrapper_import_error(monkeypatch):
    runtime = TactusRuntime(procedure_id="proc", hitl_handler=object())

    original_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "pydantic_ai.toolsets":
            raise ImportError("missing")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    toolset = await runtime._resolve_tool_source("cli_tool", "cli.echo")

    assert toolset is None


@pytest.mark.asyncio
async def test_resolve_tool_source_broker_invalid():
    runtime = TactusRuntime(procedure_id="proc", hitl_handler=object())

    result = await runtime._resolve_tool_source("broker_tool", "broker.")

    assert result is None


@pytest.mark.asyncio
async def test_resolve_tool_source_broker_mock_response(monkeypatch):
    runtime = TactusRuntime(procedure_id="proc", hitl_handler=object())
    runtime.tool_primitive = DummyToolPrimitive()
    runtime.mock_manager = DummyMockManager(response={"mock": True})
    runtime.host_primitive = DummyHostPrimitive()

    monkeypatch.setattr("pydantic_ai.toolsets.FunctionToolset", DummyToolset)
    monkeypatch.setattr("pydantic_ai.Tool", DummyTool)

    toolset = await runtime._resolve_tool_source("broker_tool", "broker.ping")

    result = toolset.tools[0].func(value=1)
    assert result == {"mock": True}
    assert runtime.tool_primitive.calls[0][0] == "broker_tool"
    assert runtime.mock_manager.calls[0][0] == "broker_tool"


@pytest.mark.asyncio
async def test_resolve_tool_source_broker_mock_response_without_tool_primitive(monkeypatch):
    runtime = TactusRuntime(procedure_id="proc", hitl_handler=object())
    runtime.tool_primitive = None
    runtime.mock_manager = DummyMockManager(response={"mock": True})
    runtime.host_primitive = DummyHostPrimitive()

    monkeypatch.setattr("pydantic_ai.toolsets.FunctionToolset", DummyToolset)
    monkeypatch.setattr("pydantic_ai.Tool", DummyTool)

    toolset = await runtime._resolve_tool_source("broker_tool", "broker.ping")

    result = toolset.tools[0].func(value=1)
    assert result == {"mock": True}


@pytest.mark.asyncio
async def test_resolve_tool_source_broker_mock_manager_falls_through(monkeypatch):
    runtime = TactusRuntime(procedure_id="proc", hitl_handler=object())
    runtime.tool_primitive = DummyToolPrimitive()
    runtime.mock_manager = DummyMockManager(response=None)
    runtime.host_primitive = DummyHostPrimitive()

    monkeypatch.setattr("pydantic_ai.toolsets.FunctionToolset", DummyToolset)
    monkeypatch.setattr("pydantic_ai.Tool", DummyTool)

    toolset = await runtime._resolve_tool_source("broker_tool", "broker.ping")

    result = toolset.tools[0].func(value=3)
    assert result["ok"] is True


@pytest.mark.asyncio
async def test_resolve_tool_source_broker_success_without_tool_primitive(monkeypatch):
    runtime = TactusRuntime(procedure_id="proc", hitl_handler=object())
    runtime.tool_primitive = None
    runtime.mock_manager = None
    runtime.host_primitive = DummyHostPrimitive()

    monkeypatch.setattr("pydantic_ai.toolsets.FunctionToolset", DummyToolset)
    monkeypatch.setattr("pydantic_ai.Tool", DummyTool)

    toolset = await runtime._resolve_tool_source("broker_tool", "broker.ping")

    result = toolset.tools[0].func(value=2)
    assert result["ok"] is True


@pytest.mark.asyncio
async def test_resolve_tool_source_broker_success(monkeypatch):
    runtime = TactusRuntime(procedure_id="proc", hitl_handler=object())
    runtime.tool_primitive = DummyToolPrimitive()
    runtime.mock_manager = None
    runtime.host_primitive = DummyHostPrimitive()

    monkeypatch.setattr("pydantic_ai.toolsets.FunctionToolset", DummyToolset)
    monkeypatch.setattr("pydantic_ai.Tool", DummyTool)

    toolset = await runtime._resolve_tool_source("broker_tool", "broker.ping")

    result = toolset.tools[0].func(value=2)
    assert result["ok"] is True
    assert runtime.host_primitive.calls[0][0] == "ping"
    assert runtime.tool_primitive.calls[0][0] == "broker_tool"


@pytest.mark.asyncio
async def test_resolve_tool_source_broker_wrapper_error(monkeypatch):
    runtime = TactusRuntime(procedure_id="proc", hitl_handler=object())
    runtime.host_primitive = DummyHostPrimitive()

    class BoomTool:
        def __init__(self, *args, **kwargs):
            raise RuntimeError("boom")

    monkeypatch.setattr("pydantic_ai.toolsets.FunctionToolset", DummyToolset)
    monkeypatch.setattr("pydantic_ai.Tool", BoomTool)

    toolset = await runtime._resolve_tool_source("broker_tool", "broker.ping")

    assert toolset is None


@pytest.mark.asyncio
async def test_resolve_tool_source_unknown_source():
    runtime = TactusRuntime(procedure_id="proc", hitl_handler=object())

    result = await runtime._resolve_tool_source("tool", "unknown.source")

    assert result is None


@pytest.mark.asyncio
async def test_resolve_tool_source_plugin_mock_response(monkeypatch):  # noqa: F811
    runtime = TactusRuntime(procedure_id="proc", hitl_handler=object())
    runtime.tool_primitive = DummyToolPrimitive()
    runtime.mock_manager = DummyMockManager(response={"mock": True})

    module = ModuleType("sample_plugin_mock")
    module.do_it = lambda value: {"ok": value}
    monkeypatch.setitem(sys.modules, "sample_plugin_mock", module)

    monkeypatch.setattr("pydantic_ai.toolsets.FunctionToolset", DummyToolset)
    monkeypatch.setattr("pydantic_ai.Tool", DummyTool)

    toolset = await runtime._resolve_tool_source("my_tool", "plugin.sample_plugin_mock.do_it")

    result = toolset.tools[0].func(value=3)
    assert result == {"mock": True}
    assert runtime.mock_manager.calls[0][0] == "my_tool"
