from datetime import datetime, timedelta, timezone

import pytest

from tactus.adapters.file_storage import FileStorage
from tactus.adapters.memory import MemoryStorage
from tactus.core.exceptions import ProcedureWaitingForTime
from tactus.core.execution_context import BaseExecutionContext
from tactus.core.runtime import TactusRuntime
from tactus.primitives.procedure import ProcedurePrimitive


def test_scheduled_continuation_outcome_is_available_from_public_api():
    from tactus import ProcedureWaitingForTime as public_exception

    assert public_exception is ProcedureWaitingForTime


class Clock:
    def __init__(self, now: datetime):
        self.now = now

    def __call__(self) -> datetime:
        return self.now


def primitive(context):
    return ProcedurePrimitive(context, runtime_factory=lambda _name, _params: None)


def request(resume_at: datetime, **overrides):
    value = {
        "key": "retry-publication",
        "resume_at": resume_at.isoformat().replace("+00:00", "Z"),
        "reason": "retry durable artifact publication",
    }
    value.update(overrides)
    return value


def test_defer_checkpoints_normalized_request_and_never_sleeps():
    clock = Clock(datetime(2026, 7, 31, 12, tzinfo=timezone.utc))
    context = BaseExecutionContext("procedure", MemoryStorage(), clock=clock)
    due = clock.now + timedelta(minutes=5)

    with pytest.raises(ProcedureWaitingForTime) as raised:
        primitive(context).defer(request(due))

    assert raised.value.request == request(due)
    assert raised.value.resume_at == due
    assert context.metadata.execution_log[0].type == "scheduled_continuation"
    assert context.metadata.execution_log[0].result == {
        "pending": True,
        "request": request(due),
    }


def test_defer_replay_before_due_reuses_durable_request_and_remains_waiting():
    clock = Clock(datetime(2026, 7, 31, 12, tzinfo=timezone.utc))
    storage = MemoryStorage()
    due = clock.now + timedelta(minutes=5)
    original = request(due)

    with pytest.raises(ProcedureWaitingForTime):
        primitive(BaseExecutionContext("procedure", storage, clock=clock)).defer(original)

    resumed = BaseExecutionContext("procedure", storage, clock=clock)
    with pytest.raises(ProcedureWaitingForTime) as raised:
        primitive(resumed).defer(original)

    assert raised.value.request == original
    assert len(resumed.metadata.execution_log) == 1
    assert resumed.metadata.execution_log[0].result == {"pending": True, "request": original}


def test_defer_due_replays_once_and_returns_completion_result(tmp_path):
    clock = Clock(datetime(2026, 7, 31, 12, tzinfo=timezone.utc))
    storage = FileStorage(str(tmp_path))
    due = clock.now + timedelta(minutes=5)
    original = request(due)

    with pytest.raises(ProcedureWaitingForTime):
        primitive(BaseExecutionContext("procedure", storage, clock=clock)).defer(original)

    clock.now = due
    resumed = BaseExecutionContext("procedure", FileStorage(str(tmp_path)), clock=clock)
    result = primitive(resumed).defer(original)

    assert result == {"completed": True, **original}
    assert resumed.metadata.execution_log[0].result == result
    resumed.metadata.replay_index = 0
    assert primitive(resumed).defer(original) == result


def test_defer_rejects_conflicting_replay_after_completion():
    clock = Clock(datetime(2026, 7, 31, 12, tzinfo=timezone.utc))
    storage = MemoryStorage()
    original = request(clock.now + timedelta(minutes=5))

    with pytest.raises(ProcedureWaitingForTime):
        primitive(BaseExecutionContext("procedure", storage, clock=clock)).defer(original)

    clock.now += timedelta(minutes=5)
    completed = BaseExecutionContext("procedure", storage, clock=clock)
    assert primitive(completed).defer(original) == {"completed": True, **original}

    completed.metadata.replay_index = 0
    with pytest.raises(ValueError, match="conflicts"):
        primitive(completed).defer({**original, "key": "different-key"})


@pytest.mark.parametrize(
    "conflict",
    [
        {"key": "different-key"},
        {"resume_at": "2026-07-31T12:06:00Z"},
        {"reason": "different reason"},
    ],
)
def test_defer_rejects_conflicting_replay_request(conflict):
    clock = Clock(datetime(2026, 7, 31, 12, tzinfo=timezone.utc))
    storage = MemoryStorage()
    original = request(clock.now + timedelta(minutes=5))

    with pytest.raises(ProcedureWaitingForTime):
        primitive(BaseExecutionContext("procedure", storage, clock=clock)).defer(original)

    changed = {**original, **conflict}
    with pytest.raises(ValueError, match="conflicts"):
        primitive(BaseExecutionContext("procedure", storage, clock=clock)).defer(changed)


@pytest.mark.parametrize(
    "invalid_request, message",
    [
        ({}, "key"),
        ({"key": "", "resume_at": "2026-07-31T12:05:00Z", "reason": "retry"}, "key"),
        ({"key": "retry", "resume_at": "not-a-time", "reason": "retry"}, "resume_at"),
        ({"key": "retry", "resume_at": "2026-07-31T12:05:00", "reason": "retry"}, "timezone"),
        ({"key": "retry", "resume_at": "2026-07-31T12:05:00Z", "reason": ""}, "reason"),
        (
            {"key": "retry", "resume_at": "2026-07-31T12:05:00Z", "reason": "retry", "extra": 1},
            "unsupported",
        ),
    ],
)
def test_defer_fails_closed_for_invalid_requests(invalid_request, message):
    context = BaseExecutionContext("procedure", MemoryStorage())
    with pytest.raises(ValueError, match=message):
        primitive(context).defer(invalid_request)


@pytest.mark.asyncio
async def test_runtime_maps_scheduled_continuation_to_waiting_for_time(tmp_path):
    source = """
Procedure {
    function(input)
        Procedure.defer({
            key = "retry-publication",
            resume_at = "2999-01-01T00:00:00Z",
            reason = "retry durable publication"
        })
        return {unexpected = true}
    end
}
"""
    runtime = TactusRuntime(
        procedure_id="scheduled-runtime", storage_backend=FileStorage(str(tmp_path))
    )

    result = await runtime.execute(source, context={}, format="lua")

    assert result == {
        "success": False,
        "status": "WAITING_FOR_TIME",
        "procedure_id": "scheduled-runtime",
        "request": {
            "key": "retry-publication",
            "resume_at": "2999-01-01T00:00:00Z",
            "reason": "retry durable publication",
        },
        "resume_at": "2999-01-01T00:00:00Z",
        "reason": "retry durable publication",
        "continuation_key": "retry-publication",
        "message": "Procedure scheduled-runtime waiting until 2999-01-01T00:00:00Z",
        "session_id": None,
    }


@pytest.mark.asyncio
async def test_legacy_yaml_runtime_preserves_scheduled_continuation_control_flow(tmp_path):
    source = """
name: Scheduled YAML
version: 1.0.0
class: Tactus
procedure: |
  Procedure.defer({
    key = "retry-publication",
    resume_at = "2999-01-01T00:00:00Z",
    reason = "retry durable publication"
  })
  return {unexpected = true}
"""
    runtime = TactusRuntime(
        procedure_id="scheduled-yaml-runtime",
        storage_backend=FileStorage(str(tmp_path)),
        run_id="stable-run",
    )

    result = await runtime.execute(source, context={}, format="yaml")

    assert result["success"] is False
    assert result["status"] == "WAITING_FOR_TIME"
    assert result["request"]["key"] == "retry-publication"
