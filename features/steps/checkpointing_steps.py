"""
Step definitions for Checkpointing feature.
"""

from behave import given, when, then
from tactus.core.execution_context import BaseExecutionContext
from tactus.adapters.memory import MemoryStorage
import math


@given("a Tactus workflow with checkpointing enabled")
def step_impl(context):
    """Initialize workflow with checkpointing."""
    context.procedure_id = "test_procedure"
    context.storage = MemoryStorage()
    context.execution_context = BaseExecutionContext(
        procedure_id=context.procedure_id, storage_backend=context.storage
    )
    context.execution_count = {}  # Track how many times operations execute


@given("an in-memory storage backend")
def step_impl(context):
    """Storage backend is already initialized in previous step."""
    assert context.storage is not None


@given('I have never run checkpoint "{checkpoint_name}"')
def step_impl(context, checkpoint_name):
    """Ensure checkpoint doesn't exist."""
    # In position-based system, check if execution log is empty at expected position
    metadata = context.storage.load_procedure_metadata(context.procedure_id)
    position = len(metadata.execution_log)
    context.checkpoint_positions = getattr(context, "checkpoint_positions", {})
    context.checkpoint_positions[checkpoint_name] = position
    assert (
        position == 0 or checkpoint_name not in context.checkpoint_positions
    ), f"Checkpoint {checkpoint_name} should not exist yet"


@when('I execute step "{checkpoint_name}" that computes factorial(100)')
def step_impl(context, checkpoint_name):
    """Execute expensive factorial calculation with checkpointing."""
    context.execution_count[checkpoint_name] = context.execution_count.get(checkpoint_name, 0)
    context.checkpoint_positions = getattr(context, "checkpoint_positions", {})

    def compute_factorial():
        context.execution_count[checkpoint_name] += 1
        return math.factorial(100)

    # Track position before execution
    position = context.execution_context.next_position()
    context.checkpoint_positions[checkpoint_name] = position
    context.result = context.execution_context.checkpoint(compute_factorial, "explicit_checkpoint")


@then("the operation should execute")
def step_impl(context):
    """Verify operation was executed (not cached)."""
    # Check that at least one operation was executed
    total_executions = sum(context.execution_count.values())
    assert total_executions > 0, "Expected operation to execute"


@then("the result should be checkpointed")
def step_impl(context):
    """Verify result was saved to storage."""
    # The step_run should have saved it, we'll verify in next step


@then('the checkpoint "{checkpoint_name}" should exist')
def step_impl(context, checkpoint_name):
    """Verify checkpoint exists in storage."""
    # In position-based system, check if execution log has entry at position
    metadata = context.storage.load_procedure_metadata(context.procedure_id)
    checkpoint_positions = getattr(context, "checkpoint_positions", {})
    if checkpoint_name in checkpoint_positions:
        position = checkpoint_positions[checkpoint_name]
        assert position < len(
            metadata.execution_log
        ), f"Checkpoint {checkpoint_name} at position {position} should exist"
    else:
        assert len(metadata.execution_log) > 0, f"Checkpoint {checkpoint_name} should exist"


@given('checkpoint "{checkpoint_name}" contains result {result:d}')
def step_impl(context, checkpoint_name, result):
    """Pre-populate a checkpoint with a result."""
    # In position-based system, add entry to execution log
    from tactus.protocols.models import CheckpointEntry
    from datetime import datetime, timezone

    metadata = context.storage.load_procedure_metadata(context.procedure_id)
    position = len(metadata.execution_log)

    entry = CheckpointEntry(
        position=position,
        type="explicit_checkpoint",
        result=result,
        timestamp=datetime.now(timezone.utc),
    )
    metadata.execution_log.append(entry)
    context.storage.save_procedure_metadata(context.procedure_id, metadata)

    # Track position for this checkpoint name
    context.checkpoint_positions = getattr(context, "checkpoint_positions", {})
    context.checkpoint_positions[checkpoint_name] = position
    context.execution_count[checkpoint_name] = 0  # Reset execution counter


@then("the operation should NOT execute")
def step_impl(context):
    """Verify operation was not executed (used cache)."""
    # Check that no new executions occurred
    # At least one checkpoint should have 0 executions (was cached)
    has_cached = any(count == 0 for count in context.execution_count.values())
    assert has_cached, "Expected at least one operation to use cached result"


@then("the result should equal {expected:d} from cache")
def step_impl(context, expected):
    """Verify result matches cached value."""
    assert context.result == expected, f"Expected {expected}, got {context.result}"


@when('I execute step "{checkpoint_name}" that loads training data')
def step_impl(context, checkpoint_name):
    """Execute data loading step."""
    context.execution_count[checkpoint_name] = context.execution_count.get(checkpoint_name, 0)
    context.checkpoint_positions = getattr(context, "checkpoint_positions", {})

    def load_data():
        context.execution_count[checkpoint_name] += 1
        return {"data": [1, 2, 3, 4, 5], "size": 5}

    # Track position before execution
    position = context.execution_context.next_position()
    context.checkpoint_positions[checkpoint_name] = position
    context.result = context.execution_context.checkpoint(load_data, "explicit_checkpoint")


@when('I execute step "{checkpoint_name}" that trains a model')
def step_impl(context, checkpoint_name):
    """Execute model training step."""
    context.execution_count[checkpoint_name] = context.execution_count.get(checkpoint_name, 0)
    context.checkpoint_positions = getattr(context, "checkpoint_positions", {})

    def train_model():
        context.execution_count[checkpoint_name] += 1
        return {"model": "trained", "accuracy": 0.95}

    # Track position before execution
    position = context.execution_context.next_position()
    context.checkpoint_positions[checkpoint_name] = position
    context.result = context.execution_context.checkpoint(train_model, "explicit_checkpoint")


@when('I execute step "{checkpoint_name}" that evaluates performance')
def step_impl(context, checkpoint_name):
    """Execute model evaluation step."""
    context.execution_count[checkpoint_name] = context.execution_count.get(checkpoint_name, 0)
    context.checkpoint_positions = getattr(context, "checkpoint_positions", {})

    def evaluate_model():
        context.execution_count[checkpoint_name] += 1
        return {"metrics": {"precision": 0.9, "recall": 0.85}}

    # Track position before execution
    position = context.execution_context.next_position()
    context.checkpoint_positions[checkpoint_name] = position
    context.result = context.execution_context.checkpoint(evaluate_model, "explicit_checkpoint")


@then('checkpoint "{checkpoint_name}" should exist')
def step_impl(context, checkpoint_name):
    """Verify checkpoint exists."""
    # In position-based system, check if execution log has entry at position
    metadata = context.storage.load_procedure_metadata(context.procedure_id)
    checkpoint_positions = getattr(context, "checkpoint_positions", {})
    if checkpoint_name in checkpoint_positions:
        position = checkpoint_positions[checkpoint_name]
        assert position < len(
            metadata.execution_log
        ), f"Checkpoint {checkpoint_name} at position {position} should exist"
    else:
        assert len(metadata.execution_log) > 0, f"Checkpoint {checkpoint_name} should exist"


@when("I clear all checkpoints")
def step_impl(context):
    """Clear all checkpoints from storage."""
    # In position-based system, clear execution log via execution context
    context.execution_context.checkpoint_clear_all()


@when('I execute step "{checkpoint_name}" that computes 2 + 2')
def step_impl(context, checkpoint_name):
    """Execute simple calculation."""
    context.execution_count[checkpoint_name] = context.execution_count.get(checkpoint_name, 0)
    context.checkpoint_positions = getattr(context, "checkpoint_positions", {})

    def compute():
        context.execution_count[checkpoint_name] += 1
        return 2 + 2

    # Track position before execution
    position = context.execution_context.next_position()
    context.checkpoint_positions[checkpoint_name] = position
    context.result = context.execution_context.checkpoint(compute, "explicit_checkpoint")


@then("the result should equal {expected:d}")
def step_impl(context, expected):
    """Verify result equals expected value."""
    assert context.result == expected, f"Expected {expected}, got {context.result}"


@then('the checkpoint "{checkpoint_name}" should contain {expected:d}')
def step_impl(context, checkpoint_name, expected):
    """Verify checkpoint contains expected value."""
    # In position-based system, get result from execution log at position
    metadata = context.storage.load_procedure_metadata(context.procedure_id)
    checkpoint_positions = getattr(context, "checkpoint_positions", {})
    assert checkpoint_name in checkpoint_positions, f"Checkpoint {checkpoint_name} not tracked"
    position = checkpoint_positions[checkpoint_name]
    assert position < len(
        metadata.execution_log
    ), f"Checkpoint at position {position} does not exist"
    result = metadata.execution_log[position].result
    assert result == expected, f"Expected checkpoint to contain {expected}, got {result}"
