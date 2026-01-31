"""
Tests for zero-wrapper script mode.

Script mode allows writing Tactus procedures without the Procedure {} wrapper:
- Top-level input {} and output {} declarations
- Direct executable code (agent calls, returns)
- Automatic transformation wraps code in implicit Procedure
"""

import pytest

from tactus.core.runtime import TactusRuntime
from tactus.core.mocking import MockManager
from tactus.adapters.file_storage import FileStorage


@pytest.mark.asyncio
async def test_script_mode_basic(tmp_path):
    """Test basic unnamed Procedure (main entry point)."""
    source = """
Procedure {
    input = { name = field.string{required = true} },
    output = { greeting = field.string{required = true} },
    function(input)
        local message = "Hello, " .. input.name .. "!"
        return {greeting = message}
    end
}
"""
    storage = FileStorage(str(tmp_path / "storage"))
    runtime = TactusRuntime(procedure_id="test", storage_backend=storage)
    result = await runtime.execute(source, context={"name": "World"}, format="lua")

    assert result["success"]
    assert result["result"]["greeting"] == "Hello, World!"


@pytest.mark.asyncio
async def test_script_mode_no_input(tmp_path):
    """Test unnamed Procedure with only output schema."""
    source = """
Procedure {
    output = { result = field.string{required = true} },
    function(input)
        local value = "test result"
        return {result = value}
    end
}
"""
    storage = FileStorage(str(tmp_path / "storage"))
    runtime = TactusRuntime(procedure_id="test", storage_backend=storage)
    result = await runtime.execute(source, context={}, format="lua")

    assert result["success"]
    assert result["result"]["result"] == "test result"


@pytest.mark.asyncio
async def test_script_mode_with_mock_agent(tmp_path):
    """Test script mode with mocked agent calls."""
    source = """
input { task = field.string{required = true} }
output { result = field.string{required = true} }

Mocks {
    worker = {
        tool_calls = {
            { tool = "done", args = { reason = "Task completed!" } }
        },
        message = "Task completed!"
    }
}

local done = require("tactus.tools.done")

worker = Agent {
    provider = "openai",
    model = "gpt-4o-mini",
    system_prompt = "Complete tasks",
    tools = {done}
}

worker({message = input.task})
return {result = "completed"}
"""
    storage = FileStorage(str(tmp_path / "storage"))
    mock_manager = MockManager()
    runtime = TactusRuntime(procedure_id="test", storage_backend=storage)
    runtime.mock_manager = mock_manager
    result = await runtime.execute(source, context={"task": "test task"}, format="lua")

    assert result["success"]
    assert result["result"]["result"] == "completed"


@pytest.mark.asyncio
async def test_script_mode_with_state(tmp_path):
    """Test unnamed Procedure with state usage."""
    source = """
Procedure {
    input = { value = field.number{required = true} },
    output = { doubled = field.number{required = true} },
    function(input)
        state.original = input.value
        state.result = state.original * 2
        return {doubled = state.result}
    end
}
"""
    storage = FileStorage(str(tmp_path / "storage"))
    runtime = TactusRuntime(procedure_id="test", storage_backend=storage)
    result = await runtime.execute(source, context={"value": 21}, format="lua")

    assert result["success"]
    assert result["result"]["doubled"] == 42


@pytest.mark.asyncio
async def test_script_mode_with_local_variables(tmp_path):
    """Test unnamed Procedure with local variables."""
    source = """
Procedure {
    input = { a = field.number{required = true}, b = field.number{required = true} },
    output = { sum = field.number{required = true}, product = field.number{required = true} },
    function(input)
        local x = input.a
        local y = input.b
        local total = x + y
        local prod = x * y
        return {sum = total, product = prod}
    end
}
"""
    storage = FileStorage(str(tmp_path / "storage"))
    runtime = TactusRuntime(procedure_id="test", storage_backend=storage)
    result = await runtime.execute(source, context={"a": 5, "b": 3}, format="lua")

    assert result["success"]
    assert result["result"]["sum"] == 8
    assert result["result"]["product"] == 15


@pytest.mark.asyncio
async def test_script_mode_with_comments(tmp_path):
    """Test that comments are preserved in unnamed Procedure."""
    source = """
-- This is a simple unnamed Procedure example
Procedure {
    input = { name = field.string{required = true} },
    output = { greeting = field.string{required = true} },
    function(input)
        -- Process the input
        local message = "Hello, " .. input.name .. "!"
        -- Return the greeting
        return {greeting = message}
    end
}
"""
    storage = FileStorage(str(tmp_path / "storage"))
    runtime = TactusRuntime(procedure_id="test", storage_backend=storage)
    result = await runtime.execute(source, context={"name": "Alice"}, format="lua")

    assert result["success"]
    assert result["result"]["greeting"] == "Hello, Alice!"


@pytest.mark.asyncio
async def test_explicit_procedure_not_transformed(tmp_path):
    """Test that explicit named Procedure is not transformed."""
    source = """
input { name = field.string{required = true} }

main = Procedure "main" {
    output = { greeting = field.string{required = true} },
    function(input)
        return {greeting = "Hi, " .. input.name}
    end
}
"""
    storage = FileStorage(str(tmp_path / "storage"))
    runtime = TactusRuntime(procedure_id="test", storage_backend=storage)
    result = await runtime.execute(source, context={"name": "Bob"}, format="lua")

    assert result["success"]
    assert result["result"]["greeting"] == "Hi, Bob"


@pytest.mark.asyncio
async def test_script_mode_only_declarations(tmp_path):
    """Test file with only declarations (no executable code)."""
    source = """
input { name = field.string{required = true} }
output { greeting = field.string{required = true} }

local done = require("tactus.tools.done")

worker = Agent {
    provider = "openai",
    model = "gpt-4o-mini",
    system_prompt = "Test",
    tools = {done}
}
"""
    storage = FileStorage(str(tmp_path / "storage"))
    runtime = TactusRuntime(procedure_id="test", storage_backend=storage)

    # Should fail - no main procedure created because no executable code
    result = await runtime.execute(source, context={"name": "Test"}, format="lua")
    assert not result["success"]
    assert "main" in result.get("error", "")


def test_script_mode_transform_skips_without_markers():
    runtime = TactusRuntime(procedure_id="test", storage_backend=FileStorage("/tmp"))
    source = "print('hi')"

    assert runtime._maybe_transform_script_mode_source(source) == source


def test_script_mode_transform_handles_long_strings_and_depth():
    runtime = TactusRuntime(procedure_id="test", storage_backend=FileStorage("/tmp"))
    source = """
input {
}}
Specifications [[
Feature: demo
Scenario: one
]]
function()
end end
return { ok = true }
"""

    transformed = runtime._maybe_transform_script_mode_source(source)

    assert "Procedure {" in transformed
    assert "Specifications [[" in transformed
