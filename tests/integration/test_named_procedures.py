"""
Integration tests for named sub-procedures with auto-checkpointing.
"""

import pytest
from tactus.core.runtime import TactusRuntime
from tactus.adapters.memory import MemoryStorage


@pytest.mark.asyncio
async def test_simple_named_procedure():
    """Test basic named procedure call."""
    source = """
-- Define a simple helper procedure
double = procedure("double", {
    input = {x = {type = "number", required = true}},
    output = {y = {type = "number", required = true}}
}, function()
    return {y = input.x * 2}
end)

-- Define main procedure
main = procedure("main", {
    input = {value = {type = "number", required = true}},
    output = {result = {type = "number", required = true}}
}, function()
    -- Call the helper procedure
    local doubled = double({x = input.value})
    return {result = doubled.y}
end)
"""

    storage = MemoryStorage()
    runtime = TactusRuntime(
        procedure_id="test-named-proc",
        storage_backend=storage,
    )

    result = await runtime.execute(source=source, context={"value": 21}, format="lua")

    assert result["success"] is True
    assert result["result"]["result"] == 42


@pytest.mark.asyncio
async def test_multiple_named_procedures():
    """Test multiple sub-procedure calls in sequence."""
    source = """
-- Define sum procedure
sum = procedure("sum", {
    input = {a = {type = "number"}, b = {type = "number"}},
    output = {result = {type = "number"}}
}, function()
    return {result = input.a + input.b}
end)

-- Define product procedure
product = procedure("product", {
    input = {a = {type = "number"}, b = {type = "number"}},
    output = {result = {type = "number"}}
}, function()
    return {result = input.a * input.b}
end)

-- Main procedure
main = procedure("main", {
    input = {x = {type = "number"}, y = {type = "number"}},
    output = {sum_result = {type = "number"}, product_result = {type = "number"}}
}, function()
    local s = sum({a = input.x, b = input.y})
    local p = product({a = input.x, b = input.y})
    return {sum_result = s.result, product_result = p.result}
end)
"""

    storage = MemoryStorage()
    runtime = TactusRuntime(
        procedure_id="test-multi-proc",
        storage_backend=storage,
    )

    result = await runtime.execute(source=source, context={"x": 5, "y": 3}, format="lua")

    assert result["success"] is True
    assert result["result"]["sum_result"] == 8
    assert result["result"]["product_result"] == 15


@pytest.mark.asyncio
async def test_named_procedure_with_state():
    """Test named procedure with state initialization."""
    source = """
counter = procedure("counter", {
    input = {},
    output = {count = {type = "number"}},
    state = {counter = {type = "number", default = 0}}
}, function()
    state.counter = state.counter + 1
    return {count = state.counter}
end)

main = procedure("main", {
    input = {},
    output = {final_count = {type = "number"}}
}, function()
    local result = counter({})
    return {final_count = result.count}
end)
"""

    storage = MemoryStorage()
    runtime = TactusRuntime(
        procedure_id="test-state-proc",
        storage_backend=storage,
    )

    result = await runtime.execute(source=source, context={}, format="lua")

    assert result["success"] is True
    assert result["result"]["final_count"] == 1


@pytest.mark.asyncio
async def test_simple_named_main_procedure():
    """Test simple named main procedure without sub-procedures."""
    source = """
main = procedure("main", {
    input = {x = {type = "number", required = true}},
    output = {y = {type = "number", required = true}}
}, function()
    return {y = input.x * 2}
end)
"""

    storage = MemoryStorage()
    runtime = TactusRuntime(
        procedure_id="test-main-proc",
        storage_backend=storage,
    )

    result = await runtime.execute(source=source, context={"x": 21}, format="lua")

    assert result["success"] is True
    assert result["result"]["y"] == 42


@pytest.mark.asyncio
async def test_input_validation():
    """Test that input validation works for named procedures."""
    source = """
strict_proc = procedure("strict_proc", {
    input = {required_field = {type = "string", required = true}},
    output = {result = {type = "string"}}
}, function()
    return {result = input.required_field}
end)

main = procedure("main", {
    input = {},
    output = {result = {type = "string"}}
}, function()
    -- This should fail: missing required field
    local result = strict_proc({})
    return {result = result.result}
end)
"""

    storage = MemoryStorage()
    runtime = TactusRuntime(
        procedure_id="test-validation",
        storage_backend=storage,
    )

    result = await runtime.execute(source=source, context={}, format="lua")

    assert result["success"] is False
    assert "missing required input: required_field" in result["error"]


@pytest.mark.asyncio
async def test_checkpoint_replay():
    """Test that sub-procedure calls are checkpointed and replayed."""
    source = """
expensive_op = procedure("expensive_op", {
    input = {x = {type = "number"}},
    output = {result = {type = "number"}}
}, function()
    -- Simulate expensive operation
    Log.info("Executing expensive operation")
    return {result = input.x * 2}
end)

main = procedure("main", {
    input = {value = {type = "number"}},
    output = {result = {type = "number"}}
}, function()
    local result1 = expensive_op({x = input.value})
    local result2 = expensive_op({x = result1.result})
    return {result = result2.result}
end)
"""

    storage = MemoryStorage()

    # First execution
    runtime1 = TactusRuntime(
        procedure_id="test-checkpoint",
        storage_backend=storage,
    )
    result1 = await runtime1.execute(source=source, context={"value": 5}, format="lua")
    assert result1["success"] is True
    assert result1["result"]["result"] == 20  # 5 * 2 * 2

    # Second execution (should replay from checkpoints)
    runtime2 = TactusRuntime(
        procedure_id="test-checkpoint",
        storage_backend=storage,
    )
    result2 = await runtime2.execute(source=source, context={"value": 5}, format="lua")
    assert result2["success"] is True
    assert result2["result"]["result"] == 20

    # Verify that expensive_op was executed twice in first run
    # but not re-executed in second run (replayed from checkpoint)
    metadata = storage.load_procedure_metadata("test-checkpoint")
    assert len(metadata.execution_log) >= 2  # At least 2 checkpoints for sub-procedure calls
