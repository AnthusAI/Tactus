import importlib
import sys
import typing

import pytest

from tactus.primitives.tool import ToolPrimitive
from tactus.primitives.tool_handle import ToolHandle


def test_tool_handle_sync_call_records():
    primitive = ToolPrimitive()

    def impl(args):
        return args["x"] + 1

    handle = ToolHandle("inc", impl, tool_primitive=primitive)
    result = handle({"x": 1})
    assert result == 2
    assert primitive.called("inc") is True
    assert handle.last_result() == 2


def test_tool_handle_async_call():
    async def impl(args):
        return args["x"] * 2

    handle = ToolHandle("double", impl, is_async=True)
    result = handle({"x": 2})
    assert result == 4


def test_tool_handle_helpers_without_primitive():
    handle = ToolHandle("noop", lambda args: "ok")
    assert handle.called() is False
    assert handle.last_call() is None
    assert handle.last_result() is None
    assert handle.call_count() == 0
    handle.reset()


def test_tool_handle_normalizes_none_arguments():
    handle = ToolHandle("noop", lambda args: args)
    assert handle.call(None) == {}


def test_tool_handle_call_count_and_reset():
    primitive = ToolPrimitive()
    handle = ToolHandle("count", lambda args: args["x"], tool_primitive=primitive)
    handle({"x": 1})
    handle({"x": 2})
    assert handle.call_count() == 2
    handle.reset()
    assert handle.call_count() == 0


def test_lua_table_to_dict_nested():
    handle = ToolHandle("noop", lambda args: args)
    data = {"a": {"b": 1}}
    assert handle._lua_table_to_dict(data) == data


def test_lua_table_to_dict_none_and_scalar():
    handle = ToolHandle("noop", lambda args: args)
    assert handle._lua_table_to_dict(None) == {}
    assert handle._lua_table_to_dict("x") == "x"


@pytest.mark.asyncio
async def test_run_async_with_running_loop_and_nest_asyncio(monkeypatch):
    async def impl(_args):
        return "ok"

    handle = ToolHandle("async", impl, is_async=True)

    class DummyNest:
        @staticmethod
        def apply(loop):
            return loop

    monkeypatch.setitem(sys.modules, "nest_asyncio", DummyNest)

    def fake_run(coro):
        coro.close()
        return "done"

    monkeypatch.setattr("tactus.primitives.tool_handle.asyncio.run", fake_run)

    result = handle.call({"x": 1})
    assert result == "done"


@pytest.mark.asyncio
async def test_run_async_with_running_loop_without_nest_asyncio(monkeypatch):
    async def impl(_args):
        return "ok"

    handle = ToolHandle("async", impl, is_async=True)

    orig_import = __import__

    def fake_import(name, *args, **kwargs):
        if name == "nest_asyncio":
            raise ImportError("no")
        return orig_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", fake_import)

    result = handle.call({"x": 1})
    assert result == "ok"


@pytest.mark.asyncio
async def test_run_async_with_running_loop_thread_exception(monkeypatch):
    async def impl(_args):
        raise ValueError("boom")

    handle = ToolHandle("async", impl, is_async=True)

    orig_import = __import__

    def fake_import(name, *args, **kwargs):
        if name == "nest_asyncio":
            raise ImportError("no")
        return orig_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", fake_import)

    with pytest.raises(ValueError, match="boom"):
        handle.call({"x": 1})


def test_tool_handle_repr():
    handle = ToolHandle("noop", lambda args: args)
    assert repr(handle) == "ToolHandle('noop')"


def test_type_checking_import_path():
    import tactus.primitives.tool_handle as tool_handle

    original = typing.TYPE_CHECKING
    try:
        typing.TYPE_CHECKING = True
        importlib.reload(tool_handle)
    finally:
        typing.TYPE_CHECKING = original
        importlib.reload(tool_handle)
