from tactus.core import dsl_stubs


class FakeLuaTable:
    def __init__(self, data):
        self._data = dict(data)

    def keys(self):
        return self._data.keys()

    def items(self):
        return self._data.items()

    def __getitem__(self, key):
        return self._data[key]


def test_lua_table_to_dict_handles_none():
    assert dsl_stubs.lua_table_to_dict(None) == {}


def test_lua_table_to_dict_returns_primitive():
    assert dsl_stubs.lua_table_to_dict("value") == "value"


def test_lua_table_to_dict_handles_empty_table():
    table = FakeLuaTable({})
    assert dsl_stubs.lua_table_to_dict(table) == []


def test_lua_table_to_dict_handles_array_table():
    table = FakeLuaTable({1: "a", 2: "b"})
    assert dsl_stubs.lua_table_to_dict(table) == ["a", "b"]


def test_lua_table_to_dict_handles_nested_tables():
    inner = FakeLuaTable({1: "x"})
    table = FakeLuaTable({"key": inner, "value": 2})
    assert dsl_stubs.lua_table_to_dict(table) == {"key": ["x"], "value": 2}


def test_normalize_schema_converts_empty_list():
    assert dsl_stubs._normalize_schema([]) == {}
    assert dsl_stubs._normalize_schema({"a": 1}) == {"a": 1}
