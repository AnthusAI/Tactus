"""
Integration tests for BDD testing with runtime execution.
"""

import os
import pytest
from pathlib import Path
import tempfile

from tactus.testing.context import TactusTestContext
from tactus.testing.mock_tools import MockToolRegistry, create_default_mocks
from tactus.testing.mock_hitl import MockHITLHandler


def test_test_context_initialization():
    """Test that TactusTestContext initializes correctly."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".tac", delete=False) as f:
        f.write('name("test")\nversion("1.0.0")\n')
        procedure_file = Path(f.name)

    try:
        context = TactusTestContext(
            procedure_file=procedure_file,
            params={"test": "value"},
            mock_tools={"done": {"status": "ok"}},
        )

        assert context.procedure_file == procedure_file
        assert context.params == {"test": "value"}
        assert context.mock_tools == {"done": {"status": "ok"}}
        assert context.runtime is None
        assert not context._procedure_executed

    finally:
        procedure_file.unlink()


def test_test_context_setup_runtime():
    """Test that runtime setup works."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".tac", delete=False) as f:
        f.write('name("test")\nversion("1.0.0")\n')
        procedure_file = Path(f.name)

    try:
        context = TactusTestContext(procedure_file=procedure_file)
        context.setup_runtime()

        assert context.runtime is not None
        assert context.runtime.procedure_id == f"test_{procedure_file.stem}"

    finally:
        procedure_file.unlink()


def test_mock_tool_registry():
    """Test mock tool registry."""
    registry = MockToolRegistry()

    # Register static mock
    registry.register("done", {"status": "complete"})
    assert registry.has_mock("done")

    # Get response
    response = registry.get_response("done", {})
    assert response == {"status": "complete"}

    # Register callable mock
    def dynamic_search(args):
        query = args.get("query", "default")
        return {"results": [f"Result for {query}"]}

    registry.register("search", dynamic_search)
    response = registry.get_response("search", {"query": "test"})
    assert response == {"results": ["Result for test"]}


def test_mock_tool_registry_missing_mock():
    """Test that missing mock raises error."""
    registry = MockToolRegistry()

    with pytest.raises(ValueError, match="No mock registered"):
        registry.get_response("nonexistent", {})


def test_default_mocks():
    """Test that default mocks are created."""
    mocks = create_default_mocks()

    assert "done" in mocks
    assert "search" in mocks
    assert "write_file" in mocks
    assert "read_file" in mocks


def test_mock_hitl_handler_approval():
    """Test mock HITL handler for approval requests."""
    from tactus.protocols.models import HITLRequest

    handler = MockHITLHandler()

    request = HITLRequest(
        request_type="approval",
        message="Approve this action?",
    )

    response = handler.request_interaction("test_proc", request)

    assert response.value is True
    assert response.timed_out is False
    assert len(handler.requests_received) == 1


def test_mock_hitl_handler_input():
    """Test mock HITL handler for input requests."""
    from tactus.protocols.models import HITLRequest

    handler = MockHITLHandler()

    request = HITLRequest(
        request_type="input",
        message="Enter your name:",
    )

    response = handler.request_interaction("test_proc", request)

    assert response.value == "test input"
    assert response.timed_out is False


def test_mock_hitl_handler_custom_responses():
    """Test mock HITL handler with custom responses."""
    from tactus.protocols.models import HITLRequest

    handler = MockHITLHandler(
        default_responses={
            "_type_approval": False,
            "_type_input": "custom input",
        }
    )

    # Test custom approval response
    request = HITLRequest(
        request_type="approval",
        message="Approve?",
    )
    response = handler.request_interaction("test_proc", request)
    assert response.value is False

    # Test custom input response
    request = HITLRequest(
        request_type="input",
        message="Enter:",
    )
    response = handler.request_interaction("test_proc", request)
    assert response.value == "custom input"


@pytest.mark.asyncio
async def test_context_primitive_capture():
    """Test that primitives are captured after execution."""
    # Create a minimal procedure that uses primitives
    procedure_code = """
agent("worker", {
  provider = "openai",
  model = "gpt-4o-mini",
  system_prompt = "Test",
  tools = {"done"}
})

stages({"start", "end"})

procedure(function()
  Stage.set("start")
  State.set("test_key", "test_value")
  Stage.set("end")
  return {success = true}
end)
"""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".tac", delete=False) as f:
        f.write(procedure_code)
        procedure_file = Path(f.name)

    try:
        context = TactusTestContext(
            procedure_file=procedure_file,
            mock_tools={"done": {"status": "ok"}},
        )

        # Execute procedure
        await context.run_procedure_async()

        # Check that primitives were captured
        assert "state" in context._primitives
        assert "stage" in context._primitives

        # Check that methods work
        assert context.state_exists("test_key")
        assert context.state_get("test_key") == "test_value"
        assert context.current_stage() == "end"

    finally:
        procedure_file.unlink()


@pytest.mark.integration
@pytest.mark.skipif(not os.getenv("OPENAI_API_KEY"), reason="OPENAI_API_KEY not set")
async def test_real_execution_with_llm():
    """Test real execution with actual LLM calls (requires API key)."""
    # Create a minimal procedure
    procedure_code = """
name("test_real")
version("1.0.0")

agent("worker", {
  provider = "openai",
  model = "gpt-4o-mini",
  system_prompt = "Say hello and call the done tool.",
  tools = {"done"}
})

procedure(function()
  Worker.turn()
  return {success = true}
end)
"""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".tac", delete=False) as f:
        f.write(procedure_code)
        procedure_file = Path(f.name)

    try:
        context = TactusTestContext(procedure_file=procedure_file)

        # Execute with real LLM
        await context.run_procedure_async()

        # Check execution completed
        assert context._procedure_executed
        assert context.execution_result is not None

        # Check that done tool was called
        # (This assumes the LLM actually calls it, which is non-deterministic)
        # In real tests, we'd use mocks for determinism

    finally:
        procedure_file.unlink()
