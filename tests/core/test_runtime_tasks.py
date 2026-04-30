from types import SimpleNamespace

import pytest

from tactus.core.exceptions import TaskSelectionRequired, TactusRuntimeError
from tactus.core.registry import TaskDeclaration
from tactus.core.runtime import TactusRuntime


def _runtime_with_registry(registry):
    runtime = TactusRuntime.__new__(TactusRuntime)
    runtime.registry = registry
    runtime.task_name = None
    runtime._top_level_result = None
    runtime._execute_task = lambda name: f"task:{name}"
    return runtime


def _runtime_for_parse(tmp_path, sandbox):
    runtime = TactusRuntime.__new__(TactusRuntime)
    runtime.lua_sandbox = sandbox
    runtime.mock_manager = None
    runtime.execution_context = None
    runtime.log_handler = None
    runtime.agents = {}
    runtime.source_file_path = str(tmp_path / "main.tac")
    runtime.reasoning_effort = None
    runtime.verbosity = None
    return runtime


def test_execute_workflow_selects_single_task():
    registry = SimpleNamespace(
        tasks={"fetch": TaskDeclaration(name="fetch")}, retrievers={}, named_procedures={}
    )
    runtime = _runtime_with_registry(registry)

    assert runtime._execute_workflow() == "task:fetch"


def test_execute_workflow_prefers_run_task():
    registry = SimpleNamespace(
        tasks={
            "run": TaskDeclaration(name="run"),
            "fetch": TaskDeclaration(name="fetch"),
        },
        retrievers={},
        named_procedures={},
    )
    runtime = _runtime_with_registry(registry)

    assert runtime._execute_workflow() == "task:run"


def test_execute_workflow_requires_task_selection():
    registry = SimpleNamespace(
        tasks={"a": TaskDeclaration(name="a"), "b": TaskDeclaration(name="b")},
        retrievers={},
        named_procedures={},
    )
    runtime = _runtime_with_registry(registry)

    with pytest.raises(TaskSelectionRequired) as exc:
        runtime._execute_workflow()

    assert sorted(exc.value.tasks) == ["a", "b"]


def test_execute_workflow_flattens_nested_tasks():
    registry = SimpleNamespace(
        tasks={
            "parent": TaskDeclaration(
                name="parent",
                children={"child": TaskDeclaration(name="child")},
            ),
            "other": TaskDeclaration(name="other"),
        },
        retrievers={},
        named_procedures={},
    )
    runtime = _runtime_with_registry(registry)

    with pytest.raises(TaskSelectionRequired) as exc:
        runtime._execute_workflow()

    assert "parent:child" in exc.value.tasks


def test_execute_workflow_requires_implicit_retriever_task():
    retriever = SimpleNamespace(config={"retriever_id": "tf-vector"}, corpus="corp")
    registry = SimpleNamespace(tasks={}, retrievers={"r1": retriever}, named_procedures={})
    runtime = _runtime_with_registry(registry)

    with pytest.raises(TaskSelectionRequired) as exc:
        runtime._execute_workflow()

    assert "index" in exc.value.tasks
    assert "index:r1" in exc.value.tasks


def test_execute_workflow_implicit_tasks_deduplicate_for_multiple_retrievers():
    retriever = SimpleNamespace(config={"retriever_id": "tf-vector"}, corpus="corp")
    registry = SimpleNamespace(
        tasks={}, retrievers={"r1": retriever, "r2": retriever}, named_procedures={}
    )
    runtime = _runtime_with_registry(registry)

    with pytest.raises(TaskSelectionRequired) as exc:
        runtime._execute_workflow()

    assert exc.value.tasks.count("index") == 1
    assert "index:r1" in exc.value.tasks
    assert "index:r2" in exc.value.tasks


def test_execute_workflow_skips_implicit_task_when_explicit_present():
    retriever = SimpleNamespace(config={"retriever_id": "tf-vector"}, corpus="corp")
    registry = SimpleNamespace(
        tasks={"index": TaskDeclaration(name="index")},
        retrievers={"r1": retriever},
        named_procedures={},
    )
    runtime = _runtime_with_registry(registry)

    assert runtime._execute_workflow() == "task:index"


def test_execute_workflow_uses_top_level_result_when_no_main():
    registry = SimpleNamespace(tasks={}, retrievers={}, named_procedures={})
    runtime = _runtime_with_registry(registry)
    runtime._top_level_result = {"ok": True}

    assert runtime._execute_workflow() == {"ok": True}


def test_execute_workflow_errors_without_main_or_result():
    registry = SimpleNamespace(tasks={}, retrievers={}, named_procedures={})
    runtime = _runtime_with_registry(registry)

    with pytest.raises(RuntimeError, match="Named 'main' procedure not found"):
        runtime._execute_workflow()


def test_execute_task_run_fallback():
    registry = SimpleNamespace(tasks={}, retrievers={}, corpora={})
    runtime = TactusRuntime.__new__(TactusRuntime)
    runtime.registry = registry
    runtime.task_name = None
    runtime._execute_workflow = lambda: "main"

    assert runtime._execute_task("run") == "main"


def test_execute_task_requires_registry():
    runtime = TactusRuntime.__new__(TactusRuntime)
    runtime.registry = None

    with pytest.raises(RuntimeError, match="No registry available"):
        runtime._execute_task("fetch")


def test_execute_task_retriever_tasks(monkeypatch):
    registry = SimpleNamespace(tasks={}, retrievers={}, corpora={})
    runtime = TactusRuntime.__new__(TactusRuntime)
    runtime.registry = registry
    runtime._resolve_retriever_task_targets = lambda _name: ["r1"]
    runtime._execute_retriever_tasks = lambda name, targets: (name, targets)

    assert runtime._execute_task("index") == ("index", ["r1"])


def test_execute_task_missing_raises():
    registry = SimpleNamespace(tasks={}, retrievers={}, corpora={})
    runtime = TactusRuntime.__new__(TactusRuntime)
    runtime.registry = registry
    runtime._resolve_retriever_task_targets = lambda _name: []

    with pytest.raises(RuntimeError, match="Task 'missing' not found"):
        runtime._execute_task("missing")


def test_execute_task_requires_entry_for_parent():
    task = TaskDeclaration(name="parent", children={"child": TaskDeclaration(name="child")})
    registry = SimpleNamespace(tasks={"parent": task}, retrievers={}, corpora={})
    runtime = TactusRuntime.__new__(TactusRuntime)
    runtime.registry = registry

    with pytest.raises(RuntimeError, match="Available sub-tasks"):
        runtime._execute_task("parent")


def test_execute_task_requires_entry_for_leaf():
    task = TaskDeclaration(name="leaf")
    registry = SimpleNamespace(tasks={"leaf": task}, retrievers={}, corpora={})
    runtime = TactusRuntime.__new__(TactusRuntime)
    runtime.registry = registry

    with pytest.raises(RuntimeError, match="has no entry"):
        runtime._execute_task("leaf")


def test_execute_task_requires_callable_entry():
    task = TaskDeclaration(name="leaf", entry="not-callable")
    registry = SimpleNamespace(tasks={"leaf": task}, retrievers={}, corpora={})
    runtime = TactusRuntime.__new__(TactusRuntime)
    runtime.registry = registry

    with pytest.raises(RuntimeError, match="entry must be a function"):
        runtime._execute_task("leaf")


def test_execute_task_invokes_entry():
    task = TaskDeclaration(name="leaf", entry=lambda: "ok")
    registry = SimpleNamespace(tasks={"leaf": task}, retrievers={}, corpora={})
    runtime = TactusRuntime.__new__(TactusRuntime)
    runtime.registry = registry

    assert runtime._execute_task("leaf") == "ok"


def test_execute_retriever_tasks_requires_targets():
    runtime = TactusRuntime.__new__(TactusRuntime)
    with pytest.raises(RuntimeError, match="No retrievers available"):
        runtime._execute_retriever_tasks("index", [])


def test_execute_retriever_tasks_runs_index(monkeypatch):
    runtime = TactusRuntime.__new__(TactusRuntime)
    runtime._execute_retriever_index = lambda name: f"snap:{name}"

    assert runtime._execute_retriever_tasks("index", ["r1"]) == "snap:r1"
    assert runtime._execute_retriever_tasks("index", ["r1", "r2"]) == [
        "snap:r1",
        "snap:r2",
    ]


def test_execute_retriever_tasks_rejects_unknown_task():
    runtime = TactusRuntime.__new__(TactusRuntime)
    with pytest.raises(RuntimeError, match="not supported"):
        runtime._execute_retriever_tasks("sync", ["r1"])


def test_execute_retriever_index_happy_path(monkeypatch, tmp_path):
    registry = SimpleNamespace(retrievers={}, corpora={})
    runtime = TactusRuntime.__new__(TactusRuntime)
    runtime.registry = registry
    runtime._build_retriever_index_plan = lambda _name: ("plan", "corpus", {})
    runtime._execute_dependency_plan = lambda **_kwargs: [{"ok": True}]

    result = runtime._execute_retriever_index("r1")

    assert result["ok"] is True


def test_execute_retriever_index_rejects_missing_registry():
    runtime = TactusRuntime.__new__(TactusRuntime)
    runtime.registry = None
    with pytest.raises(RuntimeError, match="No registry available"):
        runtime._execute_retriever_index("r1")


def test_execute_retriever_index_rejects_missing_retriever():
    registry = SimpleNamespace(retrievers={}, corpora={})
    runtime = TactusRuntime.__new__(TactusRuntime)
    runtime.registry = registry
    with pytest.raises(RuntimeError, match="Retriever 'r1' not found"):
        runtime._execute_retriever_index("r1")


def test_execute_retriever_index_rejects_missing_corpus():
    retriever = SimpleNamespace(corpus=None, config={"retriever_id": "tf-vector"})
    registry = SimpleNamespace(retrievers={"r1": retriever}, corpora={})
    runtime = TactusRuntime.__new__(TactusRuntime)
    runtime.registry = registry
    with pytest.raises(RuntimeError, match="has no corpus configured"):
        runtime._execute_retriever_index("r1")


def test_execute_retriever_index_rejects_missing_corpus_decl():
    retriever = SimpleNamespace(corpus="docs", config={"retriever_id": "tf-vector"})
    registry = SimpleNamespace(retrievers={"r1": retriever}, corpora={})
    runtime = TactusRuntime.__new__(TactusRuntime)
    runtime.registry = registry
    with pytest.raises(RuntimeError, match="Corpus 'docs' not found"):
        runtime._execute_retriever_index("r1")


def test_execute_retriever_index_rejects_missing_root():
    retriever = SimpleNamespace(corpus="docs", config={"retriever_id": "tf-vector"})
    corpus_decl = SimpleNamespace(config={})
    registry = SimpleNamespace(retrievers={"r1": retriever}, corpora={"docs": corpus_decl})
    runtime = TactusRuntime.__new__(TactusRuntime)
    runtime.registry = registry
    with pytest.raises(RuntimeError, match="missing a root path"):
        runtime._execute_retriever_index("r1")


def test_execute_retriever_index_rejects_missing_retriever_id():
    retriever = SimpleNamespace(corpus="docs", config={})
    corpus_decl = SimpleNamespace(config={"root": "/tmp"})
    registry = SimpleNamespace(retrievers={"r1": retriever}, corpora={"docs": corpus_decl})
    runtime = TactusRuntime.__new__(TactusRuntime)
    runtime.registry = registry
    with pytest.raises(RuntimeError, match="missing retriever_id"):
        runtime._execute_retriever_index("r1")


def test_execute_retriever_index_import_error(monkeypatch):
    retriever = SimpleNamespace(corpus="docs", config={"retriever_id": "tf-vector"})
    corpus_decl = SimpleNamespace(config={"root": "/tmp"})
    registry = SimpleNamespace(retrievers={"r1": retriever}, corpora={"docs": corpus_decl})
    runtime = TactusRuntime.__new__(TactusRuntime)
    runtime.registry = registry

    monkeypatch.setitem(__import__("sys").modules, "biblicus.workflow", None)

    with pytest.raises(RuntimeError, match="Biblicus workflow unavailable"):
        runtime._build_retriever_index_plan("r1")


def test_retriever_index_config_normalizes_pipeline_lists():
    runtime = TactusRuntime.__new__(TactusRuntime)
    retriever = SimpleNamespace(config={"retriever_id": "tf-vector", "pipeline": {"index": []}})

    assert runtime._retriever_index_config(retriever) == {}


def test_retriever_index_config_prefers_configuration_pipeline():
    runtime = TactusRuntime.__new__(TactusRuntime)
    retriever = SimpleNamespace(
        config={
            "retriever_id": "tf-vector",
            "configuration": {"pipeline": {"index": {"keep": True}}},
        }
    )

    assert runtime._retriever_index_config(retriever) == {"keep": True}


def test_corpus_pipeline_config_extract_from_pipeline():
    runtime = TactusRuntime.__new__(TactusRuntime)
    corpus_decl = SimpleNamespace(
        config={"configuration": {"pipeline": {"extract": {"steps": []}}}}
    )

    assert runtime._corpus_pipeline_config(corpus_decl) == {"steps": []}


def test_corpus_pipeline_config_skips_non_dict_pipeline():
    runtime = TactusRuntime.__new__(TactusRuntime)
    corpus_decl = SimpleNamespace(config={"configuration": {"pipeline": ["bad"]}})

    assert runtime._corpus_pipeline_config(corpus_decl) is None


def test_resolve_task_inline_child():
    parent = TaskDeclaration(
        name="parent",
        children={},
        child={"__tactus_task_config": True, "entry": lambda: None},
    )
    registry = SimpleNamespace(tasks={"parent": parent}, retrievers={}, corpora={})
    runtime = TactusRuntime.__new__(TactusRuntime)
    runtime.registry = registry

    resolved = runtime._resolve_task("parent:child")

    assert resolved is not None
    assert resolved.name == "child"


def test_resolve_task_nested_child():
    parent = TaskDeclaration(
        name="parent",
        children={"child": TaskDeclaration(name="child")},
    )
    registry = SimpleNamespace(tasks={"parent": parent}, retrievers={}, corpora={})
    runtime = TactusRuntime.__new__(TactusRuntime)
    runtime.registry = registry

    resolved = runtime._resolve_task("parent:child")

    assert resolved is not None
    assert resolved.name == "child"


def test_resolve_task_inline_child_invalid_returns_none():
    parent = TaskDeclaration(
        name="parent",
        children={},
        child={"__tactus_task_config": True, "children": "bad"},
    )
    registry = SimpleNamespace(tasks={"parent": parent}, retrievers={}, corpora={})
    runtime = TactusRuntime.__new__(TactusRuntime)
    runtime.registry = registry

    assert runtime._resolve_task("parent:child") is None


def test_resolve_task_inline_child_non_dict_returns_none():
    parent = TaskDeclaration(
        name="parent",
        children={},
        child="bad",
    )
    registry = SimpleNamespace(tasks={"parent": parent}, retrievers={}, corpora={})
    runtime = TactusRuntime.__new__(TactusRuntime)
    runtime.registry = registry

    assert runtime._resolve_task("parent:child") is None


def test_resolve_task_handles_missing_registry():
    runtime = TactusRuntime.__new__(TactusRuntime)
    runtime.registry = None

    assert runtime._resolve_task("anything") is None


def test_resolve_task_handles_empty_name():
    registry = SimpleNamespace(tasks={}, retrievers={}, corpora={})
    runtime = TactusRuntime.__new__(TactusRuntime)
    runtime.registry = registry

    assert runtime._resolve_task("") is None


def test_resolve_task_missing_parent_returns_none():
    registry = SimpleNamespace(tasks={}, retrievers={}, corpora={})
    runtime = TactusRuntime.__new__(TactusRuntime)
    runtime.registry = registry

    assert runtime._resolve_task("missing:child") is None


def test_resolve_task_inline_child_invalid(monkeypatch):
    parent = TaskDeclaration(
        name="parent",
        children={},
        child={"__tactus_task_config": True, "entry": lambda: None},
    )
    registry = SimpleNamespace(tasks={"parent": parent}, retrievers={}, corpora={})
    runtime = TactusRuntime.__new__(TactusRuntime)
    runtime.registry = registry

    monkeypatch.setattr(
        "tactus.core.runtime.TaskDeclaration",
        lambda **_kw: (_ for _ in ()).throw(ValueError("bad")),
    )

    assert runtime._resolve_task("parent:child") is None


def test_expand_inline_task_children_adds_children():
    parent = TaskDeclaration(
        name="parent",
        children={},
        child={"__tactus_task_config": True, "entry": lambda: None},
    )
    registry = SimpleNamespace(tasks={"parent": parent})
    runtime = TactusRuntime.__new__(TactusRuntime)

    runtime._expand_inline_task_children(registry)

    assert "child" in registry.tasks["parent"].children


def test_expand_inline_task_children_skips_missing_marker():
    parent = TaskDeclaration(name="parent", children={}, child={"entry": lambda: None})
    registry = SimpleNamespace(tasks={"parent": parent})
    runtime = TactusRuntime.__new__(TactusRuntime)

    runtime._expand_inline_task_children(registry)

    assert registry.tasks["parent"].children == {}


def test_expand_inline_task_children_skips_existing_child():
    parent = TaskDeclaration(
        name="parent",
        children={"child": TaskDeclaration(name="child")},
        child={"__tactus_task_config": True, "entry": lambda: None},
    )
    registry = SimpleNamespace(tasks={"parent": parent})
    runtime = TactusRuntime.__new__(TactusRuntime)

    runtime._expand_inline_task_children(registry)

    assert list(registry.tasks["parent"].children.keys()) == ["child"]


def test_expand_inline_task_children_handles_invalid_child(monkeypatch):
    parent = TaskDeclaration(
        name="parent",
        children={},
        child={"__tactus_task_config": True, "entry": lambda: None},
    )
    registry = SimpleNamespace(tasks={"parent": parent})
    runtime = TactusRuntime.__new__(TactusRuntime)

    monkeypatch.setattr(
        "tactus.core.runtime.TaskDeclaration",
        lambda **_kw: (_ for _ in ()).throw(ValueError("bad")),
    )

    runtime._expand_inline_task_children(registry)

    assert registry.tasks["parent"].children == {}


def test_resolve_retriever_task_targets_filters_target():
    retriever = SimpleNamespace(config={"retriever_id": "tf-vector"})
    registry = SimpleNamespace(retrievers={"r1": retriever, "r2": retriever})
    runtime = TactusRuntime.__new__(TactusRuntime)
    runtime.registry = registry

    assert runtime._resolve_retriever_task_targets("index:r2") == ["r2"]


def test_resolve_retriever_task_targets_returns_all():
    retriever = SimpleNamespace(config={"retriever_id": "tf-vector"})
    registry = SimpleNamespace(retrievers={"r1": retriever, "r2": retriever})
    runtime = TactusRuntime.__new__(TactusRuntime)
    runtime.registry = registry

    assert runtime._resolve_retriever_task_targets("index") == ["r1", "r2"]


def test_resolve_retriever_task_targets_skips_unknown_retriever_id():
    retriever = SimpleNamespace(config={"retriever_id": "unknown"})
    registry = SimpleNamespace(retrievers={"r1": retriever})
    runtime = TactusRuntime.__new__(TactusRuntime)
    runtime.registry = registry

    assert runtime._resolve_retriever_task_targets("index") == []


def test_resolve_retriever_task_targets_empty_registry():
    runtime = TactusRuntime.__new__(TactusRuntime)
    runtime.registry = None

    assert runtime._resolve_retriever_task_targets("index") == []


def test_resolve_retriever_task_targets_empty_segments():
    registry = SimpleNamespace(
        retrievers={"r1": SimpleNamespace(config={"retriever_id": "tf-vector"})}
    )
    runtime = TactusRuntime.__new__(TactusRuntime)
    runtime.registry = registry

    assert runtime._resolve_retriever_task_targets(":") == []


def test_parse_declarations_includes_tasks_with_namespace(tmp_path):
    class FakeSandbox:
        def __init__(self, include_source):
            self._globals = {}
            self.include_source = include_source
            self.lua = SimpleNamespace(globals=lambda: {})

        def set_global(self, name, value):
            self._globals[name] = value

        def setup_assignment_interception(self, _callback):
            pass

        def execute(self, source):
            if source == self.include_source:
                self._globals["Task"]("fetch", {"entry": lambda: None})
                return None
            self._globals["IncludeTasks"]("tasks.tac", "extras")
            return None

    include_source = 'Task "fetch" { entry = function() end }'
    include_file = tmp_path / "tasks.tac"
    include_file.write_text(include_source)

    runtime = _runtime_for_parse(tmp_path, FakeSandbox(include_source))

    registry = runtime._parse_declarations('IncludeTasks("tasks.tac")')

    assert "extras" in registry.tasks
    assert "fetch" in registry.tasks["extras"].children


def test_parse_declarations_extends_include_queue(tmp_path):
    class FakeSandbox:
        def __init__(self, include_source, nested_source):
            self._globals = {}
            self.include_source = include_source
            self.nested_source = nested_source
            self.lua = SimpleNamespace(globals=lambda: {})

        def set_global(self, name, value):
            self._globals[name] = value

        def setup_assignment_interception(self, _callback):
            pass

        def execute(self, source):
            if source == self.include_source:
                self._globals["IncludeTasks"]("nested.tac")
                return None
            if source == self.nested_source:
                self._globals["Task"]("inner", {"entry": lambda: None})
                return None
            self._globals["IncludeTasks"]("tasks.tac")
            return None

    include_source = 'IncludeTasks("nested.tac")'
    nested_source = 'Task "inner" { entry = function() end }'
    (tmp_path / "tasks.tac").write_text(include_source)
    (tmp_path / "nested.tac").write_text(nested_source)

    runtime = _runtime_for_parse(tmp_path, FakeSandbox(include_source, nested_source))

    registry = runtime._parse_declarations('IncludeTasks("tasks.tac")')

    assert "inner" in registry.tasks


def test_parse_declarations_skips_empty_include_paths(tmp_path, monkeypatch):
    class FakeSandbox:
        def __init__(self):
            self._globals = {}
            self.lua = SimpleNamespace(globals=lambda: {})

        def set_global(self, name, value):
            self._globals[name] = value

        def setup_assignment_interception(self, _callback):
            pass

        def execute(self, _source):
            self._globals["IncludeTasks"](None)
            return None

    captured = {}

    def fake_create_dsl_stubs(builder, *_args, **_kwargs):
        captured["builder"] = builder

        def include_tasks(_path=None, _namespace=None):
            builder.register_include_tasks(None)

        return {"IncludeTasks": include_tasks, "_tactus_register_binding": None, "_registries": {}}

    monkeypatch.setattr("tactus.core.runtime.create_dsl_stubs", fake_create_dsl_stubs)

    runtime = _runtime_for_parse(tmp_path, FakeSandbox())

    registry = runtime._parse_declarations("IncludeTasks(nil)")

    assert registry.tasks == {}


def test_parse_declarations_rejects_non_task_include(tmp_path):
    class FakeSandbox:
        def __init__(self, include_source):
            self._globals = {}
            self.include_source = include_source
            self.lua = SimpleNamespace(globals=lambda: {})

        def set_global(self, name, value):
            self._globals[name] = value

        def setup_assignment_interception(self, _callback):
            pass

        def execute(self, source):
            if source == self.include_source:
                self._globals["Agent"](
                    {"provider": "openai", "model": "gpt-4o", "system_prompt": "hi"}
                )
                return None
            self._globals["IncludeTasks"]("tasks.tac")
            return None

    include_source = 'Agent "alpha" { provider = "openai" }'
    include_file = tmp_path / "tasks.tac"
    include_file.write_text(include_source)

    runtime = _runtime_for_parse(tmp_path, FakeSandbox(include_source))

    with pytest.raises(
        TactusRuntimeError, match="IncludeTasks files must only contain Task declarations"
    ):
        runtime._parse_declarations('IncludeTasks("tasks.tac")')


def test_parse_declarations_detects_include_cycle(tmp_path):
    class FakeSandbox:
        def __init__(self, include_source):
            self._globals = {}
            self.include_source = include_source
            self.lua = SimpleNamespace(globals=lambda: {})

        def set_global(self, name, value):
            self._globals[name] = value

        def setup_assignment_interception(self, _callback):
            pass

        def execute(self, source):
            if source == self.include_source:
                self._globals["IncludeTasks"]("tasks.tac")
                return None
            self._globals["IncludeTasks"]("tasks.tac")
            return None

    include_source = 'IncludeTasks("tasks.tac")'
    include_file = tmp_path / "tasks.tac"
    include_file.write_text(include_source)

    runtime = _runtime_for_parse(tmp_path, FakeSandbox(include_source))

    with pytest.raises(TactusRuntimeError, match="IncludeTasks cycle detected"):
        runtime._parse_declarations('IncludeTasks("tasks.tac")')


def test_parse_declarations_missing_include_file(tmp_path):
    class FakeSandbox:
        def __init__(self):
            self._globals = {}
            self.lua = SimpleNamespace(globals=lambda: {})

        def set_global(self, name, value):
            self._globals[name] = value

        def setup_assignment_interception(self, _callback):
            pass

        def execute(self, _source):
            self._globals["IncludeTasks"]("missing.tac")
            return None

    runtime = _runtime_for_parse(tmp_path, FakeSandbox())

    with pytest.raises(TactusRuntimeError, match="Included tasks file not found"):
        runtime._parse_declarations('IncludeTasks("missing.tac")')


def test_parse_declarations_include_lua_error(tmp_path):
    from tactus.core import runtime as runtime_module

    class FakeSandbox:
        def __init__(self, include_source):
            self._globals = {}
            self.include_source = include_source
            self.lua = SimpleNamespace(globals=lambda: {})

        def set_global(self, name, value):
            self._globals[name] = value

        def setup_assignment_interception(self, _callback):
            pass

        def execute(self, source):
            if source == self.include_source:
                raise runtime_module.LuaSandboxError("boom")
            self._globals["IncludeTasks"]("tasks.tac")
            return None

    include_source = 'Task "fetch" { entry = function() end }'
    include_file = tmp_path / "tasks.tac"
    include_file.write_text(include_source)

    runtime = _runtime_for_parse(tmp_path, FakeSandbox(include_source))

    with pytest.raises(TactusRuntimeError, match="Failed to execute IncludeTasks file"):
        runtime._parse_declarations('IncludeTasks("tasks.tac")')


def test_parse_declarations_rejects_duplicate_namespace(tmp_path):
    class FakeSandbox:
        def __init__(self, include_source):
            self._globals = {}
            self.include_source = include_source
            self.lua = SimpleNamespace(globals=lambda: {})

        def set_global(self, name, value):
            self._globals[name] = value

        def setup_assignment_interception(self, _callback):
            pass

        def execute(self, source):
            if source == self.include_source:
                self._globals["Task"]("fetch", {"entry": lambda: None})
                return None
            self._globals["Task"]("extras", {"entry": lambda: None})
            self._globals["IncludeTasks"]("tasks.tac", "extras")
            return None

    include_source = 'Task "fetch" { entry = function() end }'
    include_file = tmp_path / "tasks.tac"
    include_file.write_text(include_source)

    runtime = _runtime_for_parse(tmp_path, FakeSandbox(include_source))

    with pytest.raises(TactusRuntimeError, match="Duplicate task namespace"):
        runtime._parse_declarations('IncludeTasks("tasks.tac", "extras")')


class _FakePlan:
    def __init__(self, *, status="ready", tasks=None):
        self.status = status
        self.tasks = tasks or []
        self.root = SimpleNamespace(reason=None)
        self.called_with = None

    def execute(self, *, mode="prompt", handler_registry=None, prompt_handler=None):
        self.called_with = {
            "mode": mode,
            "handler_registry": handler_registry or {},
            "prompt_handler": prompt_handler,
        }
        return [{"ok": True}]


def test_execute_dependency_plan_returns_empty_when_complete():
    runtime = TactusRuntime.__new__(TactusRuntime)
    runtime.dependency_mode = "auto"
    plan = _FakePlan(status="complete")

    result = runtime._execute_dependency_plan(plan=plan, corpus=object(), label="test")

    assert result == []


def test_execute_dependency_plan_rejects_blocked_plan():
    runtime = TactusRuntime.__new__(TactusRuntime)
    runtime.dependency_mode = "auto"
    plan = _FakePlan(status="blocked")
    plan.root.reason = "blocked"

    with pytest.raises(RuntimeError, match="blocked"):
        runtime._execute_dependency_plan(plan=plan, corpus=object(), label="test")


def test_execute_dependency_plan_rejects_when_no_deps():
    runtime = TactusRuntime.__new__(TactusRuntime)
    runtime.dependency_mode = "none"
    plan = _FakePlan(status="ready")

    with pytest.raises(RuntimeError, match="Dependencies missing"):
        runtime._execute_dependency_plan(plan=plan, corpus=object(), label="test")


def test_execute_dependency_plan_rejects_prompt_decline():
    runtime = TactusRuntime.__new__(TactusRuntime)
    runtime.dependency_mode = "prompt"
    runtime.dependency_prompt_handler = lambda *_args, **_kwargs: False
    plan = _FakePlan(status="ready")

    with pytest.raises(RuntimeError, match="declined"):
        runtime._execute_dependency_plan(plan=plan, corpus=object(), label="test")


def test_execute_dependency_plan_executes_with_handlers(monkeypatch):
    runtime = TactusRuntime.__new__(TactusRuntime)
    runtime.dependency_mode = "auto"
    plan = _FakePlan(status="ready")

    monkeypatch.setattr("biblicus.workflow.build_default_handler_registry", lambda _corpus: {})

    result = runtime._execute_dependency_plan(
        plan=plan,
        corpus=object(),
        label="test",
        load_task_name="fetch",
        extract_task_name="extract",
        index_task_name="index",
    )

    assert result == [{"ok": True}]
    assert plan.called_with is not None
    assert plan.called_with["mode"] == "auto"
    assert "load" in plan.called_with["handler_registry"]
    assert "extract" in plan.called_with["handler_registry"]
    assert "index" in plan.called_with["handler_registry"]


def test_find_task_providing_normalizes_aliases():
    runtime = TactusRuntime.__new__(TactusRuntime)
    task = TaskDeclaration(name="fetch", provides={"kind": "fetch", "corpus": "docs"})
    registry = SimpleNamespace(tasks={"fetch": task}, retrievers={}, corpora={"docs": {}})
    runtime.registry = registry

    assert runtime._find_task_providing(kind="load", corpus_name="docs") == "fetch"
