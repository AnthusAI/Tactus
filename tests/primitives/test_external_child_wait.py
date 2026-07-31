import pytest

from tactus.adapters.memory import MemoryStorage
from tactus.adapters.file_storage import FileStorage
from tactus.core.exceptions import ProcedureWaitingForChildren
from tactus.core.execution_context import BaseExecutionContext
from tactus.core.runtime import TactusRuntime
from tactus.primitives.procedure import ProcedurePrimitive


class Resolver:
    def __init__(self, children, complete=False):
        self.children = children
        self.complete = complete
        self.requests = []

    def __call__(self, request):
        self.requests.append(request)
        return {"children": self.children, "complete": self.complete}


def primitive(context):
    return ProcedurePrimitive(context, runtime_factory=lambda _name, _params: None)


def test_await_children_preserves_references_and_suspends_without_thread():
    resolver = Resolver(
        [
            {"id": "a", "terminal": True, "status": "complete"},
            {"id": "b", "terminal": False, "resource": {"url": "host://b"}},
        ]
    )
    context = BaseExecutionContext("procedure", MemoryStorage(), child_wait_resolver=resolver)
    request = {
        "children": [
            {"id": "a", "opaque": {"ticket": 1}},
            {"id": "b", "host_field": ["unmodified"]},
        ]
    }

    with pytest.raises(ProcedureWaitingForChildren) as raised:
        primitive(context).await_children(request)

    assert resolver.requests == [{**request, "mode": "all"}]
    assert raised.value.procedure_id == "procedure"
    assert raised.value.request == {**request, "mode": "all"}
    assert raised.value.children == resolver.children
    assert context.metadata.execution_log[0].result == {
        "pending": True,
        "request": {**request, "mode": "all"},
    }
    assert primitive(context).handles == {}


@pytest.mark.parametrize(
    ("wait_request", "message"),
    [
        ({}, "at least one child"),
        ({"children": []}, "at least one child"),
        ({"children": [{"id": ""}]}, "nonempty string id"),
        ({"children": [{"id": "a"}, {"id": "a"}]}, "duplicated"),
        ({"children": [{"id": "a"}], "mode": "first"}, "mode"),
    ],
)
def test_await_children_validates_request(wait_request, message):
    context = BaseExecutionContext(
        "procedure", MemoryStorage(), child_wait_resolver=lambda _request: {}
    )
    with pytest.raises(ValueError, match=message):
        primitive(context).await_children(wait_request)


def test_await_children_any_returns_all_current_results_when_one_terminal():
    children = [
        {"id": "a", "terminal": True, "status": "failed", "error": "remote"},
        {"id": "b", "terminal": False, "status": "running"},
    ]
    resolver = Resolver(children)
    context = BaseExecutionContext("procedure", MemoryStorage(), child_wait_resolver=resolver)

    result = primitive(context).await_children(
        {"children": [{"id": "a"}, {"id": "b"}], "mode": "any"}
    )

    assert result == {"children": children, "complete": True}


def test_await_children_replays_pending_checkpoint_and_returns_once_after_progress():
    storage = MemoryStorage()
    resolver = Resolver([{"id": "a", "terminal": False}], complete=False)
    request = {"children": [{"id": "a", "opaque": "preserved"}]}
    context = BaseExecutionContext("procedure", storage, child_wait_resolver=resolver)

    with pytest.raises(ProcedureWaitingForChildren):
        primitive(context).await_children(request)

    resolver.children = [{"id": "a", "terminal": True, "result": {"ok": True}}]
    resumed = BaseExecutionContext("procedure", storage, child_wait_resolver=resolver)
    result = primitive(resumed).await_children(request)

    assert result == {"children": resolver.children, "complete": True}
    assert len(resumed.metadata.execution_log) == 1
    assert resumed.metadata.execution_log[0].result == result
    assert len(resolver.requests) == 2
    resumed.metadata.replay_index = 0
    assert primitive(resumed).await_children(request) == result
    assert len(resolver.requests) == 2


def test_await_children_pending_request_survives_file_storage_replay(tmp_path):
    storage = FileStorage(str(tmp_path))
    resolver = Resolver([{"id": "a", "terminal": False}])
    request = {"children": [{"id": "a", "opaque": {"host": "reference"}}]}

    with pytest.raises(ProcedureWaitingForChildren):
        primitive(
            BaseExecutionContext("procedure", storage, child_wait_resolver=resolver)
        ).await_children(request)

    restored = BaseExecutionContext(
        "procedure", FileStorage(str(tmp_path)), child_wait_resolver=resolver
    )
    assert restored.metadata.execution_log[0].result == {
        "pending": True,
        "request": {**request, "mode": "all"},
    }


def test_await_children_replay_uses_persisted_request_when_dynamic_input_changes(tmp_path):
    """A retry must resolve the child identities captured by the first attempt."""
    storage = FileStorage(str(tmp_path))
    resolver = Resolver([{"id": "first-child", "terminal": False}])
    original_request = {"children": [{"id": "first-child", "opaque": {"launch": "first"}}]}

    with pytest.raises(ProcedureWaitingForChildren):
        primitive(
            BaseExecutionContext("procedure", storage, child_wait_resolver=resolver)
        ).await_children(original_request)

    resolver.children = [{"id": "first-child", "terminal": True, "status": "complete"}]
    resumed = BaseExecutionContext(
        "procedure", FileStorage(str(tmp_path)), child_wait_resolver=resolver
    )
    changed_request = {"children": [{"id": "second-child", "opaque": {"launch": "changed"}}]}

    result = primitive(resumed).await_children(changed_request)

    assert result == {"children": resolver.children, "complete": True}
    assert resolver.requests == [
        {**original_request, "mode": "all"},
        {**original_request, "mode": "all"},
    ]
    assert resumed.metadata.execution_log[0].result == result

    resumed.metadata.replay_index = 0
    assert primitive(resumed).await_children(changed_request) == result
    assert len(resolver.requests) == 2


@pytest.mark.asyncio
async def test_runtime_file_replay_keeps_persisted_children_and_reports_waiting_status(tmp_path):
    """The public runtime status and a FileStorage restart retain the original child."""
    source = """
Procedure {
    input = { child_id = field.string{required = true} },
    output = { child_id = field.string{required = true} },
    function(input)
        local result = Procedure.await_children({
            children = {{id = input.child_id, host_reference = "opaque"}}
        })
        return {child_id = result.children[0].id}
    end
}
"""
    storage_directory = str(tmp_path / "storage")
    resolver = Resolver([{"id": "first-child", "terminal": False}])

    first = TactusRuntime(
        procedure_id="external-wait-runtime",
        storage_backend=FileStorage(storage_directory),
        child_wait_resolver=resolver,
    )
    pending = await first.execute(source, context={"child_id": "first-child"}, format="lua")

    assert pending["success"] is False
    assert pending["status"] == "WAITING_FOR_CHILDREN"
    assert pending["request"] == {
        "children": [{"id": "first-child", "host_reference": "opaque"}],
        "mode": "all",
    }

    resolver.children = [{"id": "first-child", "terminal": True, "status": "complete"}]
    resumed = TactusRuntime(
        procedure_id="external-wait-runtime",
        storage_backend=FileStorage(storage_directory),
        child_wait_resolver=resolver,
    )
    completed = await resumed.execute(source, context={"child_id": "second-child"}, format="lua")

    assert completed["success"] is True
    assert completed["result"] == {"child_id": "first-child"}
    assert resolver.requests == [
        {
            "children": [{"id": "first-child", "host_reference": "opaque"}],
            "mode": "all",
        },
        {
            "children": [{"id": "first-child", "host_reference": "opaque"}],
            "mode": "all",
        },
    ]

    replayed = TactusRuntime(
        procedure_id="external-wait-runtime",
        storage_backend=FileStorage(storage_directory),
        child_wait_resolver=resolver,
    )
    cached = await replayed.execute(source, context={"child_id": "third-child"}, format="lua")

    assert cached["success"] is True
    assert cached["result"] == {"child_id": "first-child"}
    assert len(resolver.requests) == 2


@pytest.mark.parametrize(
    "resolution",
    [
        {"children": [], "complete": False},
        {"children": [{"id": "unknown", "terminal": True}], "complete": True},
        {"children": [{"id": "a", "terminal": True}], "complete": "yes"},
        {"children": [{"id": "a", "terminal": "yes"}], "complete": True},
    ],
)
def test_await_children_validates_resolver_contract(resolution):
    context = BaseExecutionContext(
        "procedure", MemoryStorage(), child_wait_resolver=lambda _request: resolution
    )
    with pytest.raises(ValueError):
        primitive(context).await_children({"children": [{"id": "a"}]})
