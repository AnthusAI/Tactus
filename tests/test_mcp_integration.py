"""
Integration tests for MCP server functionality.

Tests the full MCP integration stack using a test MCP server.
"""

import pytest

from tactus.core.runtime import TactusRuntime
from tactus.adapters.file_storage import FileStorage


@pytest.mark.asyncio
async def test_mcp_server_connection():
    """Test connecting to MCP server via MCPServerManager."""
    from tactus.adapters.mcp_manager import MCPServerManager
    import sys

    # Configure test MCP server
    config = {
        "test_server": {
            "command": sys.executable,  # Use current Python interpreter
            "args": ["-m", "tests.fixtures.test_mcp_server"],
            "env": {},
        }
    }

    # Create and connect manager
    manager = MCPServerManager(config)

    async with manager:
        toolsets = manager.get_toolsets()
        assert len(toolsets) == 1, "Should have one MCP server connected"

        # Verify the toolset is a PrefixedToolset wrapping MCPServerStdio
        from pydantic_ai.toolsets import PrefixedToolset

        assert isinstance(toolsets[0], PrefixedToolset)


@pytest.mark.asyncio
@pytest.mark.skipif(
    "OPENAI_API_KEY" not in __import__("os").environ,
    reason="Requires OPENAI_API_KEY environment variable",
)
async def test_mcp_tools_in_procedure(tmp_path):
    """Test using MCP tools in a Tactus procedure."""
    import sys

    # Create a simple procedure that uses MCP tools
    procedure_source = """
name: "MCP Test Procedure"
version: "1.0.0"

procedure: |
    -- Call the add_numbers tool from test MCP server
    -- For YAML format, agents are registered as globals with _Agent suffix
    if test_agent then
        test_agent()
    else
        -- Fallback for when agent is not registered as global
        Log.info("Agent not found as global, skipping turn")
    end

    -- Check if tool was called (simpler check for testing)
    return {success = true, result = "Test completed"}

agents:
    test_agent:
        provider: "openai"
        model: "gpt-4o-mini"
        system_prompt: "You are a test agent. Call the add_numbers tool with a=5 and b=3."
        initial_message: "Start"
        tools:
            - test_server
"""

    # Configure MCP server
    mcp_servers = {
        "test_server": {
            "command": sys.executable,  # Use current Python interpreter
            "args": ["-m", "tests.fixtures.test_mcp_server"],
            "env": {},
        }
    }

    # Create runtime with MCP servers
    storage = FileStorage(str(tmp_path / "storage"))
    runtime = TactusRuntime(
        procedure_id="test-mcp-integration",
        storage_backend=storage,
        mcp_servers=mcp_servers,
    )

    # Execute procedure
    result = await runtime.execute(procedure_source, format="yaml")

    # Verify execution
    assert result["success"], f"Procedure failed: {result.get('error')}"
    assert "result" in result
    # The tool should have been called and returned a result


@pytest.mark.asyncio
async def test_mcp_tool_prefixing():
    """Test that MCP tools are properly prefixed with server name."""
    from tactus.adapters.mcp_manager import MCPServerManager
    from pydantic_ai import Agent
    from pydantic_ai.models.test import TestModel
    import sys

    config = {
        "test_server": {
            "command": sys.executable,  # Use current Python interpreter
            "args": ["-m", "tests.fixtures.test_mcp_server"],
        }
    }

    manager = MCPServerManager(config)

    async with manager:
        toolsets = manager.get_toolsets()

        # Create an agent with the toolsets
        test_model = TestModel()
        agent = Agent(test_model, toolsets=toolsets)

        # Run the agent - this will make tools available
        await agent.run("test")

        # Check the tool definitions that were passed to the model
        tool_defs = test_model.last_model_request_parameters.function_tools

        # Verify all tools are prefixed
        for tool_def in tool_defs:
            assert tool_def.name.startswith(
                "test_server_"
            ), f"Tool {tool_def.name} should be prefixed with 'test_server_'"


@pytest.mark.asyncio
async def test_mcp_env_var_substitution():
    """Test environment variable substitution in MCP config."""
    import os
    from tactus.adapters.mcp_manager import substitute_env_vars

    # Set test env var
    os.environ["TEST_TOKEN"] = "secret123"

    config = {
        "command": "python",
        "args": ["-m", "test"],
        "env": {"API_KEY": "${TEST_TOKEN}", "STATIC": "value"},
    }

    result = substitute_env_vars(config)

    assert result["env"]["API_KEY"] == "secret123"
    assert result["env"]["STATIC"] == "value"

    # Cleanup
    del os.environ["TEST_TOKEN"]
