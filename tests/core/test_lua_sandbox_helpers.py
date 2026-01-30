import pytest
import sys
import importlib

from tactus.core import lua_sandbox as lua_module


class DummyLuaTable(dict):
    pass


class DummyGlobals:
    def __init__(self, pairs_func):
        self._pairs = pairs_func

    def pairs(self, table):
        return self._pairs(table)


class DummyLua:
    def __init__(self):
        self._globals = {}
        self.table_from = DummyLuaTable
        self.executed = []

    def globals(self):
        return self._globals

    def table(self, **kwargs):
        table = DummyLuaTable()
        table.update(kwargs)
        return table

    def eval(self, _expr):
        raise lua_module.lupa.LuaError("bad eval")

    def execute(self, _code):
        self.executed.append(_code)
        raise lua_module.lupa.LuaError("bad exec")


class DummyLuaSuccess(DummyLua):
    def execute(self, _code):
        self.executed.append(_code)
        return None


def test_lua_sandbox_init_without_lupa(monkeypatch):
    monkeypatch.setattr(lua_module, "LUPA_AVAILABLE", False)
    monkeypatch.setattr(lua_module, "LuaRuntime", None)

    with pytest.raises(lua_module.LuaSandboxError):
        lua_module.LuaSandbox()


def test_attribute_filter_blocks_private_and_dangerous():
    sandbox = lua_module.LuaSandbox.__new__(lua_module.LuaSandbox)

    with pytest.raises(AttributeError):
        sandbox._attribute_filter(object(), "_private", False)

    with pytest.raises(AttributeError):
        sandbox._attribute_filter(object(), "eval", False)

    assert sandbox._attribute_filter(object(), "safe", False) == "safe"


def test_set_global_and_dict_conversion():
    sandbox = lua_module.LuaSandbox.__new__(lua_module.LuaSandbox)
    sandbox.lua = DummyLua()

    sandbox.set_global("config", {"a": {"b": 2}})

    assert isinstance(sandbox.lua.globals()["config"], DummyLuaTable)
    assert sandbox.lua.globals()["config"]["a"]["b"] == 2


def test_create_lua_table_and_to_dict():
    sandbox = lua_module.LuaSandbox.__new__(lua_module.LuaSandbox)
    sandbox.lua = DummyLua()

    empty = sandbox.create_lua_table()
    assert isinstance(empty, DummyLuaTable)

    table = sandbox.create_lua_table({"a": 1})
    assert table["a"] == 1

    def pairs_func(table_obj):
        return table_obj.items()

    sandbox.lua.globals = lambda: DummyGlobals(pairs_func)
    nested = DummyLuaTable({"k": DummyLuaTable({"v": 2})})

    result = sandbox.lua_table_to_dict(nested)
    assert result == {"k": {"v": 2}}


def test_execute_and_eval_errors(monkeypatch):
    pytest.importorskip("lupa")
    sandbox = lua_module.LuaSandbox.__new__(lua_module.LuaSandbox)
    sandbox.lua = DummyLua()

    with pytest.raises(lua_module.LuaSandboxError):
        sandbox.execute("print('hi')")

    with pytest.raises(lua_module.LuaSandboxError):
        sandbox.eval("1+1")


def test_setup_safe_globals_without_context_sets_os_date():
    sandbox = lua_module.LuaSandbox.__new__(lua_module.LuaSandbox)
    sandbox.lua = DummyLuaSuccess()
    sandbox.execution_context = None

    sandbox._setup_safe_globals()

    safe_os = sandbox.lua.globals()["os"]
    assert "date" in safe_os
    assert isinstance(safe_os["date"](), str)
    assert isinstance(safe_os["date"](object()), str)
    assert "T" in safe_os["date"]("%Y-%m-%dT%H:%M:%SZ")


def test_lua_sandbox_import_handles_missing_lupa(monkeypatch):
    import builtins

    original_import = builtins.__import__
    original_lupa = sys.modules.get("lupa")

    def fake_import(name, *args, **kwargs):
        if name == "lupa":
            raise ImportError("nope")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    sys.modules.pop("lupa", None)

    reloaded = importlib.reload(lua_module)
    assert reloaded.LUPA_AVAILABLE is False
    assert reloaded.LuaRuntime is None

    monkeypatch.undo()
    if original_lupa is not None:
        sys.modules["lupa"] = original_lupa
    else:
        sys.modules.pop("lupa", None)
    importlib.reload(lua_module)


def test_setup_safe_globals_with_context_installs_safe_libraries(monkeypatch):
    sandbox = lua_module.LuaSandbox.__new__(lua_module.LuaSandbox)
    sandbox.lua = DummyLua()
    sandbox.execution_context = object()
    sandbox.strict_determinism = False

    def fake_math(get_context, strict):
        assert get_context() is sandbox.execution_context
        assert strict is False
        return {"sqrt": 2}

    def fake_os(get_context, strict):
        assert get_context() is sandbox.execution_context
        assert strict is False
        return {"date": "ok"}

    monkeypatch.setattr("tactus.utils.safe_libraries.create_safe_math_library", fake_math)
    monkeypatch.setattr("tactus.utils.safe_libraries.create_safe_os_library", fake_os)

    sandbox._setup_safe_globals()

    assert sandbox.lua.globals()["math"]["sqrt"] == 2
    assert sandbox.lua.globals()["os"]["date"] == "ok"


def test_setup_safe_require_without_package_logs_warning(monkeypatch):
    sandbox = lua_module.LuaSandbox.__new__(lua_module.LuaSandbox)
    sandbox.lua = DummyLua()
    sandbox.lua.globals()["package"] = None
    sandbox.base_path = "/tmp"

    monkeypatch.setattr(sandbox, "_setup_python_stdlib_loader", lambda: None)

    sandbox._setup_safe_require()


def test_setup_assignment_interception_error(monkeypatch):
    sandbox = lua_module.LuaSandbox.__new__(lua_module.LuaSandbox)
    sandbox.lua = DummyLua()

    def fail_execute(_code):
        raise Exception("nope")

    monkeypatch.setattr(sandbox.lua, "execute", fail_execute)

    with pytest.raises(lua_module.LuaSandboxError):
        sandbox.setup_assignment_interception(lambda *_args: None)


def test_remove_dangerous_modules_and_safe_debug():
    sandbox = lua_module.LuaSandbox.__new__(lua_module.LuaSandbox)
    sandbox.lua = DummyLuaSuccess()
    sandbox.lua.globals().update({"io": object(), "os": object(), "debug": object()})

    sandbox._remove_dangerous_modules()

    assert sandbox.lua.globals()["io"] is None
    assert sandbox.lua.globals()["os"] is None
    assert sandbox.lua.executed


def test_remove_dangerous_modules_without_debug():
    sandbox = lua_module.LuaSandbox.__new__(lua_module.LuaSandbox)
    sandbox.lua = DummyLuaSuccess()
    sandbox.lua.globals().update({"io": object(), "os": object()})

    sandbox._remove_dangerous_modules()

    assert sandbox.lua.globals()["io"] is None
    assert sandbox.lua.globals()["os"] is None
    assert sandbox.lua.executed == []


def test_setup_safe_require_with_package(monkeypatch):
    sandbox = lua_module.LuaSandbox.__new__(lua_module.LuaSandbox)
    sandbox.lua = DummyLuaSuccess()
    sandbox.base_path = "/tmp"
    sandbox.lua.globals()["package"] = {"preload": {"a": 1}, "loaders": []}

    class DummyLoader:
        def __init__(self, *_args, **_kwargs):
            pass

        def create_loader_function(self):
            return lambda _name: None

    monkeypatch.setattr("tactus.stdlib.loader.StdlibModuleLoader", DummyLoader)

    sandbox._setup_safe_require()

    assert "_tactus_python_loader" in sandbox.lua.globals()
    assert sandbox.lua.globals()["package"]["cpath"] == ""


def test_setup_safe_require_with_empty_preload(monkeypatch):
    sandbox = lua_module.LuaSandbox.__new__(lua_module.LuaSandbox)
    sandbox.lua = DummyLuaSuccess()
    sandbox.base_path = "/tmp"
    sandbox.lua.globals()["package"] = {"preload": {}, "loaders": []}

    class DummyLoader:
        def __init__(self, *_args, **_kwargs):
            pass

        def create_loader_function(self):
            return lambda _name: None

    monkeypatch.setattr("tactus.stdlib.loader.StdlibModuleLoader", DummyLoader)

    sandbox._setup_safe_require()

    assert len(sandbox.lua.executed) == 1


def test_lua_table_to_dict_fallback_iteration():
    sandbox = lua_module.LuaSandbox.__new__(lua_module.LuaSandbox)
    sandbox.lua = DummyLuaSuccess()

    class DummyGlobalsError:
        def pairs(self, _table):
            raise RuntimeError("boom")

    sandbox.lua.globals = lambda: DummyGlobalsError()

    table = DummyLuaTable({"a": 1})
    assert sandbox.lua_table_to_dict(table) == {"a": 1}


def test_lua_table_to_dict_fallback_iteration_failure():
    sandbox = lua_module.LuaSandbox.__new__(lua_module.LuaSandbox)
    sandbox.lua = DummyLuaSuccess()

    class DummyGlobalsError:
        def pairs(self, _table):
            raise RuntimeError("boom")

    class BadTable:
        def __iter__(self):
            raise TypeError("nope")

        def __getitem__(self, _key):
            raise KeyError("nope")

    sandbox.lua.globals = lambda: DummyGlobalsError()

    assert sandbox.lua_table_to_dict(BadTable()) == {}


def test_dict_to_lua_table_nested():
    sandbox = lua_module.LuaSandbox.__new__(lua_module.LuaSandbox)
    sandbox.lua = DummyLuaSuccess()

    table = sandbox._dict_to_lua_table({"a": {"b": 2}})
    assert isinstance(table, DummyLuaTable)
    assert table["a"]["b"] == 2
