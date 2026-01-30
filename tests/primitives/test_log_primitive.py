import logging

from tactus.primitives.log import LogPrimitive


class DummyLogHandler:
    def __init__(self):
        self.events = []

    def log(self, event):
        self.events.append(event)


class DictLike:
    def __init__(self, data):
        self._data = data

    def items(self):
        return self._data.items()


class IterableFail:
    def __iter__(self):
        raise RuntimeError("boom")


def test_format_message_with_context():
    primitive = LogPrimitive("proc")
    message = primitive._format_message("Hello", {"a": 1})
    assert "Context" in message
    assert "Hello" in message


def test_lua_to_python_handles_dict_like_and_iterable():
    primitive = LogPrimitive("proc")
    converted = primitive._lua_to_python(DictLike({"a": 1, "b": [1, 2]}))
    assert converted == {"a": 1, "b": [1, 2]}


def test_lua_to_python_iterable_failure_returns_obj():
    primitive = LogPrimitive("proc")
    obj = IterableFail()
    assert primitive._lua_to_python(obj) is obj


def test_logs_with_handler_emit_events():
    handler = DummyLogHandler()
    primitive = LogPrimitive("proc", log_handler=handler)

    primitive.debug("d", {"a": 1})
    primitive.info("i")
    primitive.warn("w")
    primitive.error("e")

    levels = [event.level for event in handler.events]
    assert levels == ["DEBUG", "INFO", "WARNING", "ERROR"]


def test_warning_alias_calls_warn():
    handler = DummyLogHandler()
    primitive = LogPrimitive("proc", log_handler=handler)
    primitive.warning("w")
    assert handler.events[0].level == "WARNING"


def test_logs_fallback_to_python_logger(caplog):
    primitive = LogPrimitive("proc")
    caplog.set_level(logging.DEBUG)

    primitive.debug("debug message")
    primitive.info("info message")
    primitive.warn("warn message")
    primitive.error("error message")

    messages = [record.message for record in caplog.records]
    assert "debug message" in messages
    assert "info message" in messages
    assert "warn message" in messages
    assert "error message" in messages


def test_repr_includes_procedure_id():
    primitive = LogPrimitive("proc")
    assert repr(primitive) == "LogPrimitive(procedure_id=proc)"
