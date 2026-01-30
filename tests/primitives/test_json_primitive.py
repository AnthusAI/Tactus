import sys
from types import SimpleNamespace

import pytest

from tactus.primitives.json import JsonPrimitive


class FakeLuaTable(dict):
    pass


class FakeLuaSandbox:
    class Lua:
        @staticmethod
        def table():
            return FakeLuaTable()

    lua = Lua()


def test_encode_decode_round_trip():
    primitive = JsonPrimitive()
    data = {"name": "Alice", "scores": [1, 2]}
    encoded = primitive.encode(data)
    decoded = primitive.decode(encoded)
    assert decoded == data


def test_decode_invalid_json():
    primitive = JsonPrimitive()
    with pytest.raises(ValueError, match="Failed to decode JSON"):
        primitive.decode("{bad}")


def test_encode_invalid_value_raises():
    primitive = JsonPrimitive()

    class Unserializable:
        pass

    with pytest.raises(ValueError, match="Failed to encode to JSON"):
        primitive.encode(Unserializable())


def test_lua_to_python_array(monkeypatch):
    fake_module = SimpleNamespace(
        lua_type=lambda value: "table" if isinstance(value, FakeLuaTable) else "string"
    )
    monkeypatch.setitem(sys.modules, "lupa", fake_module)

    primitive = JsonPrimitive()
    lua_table = FakeLuaTable({1: "a", 2: "b"})
    assert primitive._lua_to_python(lua_table) == ["a", "b"]


def test_lua_to_python_dict_like(monkeypatch):
    fake_module = SimpleNamespace(
        lua_type=lambda value: "table" if isinstance(value, FakeLuaTable) else "string"
    )
    monkeypatch.setitem(sys.modules, "lupa", fake_module)

    primitive = JsonPrimitive()
    lua_table = FakeLuaTable({1: "a", 3: "b", "x": "y"})
    assert primitive._lua_to_python(lua_table) == {1: "a", 3: "b", "x": "y"}


def test_lua_to_python_non_consecutive_array(monkeypatch):
    fake_module = SimpleNamespace(
        lua_type=lambda value: "table" if isinstance(value, FakeLuaTable) else "string"
    )
    monkeypatch.setitem(sys.modules, "lupa", fake_module)

    primitive = JsonPrimitive()
    lua_table = FakeLuaTable({1: "a", 3: "b"})
    assert primitive._lua_to_python(lua_table) == {1: "a", 3: "b"}


def test_lua_to_python_import_error(monkeypatch):
    monkeypatch.delitem(sys.modules, "lupa", raising=False)

    original_import = __import__

    def fake_import(name, *args, **kwargs):
        if name == "lupa":
            raise ImportError("missing")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", fake_import)

    primitive = JsonPrimitive()
    obj = FakeLuaTable({1: "a"})
    assert primitive._lua_to_python(obj) is obj


def test_python_to_lua_with_sandbox():
    primitive = JsonPrimitive(lua_sandbox=FakeLuaSandbox())
    lua_table = primitive._python_to_lua({"a": [1, 2]})
    assert lua_table["a"][1] == 1
    assert lua_table["a"][2] == 2


def test_python_to_lua_without_sandbox_returns_value():
    primitive = JsonPrimitive()
    assert primitive._python_to_lua({"a": 1}) == {"a": 1}


def test_decode_with_sandbox_uses_python_to_lua():
    primitive = JsonPrimitive(lua_sandbox=FakeLuaSandbox())
    decoded = primitive.decode('{"a": [1, 2]}')
    assert decoded["a"][1] == 1


def test_repr():
    assert repr(JsonPrimitive()) == "JsonPrimitive()"
