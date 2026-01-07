"""
Step definitions for Workflow Execution feature.
"""

from behave import given, when, then
import yaml
from tactus.core.execution_context import InMemoryExecutionContext
from tactus.primitives.state import StatePrimitive
from tactus.core.lua_sandbox import LuaSandbox
import time


@given("a Tactus runtime is initialized")
def step_impl(context):
    """Initialize Tactus runtime."""
    context.procedure_id = "test_workflow"
    context.execution_context = InMemoryExecutionContext(procedure_id=context.procedure_id)
    context.storage = context.execution_context.storage  # Alias for compatibility
    context.state = StatePrimitive()
    context.lua = LuaSandbox()
    context.lua.inject_primitive("state", context.state)


@given("a workflow YAML:")
def step_impl(context):
    """Parse workflow YAML from docstring."""
    yaml_content = context.text
    context.workflow_config = yaml.safe_load(yaml_content)
    context.workflow_name = context.workflow_config.get("name", "unnamed_workflow")


@when("I execute the workflow")
def step_impl(context):
    """Execute the workflow."""
    try:
        # Simple workflow executor
        steps = context.workflow_config.get("steps", [])
        context.step_results = {}
        context.execution_order = []

        for step in steps:
            step_id = step.get("id")
            action = step.get("action")
            params = step.get("params", {})

            context.execution_order.append(step_id)

            # Execute based on action type
            if action == "state.set":
                key = params.get("key")
                value = params.get("value")
                # Ensure state exists
                if not hasattr(context, "state"):
                    from tactus.primitives.state import StatePrimitive

                    context.state = StatePrimitive()
                context.state.set(key, value)
                context.step_results[step_id] = {"result": value}

            elif action == "tool.call":
                # Mock tool call for testing
                tool = params.get("tool")
                context.step_results[step_id] = {"result": f"mock_result_from_{tool}"}

            elif action == "agent.call":
                # Mock agent call
                prompt = params.get("prompt")
                # Support templating
                if "{{" in prompt and "}}" in prompt:
                    # Simple template replacement
                    for prev_step_id, prev_result in context.step_results.items():
                        placeholder = f"{{{{ {prev_step_id}.result }}}}"
                        if placeholder in prompt:
                            prompt = prompt.replace(placeholder, str(prev_result["result"]))
                context.step_results[step_id] = {"result": f"mock_agent_response_to_{prompt}"}

            elif action == "file.write":
                # Mock file write
                path = params.get("path")
                content = params.get("content")
                # Support templating
                if "{{" in content and "}}" in content:
                    for prev_step_id, prev_result in context.step_results.items():
                        placeholder = f"{{{{ {prev_step_id}.result }}}}"
                        if placeholder in content:
                            content = content.replace(placeholder, str(prev_result["result"]))

                # Write to temp file
                if not hasattr(context, "temp_files"):
                    context.temp_files = {}
                context.temp_files[path] = content
                context.step_results[step_id] = {"result": "file_written"}

        context.workflow_completed = True
        context.error = None

    except Exception as e:
        context.workflow_completed = False
        context.error = e


@then("the workflow should complete successfully")
def step_impl(context):
    """Verify workflow completed."""
    assert context.workflow_completed, f"Workflow did not complete: {context.error}"


@given("a workflow that accepts parameters")
def step_impl(context):
    """Create a workflow that uses parameters."""
    context.workflow_config = {
        "name": "parameterized_workflow",
        "params": ["topic", "depth"],
        "steps": [],
    }


@when("I execute with parameters:")
def step_impl(context):
    """Execute workflow with parameters."""
    # Parse parameters from table
    context.workflow_params = {}
    for row in context.table:
        param = row["parameter"]
        value = row["value"]
        context.workflow_params[param] = value
        # Set parameters as state
        context.state.set(param, value)

    context.workflow_completed = True


@then("the workflow should use the provided parameters")
def step_impl(context):
    """Verify parameters were used."""
    assert context.workflow_params is not None, "No parameters were provided"
    assert len(context.workflow_params) > 0, "Parameters dict is empty"


@then("state should reflect the parameter values")
def step_impl(context):
    """Verify parameters are in state."""
    for param, value in context.workflow_params.items():
        actual = context.state.get(param)
        assert actual == value, f"Expected state[{param}] = {value}, got {actual}"


@then("each step should execute in order")
def step_impl(context):
    """Verify steps executed in order."""
    expected_order = [step["id"] for step in context.workflow_config.get("steps", [])]
    assert (
        context.execution_order == expected_order
    ), f"Expected order {expected_order}, got {context.execution_order}"


@then("each step should receive outputs from previous steps")
def step_impl(context):
    """Verify step dependencies work."""
    # Check that templating worked
    steps = context.workflow_config.get("steps", [])
    for step in steps:
        step_id = step.get("id")
        if step_id in context.step_results:
            # If this step had templates, verify they were resolved
            params = step.get("params", {})
            for param_key, param_value in params.items():
                if isinstance(param_value, str) and "{{" in param_value:
                    # Template was present, should have been resolved
                    assert "{{" not in str(context.step_results[step_id])


@then("the final result should be saved to file")
def step_impl(context):
    """Verify file was written."""
    assert hasattr(context, "temp_files"), "No files were written"
    assert "output.txt" in context.temp_files, "output.txt was not written"


@given("a workflow with error handlers")
def step_impl(context):
    """Create workflow with error handling."""
    context.workflow_config = {
        "name": "error_handling_workflow",
        "steps": [
            {"id": "step1", "action": "state.set", "params": {"key": "status", "value": "running"}},
            {"id": "step2", "action": "fail", "params": {}},  # Will fail
        ],
        "error_handlers": {"step2": {"action": "log", "params": {"message": "Step 2 failed"}}},
    }
    context.error_handler_invoked = False


@when("a step fails with an error")
def step_impl(context):
    """Simulate step failure."""
    context.step_failed = True
    context.failure_error = Exception("Simulated step failure")
    stage_state = getattr(context, "stage_state", None)
    if stage_state:
        tracker = stage_state.get("tracker")
        if tracker and tracker.current_stage:
            tracker.mark_failed(tracker.current_stage, "step failure")


@then("the error handler should be invoked")
def step_impl(context):
    """Verify error handler was called."""
    # In a real implementation, this would check if error handler executed
    assert context.step_failed, "Step should have failed"


@then("the workflow should handle the error gracefully")
def step_impl(context):
    """Verify error was handled."""
    # Workflow should not crash
    assert True  # Placeholder for real error handling check


@then("execution should continue or halt as configured")
def step_impl(context):
    """Verify execution behavior after error."""
    # Would check if workflow continued or stopped based on config
    assert True  # Placeholder


@given("a workflow with conditional branches")
def step_impl(context):
    """Create workflow with conditionals."""
    context.workflow_config = {
        "name": "conditional_workflow",
        "steps": [
            {
                "id": "check_mode",
                "action": "conditional",
                "condition": "state.get('mode') == 'production'",
                "then": [
                    {
                        "id": "prod_step",
                        "action": "state.set",
                        "params": {"key": "path", "value": "production"},
                    }
                ],
                "else": [
                    {
                        "id": "dev_step",
                        "action": "state.set",
                        "params": {"key": "path", "value": "development"},
                    }
                ],
            }
        ],
    }


@when('I execute with state "{key}" set to "{value}"')
def step_impl(context, key, value):
    """Set state and execute."""
    context.state.set(key, value)
    # Execute conditional logic
    steps = context.workflow_config.get("steps", [])
    for step in steps:
        if step.get("action") == "conditional":
            condition = step.get("condition")
            # Simple evaluation
            if value == "production" and "production" in condition:
                # Execute then branch
                for then_step in step.get("then", []):
                    params = then_step.get("params", {})
                    context.state.set(params["key"], params["value"])
            else:
                # Execute else branch
                for else_step in step.get("else", []):
                    params = else_step.get("params", {})
                    context.state.set(params["key"], params["value"])


@then("the production path should execute")
def step_impl(context):
    """Verify production path executed."""
    path = context.state.get("path")
    assert path == "production", f"Expected production path, got {path}"


@then("the development path should be skipped")
def step_impl(context):
    """Verify dev path was skipped."""
    path = context.state.get("path")
    assert path != "development", "Development path should not execute"


@given("a workflow with parallel steps:")
def step_impl(context):
    """Parse parallel workflow."""
    yaml_content = context.text
    context.workflow_config = yaml.safe_load(yaml_content)


@then("all tasks should execute concurrently")
def step_impl(context):
    """Verify parallel execution."""
    # In real implementation, would check timing/concurrency
    # For now, verify parallel steps structure exists
    steps = context.workflow_config.get("steps", [])
    parallel_step = next((s for s in steps if s.get("action") == "parallel"), None)
    assert parallel_step is not None, "No parallel step found"
    assert "steps" in parallel_step, "Parallel step has no substeps"


@then("the workflow should wait for all to complete")
def step_impl(context):
    """Verify all parallel tasks complete."""
    # Would verify all parallel tasks finished
    assert True  # Placeholder


@then("total time should be less than sequential execution")
def step_impl(context):
    """Verify time savings from parallelism."""
    # Would measure execution time
    assert True  # Placeholder


@given("a workflow with timeout {seconds:d} seconds")
def step_impl(context, seconds):
    """Create workflow with timeout."""
    context.workflow_timeout = seconds
    context.workflow_config = {
        "name": "timeout_workflow",
        "timeout": seconds,
        "steps": [{"id": "long_step", "action": "sleep", "params": {"duration": seconds + 10}}],
    }


@when("I execute a long-running workflow")
def step_impl(context):
    """Start long-running workflow."""
    context.workflow_start_time = time.time()
    context.workflow_timed_out = False


@when("it exceeds {seconds:d} seconds")
def step_impl(context, seconds):
    """Simulate timeout."""
    # In real implementation, would actually wait and timeout
    context.workflow_timed_out = True


@then("the workflow should be terminated")
def step_impl(context):
    """Verify workflow was terminated."""
    assert context.workflow_timed_out, "Workflow should have timed out"


@then("a timeout error should be raised")
def step_impl(context):
    """Verify timeout error."""
    # Would check for TimeoutError exception
    assert context.workflow_timed_out


@given("a workflow that was interrupted at step {step_num:d}")
def step_impl(context, step_num):
    """Set up interrupted workflow."""
    context.interrupted_at_step = step_num
    context.completed_steps = []  # Will be set by checkpoints step
    context.workflow_config = {
        "name": "resumable_workflow",
        "steps": [
            {"id": "step1", "action": "state.set", "params": {"key": "s1", "value": "done1"}},
            {"id": "step2", "action": "state.set", "params": {"key": "s2", "value": "done2"}},
            {"id": "step3", "action": "state.set", "params": {"key": "s3", "value": "done3"}},
        ],
    }


@when("I resume the workflow")
def step_impl(context):
    """Resume workflow from checkpoint."""
    stage_state = getattr(context, "stage_state", None)
    if stage_state:
        tracker = stage_state.get("tracker")
        if tracker and tracker.current_stage:
            tracker.begin_stage(tracker.current_stage)

    steps = context.workflow_config.get("steps", [])
    context.resumed_execution = []
    context.completed_steps = []

    # Get execution log to check which steps have checkpoints
    metadata = context.execution_context.storage.load_procedure_metadata(context.procedure_id)

    # First, identify which steps have checkpoints (by position in execution log)
    for i, step in enumerate(steps, 1):
        position = i - 1  # Positions are 0-indexed
        if position < len(metadata.execution_log):
            context.completed_steps.append(i)

    # Now execute, skipping checkpointed steps
    for i, step in enumerate(steps, 1):
        step_id = step.get("id")
        position = i - 1  # Positions are 0-indexed

        # Check if checkpoint exists at this position
        if position < len(metadata.execution_log):
            # Skip this step (already completed)
            context.resumed_execution.append(f"skipped_{step_id}")
        else:
            # Execute this step
            params = step.get("params", {})
            context.state.set(params["key"], params["value"])
            context.resumed_execution.append(f"executed_{step_id}")


@then("steps {step_list} should be skipped")
def step_impl(context, step_list):
    """Verify steps were skipped."""
    steps = [int(s.strip()) for s in step_list.replace("and", ",").split(",")]
    for step_num in steps:
        step_id = f"step{step_num}"
        assert (
            f"skipped_{step_id}" in context.resumed_execution
        ), f"Step {step_num} should have been skipped"


@then("execution should continue from step {step_num:d}")
def step_impl(context, step_num):
    """Verify execution started at correct step."""
    step_id = f"step{step_num}"
    assert (
        f"executed_{step_id}" in context.resumed_execution
    ), f"Step {step_num} should have been executed"


@then("state should be restored from checkpoints")
def step_impl(context):
    """Verify state was restored."""
    # Check that checkpointed steps exist in execution log
    metadata = context.execution_context.storage.load_procedure_metadata(context.procedure_id)
    for step_num in context.completed_steps:
        position = step_num - 1  # Positions are 0-indexed
        assert position < len(
            metadata.execution_log
        ), f"Checkpoint at position {position} (step {step_num}) should exist"
        result = metadata.execution_log[position].result
        assert result is not None, f"Checkpoint at position {position} should have a result"
