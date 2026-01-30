import pytest

from tactus.primitives.toolset import ToolsetPrimitive


class FakeToolset:
    def __init__(self, name="toolset"):
        self.name = name
        self.filtered_calls = []

    def filtered(self, predicate):
        self.filtered_calls.append(predicate)
        return f"filtered:{self.name}"


class FakeRuntime:
    def __init__(self, resolved=None, mcp_toolset=None):
        self._resolved = resolved
        self.tool_primitive = None
        self.mcp_manager = None
        if mcp_toolset is not None:
            self.mcp_manager = type(
                "MCP", (), {"get_toolset_by_name": lambda self, name: mcp_toolset}
            )()

    def resolve_toolset(self, name):
        return self._resolved


def test_define_and_get_from_runtime():
    runtime = FakeRuntime(resolved="runtime-toolset")
    toolset = ToolsetPrimitive(runtime)
    assert toolset.get("anything") == "runtime-toolset"


def test_define_and_get_from_definition(monkeypatch):
    runtime = FakeRuntime()
    toolset = ToolsetPrimitive(runtime)

    fake_toolset = FakeToolset()

    class FakeLoader:
        def __init__(self, tool_primitive=None):
            self.tool_primitive = tool_primitive

        def create_toolset(self, paths, name=None):
            return fake_toolset

    monkeypatch.setattr("tactus.adapters.plugins.PluginLoader", FakeLoader, raising=False)

    toolset.define("plugins", {"type": "plugin", "paths": ["/tmp/tools"]})
    assert toolset.get("plugins") is fake_toolset


def test_get_unknown_raises():
    toolset = ToolsetPrimitive(FakeRuntime())
    with pytest.raises(ValueError, match="not found"):
        toolset.get("missing")


def test_create_mcp_toolset_reference():
    mcp_toolset = FakeToolset("mcp")
    runtime = FakeRuntime(mcp_toolset=mcp_toolset)
    toolset = ToolsetPrimitive(runtime)
    toolset.define("mcp-tools", {"type": "mcp", "server": "srv"})
    assert toolset.get("mcp-tools") is mcp_toolset


def test_plugin_toolset_missing_paths_raises():
    toolset = ToolsetPrimitive(FakeRuntime())
    toolset.define("plugins", {"type": "plugin", "paths": []})
    with pytest.raises(ValueError, match="must specify 'paths'"):
        toolset.get("plugins")


def test_mcp_toolset_missing_server_raises():
    toolset = ToolsetPrimitive(FakeRuntime())
    toolset.define("mcp-tools", {"type": "mcp"})
    with pytest.raises(ValueError, match="must specify 'server'"):
        toolset.get("mcp-tools")


def test_mcp_toolset_missing_manager_raises():
    toolset = ToolsetPrimitive(FakeRuntime())
    toolset.define("mcp-tools", {"type": "mcp", "server": "srv"})
    with pytest.raises(ValueError, match="not configured"):
        toolset.get("mcp-tools")


def test_mcp_toolset_not_found_raises():
    class MissingMcpManager:
        def get_toolset_by_name(self, name):
            return None

    runtime = FakeRuntime()
    runtime.mcp_manager = MissingMcpManager()

    toolset = ToolsetPrimitive(runtime)
    toolset.define("mcp-tools", {"type": "mcp", "server": "srv"})
    with pytest.raises(ValueError, match="not found"):
        toolset.get("mcp-tools")


def test_combined_toolset_missing_sources_raises():
    toolset = ToolsetPrimitive(FakeRuntime())
    toolset.define("combo", {"type": "combined", "sources": []})
    with pytest.raises(ValueError, match="must specify 'sources'"):
        toolset.get("combo")


def test_filtered_toolset_missing_fields_raises():
    toolset = ToolsetPrimitive(FakeRuntime())
    toolset.define("filtered", {"type": "filtered"})
    with pytest.raises(ValueError, match="must specify 'source'"):
        toolset.get("filtered")

    toolset.define("filtered2", {"type": "filtered", "source": "base"})
    with pytest.raises(ValueError, match="must specify 'filter'"):
        toolset.get("filtered2")


def test_unknown_toolset_type_raises():
    toolset = ToolsetPrimitive(FakeRuntime())
    toolset.define("weird", {"type": "unknown"})
    with pytest.raises(ValueError, match="Unknown toolset type"):
        toolset.get("weird")


def test_combined_and_filtered_toolsets(monkeypatch):
    runtime = FakeRuntime()
    toolset = ToolsetPrimitive(runtime)

    a = FakeToolset("a")
    b = FakeToolset("b")

    toolset.definitions = {"a": {"type": "plugin", "paths": ["x"]}}

    class FakeLoader:
        def __init__(self, tool_primitive=None):
            pass

        def create_toolset(self, paths, name=None):
            return a

    monkeypatch.setattr("tactus.adapters.plugins.PluginLoader", FakeLoader, raising=False)

    combined = toolset.combine(a, b)
    assert combined is not None

    filtered = toolset.filter(a, lambda name: name.startswith("a"))
    assert filtered == "filtered:a"


def test_combined_definition_resolves_sources(monkeypatch):
    runtime = FakeRuntime()
    toolset = ToolsetPrimitive(runtime)

    source_a = FakeToolset("a")
    source_b = FakeToolset("b")

    class FakeLoader:
        def __init__(self, tool_primitive=None):
            pass

        def create_toolset(self, paths, name=None):
            return {"a": source_a, "b": source_b}[name]

    monkeypatch.setattr("tactus.adapters.plugins.PluginLoader", FakeLoader, raising=False)

    toolset.define("a", {"type": "plugin", "paths": ["x"]})
    toolset.define("b", {"type": "plugin", "paths": ["y"]})
    toolset.define("combo", {"type": "combined", "sources": ["a", "b"]})

    combined = toolset.get("combo")
    assert combined is not None


def test_filtered_definition_uses_regex(monkeypatch):
    runtime = FakeRuntime()
    toolset = ToolsetPrimitive(runtime)

    source = FakeToolset("source")

    toolset.definitions = {"source": {"type": "plugin", "paths": ["x"]}}

    class FakeLoader:
        def __init__(self, tool_primitive=None):
            pass

        def create_toolset(self, paths, name=None):
            return source

    monkeypatch.setattr("tactus.adapters.plugins.PluginLoader", FakeLoader, raising=False)

    toolset.define("filtered", {"type": "filtered", "source": "source", "filter": "^web_"})
    assert toolset.get("filtered") == "filtered:source"


def test_filtered_definition_calls_predicate(monkeypatch):
    runtime = FakeRuntime()
    toolset = ToolsetPrimitive(runtime)

    class Tool:
        def __init__(self, name):
            self.name = name

    class PredicateToolset:
        def filtered(self, predicate):
            return predicate(None, Tool("web_search"))

    class FakeLoader:
        def __init__(self, tool_primitive=None):
            pass

        def create_toolset(self, paths, name=None):
            return PredicateToolset()

    monkeypatch.setattr("tactus.adapters.plugins.PluginLoader", FakeLoader, raising=False)

    toolset.define("source", {"type": "plugin", "paths": ["x"]})
    toolset.define("filtered", {"type": "filtered", "source": "source", "filter": "^web_"})
    assert toolset.get("filtered") is True


def test_filter_calls_predicate_with_tool_name():
    runtime = FakeRuntime()
    toolset = ToolsetPrimitive(runtime)

    class Tool:
        def __init__(self, name):
            self.name = name

    class PredicateToolset:
        def filtered(self, predicate):
            return predicate(None, Tool("alpha_tool"))

    assert toolset.filter(PredicateToolset(), lambda name: name == "alpha_tool") is True
