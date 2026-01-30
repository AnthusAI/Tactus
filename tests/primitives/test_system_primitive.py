import pytest

from tactus.primitives.system import SystemPrimitive


class DummyLuaTable:
    def __init__(self, items):
        self._items = items

    def items(self):
        return self._items.items()


def test_alert_invalid_level_raises():
    system = SystemPrimitive()
    with pytest.raises(ValueError, match="Invalid alert level"):
        system.alert({"message": "bad", "level": "nope"})


def test_alert_emits_structured_event():
    captured = {}

    class DummyHandler:
        def log(self, event):
            captured["event"] = event

    system = SystemPrimitive(procedure_id="proc-1", log_handler=DummyHandler())
    system.alert({"message": "Hello", "level": "warning", "context": "ctx"})

    event = captured["event"]
    assert event.level == "warning"
    assert event.message == "Hello"
    assert event.procedure_id == "proc-1"
    assert event.context == {"context": "ctx"}


def test_alert_fallback_logging(caplog):
    system = SystemPrimitive()
    system.alert({"message": "Hello", "level": "error"})

    assert any("System.alert [error]" in record.message for record in caplog.records)


def test_alert_fallback_logging_with_context(caplog):
    caplog.set_level("INFO", logger="tactus.primitives.system")
    system = SystemPrimitive()
    system.alert({"message": "Hello", "level": "info", "context": {"x": 1}})

    assert any("| {'x': 1}" in record.getMessage() for record in caplog.records)


def test_lua_to_python_converts_tables():
    system = SystemPrimitive()
    lua_table = DummyLuaTable({"a": 1, "b": DummyLuaTable({"c": 2})})

    assert system._lua_to_python(lua_table) == {"a": 1, "b": {"c": 2}}


def test_lua_to_python_handles_none():
    system = SystemPrimitive()

    assert system._lua_to_python(None) is None


def test_lua_to_python_handles_sequences():
    system = SystemPrimitive()

    assert system._lua_to_python([1, DummyLuaTable({"a": 2})]) == [1, {"a": 2}]
    assert system._lua_to_python((DummyLuaTable({"b": 3}), 4)) == [{"b": 3}, 4]
