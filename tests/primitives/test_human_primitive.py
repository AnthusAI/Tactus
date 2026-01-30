import pytest

from tactus.primitives.human import HumanPrimitive


class FakeResponse:
    def __init__(self, value):
        self.value = value


class FakeLua:
    def table_from(self, value):
        return value


class FakeLuaSandbox:
    def __init__(self):
        self.lua = FakeLua()


class FakeExecutionContext:
    def __init__(self):
        self.calls = []
        self.checkpoints = []
        self.lua_sandbox = FakeLuaSandbox()

    def wait_for_human(
        self,
        request_type,
        message,
        timeout_seconds,
        default_value,
        options,
        metadata,
        config_key=None,
    ):
        self.calls.append(
            {
                "request_type": request_type,
                "message": message,
                "timeout_seconds": timeout_seconds,
                "default_value": default_value,
                "options": options,
                "metadata": metadata,
                "config_key": config_key,
            }
        )
        return FakeResponse(default_value)

    def checkpoint(self, fn, checkpoint_type):
        self.checkpoints.append(checkpoint_type)
        return fn()


class FakeLuaTable:
    def __init__(self, items):
        self._items = items

    def items(self):
        return list(self._items)


def test_convert_lua_table_to_list():
    primitive = HumanPrimitive(FakeExecutionContext())
    lua_table = FakeLuaTable([(1, "a"), (2, "b")])

    assert primitive._convert_lua_to_python(lua_table) == ["a", "b"]


def test_convert_lua_none_and_sparse_numeric_table():
    primitive = HumanPrimitive(FakeExecutionContext())
    lua_table = FakeLuaTable([(1, "a"), (3, "c")])

    assert primitive._convert_lua_to_python(None) is None
    assert primitive._convert_lua_to_python(lua_table) == {1: "a", 3: "c"}


def test_convert_lua_table_to_dict():
    primitive = HumanPrimitive(FakeExecutionContext())
    lua_table = FakeLuaTable([("a", 1), ("b", 2)])

    assert primitive._convert_lua_to_python(lua_table) == {"a": 1, "b": 2}


def test_approve_merges_config_and_uses_checkpoint():
    ctx = FakeExecutionContext()
    primitive = HumanPrimitive(ctx, hitl_config={"deploy": {"message": "Override"}})

    result = primitive.approve({"config_key": "deploy", "message": "Ship?"})

    assert result is False
    assert ctx.checkpoints == ["hitl_approval"]
    assert ctx.calls[0]["message"] == "Ship?"


def test_approve_supports_string_shorthand():
    ctx = FakeExecutionContext()
    primitive = HumanPrimitive(ctx)

    primitive.approve("Continue?")

    assert ctx.calls[0]["message"] == "Continue?"


def test_input_uses_placeholder_metadata():
    ctx = FakeExecutionContext()
    primitive = HumanPrimitive(ctx)

    primitive.input({"message": "Name?", "placeholder": "Jane"})

    assert ctx.calls[0]["metadata"] == {"placeholder": "Jane"}
    assert ctx.checkpoints == ["hitl_input"]


def test_input_merges_config():
    ctx = FakeExecutionContext()
    primitive = HumanPrimitive(ctx, hitl_config={"ask": {"message": "Config"}})

    primitive.input({"config_key": "ask", "message": "Override"})

    assert ctx.calls[0]["message"] == "Override"


def test_review_formats_options():
    ctx = FakeExecutionContext()
    primitive = HumanPrimitive(ctx)

    primitive.review({"options": ["approve", {"label": "Edit", "type": "action"}]})

    options = ctx.calls[0]["options"]
    assert options[0]["label"] == "Approve"
    assert options[1]["label"] == "Edit"
    assert ctx.checkpoints == ["hitl_review"]


def test_review_merges_config():
    ctx = FakeExecutionContext()
    primitive = HumanPrimitive(ctx, hitl_config={"review": {"message": "Config"}})

    primitive.review({"config_key": "review", "message": "Override"})

    assert ctx.calls[0]["message"] == "Override"


def test_notify_does_not_block():
    ctx = FakeExecutionContext()
    primitive = HumanPrimitive(ctx)

    primitive.notify({"message": "Done"})

    assert ctx.calls == []


def test_escalate_blocks_without_timeout():
    ctx = FakeExecutionContext()
    primitive = HumanPrimitive(ctx)

    primitive.escalate({"message": "Help", "severity": "critical"})

    assert ctx.calls[0]["request_type"] == "escalation"
    assert ctx.calls[0]["timeout_seconds"] is None
    assert ctx.checkpoints == ["hitl_escalation"]


def test_escalate_merges_config():
    ctx = FakeExecutionContext()
    primitive = HumanPrimitive(ctx, hitl_config={"urgent": {"message": "Config"}})

    primitive.escalate({"config_key": "urgent", "message": "Override"})

    assert ctx.calls[0]["message"] == "Override"


def test_select_builds_metadata_and_options():
    ctx = FakeExecutionContext()
    primitive = HumanPrimitive(ctx)

    primitive.select(
        {
            "message": "Pick",
            "options": [{"value": "a"}, "b"],
            "mode": "multiple",
            "style": "checkbox",
            "min": 1,
            "max": 2,
        }
    )

    call = ctx.calls[0]
    assert call["metadata"]["style"] == "checkbox"
    assert call["metadata"]["mode"] == "multiple"
    assert call["options"][0]["label"] == "a"
    assert call["options"][1]["value"] == "b"


def test_select_merges_config_and_uses_label_option():
    ctx = FakeExecutionContext()
    primitive = HumanPrimitive(ctx, hitl_config={"pick": {"message": "Config"}})

    primitive.select({"config_key": "pick", "message": "Override", "options": [{"label": "Alpha"}]})

    call = ctx.calls[0]
    assert call["message"] == "Override"
    assert call["options"][0]["label"] == "Alpha"


def test_upload_normalizes_accept_and_size():
    ctx = FakeExecutionContext()
    primitive = HumanPrimitive(ctx)

    primitive.upload({"accept": ".pdf,.doc", "max_size": "1MB"})

    metadata = ctx.calls[0]["metadata"]
    assert metadata["accept"] == [".pdf", ".doc"]
    assert metadata["max_size"] == 1024 * 1024


def test_upload_merges_config():
    ctx = FakeExecutionContext()
    primitive = HumanPrimitive(ctx, hitl_config={"upload": {"message": "Config"}})

    primitive.upload({"config_key": "upload", "message": "Override"})

    assert ctx.calls[0]["message"] == "Override"


def test_parse_size_invalid_logs_default(caplog):
    ctx = FakeExecutionContext()
    primitive = HumanPrimitive(ctx)

    with caplog.at_level("WARNING"):
        size = primitive._parse_size("bad-size")

    assert size == 10 * 1024 * 1024
    assert "Could not parse size" in caplog.text


def test_inputs_requires_items():
    ctx = FakeExecutionContext()
    primitive = HumanPrimitive(ctx)

    with pytest.raises(ValueError):
        primitive.inputs([])


def test_inputs_validation_errors():
    ctx = FakeExecutionContext()
    primitive = HumanPrimitive(ctx)

    with pytest.raises(ValueError):
        primitive.inputs([{"label": "A", "type": "input", "message": "M"}])

    with pytest.raises(ValueError):
        primitive.inputs([{"id": "a"}])

    with pytest.raises(ValueError):
        primitive.inputs([{"id": "a", "label": "A", "type": "input", "message": "M"}, "bad"])

    with pytest.raises(ValueError):
        primitive.inputs(
            [
                {"id": "a", "label": "A", "type": "input", "message": "M"},
                {"id": "a", "label": "A2", "type": "input", "message": "M2"},
            ]
        )

    with pytest.raises(ValueError):
        primitive.inputs([{"id": "a", "label": "A", "message": "M"}])

    with pytest.raises(ValueError):
        primitive.inputs([{"id": "a", "label": "A", "type": "input"}])


def test_inputs_formats_options_and_returns_table():
    ctx = FakeExecutionContext()
    primitive = HumanPrimitive(ctx)

    result = primitive.inputs(
        [
            {
                "id": "target",
                "label": "Target",
                "type": "select",
                "message": "Pick",
                "options": [{"value": "staging"}, "prod"],
            }
        ]
    )

    assert result == {}
    assert ctx.calls[0]["request_type"] == "inputs"


def test_inputs_formats_label_options_and_list_response():
    class ResponseContext(FakeExecutionContext):
        def wait_for_human(self, *args, **kwargs):
            super().wait_for_human(*args, **kwargs)
            return FakeResponse({"ids": ["a", "b"]})

    ctx = ResponseContext()
    primitive = HumanPrimitive(ctx)

    result = primitive.inputs(
        [
            {
                "id": "target",
                "label": "Target",
                "type": "select",
                "message": "Pick",
                "options": [{"label": "Alpha", "value": "a"}],
            }
        ]
    )

    assert result == {"ids": ["a", "b"]}
    assert ctx.calls[0]["metadata"]["items"][0]["options"][0]["label"] == "Alpha"


def test_inputs_converts_non_list_values():
    class ResponseContext(FakeExecutionContext):
        def wait_for_human(self, *args, **kwargs):
            super().wait_for_human(*args, **kwargs)
            return FakeResponse({"status": "ok"})

    ctx = ResponseContext()
    primitive = HumanPrimitive(ctx)

    result = primitive.inputs(
        [
            {
                "id": "status",
                "label": "Status",
                "type": "input",
                "message": "Status?",
            }
        ]
    )

    assert result == {"status": "ok"}


def test_multiple_delegates_to_inputs(monkeypatch):
    ctx = FakeExecutionContext()
    primitive = HumanPrimitive(ctx)

    called = {}

    def fake_inputs(items):
        called["items"] = items
        return {"ok": True}

    monkeypatch.setattr(primitive, "inputs", fake_inputs)
    assert primitive.multiple([{"id": "a"}]) == {"ok": True}
    assert called["items"] == [{"id": "a"}]


def test_custom_requires_fields():
    ctx = FakeExecutionContext()
    primitive = HumanPrimitive(ctx)

    with pytest.raises(TypeError):
        primitive.custom("bad")

    with pytest.raises(ValueError):
        primitive.custom({"message": "Missing component"})

    with pytest.raises(ValueError):
        primitive.custom({"component_type": "x"})


def test_custom_sends_metadata_and_config_key():
    ctx = FakeExecutionContext()
    primitive = HumanPrimitive(ctx)

    primitive.custom(
        {
            "component_type": "picker",
            "message": "Pick",
            "data": {"a": 1},
            "actions": [{"id": "ok"}],
            "config_key": "custom",
        }
    )

    call = ctx.calls[0]
    assert call["request_type"] == "custom"
    assert call["metadata"]["component_type"] == "picker"
    assert call["config_key"] == "custom"
