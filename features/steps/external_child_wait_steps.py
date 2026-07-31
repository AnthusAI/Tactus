"""Outside-in specifications for the host-neutral external-child wait primitive."""

import pytest
from behave import given, then, when

from tactus.adapters.memory import MemoryStorage
from tactus.core.exceptions import ProcedureWaitingForChildren
from tactus.core.execution_context import BaseExecutionContext
from tactus.primitives.procedure import ProcedurePrimitive


class ExternalChildResolver:
    def __init__(self):
        self.children = []
        self.requests = []

    def __call__(self, request):
        self.requests.append(request)
        return {"children": self.children, "complete": False}


def _primitive(context):
    return ProcedurePrimitive(
        context.execution_context,
        runtime_factory=lambda _name, _params: None,
    )


@given("a procedure has stable external child references")
def step_stable_children(context):
    context.resolver = ExternalChildResolver()
    context.resolver.children = [
        {"id": "alpha", "terminal": True, "status": "succeeded"},
        {"id": "beta", "terminal": False, "status": "running"},
    ]
    context.execution_context = BaseExecutionContext(
        "external-children", MemoryStorage(), child_wait_resolver=context.resolver
    )
    context.request = {
        "children": [
            {"id": "alpha", "host_token": "one"},
            {"id": "beta", "host_token": "two"},
        ]
    }


@when("it waits for all children and at least one remains nonterminal")
def step_wait_for_all(context):
    with pytest.raises(ProcedureWaitingForChildren) as raised:
        _primitive(context).await_children(context.request)
    context.waiting = raised.value


@then("Tactus checkpoints the wait request")
def step_checkpoints_wait_request(context):
    assert context.execution_context.metadata.execution_log[0].result == {
        "pending": True,
        "request": {**context.request, "mode": "all"},
    }
    assert context.waiting.request == {**context.request, "mode": "all"}


@then("exposes a distinct waiting-for-children outcome")
def step_distinct_wait_outcome(context):
    assert context.waiting.procedure_id == "external-children"
    assert context.waiting.children == context.resolver.children


@then("does not use an in-memory thread or fixed completion timeout")
def step_no_process_local_wait(context):
    primitive = _primitive(context)
    assert primitive.handles == {}
    assert not hasattr(context.waiting, "timeout")


@given("a waiting procedure is resumed")
def step_waiting_procedure_resumed(context):
    step_stable_children(context)
    step_wait_for_all(context)
    context.execution_context = BaseExecutionContext(
        "external-children", context.execution_context.storage, child_wait_resolver=context.resolver
    )


@when("the host reports terminal states for every requested child")
def step_all_children_terminal(context):
    context.resolver.children = [
        {"id": "alpha", "terminal": True, "status": "succeeded"},
        {"id": "beta", "terminal": True, "status": "failed", "error": "remote failure"},
    ]
    context.result = _primitive(context).await_children(context.request)


@then("the wait checkpoint returns the terminal child results")
def step_terminal_results(context):
    assert context.result == {"children": context.resolver.children, "complete": True}


@then("execution continues exactly once after the wait")
def step_continues_once(context):
    assert len(context.execution_context.metadata.execution_log) == 1
    assert len(context.resolver.requests) == 2


@given("several external children complete with mixed terminal states")
def step_mixed_children(context):
    context.resolver = ExternalChildResolver()
    context.resolver.children = [
        {"id": "success", "terminal": True, "status": "succeeded", "result": {"value": 1}},
        {"id": "failure", "terminal": True, "status": "failed", "error": "remote failure"},
    ]
    context.execution_context = BaseExecutionContext(
        "mixed-children", MemoryStorage(), child_wait_resolver=context.resolver
    )
    context.request = {"children": [{"id": "success"}, {"id": "failure"}]}


@when("the wait resolves")
def step_mixed_wait_resolves(context):
    context.result = _primitive(context).await_children(context.request)


@then("each child result remains independently visible")
def step_results_visible(context):
    assert context.result["children"] == context.resolver.children


@then("successful siblings are not discarded or cancelled")
def step_success_not_cancelled(context):
    assert context.result["children"][0]["status"] == "succeeded"
    assert "cancelled" not in context.result["children"][0]
