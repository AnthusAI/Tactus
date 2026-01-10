from tactus.adapters.memory import MemoryStorage
from tactus.core.execution_context import BaseExecutionContext
from tactus.primitives.step import CheckpointPrimitive


def test_checkpoint_exists_and_get_by_position():
    storage = MemoryStorage()
    context = BaseExecutionContext(procedure_id="proc_1", storage_backend=storage)
    checkpoint = CheckpointPrimitive(context)

    context.checkpoint(lambda: {"value": 123}, "explicit_checkpoint")

    assert checkpoint.exists(0) is True
    assert checkpoint.get(0) == {"value": 123}

    assert checkpoint.exists(1) is False
    assert checkpoint.get(1) is None


def test_checkpoint_accepts_string_positions():
    storage = MemoryStorage()
    context = BaseExecutionContext(procedure_id="proc_2", storage_backend=storage)
    checkpoint = CheckpointPrimitive(context)

    context.checkpoint(lambda: "ok", "explicit_checkpoint")

    assert checkpoint.exists("0") is True
    assert checkpoint.get("0") == "ok"


def test_checkpoint_clear_after_affects_exists_and_get():
    storage = MemoryStorage()
    context = BaseExecutionContext(procedure_id="proc_3", storage_backend=storage)
    checkpoint = CheckpointPrimitive(context)

    context.checkpoint(lambda: "a", "explicit_checkpoint")
    context.checkpoint(lambda: "b", "explicit_checkpoint")
    context.checkpoint(lambda: "c", "explicit_checkpoint")

    assert checkpoint.exists(2) is True
    assert checkpoint.get(2) == "c"

    checkpoint.clear_after(2)

    assert checkpoint.exists(1) is True
    assert checkpoint.get(1) == "b"
    assert checkpoint.exists(2) is False
    assert checkpoint.get(2) is None
