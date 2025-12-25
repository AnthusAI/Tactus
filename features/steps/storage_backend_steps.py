"""
Step definitions for Storage Backends feature.
"""

from behave import given, when, then
from tactus.core.execution_context import BaseExecutionContext
from tactus.adapters.memory import MemoryStorage
from tactus.adapters.file_storage import FileStorage
from tactus.protocols.models import CheckpointEntry
from datetime import datetime, timezone
import tempfile
import shutil
import os


@given("a Tactus runtime with in-memory storage")
def step_impl(context):
    """Initialize with in-memory storage."""
    context.procedure_id = "test_procedure"
    context.storage = MemoryStorage()
    context.execution_context = BaseExecutionContext(
        procedure_id=context.procedure_id, storage_backend=context.storage
    )


@when("I execute a workflow that sets state")
def step_impl(context):
    """Execute workflow that sets state."""
    state = context.storage.get_state(context.procedure_id)
    state["test_key"] = "test_value"
    state["another_key"] = 42
    context.storage.set_state(context.procedure_id, state)


@then("state should be stored in memory")
def step_impl(context):
    """Verify state is in memory."""
    state = context.storage.get_state(context.procedure_id)
    assert state["test_key"] == "test_value"
    assert state["another_key"] == 42


@then("it should be available within the same session")
def step_impl(context):
    """Verify state is accessible in same session."""
    # Access state through same storage instance
    state = context.storage.get_state(context.procedure_id)
    assert state["test_key"] == "test_value"


@then("it should not persist after restart")
def step_impl(context):
    """Verify memory storage doesn't persist."""
    # Create a new storage instance (simulating restart)
    new_storage = MemoryStorage()
    # State should not exist in new instance
    state = new_storage.get_state(context.procedure_id)
    assert "test_key" not in state


@given("a Tactus runtime with file-based storage")
def step_impl(context):
    """Initialize with file-based storage."""
    # Create temporary directory for testing
    context.temp_dir = tempfile.mkdtemp()
    context.storage_dir = context.temp_dir
    context.procedure_id = "test_procedure"
    context.storage = FileStorage(storage_dir=context.storage_dir)
    context.execution_context = BaseExecutionContext(
        procedure_id=context.procedure_id, storage_backend=context.storage
    )


@given('storage directory is "{directory}"')
def step_impl(context, directory):
    """Set storage directory (already set in previous step)."""
    # Directory is already configured in previous step
    pass


@when('I execute a workflow that sets state "{key}" to "{value}"')
def step_impl(context, key, value):
    """Set state with specific key and value."""
    state = context.storage.get_state(context.procedure_id)
    state[key] = value
    context.storage.set_state(context.procedure_id, state)


@then("a file should be created in the storage directory")
def step_impl(context):
    """Verify file was created."""
    file_path = os.path.join(context.storage_dir, f"{context.procedure_id}.json")
    assert os.path.exists(file_path), f"File {file_path} should exist"


@then("reading the file should show the state value")
def step_impl(context):
    """Verify file contains state data."""
    import json

    file_path = os.path.join(context.storage_dir, f"{context.procedure_id}.json")
    with open(file_path, "r") as f:
        data = json.load(f)
    assert "state" in data
    assert "user" in data["state"]
    assert data["state"]["user"] == "Alice"


@when("I restart the workflow")
def step_impl(context):
    """Simulate restart by creating new context with same storage directory."""
    context.storage = FileStorage(storage_dir=context.storage_dir)
    context.execution_context = BaseExecutionContext(
        procedure_id=context.procedure_id, storage_backend=context.storage
    )


@then('state "{key}" should still equal "{value}"')
def step_impl(context, key, value):
    """Verify state persisted across restart."""
    state = context.storage.get_state(context.procedure_id)
    actual = state.get(key)
    assert actual == value, f"Expected {value}, got {actual}"


@given('a workflow "{procedure_id}" was previously executed')
def step_impl(context, procedure_id):
    """Set up previously executed workflow."""
    context.procedure_id = procedure_id
    context.storage = MemoryStorage()


@given("checkpoints exist for steps {step_nums}")
def step_impl(context, step_nums):
    """Create checkpoints for specified steps."""
    # Parse step numbers: "1, 2, 3" or "1 and 2" -> [1, 2, 3]
    step_nums_normalized = step_nums.replace(" and ", ", ")
    steps = [s.strip() for s in step_nums_normalized.split(",")]

    metadata = context.storage.load_procedure_metadata(context.procedure_id)
    for i, step_num in enumerate(steps):
        entry = CheckpointEntry(
            position=i,
            type="explicit_checkpoint",
            result=f"result_{step_num}",
            timestamp=datetime.now(timezone.utc),
        )
        metadata.execution_log.append(entry)
    context.storage.save_procedure_metadata(context.procedure_id, metadata)


@given("state contains accumulated results")
def step_impl(context):
    """Set up state with accumulated results."""
    state = {"results": ["result_1", "result_2", "result_3"], "count": 3}
    context.storage.set_state(context.procedure_id, state)


@when('I initialize the runtime with procedure_id "{procedure_id}"')
def step_impl(context, procedure_id):
    """Initialize runtime with existing procedure ID."""
    context.execution_context = BaseExecutionContext(
        procedure_id=procedure_id, storage_backend=context.storage
    )


@then("the storage backend should load existing metadata")
def step_impl(context):
    """Verify metadata was loaded."""
    metadata = context.storage.load_procedure_metadata(context.procedure_id)
    assert metadata.procedure_id == context.procedure_id


@then("checkpoints should be available")
def step_impl(context):
    """Verify checkpoints are accessible."""
    metadata = context.storage.load_procedure_metadata(context.procedure_id)
    assert len(metadata.execution_log) >= 3, "Expected at least 3 checkpoints"
    # Verify we have checkpoint results
    assert metadata.execution_log[0].result == "result_1"
    assert metadata.execution_log[1].result == "result_2"
    assert metadata.execution_log[2].result == "result_3"


@then("state should be restored")
def step_impl(context):
    """Verify state is restored."""
    state = context.storage.get_state(context.procedure_id)
    assert state["results"] == ["result_1", "result_2", "result_3"]
    assert state["count"] == 3


@given('two workflows "{workflow_a}" and "{workflow_b}"')
def step_impl(context, workflow_a, workflow_b):
    """Set up two separate workflows."""
    context.storage = MemoryStorage()
    context.workflow_a = workflow_a
    context.workflow_b = workflow_b


@when('"{workflow_id}" saves checkpoint "{checkpoint_name}" with value "{value}"')
def step_impl(context, workflow_id, checkpoint_name, value):
    """Save checkpoint for specific workflow."""
    metadata = context.storage.load_procedure_metadata(workflow_id)
    position = len(metadata.execution_log)
    entry = CheckpointEntry(
        position=position,
        type="explicit_checkpoint",
        result=value,
        timestamp=datetime.now(timezone.utc),
    )
    metadata.execution_log.append(entry)
    context.storage.save_procedure_metadata(workflow_id, metadata)

    # Track the position for later retrieval
    if not hasattr(context, "checkpoint_positions"):
        context.checkpoint_positions = {}
    if workflow_id not in context.checkpoint_positions:
        context.checkpoint_positions[workflow_id] = {}
    context.checkpoint_positions[workflow_id][checkpoint_name] = position


@then('"{workflow_id}" checkpoint should contain "{expected}"')
def step_impl(context, workflow_id, expected):
    """Verify workflow checkpoint has expected value."""
    metadata = context.storage.load_procedure_metadata(workflow_id)
    # Get the first checkpoint (position 0)
    assert len(metadata.execution_log) > 0, "Expected at least one checkpoint"
    actual = metadata.execution_log[0].result
    assert actual == expected, f"Expected {expected}, got {actual}"


@then("checkpoints should not interfere with each other")
def step_impl(context):
    """Verify isolation between workflows."""
    metadata_a = context.storage.load_procedure_metadata(context.workflow_a)
    metadata_b = context.storage.load_procedure_metadata(context.workflow_b)
    a_value = metadata_a.execution_log[0].result
    b_value = metadata_b.execution_log[0].result
    assert a_value != b_value, "Workflows should have different checkpoint values"


@given("a workflow with multiple checkpoints")
def step_impl(context):
    """Create workflow with multiple checkpoints."""
    context.procedure_id = "test_procedure"
    context.storage = MemoryStorage()
    context.execution_context = BaseExecutionContext(
        procedure_id=context.procedure_id, storage_backend=context.storage
    )
    # Create several checkpoints
    metadata = context.storage.load_procedure_metadata(context.procedure_id)
    for i, result in enumerate(["result1", "result2", "result3"]):
        entry = CheckpointEntry(
            position=i,
            type="explicit_checkpoint",
            result=result,
            timestamp=datetime.now(timezone.utc),
        )
        metadata.execution_log.append(entry)
    context.storage.save_procedure_metadata(context.procedure_id, metadata)


@given("state contains multiple keys")
def step_impl(context):
    """Set up state with multiple keys."""
    state = {"key1": "value1", "key2": "value2", "key3": "value3"}
    context.storage.set_state(context.procedure_id, state)


@then("no checkpoints should exist")
def step_impl(context):
    """Verify no checkpoints exist."""
    metadata = context.storage.load_procedure_metadata(context.procedure_id)
    assert len(metadata.execution_log) == 0, "Expected no checkpoints"


@then("state should remain intact")
def step_impl(context):
    """Verify state was not cleared."""
    state = context.storage.get_state(context.procedure_id)
    assert state["key1"] == "value1"
    assert state["key2"] == "value2"
    assert state["key3"] == "value3"


@given("a file-based storage with read-only directory")
def step_impl(context):
    """Create file storage with read-only directory."""
    context.temp_dir = tempfile.mkdtemp()
    # Make directory read-only
    os.chmod(context.temp_dir, 0o444)
    context.storage_dir = context.temp_dir
    context.procedure_id = "test_procedure"
    context.storage = FileStorage(storage_dir=context.storage_dir)


@when("I try to save state")
def step_impl(context):
    """Try to save state (should fail)."""
    try:
        state = {"key": "value"}
        context.storage.set_state(context.procedure_id, state)
        context.error = None
    except Exception as e:
        context.error = e


@then("a storage error should be raised")
def step_impl(context):
    """Verify error was raised."""
    assert context.error is not None, "Expected an error to be raised"


@then("the error should be descriptive")
def step_impl(context):
    """Verify error message is descriptive."""
    error_msg = str(context.error)
    assert "Failed to write" in error_msg or "Permission denied" in error_msg


@given("multiple workflow instances using the same storage")
def step_impl(context):
    """Create multiple workflow instances."""
    context.storage = MemoryStorage()
    context.workflows = ["workflow_1", "workflow_2", "workflow_3"]


@when("workflows run concurrently")
def step_impl(context):
    """Simulate concurrent workflow execution."""
    # Simulate by running sequentially (actual concurrency would need threading)
    for workflow_id in context.workflows:
        # Set state
        state = {"status": f"running_{workflow_id}"}
        context.storage.set_state(workflow_id, state)

        # Save checkpoint
        metadata = context.storage.load_procedure_metadata(workflow_id)
        entry = CheckpointEntry(
            position=0,
            type="explicit_checkpoint",
            result=f"result_{workflow_id}",
            timestamp=datetime.now(timezone.utc),
        )
        metadata.execution_log.append(entry)
        context.storage.save_procedure_metadata(workflow_id, metadata)


@then("each workflow should have isolated state")
def step_impl(context):
    """Verify each workflow has its own state."""
    for workflow_id in context.workflows:
        state = context.storage.get_state(workflow_id)
        status = state.get("status")
        assert status == f"running_{workflow_id}", f"Expected isolated status for {workflow_id}"


@then("no data corruption should occur")
def step_impl(context):
    """Verify no data corruption."""
    for workflow_id in context.workflows:
        metadata = context.storage.load_procedure_metadata(workflow_id)
        result = metadata.execution_log[0].result
        assert (
            result == f"result_{workflow_id}"
        ), f"Expected uncorrupted checkpoint for {workflow_id}"


@given("a workflow using in-memory storage")
def step_impl(context):
    """Set up workflow with in-memory storage."""
    context.procedure_id = "migration_test"
    context.memory_storage = MemoryStorage()

    # Set state
    state = {"migrated_key": "migrated_value"}
    context.memory_storage.set_state(context.procedure_id, state)

    # Save checkpoint
    metadata = context.memory_storage.load_procedure_metadata(context.procedure_id)
    entry = CheckpointEntry(
        position=0,
        type="explicit_checkpoint",
        result="checkpoint_result",
        timestamp=datetime.now(timezone.utc),
    )
    metadata.execution_log.append(entry)
    context.memory_storage.save_procedure_metadata(context.procedure_id, metadata)


@when("I switch to file-based storage")
def step_impl(context):
    """Switch to file-based storage."""
    context.temp_dir = tempfile.mkdtemp()
    context.file_storage = FileStorage(storage_dir=context.temp_dir)

    # Manually migrate data
    metadata = context.memory_storage.load_procedure_metadata(context.procedure_id)
    context.file_storage.save_procedure_metadata(context.procedure_id, metadata)


@then("existing state should be preserved")
def step_impl(context):
    """Verify state was preserved."""
    state = context.file_storage.get_state(context.procedure_id)
    value = state.get("migrated_key")
    assert value == "migrated_value", f"Expected 'migrated_value', got {value}"


@then("the workflow should continue seamlessly")
def step_impl(context):
    """Verify checkpoint was preserved."""
    metadata = context.file_storage.load_procedure_metadata(context.procedure_id)
    assert len(metadata.execution_log) > 0, "Expected checkpoint to be preserved"
    result = metadata.execution_log[0].result
    assert result == "checkpoint_result", "Expected checkpoint to be preserved"

    # Cleanup
    if hasattr(context, "temp_dir"):
        shutil.rmtree(context.temp_dir, ignore_errors=True)
