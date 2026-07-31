"""Outside-in specifications for the host-neutral scheduled-continuation primitive."""

from datetime import datetime, timedelta, timezone

import pytest
from behave import given, then, when

from tactus.adapters.memory import MemoryStorage
from tactus.core.exceptions import ProcedureWaitingForTime
from tactus.core.execution_context import BaseExecutionContext
from tactus.primitives.procedure import ProcedurePrimitive


class Clock:
    def __init__(self, now: datetime):
        self.now = now

    def __call__(self) -> datetime:
        return self.now


def _primitive(context):
    return ProcedurePrimitive(
        context.execution_context,
        runtime_factory=lambda _name, _params: None,
    )


def _request(context, *, key="artifact-publication"):
    return {
        "key": key,
        "resume_at": context.resume_at.isoformat().replace("+00:00", "Z"),
        "reason": "artifact publication retry",
    }


@given("a procedure requests a stable continuation key and a future resume time")
def step_future_continuation(context):
    context.clock = Clock(datetime(2026, 7, 31, 12, tzinfo=timezone.utc))
    context.resume_at = context.clock.now + timedelta(minutes=5)
    context.execution_context = BaseExecutionContext(
        "scheduled-continuation", MemoryStorage(), clock=context.clock
    )
    context.request = _request(context)


@when("it calls Procedure.defer")
def step_defer(context):
    with pytest.raises(ProcedureWaitingForTime) as raised:
        _primitive(context).defer(context.request)
    context.waiting = raised.value


@then("Tactus checkpoints the normalized scheduled continuation request")
def step_checkpointed(context):
    assert context.execution_context.metadata.execution_log[0].result == {
        "pending": True,
        "request": context.request,
    }


@then("exposes a distinct waiting-for-time outcome")
def step_waiting_outcome(context):
    assert context.waiting.procedure_id == "scheduled-continuation"
    assert context.waiting.request == context.request
    assert context.waiting.resume_at == context.resume_at


@then("does not sleep the worker thread")
def step_no_sleep(context):
    assert not hasattr(context.waiting, "thread")
    assert context.execution_context.metadata.execution_log[0].type == "scheduled_continuation"


@given("a checkpointed scheduled continuation is not yet due")
def step_pending_continuation(context):
    step_future_continuation(context)
    step_defer(context)
    context.execution_context = BaseExecutionContext(
        "scheduled-continuation", context.execution_context.storage, clock=context.clock
    )


@when("the procedure replays before the due time")
def step_replay_before_due(context):
    with pytest.raises(ProcedureWaitingForTime) as raised:
        _primitive(context).defer(context.request)
    context.replayed_waiting = raised.value


@then("the original scheduled continuation remains authoritative")
def step_original_authoritative(context):
    assert context.replayed_waiting.request == context.request
    assert len(context.execution_context.metadata.execution_log) == 1


@then("Tactus exposes waiting-for-time again")
def step_waiting_again(context):
    assert context.replayed_waiting.resume_at == context.resume_at


@given("a checkpointed scheduled continuation is due")
def step_due_continuation(context):
    step_pending_continuation(context)
    context.clock.now = context.resume_at


@when("the host resumes the procedure")
def step_resume_due(context):
    context.result = _primitive(context).defer(context.request)


@then("Procedure.defer returns the completed continuation result")
def step_completed_result(context):
    assert context.result == {"completed": True, **context.request}


@then("execution continues exactly once after the scheduled continuation")
def step_once(context):
    assert len(context.execution_context.metadata.execution_log) == 1
    context.execution_context.metadata.replay_index = 0
    assert _primitive(context).defer(context.request) == context.result


@given("a scheduled continuation is already checkpointed")
def step_existing_continuation(context):
    step_pending_continuation(context)


@when("replay supplies a conflicting continuation key or time")
def step_conflicting_continuation(context):
    context.conflicting_request = _request(context, key="different-key")


@then("Tactus rejects the conflicting scheduled continuation")
def step_reject_conflict(context):
    with pytest.raises(ValueError, match="conflicts"):
        _primitive(context).defer(context.conflicting_request)
