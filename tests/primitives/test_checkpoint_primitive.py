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


def test_checkpoint_coerce_position_errors():
    storage = MemoryStorage()
    context = BaseExecutionContext(procedure_id="proc_4", storage_backend=storage)
    checkpoint = CheckpointPrimitive(context)

    for value in [True, 1.5, "bad", [], {}]:
        try:
            checkpoint._coerce_position(value)
        except TypeError:
            continue
        raise AssertionError(f"Expected TypeError for {value!r}")


def test_checkpoint_coerce_position_accepts_integer_float():
    storage = MemoryStorage()
    context = BaseExecutionContext(procedure_id="proc_5", storage_backend=storage)
    checkpoint = CheckpointPrimitive(context)

    assert checkpoint._coerce_position(3.0) == 3


def test_checkpoint_clear_all_and_next_position():
    class DummyContext:
        def __init__(self):
            self.cleared = False
            self.cleared_after = None
            self.pos = 7

        def checkpoint_clear_all(self):
            self.cleared = True

        def checkpoint_clear_after(self, position):
            self.cleared_after = position

        def next_position(self):
            return self.pos

    context = DummyContext()
    checkpoint = CheckpointPrimitive(context)

    checkpoint.clear_all()
    assert context.cleared is True

    checkpoint.clear_after(4)
    assert context.cleared_after == 4

    assert checkpoint.next_position() == 7


def test_checkpoint_exists_without_metadata_raises():
    class DummyContext:
        metadata = None

    checkpoint = CheckpointPrimitive(DummyContext())

    try:
        checkpoint.exists(0)
    except RuntimeError as exc:
        assert "checkpoint metadata" in str(exc)
    else:
        raise AssertionError("Expected RuntimeError for missing metadata")


def test_checkpoint_get_without_metadata_raises():
    class DummyContext:
        metadata = None

    checkpoint = CheckpointPrimitive(DummyContext())

    try:
        checkpoint.get(0)
    except RuntimeError as exc:
        assert "checkpoint metadata" in str(exc)
    else:
        raise AssertionError("Expected RuntimeError for missing metadata")
