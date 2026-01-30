from tactus.primitives.step import StepPrimitive


class DummyExecutionContext:
    def __init__(self):
        self._pos = 0
        self.current_tac_file = "workflow.tac"
        self.last_source_info = None

    def next_position(self):
        self._pos += 1
        return self._pos

    def checkpoint(self, fn, _checkpoint_type, source_info=None):
        self.last_source_info = source_info
        return fn()


class DummyLuaInfo:
    def __init__(self, payload):
        self._payload = payload

    def items(self):
        return self._payload.items()


def test_checkpoint_uses_lua_source_info_dict():
    context = DummyExecutionContext()
    step = StepPrimitive(context)

    result = step.checkpoint(lambda: "ok", lua_source_info={"file": "lua.tac", "line": 9})

    assert result == "ok"
    assert context.last_source_info["file"] == "workflow.tac"
    assert context.last_source_info["line"] == 9


def test_checkpoint_uses_lua_source_info_items():
    context = DummyExecutionContext()
    step = StepPrimitive(context)

    lua_info = DummyLuaInfo({"file": "lua.tac", "line": 3, "function": "main"})
    step.checkpoint(lambda: "ok", lua_source_info=lua_info)

    assert context.last_source_info["line"] == 3
    assert context.last_source_info["function"] == "main"


def test_checkpoint_falls_back_to_python_source():
    context = DummyExecutionContext()
    step = StepPrimitive(context)

    step.checkpoint(lambda: "ok")

    assert context.last_source_info is not None
    assert "function" in context.last_source_info


def test_checkpoint_lua_source_info_conversion_failure():
    context = DummyExecutionContext()
    step = StepPrimitive(context)

    class BadLuaInfo:
        def __iter__(self):
            raise TypeError("boom")

    step.checkpoint(lambda: "ok", lua_source_info=BadLuaInfo())

    assert context.last_source_info["line"] == 0
    assert context.last_source_info["file"] == "workflow.tac"


def test_checkpoint_fallback_without_frame(monkeypatch):
    context = DummyExecutionContext()
    step = StepPrimitive(context)

    def fake_currentframe():
        class Frame:
            f_back = None

        return Frame()

    monkeypatch.setattr("inspect.currentframe", fake_currentframe)
    step.checkpoint(lambda: "ok")
    assert context.last_source_info is None


def test_checkpoint_propagates_errors():
    class FailingContext(DummyExecutionContext):
        def checkpoint(self, fn, _checkpoint_type, source_info=None):
            raise RuntimeError("boom")

    step = StepPrimitive(FailingContext())
    try:
        step.checkpoint(lambda: "ok")
    except RuntimeError as exc:
        assert str(exc) == "boom"
    else:
        raise AssertionError("Expected checkpoint to raise")
