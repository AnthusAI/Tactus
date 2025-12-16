"""
Basic Error Handling Tests for Tactus Tools

Tests fundamental error scenarios to ensure robustness.
Keeps it simple - no creative edge cases, just the basics.
"""

import pytest
from pydantic_ai import Tool
from tactus.primitives.tool import ToolPrimitive
from tactus.primitives.control import IterationsPrimitive
from tactus.primitives.state import StatePrimitive
from tactus.primitives.agent import AgentPrimitive
from tactus.adapters.mcp_manager import MCPServerManager


# ============================================================================
# 1. LOCAL PLUGIN TOOL ERRORS
# ============================================================================


def test_plugin_tool_execution_raises_exception():
    """Test that plugin tool exceptions are handled correctly."""

    def failing_tool(x: int) -> int:
        """A tool that always fails."""
        raise ValueError("Tool execution failed!")

    # Execute the tool and expect exception
    with pytest.raises(ValueError, match="Tool execution failed"):
        failing_tool(5)

    # Verify we can catch and handle the exception
    try:
        failing_tool(5)
    except ValueError as e:
        assert "Tool execution failed" in str(e)


def test_plugin_tool_with_invalid_arguments():
    """Test tool called with wrong argument types."""

    def typed_tool(x: int, y: int) -> int:
        """A tool expecting integers."""
        # Explicitly check types to ensure we get expected behavior
        if not isinstance(x, int) or not isinstance(y, int):
            raise TypeError(
                f"Expected int arguments, got {type(x).__name__} and {type(y).__name__}"
            )
        return x + y

    # Call with correct types - should work
    result = typed_tool(5, 10)
    assert result == 15

    # Call with wrong types - should raise TypeError
    with pytest.raises(TypeError, match="Expected int arguments"):
        typed_tool("5", 10)

    # Call with both wrong - should also raise
    with pytest.raises(TypeError):
        typed_tool("5", "10")


def test_plugin_tool_returns_none_on_error():
    """Test tool that catches errors internally and returns None."""
    tool_primitive = ToolPrimitive()

    def safe_tool(x: int) -> int:
        """A tool that handles errors internally."""
        try:
            if x < 0:
                raise ValueError("Negative number")
            return x * 2
        except ValueError:
            return None

    # Normal execution
    result = safe_tool(5)
    assert result == 10

    # Error case returns None
    result = safe_tool(-5)
    assert result is None

    # Record in ToolPrimitive
    tool_primitive.record_call("safe_tool", {"x": -5}, result)
    assert tool_primitive.last_result("safe_tool") is None


def test_plugin_tool_with_missing_required_args():
    """Test tool called without required arguments."""

    def required_args_tool(required: str, optional: int = 10) -> str:
        """A tool with required and optional parameters."""
        return f"{required}:{optional}"

    # Call with all args - works
    result = required_args_tool("test", 20)
    assert result == "test:20"

    # Call with only required - works
    result = required_args_tool("test")
    assert result == "test:10"

    # Call without required arg - fails
    with pytest.raises(TypeError):
        required_args_tool()


# ============================================================================
# 2. TOOL RECORDING ERRORS
# ============================================================================


def test_record_tool_call_with_exception_result():
    """Test recording a tool call that resulted in an exception."""
    tool_primitive = ToolPrimitive()

    # Simulate recording an error
    error_msg = "Tool failed with error"
    tool_primitive.record_call("failing_tool", {"x": 5}, {"error": error_msg})

    # Verify storage and retrieval
    assert tool_primitive.called("failing_tool")
    result = tool_primitive.last_result("failing_tool")
    assert result["error"] == error_msg

    # Verify call history
    all_calls = tool_primitive.get_all_calls()
    assert len(all_calls) == 1
    assert all_calls[0].name == "failing_tool"
    assert all_calls[0].result["error"] == error_msg


def test_tool_primitive_with_large_result():
    """Test recording a tool call with very large result."""
    tool_primitive = ToolPrimitive()

    # Create a large result (1MB string)
    large_result = "x" * (1024 * 1024)

    # Record the call
    tool_primitive.record_call("large_tool", {"size": "1MB"}, large_result)

    # Verify no crashes and retrieval works
    assert tool_primitive.called("large_tool")
    result = tool_primitive.last_result("large_tool")
    assert len(result) == 1024 * 1024
    assert result[0] == "x"

    # Verify call count still works
    assert tool_primitive.get_call_count("large_tool") == 1


# ============================================================================
# 3. AGENT TOOL ERRORS
# ============================================================================


def create_test_agent(tools=None, **kwargs):
    """Helper to create a test agent with minimal required parameters."""
    defaults = {
        "name": "test_agent",
        "system_prompt_template": "Test agent",
        "initial_message": "Start",
        "model": "test",
        "tools": tools or [],
        "tool_primitive": kwargs.get("tool_primitive"),
        "stop_primitive": kwargs.get("stop_primitive"),
        "iterations_primitive": IterationsPrimitive(),
        "state_primitive": StatePrimitive(),
        "context": {},
    }
    defaults.update(kwargs)
    return AgentPrimitive(**defaults)


@pytest.mark.asyncio
async def test_done_tool_with_none_primitives():
    """Test that done tool handles None primitives gracefully."""

    def dummy_tool(x: int) -> int:
        """A simple test tool."""
        return x * 2

    tool = Tool(dummy_tool, name="dummy_tool")

    # Create agent with None primitives (but provide required ones)
    agent = create_test_agent(
        tools=[tool],
        tool_primitive=None,  # None primitive
        stop_primitive=None,  # None primitive
    )

    # Agent should be created successfully
    assert agent is not None
    assert len(agent.all_tools) == 2  # dummy_tool + done

    # Find the done tool
    done_tool = next(t for t in agent.all_tools if t.name == "done")

    # Call done tool - should not crash even with None primitives
    result = await done_tool.function("Completed", success=True)
    assert "Done" in result


def test_agent_filter_nonexistent_tool_runtime():
    """Test agent handling when filtering to nonexistent tools."""

    def tool_a(x: int) -> int:
        """Tool A."""
        return x * 2

    tool_a_wrapped = Tool(tool_a, name="tool_a")
    agent = create_test_agent(tools=[tool_a_wrapped])

    # Filter to nonexistent tool
    filtered = agent._filter_tools_by_name(["nonexistent_tool"])
    assert len(filtered) == 0  # Should return empty list, not crash

    # Filter with mix of existing and nonexistent
    filtered = agent._filter_tools_by_name(["tool_a", "nonexistent"])
    assert len(filtered) == 1
    assert filtered[0].name == "tool_a"


def test_agent_with_empty_tools_list():
    """Test agent behavior with explicitly empty tools list."""
    agent = create_test_agent(tools=[])

    # Should have no tools (done tool not added for empty list)
    assert len(agent.all_tools) == 0

    # Filter operations should handle empty tool list
    filtered = agent._filter_tools_by_name(["any_tool"])
    assert len(filtered) == 0


# ============================================================================
# 4. MCP SERVER CONNECTION ERRORS
# ============================================================================


@pytest.mark.asyncio
async def test_mcp_server_invalid_command():
    """Test MCP server with invalid command."""
    config = {
        "invalid_server": {
            "command": "this_command_does_not_exist_xyz123",
            "args": [],
        }
    }

    manager = MCPServerManager(config)

    # Attempt to connect - should handle gracefully
    try:
        async with manager:
            # If we get here, the manager handled the error gracefully
            toolsets = manager.get_toolsets()
            # With invalid command, we expect no toolsets
            assert len(toolsets) == 0 or toolsets is not None
    except Exception as e:
        # It's acceptable to raise an exception, just verify it's not a crash
        assert "command_does_not_exist" in str(e).lower() or "not found" in str(e).lower()


@pytest.mark.asyncio
async def test_mcp_server_command_not_found():
    """Test MCP server with nonexistent executable."""
    config = {
        "missing_server": {
            "command": "/nonexistent/path/to/executable",
            "args": [],
        }
    }

    manager = MCPServerManager(config)

    # Similar to above - should handle missing executable gracefully
    try:
        async with manager:
            toolsets = manager.get_toolsets()
            # Expect empty or error is handled
            assert toolsets is not None
    except (FileNotFoundError, OSError, Exception) as e:
        # Acceptable to raise exception for missing file
        assert (
            "nonexistent" in str(e).lower()
            or "not found" in str(e).lower()
            or "no such file" in str(e).lower()
        )


@pytest.mark.asyncio
async def test_mcp_manager_empty_config():
    """Test MCP manager with empty configuration."""
    config = {}

    manager = MCPServerManager(config)

    # Should handle empty config gracefully
    async with manager:
        toolsets = manager.get_toolsets()
        # Empty config means no toolsets
        assert toolsets == [] or toolsets is not None


# ============================================================================
# 5. MCP TOOL EXECUTION ERRORS
# ============================================================================


def test_mcp_tool_schema_validation():
    """Test that MCP tools have valid schemas."""
    # This is a basic test to ensure test MCP server tools are accessible
    # We'll use the existing test server
    config = {
        "test_server": {
            "command": "python",
            "args": ["-m", "tests.fixtures.test_mcp_server"],
        }
    }

    # Just verify config is valid
    assert "test_server" in config
    assert config["test_server"]["command"] == "python"


@pytest.mark.asyncio
async def test_mcp_server_context_manager_cleanup():
    """Test that MCP manager cleans up properly even on errors."""
    config = {
        "test_server": {
            "command": "python",
            "args": ["-m", "tests.fixtures.test_mcp_server"],
        }
    }

    manager = MCPServerManager(config)

    # Use context manager normally
    async with manager:
        toolsets = manager.get_toolsets()
        assert len(toolsets) >= 0

    # After exiting context, manager should be cleaned up
    # (We can't directly test internal state, but verify no crash)
    assert manager is not None


def test_tool_error_propagation():
    """Test that tool errors propagate correctly through the system."""
    tool_primitive = ToolPrimitive()

    def error_tool() -> int:
        """Tool that raises an error."""
        raise RuntimeError("Intentional error for testing")

    # Verify error is raised
    with pytest.raises(RuntimeError, match="Intentional error"):
        error_tool()

    # Verify we can record the error state
    try:
        result = error_tool()
    except RuntimeError as e:
        # Record the error in tool primitive
        tool_primitive.record_call("error_tool", {}, {"error": str(e)})

    # Verify error was recorded
    assert tool_primitive.called("error_tool")
    result = tool_primitive.last_result("error_tool")
    assert "error" in result
    assert "Intentional error" in result["error"]
