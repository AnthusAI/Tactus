from types import SimpleNamespace

from tactus.testing.context import TactusTestContext


def test_capture_primitives_populates_registry(tmp_path):
    ctx = TactusTestContext(procedure_file=tmp_path / "proc.tac")
    ctx.runtime = SimpleNamespace(
        lua_sandbox=object(),
        tool_primitive="tool",
        state_primitive="state",
        iterations_primitive="iterations",
        stop_primitive="stop",
    )

    ctx._capture_primitives()

    assert ctx._primitives["tool"] == "tool"
    assert ctx._primitives["state"] == "state"
    assert ctx._primitives["iterations"] == "iterations"
    assert ctx._primitives["stop"] == "stop"


def test_inject_mocked_dependencies_no_dependencies(tmp_path):
    ctx = TactusTestContext(procedure_file=tmp_path / "proc.tac", mocked=True)

    ctx.runtime = SimpleNamespace(registry=SimpleNamespace(dependencies={}), user_dependencies=None)

    async def create_mock_dependencies(_deps):
        return {}

    ctx.mock_registry = SimpleNamespace(create_mock_dependencies=create_mock_dependencies)

    # Run the coroutine to cover the early return branch.
    import asyncio

    asyncio.run(ctx._inject_mocked_dependencies())
