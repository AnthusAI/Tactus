from types import SimpleNamespace

import pytest

from tactus.testing.context import TactusTestContext


def test_setup_mock_tools_creates_mocked_tool_primitive(tmp_path):
    ctx = TactusTestContext(procedure_file=tmp_path / "proc.tac", mock_tools={"tool": {"ok": True}})

    ctx._setup_mock_tools()

    assert hasattr(ctx, "_mocked_tool_primitive")


def test_mock_tool_returns_creates_mock_manager(tmp_path):
    ctx = TactusTestContext(procedure_file=tmp_path / "proc.tac")
    ctx.runtime = SimpleNamespace(mock_manager=None)

    ctx.mock_tool_returns("tool", {"ok": True})

    assert ctx.runtime.mock_manager is not None
    assert ctx.runtime.mock_manager.get_mock_response("tool", {}) == {"ok": True}


@pytest.mark.asyncio
async def test_inject_mocked_dependencies_handles_missing_runtime(tmp_path):
    ctx = TactusTestContext(procedure_file=tmp_path / "proc.tac")

    await ctx._inject_mocked_dependencies()


@pytest.mark.asyncio
async def test_inject_mocked_dependencies_sets_user_dependencies(tmp_path):
    ctx = TactusTestContext(procedure_file=tmp_path / "proc.tac", mocked=True)

    async def create_mock_dependencies(_deps):
        return {"api": "mock"}

    ctx.mock_registry = SimpleNamespace(create_mock_dependencies=create_mock_dependencies)

    ctx.runtime = SimpleNamespace(
        registry=SimpleNamespace(
            dependencies={"api": SimpleNamespace(config={"type": "http_client"})}
        ),
        user_dependencies=None,
    )

    await ctx._inject_mocked_dependencies()

    assert ctx.runtime.user_dependencies == {"api": "mock"}


@pytest.mark.asyncio
async def test_run_procedure_async_captures_metrics_and_primitives(tmp_path):
    proc = tmp_path / "proc.tac"
    proc.write_text('Agent "test" {}')

    class DummyRuntime:
        def __init__(self):
            self.lua_sandbox = True
            self.tool_primitive = "tool"
            self.state_primitive = "state"
            self.iterations_primitive = "iterations"
            self.stop_primitive = "stop"

        async def execute(self, source, context, format):
            return {
                "success": True,
                "total_cost": 1.2,
                "total_tokens": 3,
                "cost_breakdown": [0.6, 0.6],
                "iterations": 2,
                "tools_used": ["tool"],
            }

    ctx = TactusTestContext(procedure_file=proc)
    ctx.runtime = DummyRuntime()

    await ctx.run_procedure_async()

    assert ctx.total_cost == 1.2
    assert ctx.total_tokens == 3
    assert ctx.cost_breakdown == [0.6, 0.6]
    assert ctx.tools_used == ["tool"]
    assert ctx._procedure_executed is True
    assert ctx._primitives["tool"] == "tool"
