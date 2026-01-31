import asyncio
import builtins
import io
import sys
from types import ModuleType

import pytest

from tactus.core.runtime import TactusRuntime


class DummyToolset:
    def __init__(self, name):
        self.name = name
        self.filtered_with = None
        self.prefixed_with = None
        self.renamed_with = None

    def filtered(self, predicate):
        self.filtered_with = predicate
        return self

    def prefixed(self, prefix):
        self.prefixed_with = prefix
        return self

    def renamed(self, rename_map):
        self.renamed_with = rename_map
        return self


class DummyCombinedToolset:
    def __init__(self, toolsets):
        self.toolsets = toolsets


def _runtime():
    runtime = TactusRuntime(procedure_id="proc", hitl_handler=object())
    runtime.toolset_registry = {}
    return runtime


def _run(coro):
    return asyncio.run(coro)


def test_parse_toolset_expressions_simple_and_transformations():
    runtime = _runtime()
    toolset = DummyToolset("tools")
    runtime.toolset_registry["tools"] = toolset

    expressions = [
        "tools",
        {"name": "tools", "include": ["a"], "exclude": ["b"], "prefix": "x_", "rename": {"a": "b"}},
    ]

    result = runtime._parse_toolset_expressions(expressions)

    assert result[0] is toolset
    assert result[1] is toolset
    assert toolset.filtered_with is not None
    assert toolset.prefixed_with == "x_"
    assert toolset.renamed_with == {"a": "b"}
    assert toolset.filtered_with(None, type("Tool", (), {"name": "a"})()) is True
    assert toolset.filtered_with(None, type("Tool", (), {"name": "b"})()) is False


def test_parse_toolset_expressions_unknown_name_raises():
    runtime = _runtime()

    with pytest.raises(ValueError, match="Toolset 'missing' not found"):
        runtime._parse_toolset_expressions(["missing"])


def test_parse_toolset_expressions_dict_unknown_name_raises():
    runtime = _runtime()

    with pytest.raises(ValueError, match="Toolset 'missing' not found"):
        runtime._parse_toolset_expressions([{"name": "missing"}])


def test_parse_toolset_expressions_missing_name_in_dict():
    runtime = _runtime()

    with pytest.raises(ValueError, match="missing 'name'"):
        runtime._parse_toolset_expressions([{"include": ["a"]}])


def test_parse_toolset_expressions_invalid_type():
    runtime = _runtime()

    with pytest.raises(ValueError, match="Invalid toolset expression"):
        runtime._parse_toolset_expressions([123])


def test_parse_toolset_expressions_include_filter_predicate():
    runtime = _runtime()
    toolset = DummyToolset("tools")
    runtime.toolset_registry["tools"] = toolset

    result = runtime._parse_toolset_expressions([{"name": "tools", "include": ["a"]}])

    assert result[0] is toolset
    assert toolset.filtered_with(None, type("Tool", (), {"name": "a"})()) is True
    assert toolset.filtered_with(None, type("Tool", (), {"name": "b"})()) is False


def test_parse_toolset_expressions_exclude_filter_predicate():
    runtime = _runtime()
    toolset = DummyToolset("tools")
    runtime.toolset_registry["tools"] = toolset

    result = runtime._parse_toolset_expressions([{"name": "tools", "exclude": ["a"]}])

    assert result[0] is toolset
    assert toolset.filtered_with(None, type("Tool", (), {"name": "a"})()) is False
    assert toolset.filtered_with(None, type("Tool", (), {"name": "b"})()) is True


@pytest.mark.asyncio
async def test_initialize_toolsets_handles_config_error(monkeypatch):
    runtime = _runtime()
    runtime.config = {"toolsets": {"broken": {}}}
    runtime.registry = type("Registry", (), {"lua_tools": {}, "toolsets": {}})()

    async def raise_error(_name, _definition):
        raise ValueError("nope")

    monkeypatch.setattr(runtime, "_create_toolset_from_config", raise_error)

    await runtime._initialize_toolsets()

    assert "broken" not in runtime.toolset_registry


@pytest.mark.asyncio
async def test_initialize_toolsets_registers_config_toolset(monkeypatch):
    runtime = _runtime()
    runtime.config = {"toolsets": {"good": {"type": "test"}}}
    runtime.registry = type("Registry", (), {"lua_tools": {}, "toolsets": {}})()

    async def create_toolset(_name, _definition):
        return object()

    monkeypatch.setattr(runtime, "_create_toolset_from_config", create_toolset)

    await runtime._initialize_toolsets()

    assert "good" in runtime.toolset_registry


@pytest.mark.asyncio
async def test_initialize_toolsets_skips_none_toolset(monkeypatch):
    runtime = _runtime()
    runtime.config = {"toolsets": {"empty": {"type": "test"}}}
    runtime.registry = type("Registry", (), {"lua_tools": {}, "toolsets": {}})()

    async def create_toolset(_name, _definition):
        return None

    monkeypatch.setattr(runtime, "_create_toolset_from_config", create_toolset)

    await runtime._initialize_toolsets()

    assert "empty" not in runtime.toolset_registry


@pytest.mark.asyncio
async def test_initialize_toolsets_without_registry_toolsets(monkeypatch):
    runtime = _runtime()
    runtime.config = {}
    runtime.registry = type("Registry", (), {"lua_tools": {}})()

    await runtime._initialize_toolsets()


@pytest.mark.asyncio
async def test_initialize_toolsets_mcp_fileno_warning(monkeypatch):
    runtime = _runtime()
    runtime.config = {}
    runtime.registry = type("Registry", (), {"lua_tools": {}, "toolsets": {}})()
    runtime.mcp_servers = {"server": {}}
    runtime.tool_primitive = object()

    class DummyMCPManager:
        def __init__(self, *args, **kwargs):
            raise io.UnsupportedOperation("fileno")

    module = ModuleType("tactus.adapters.mcp_manager")
    module.MCPServerManager = DummyMCPManager
    monkeypatch.setitem(sys.modules, "tactus.adapters.mcp_manager", module)

    await runtime._initialize_toolsets()


@pytest.mark.asyncio
async def test_initialize_toolsets_mcp_toolset_missing(monkeypatch):
    runtime = _runtime()
    runtime.config = {}
    runtime.registry = type("Registry", (), {"lua_tools": {}, "toolsets": {}})()
    runtime.mcp_servers = {"server": {}}
    runtime.tool_primitive = object()

    class DummyMCPManager:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        def get_toolset_by_name(self, _name):
            return None

        def get_toolsets(self):
            return []

    module = ModuleType("tactus.adapters.mcp_manager")
    module.MCPServerManager = DummyMCPManager
    monkeypatch.setitem(sys.modules, "tactus.adapters.mcp_manager", module)

    await runtime._initialize_toolsets()

    assert "server" not in runtime.toolset_registry


@pytest.mark.asyncio
async def test_create_toolset_from_config_inline_tools(monkeypatch):
    runtime = _runtime()
    runtime.tool_primitive = object()
    runtime.mock_manager = object()

    class FakeLuaAdapter:
        def __init__(self, tool_primitive=None, mock_manager=None):
            self.tool_primitive = tool_primitive
            self.mock_manager = mock_manager

        def create_inline_toolset(self, name, tools_list):
            return {"name": name, "tools": tools_list}

    module = ModuleType("tactus.adapters.lua_tools")
    module.LuaToolsAdapter = FakeLuaAdapter
    monkeypatch.setitem(sys.modules, "tactus.adapters.lua_tools", module)

    toolset = await runtime._create_toolset_from_config(
        "inline", {"tools": [{"handler": lambda: "ok"}]}
    )

    assert toolset["name"] == "inline"


@pytest.mark.asyncio
async def test_create_toolset_from_config_tools_list_without_inline(monkeypatch):
    runtime = _runtime()
    runtime.toolset_registry = {"existing": DummyToolset("existing")}

    monkeypatch.setattr("pydantic_ai.toolsets.CombinedToolset", DummyCombinedToolset)
    toolset = await runtime._create_toolset_from_config("named", {"tools": ["existing"]})

    assert isinstance(toolset, DummyCombinedToolset)


@pytest.mark.asyncio
async def test_create_toolset_from_config_tools_tuple(monkeypatch):
    runtime = _runtime()
    runtime.toolset_registry = {"existing": DummyToolset("existing")}

    monkeypatch.setattr("pydantic_ai.toolsets.CombinedToolset", DummyCombinedToolset)
    toolset = await runtime._create_toolset_from_config("named", {"tools": ("existing",)})

    assert isinstance(toolset, DummyCombinedToolset)


@pytest.mark.asyncio
async def test_create_toolset_from_config_dict_tools_without_handlers(monkeypatch):
    runtime = _runtime()
    runtime.toolset_registry = {"existing": DummyToolset("existing")}

    monkeypatch.setattr("pydantic_ai.toolsets.CombinedToolset", DummyCombinedToolset)
    toolset = await runtime._create_toolset_from_config("named", {"tools": ["missing", "existing"]})

    assert isinstance(toolset, DummyCombinedToolset)


@pytest.mark.asyncio
async def test_create_toolset_from_config_inline_tools_with_non_handler(monkeypatch):
    runtime = _runtime()
    runtime.tool_primitive = object()
    runtime.mock_manager = object()

    class FakeLuaAdapter:
        def __init__(self, tool_primitive=None, mock_manager=None):
            self.tool_primitive = tool_primitive
            self.mock_manager = mock_manager

        def create_inline_toolset(self, name, tools_list):
            return {"name": name, "tools": tools_list}

    module = ModuleType("tactus.adapters.lua_tools")
    module.LuaToolsAdapter = FakeLuaAdapter
    monkeypatch.setitem(sys.modules, "tactus.adapters.lua_tools", module)

    toolset = await runtime._create_toolset_from_config(
        "inline", {"tools": [{"name": "noop"}, {"handler": lambda: "ok"}]}
    )

    assert toolset["name"] == "inline"


@pytest.mark.asyncio
async def test_initialize_toolsets_mcp_error(monkeypatch):
    runtime = _runtime()
    runtime.config = {}
    runtime.registry = type("Registry", (), {"lua_tools": {}, "toolsets": {}})()
    runtime.mcp_servers = {"server": {}}
    runtime.tool_primitive = object()

    class DummyMCPManager:
        def __init__(self, *args, **kwargs):
            raise ValueError("boom")

    module = ModuleType("tactus.adapters.mcp_manager")
    module.MCPServerManager = DummyMCPManager
    monkeypatch.setitem(sys.modules, "tactus.adapters.mcp_manager", module)

    await runtime._initialize_toolsets()


@pytest.mark.asyncio
async def test_initialize_toolsets_plugin_import_error(monkeypatch):
    runtime = _runtime()
    runtime.config = {}
    runtime.registry = type("Registry", (), {"lua_tools": {}, "toolsets": {}})()
    runtime.tool_paths = ["./tools"]

    original_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "tactus.adapters.plugins":
            raise ImportError("missing")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    await runtime._initialize_toolsets()


@pytest.mark.asyncio
async def test_initialize_toolsets_plugin_create_error(monkeypatch):
    runtime = _runtime()
    runtime.config = {}
    runtime.registry = type("Registry", (), {"lua_tools": {}, "toolsets": {}})()
    runtime.tool_paths = ["./tools"]

    class DummyPluginLoader:
        def __init__(self, *args, **kwargs):
            pass

        def create_toolset(self, *args, **kwargs):
            raise RuntimeError("nope")

    module = ModuleType("tactus.adapters.plugins")
    module.PluginLoader = DummyPluginLoader
    monkeypatch.setitem(sys.modules, "tactus.adapters.plugins", module)

    await runtime._initialize_toolsets()


@pytest.mark.asyncio
async def test_initialize_toolsets_lua_tools_import_error(monkeypatch):
    runtime = _runtime()
    runtime.config = {}
    runtime.registry = type("Registry", (), {"lua_tools": {"tool": {}}, "toolsets": {}})()

    original_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "tactus.adapters.lua_tools":
            raise ImportError("missing")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    await runtime._initialize_toolsets()


@pytest.mark.asyncio
async def test_initialize_toolsets_lua_tool_create_error(monkeypatch):
    runtime = _runtime()
    runtime.config = {}
    runtime.registry = type("Registry", (), {"lua_tools": {"tool": {}}, "toolsets": {}})()

    class DummyLuaAdapter:
        def __init__(self, *args, **kwargs):
            pass

        def create_single_tool_toolset(self, name, definition):
            raise RuntimeError("boom")

    module = ModuleType("tactus.adapters.lua_tools")
    module.LuaToolsAdapter = DummyLuaAdapter
    monkeypatch.setitem(sys.modules, "tactus.adapters.lua_tools", module)

    await runtime._initialize_toolsets()


@pytest.mark.asyncio
async def test_initialize_toolsets_without_registry():
    runtime = _runtime()
    runtime.config = {}
    runtime.registry = None

    await runtime._initialize_toolsets()


@pytest.mark.asyncio
async def test_initialize_toolsets_dsl_toolset_returns_none(monkeypatch):
    runtime = _runtime()
    runtime.config = {}
    runtime.registry = type(
        "Registry", (), {"lua_tools": {}, "toolsets": {"dsl": {"type": "test"}}}
    )()

    async def create_toolset(_name, _definition):
        return None

    monkeypatch.setattr(runtime, "_create_toolset_from_config", create_toolset)

    await runtime._initialize_toolsets()
    assert "dsl" not in runtime.toolset_registry


@pytest.mark.asyncio
async def test_initialize_toolsets_dsl_toolset_raises(monkeypatch):
    runtime = _runtime()
    runtime.config = {}
    runtime.registry = type(
        "Registry", (), {"lua_tools": {}, "toolsets": {"dsl": {"type": "test"}}}
    )()

    async def create_toolset(_name, _definition):
        raise RuntimeError("boom")

    monkeypatch.setattr(runtime, "_create_toolset_from_config", create_toolset)

    await runtime._initialize_toolsets()


def test_create_toolset_from_config_lua_success(monkeypatch):
    runtime = _runtime()
    runtime.tool_primitive = object()

    class DummyLuaAdapter:
        def __init__(self, *args, **kwargs):
            pass

        def create_lua_toolset(self, name, definition):
            return {"name": name, "definition": definition}

    module = ModuleType("tactus.adapters.lua_tools")
    module.LuaToolsAdapter = DummyLuaAdapter
    monkeypatch.setitem(sys.modules, "tactus.adapters.lua_tools", module)

    toolset = _run(runtime._create_toolset_from_config("lua", {"type": "lua"}))

    assert toolset["name"] == "lua"


def test_create_toolset_from_config_lua_import_error(monkeypatch):
    runtime = _runtime()

    original_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "tactus.adapters.lua_tools":
            raise ImportError("missing")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    toolset = _run(runtime._create_toolset_from_config("lua", {"type": "lua"}))

    assert toolset is None


def test_create_toolset_from_config_plugin_missing_paths():
    runtime = _runtime()

    toolset = _run(runtime._create_toolset_from_config("plugin", {"type": "plugin"}))

    assert toolset is None


def test_create_toolset_from_config_plugin_success(monkeypatch):
    runtime = _runtime()
    runtime.tool_primitive = object()

    class DummyPluginLoader:
        def __init__(self, *args, **kwargs):
            pass

        def create_toolset(self, paths, name=None):
            return {"paths": paths, "name": name}

    module = ModuleType("tactus.adapters.plugins")
    module.PluginLoader = DummyPluginLoader
    monkeypatch.setitem(sys.modules, "tactus.adapters.plugins", module)

    toolset = _run(
        runtime._create_toolset_from_config("plugin", {"type": "plugin", "paths": ["./tools"]})
    )

    assert toolset["name"] == "plugin"


def test_create_toolset_from_config_mcp_missing_server():
    runtime = _runtime()

    toolset = _run(runtime._create_toolset_from_config("mcp", {"type": "mcp"}))

    assert toolset is None


def test_create_toolset_from_config_mcp_resolves_toolset():
    runtime = _runtime()
    runtime.toolset_registry["server"] = DummyToolset("server")

    toolset = _run(runtime._create_toolset_from_config("mcp", {"type": "mcp", "server": "server"}))

    assert toolset is runtime.toolset_registry["server"]


def test_create_toolset_from_config_filtered_missing_source():
    runtime = _runtime()

    toolset = _run(runtime._create_toolset_from_config("filtered", {"type": "filtered"}))

    assert toolset is None


def test_create_toolset_from_config_filtered_no_source_found():
    runtime = _runtime()

    toolset = _run(
        runtime._create_toolset_from_config(
            "filtered",
            {"type": "filtered", "source": "missing"},
        )
    )

    assert toolset is None


def test_create_toolset_from_config_filtered_with_pattern():
    runtime = _runtime()
    runtime.toolset_registry["base"] = DummyToolset("base")

    toolset = _run(
        runtime._create_toolset_from_config(
            "filtered",
            {"type": "filtered", "source": "base", "pattern": "^ok"},
        )
    )

    assert toolset is runtime.toolset_registry["base"]
    assert toolset.filtered_with is not None
    assert toolset.filtered_with(None, type("Tool", (), {"name": "ok_tool"})())
    assert toolset.filtered_with(None, type("Tool", (), {"name": "nope"})()) is None


def test_create_toolset_from_config_filtered_without_pattern():
    runtime = _runtime()
    runtime.toolset_registry["base"] = DummyToolset("base")

    toolset = _run(
        runtime._create_toolset_from_config(
            "filtered",
            {"type": "filtered", "source": "base"},
        )
    )

    assert toolset is runtime.toolset_registry["base"]


def test_create_toolset_from_config_combined_missing_sources():
    runtime = _runtime()

    toolset = _run(runtime._create_toolset_from_config("combined", {"type": "combined"}))

    assert toolset is None


def test_create_toolset_from_config_combined_success(monkeypatch):
    runtime = _runtime()
    runtime.toolset_registry["a"] = DummyToolset("a")
    runtime.toolset_registry["b"] = DummyToolset("b")

    monkeypatch.setattr("pydantic_ai.toolsets.CombinedToolset", DummyCombinedToolset)

    toolset = _run(
        runtime._create_toolset_from_config(
            "combined",
            {"type": "combined", "sources": ["a", "b"]},
        )
    )

    assert [t.name for t in toolset.toolsets] == ["a", "b"]


def test_create_toolset_from_config_combined_partial_sources(monkeypatch):
    runtime = _runtime()
    runtime.toolset_registry["a"] = DummyToolset("a")

    monkeypatch.setattr("pydantic_ai.toolsets.CombinedToolset", DummyCombinedToolset)

    toolset = _run(
        runtime._create_toolset_from_config(
            "combined",
            {"type": "combined", "sources": ["a", "missing"]},
        )
    )

    assert len(toolset.toolsets) == 1


def test_create_toolset_from_config_combined_no_valid_sources(monkeypatch):
    runtime = _runtime()

    monkeypatch.setattr("pydantic_ai.toolsets.CombinedToolset", DummyCombinedToolset)

    toolset = _run(
        runtime._create_toolset_from_config(
            "combined",
            {"type": "combined", "sources": ["missing"]},
        )
    )

    assert toolset is None


def test_create_toolset_from_config_builtin_unimplemented():
    runtime = _runtime()

    toolset = _run(runtime._create_toolset_from_config("builtin", {"type": "builtin"}))

    assert toolset is None


def test_create_toolset_from_config_inline_tools(monkeypatch):  # noqa: F811
    runtime = _runtime()
    runtime.tool_primitive = object()

    class DummyLuaAdapter:
        def __init__(self, *args, **kwargs):
            pass

        def create_inline_toolset(self, name, tools_list):
            return {"name": name, "tools": tools_list}

    module = ModuleType("tactus.adapters.lua_tools")
    module.LuaToolsAdapter = DummyLuaAdapter
    monkeypatch.setitem(sys.modules, "tactus.adapters.lua_tools", module)

    toolset = _run(
        runtime._create_toolset_from_config(
            "inline",
            {"tools": [{"handler": "noop"}]},
        )
    )

    assert toolset["name"] == "inline"


def test_create_toolset_from_config_inline_tools_error(monkeypatch):
    runtime = _runtime()
    runtime.tool_primitive = object()

    class DummyLuaAdapter:
        def __init__(self, *args, **kwargs):
            pass

        def create_inline_toolset(self, *args, **kwargs):
            raise RuntimeError("boom")

    module = ModuleType("tactus.adapters.lua_tools")
    module.LuaToolsAdapter = DummyLuaAdapter
    monkeypatch.setitem(sys.modules, "tactus.adapters.lua_tools", module)

    toolset = _run(
        runtime._create_toolset_from_config(
            "inline",
            {"tools": [{"handler": "noop"}]},
        )
    )

    assert toolset is None


def test_create_toolset_from_config_tool_names(monkeypatch):
    runtime = _runtime()
    runtime.toolset_registry["a"] = DummyToolset("a")

    monkeypatch.setattr("pydantic_ai.toolsets.CombinedToolset", DummyCombinedToolset)

    toolset = _run(
        runtime._create_toolset_from_config(
            "names",
            {"tools": ["a", "missing"]},
        )
    )

    assert toolset.toolsets[0].name == "a"


def test_create_toolset_from_config_tool_names_no_valid(monkeypatch):
    runtime = _runtime()

    monkeypatch.setattr("pydantic_ai.toolsets.CombinedToolset", DummyCombinedToolset)

    toolset = _run(
        runtime._create_toolset_from_config(
            "names",
            {"tools": ["missing"]},
        )
    )

    assert toolset is None


def test_create_toolset_from_config_use_tac_missing(tmp_path):
    runtime = _runtime()
    runtime.source_file_path = str(tmp_path / "main.tac")

    toolset = _run(
        runtime._create_toolset_from_config(
            "use",
            {"use": "./missing.tac"},
        )
    )

    assert toolset is None


def test_create_toolset_from_config_use_tac_wrong_suffix(tmp_path):
    runtime = _runtime()
    runtime.source_file_path = str(tmp_path / "main.tac")
    bad_path = tmp_path / "file.txt"
    bad_path.write_text("content")

    toolset = _run(runtime._create_toolset_from_config("use", {"use": "./file.txt"}))

    assert toolset is None


def test_create_toolset_from_config_use_tac_returns_empty(monkeypatch, tmp_path):
    runtime = _runtime()
    runtime.source_file_path = str(tmp_path / "main.tac")
    tool_path = tmp_path / "tools.tac"
    tool_path.write_text("content")

    class DummyFunctionToolset:
        def __init__(self, tools):
            self.tools = tools

    monkeypatch.setattr("pydantic_ai.toolsets.FunctionToolset", DummyFunctionToolset)

    toolset = _run(
        runtime._create_toolset_from_config(
            "use",
            {"use": "./tools.tac"},
        )
    )

    assert toolset.tools == []


def test_create_toolset_from_config_use_tac_absolute_path(monkeypatch, tmp_path):
    runtime = _runtime()
    tool_path = tmp_path / "tools.tac"
    tool_path.write_text("content")

    class DummyFunctionToolset:
        def __init__(self, tools):
            self.tools = tools

    monkeypatch.setattr("pydantic_ai.toolsets.FunctionToolset", DummyFunctionToolset)

    toolset = _run(runtime._create_toolset_from_config("use", {"use": str(tool_path)}))

    assert toolset.tools == []


def test_create_toolset_from_config_use_mcp():
    runtime = _runtime()
    runtime.toolset_registry["server"] = DummyToolset("server")

    toolset = _run(
        runtime._create_toolset_from_config(
            "use",
            {"use": "mcp.server"},
        )
    )

    assert toolset is runtime.toolset_registry["server"]


def test_create_toolset_from_config_use_unknown():
    runtime = _runtime()

    toolset = _run(
        runtime._create_toolset_from_config(
            "use",
            {"use": "unknown"},
        )
    )

    assert toolset is None


def test_create_toolset_from_config_missing_fields():
    runtime = _runtime()

    toolset = _run(runtime._create_toolset_from_config("bad", {}))

    assert toolset is None


@pytest.mark.asyncio
async def test_initialize_toolsets_lua_tool_source_missing(monkeypatch):
    runtime = _runtime()
    runtime.config = {}
    runtime.tool_primitive = object()
    runtime.registry = type(
        "Registry",
        (),
        {
            "lua_tools": {"tool": {"source": "mcp.missing"}},
            "toolsets": {},
        },
    )()

    class DummyLuaAdapter:
        def __init__(self, *args, **kwargs):
            pass

    module = ModuleType("tactus.adapters.lua_tools")
    module.LuaToolsAdapter = DummyLuaAdapter
    monkeypatch.setitem(sys.modules, "tactus.adapters.lua_tools", module)

    await runtime._initialize_toolsets()
