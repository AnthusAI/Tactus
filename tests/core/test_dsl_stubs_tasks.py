import pytest

from tactus.core.dsl_stubs import _make_binding_callback, create_dsl_stubs
from tactus.core.registry import RegistryBuilder


def test_task_function_requires_callable():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)
    with pytest.raises(TypeError, match="TaskFunction expects a callable"):
        stubs["TaskFunction"]("not-callable")


def test_task_function_defers_execution():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    def handler(args):
        return args["value"] + 1

    deferred = stubs["TaskFunction"](handler)
    runner = deferred({"value": 2})
    assert runner() == 3


def test_task_function_passes_non_table_args():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)
    captured = {}

    def handler(args):
        captured["args"] = args
        return "ok"

    deferred = stubs["TaskFunction"](handler)
    runner = deferred("raw")
    assert runner() == "ok"
    assert captured["args"] == "raw"


def test_task_stub_registers_named_task_and_children():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    stubs["Task"](
        "fetch",
        {
            "entry": lambda: None,
            "NOAA": {"entry": lambda: None},
        },
    )

    assert "fetch" in builder.registry.tasks
    assert "NOAA" in builder.registry.tasks["fetch"].children


def test_task_stub_rejects_non_callable_entry():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    with pytest.raises(TypeError, match="entry must be a function"):
        stubs["Task"]("fetch", {"entry": "nope"})


def test_task_stub_handles_config_without_setitem():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    class NoSetItemConfig:
        def __init__(self):
            self._data = {}

        def __getitem__(self, key):
            return self._data[key]

        def keys(self):
            return list(self._data.keys())

        def items(self):
            return list(self._data.items())

    stubs["Task"]("fetch", NoSetItemConfig())

    assert "fetch" in builder.registry.tasks


def test_task_stub_registers_child_from_non_string_key(monkeypatch):
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    child_config = {"__task_name": "child", "entry": lambda: None}

    def fake_lua_table_to_dict(value):
        if value is child_config:
            return child_config
        return {}

    monkeypatch.setattr("tactus.core.dsl_stubs.lua_table_to_dict", fake_lua_table_to_dict)

    stubs["Task"](
        "fetch",
        {
            2: child_config,
        },
    )

    assert "child" in builder.registry.tasks["fetch"].children


def test_task_stub_handles_unsettable_config():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    class UnsettableConfig:
        def __init__(self):
            self._data = {}

        def __getitem__(self, key):
            return self._data[key]

        def __setitem__(self, _key, _value):
            raise RuntimeError("nope")

        def keys(self):
            return list(self._data.keys())

        def items(self):
            return list(self._data.items())

    stubs["Task"]("fetch", UnsettableConfig())

    assert "fetch" in builder.registry.tasks


def test_task_stub_assignment_records_child_tasks():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    config = stubs["Task"]({"NOAA": {"entry": lambda: None, "__tactus_task_config": True}})

    assert config.get("__tactus_child_tasks") is not None


def test_task_stub_assignment_handles_unsettable_config():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    class UnsettableConfig:
        def __init__(self):
            self._data = {"NOAA": {"entry": lambda: None}}

        def __getitem__(self, key):
            return self._data[key]

        def __setitem__(self, _key, _value):
            raise RuntimeError("nope")

        def keys(self):
            return list(self._data.keys())

        def items(self):
            return list(self._data.items())

    config = stubs["Task"](UnsettableConfig())

    assert config is not None


def test_task_stub_assignment_without_setitem():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    class NoSetItemConfig:
        def __init__(self):
            self._data = {"NOAA": {"entry": lambda: None}}

        def items(self):
            return list(self._data.items())

    config = stubs["Task"](NoSetItemConfig())

    assert config is not None


def test_task_stub_skips_children_when_config_has_no_items(monkeypatch):
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    class NoItemsConfig:
        def __init__(self):
            self._data = {}

        def __setitem__(self, _key, _value):
            self._data[_key] = _value

    monkeypatch.setattr("tactus.core.dsl_stubs.lua_table_to_dict", lambda _value: {})

    stubs["Task"]("fetch", NoItemsConfig())

    assert "fetch" in builder.registry.tasks
    assert builder.registry.tasks["fetch"].children == {}


def test_task_stub_skips_child_without_entry():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    stubs["Task"](
        "fetch",
        {
            "child": {"__task_name": "child"},
        },
    )

    assert "fetch" in builder.registry.tasks
    assert builder.registry.tasks["fetch"].children == {}


def test_task_stub_assignment_without_child_tasks():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    config = stubs["Task"]({"note": "no child"})

    assert "__tactus_child_tasks" not in config


def test_task_stub_assignment_handles_items_removed():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    class ItemsRemovedConfig:
        def __init__(self):
            self._data = {}
            self.items = lambda: list(self._data.items())

        def __setitem__(self, key, value):
            self._data[key] = value
            if hasattr(self, "items"):
                delattr(self, "items")

    config = stubs["Task"](ItemsRemovedConfig())

    assert config is not None


def test_task_stub_returns_empty_for_missing_config():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    assert stubs["Task"]() == {}


def test_include_tasks_stub_supports_table_config():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    stubs["IncludeTasks"]({"path": "tasks.tac", "namespace": "extras"})

    assert builder.registry.include_tasks == [{"path": "tasks.tac", "namespace": "extras"}]


def test_include_tasks_stub_supports_string_config():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    stubs["IncludeTasks"]("tasks.tac", "extras")

    assert builder.registry.include_tasks == [{"path": "tasks.tac", "namespace": "extras"}]


def test_include_tasks_stub_ignores_non_string_path():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    stubs["IncludeTasks"]({"path": 123, "namespace": "extras"})

    assert builder.registry.include_tasks == []


def test_include_tasks_stub_ignores_non_string_namespace():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    stubs["IncludeTasks"]("tasks.tac", 123)

    assert builder.registry.include_tasks == [{"path": "tasks.tac"}]


def test_include_tasks_stub_ignores_non_string_path_without_table():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    stubs["IncludeTasks"](123)

    assert builder.registry.include_tasks == []


def test_binding_callback_rejects_non_callable_task_entry():
    builder = RegistryBuilder()
    callback = _make_binding_callback(builder, {}, {}, {}, {}, {}, {}, {})

    with pytest.raises(TypeError, match="entry must be a function"):
        callback("fetch", {"__tactus_task_config": True, "entry": "nope"})


def test_binding_callback_rejects_non_callable_child_entry():
    builder = RegistryBuilder()
    callback = _make_binding_callback(builder, {}, {}, {}, {}, {}, {}, {})

    with pytest.raises(TypeError, match="entry must be a function"):
        callback(
            "parent",
            {
                "__tactus_task_config": True,
                "entry": lambda: None,
                "__tactus_child_tasks": {"child": {"__tactus_task_config": True, "entry": "nope"}},
            },
        )


def test_binding_callback_registers_task():
    builder = RegistryBuilder()
    callback = _make_binding_callback(builder, {}, {}, {}, {}, {}, {}, {})

    callback("fetch", {"__tactus_task_config": True, "entry": lambda: None})

    assert "fetch" in builder.registry.tasks


def test_binding_callback_skips_existing_task_registration():
    builder = RegistryBuilder()
    builder.register_task("fetch", {"entry": lambda: None})
    callback = _make_binding_callback(builder, {}, {}, {}, {}, {}, {}, {})

    callback("fetch", {"__tactus_task_config": True, "entry": lambda: None})

    assert list(builder.registry.tasks.keys()) == ["fetch"]


def test_binding_callback_skips_task_config_when_table_conversion_fails(monkeypatch):
    builder = RegistryBuilder()
    callback = _make_binding_callback(builder, {}, {}, {}, {}, {}, {}, {})
    monkeypatch.setattr(
        "tactus.core.dsl_stubs.lua_table_to_dict",
        lambda _value: (_ for _ in ()).throw(ValueError("bad")),
    )

    callback("fetch", {"__tactus_task_config": True, "entry": lambda: None})


def test_binding_callback_skips_child_without_name():
    builder = RegistryBuilder()
    callback = _make_binding_callback(builder, {}, {}, {}, {}, {}, {}, {})

    callback(
        "parent",
        {
            "__tactus_task_config": True,
            "entry": lambda: None,
            "__tactus_child_tasks": {1: {"entry": lambda: None}},
        },
    )

    assert "parent" in builder.registry.tasks
    assert builder.registry.tasks["parent"].children == {}

    assert "fetch" not in builder.registry.tasks


def test_binding_callback_registers_child_from_task_name():
    builder = RegistryBuilder()
    callback = _make_binding_callback(builder, {}, {}, {}, {}, {}, {}, {})

    callback(
        "parent",
        {
            "__tactus_task_config": True,
            "entry": lambda: None,
            "__tactus_child_tasks": {2: {"__task_name": "child", "entry": lambda: None}},
        },
    )

    assert "parent" in builder.registry.tasks
    assert "child" in builder.registry.tasks["parent"].children


def test_binding_callback_registers_child_from_child_sources_dict():
    builder = RegistryBuilder()
    callback = _make_binding_callback(builder, {}, {}, {}, {}, {}, {}, {})

    callback(
        "parent",
        {
            "__tactus_task_config": True,
            "entry": lambda: None,
            "__tactus_child_tasks": {"child": {"entry": lambda: None}},
        },
    )

    assert "child" in builder.registry.tasks["parent"].children
