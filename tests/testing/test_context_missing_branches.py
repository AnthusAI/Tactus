from types import SimpleNamespace


from tactus.testing.context import TactusTestContext


def test_mock_agent_tool_call_replaces_non_list_tool_calls(tmp_path):
    ctx = TactusTestContext(procedure_file=tmp_path / "proc.tac")
    ctx.runtime = SimpleNamespace(external_agent_mocks=None)
    ctx._agent_mock_turns["agent"] = [{"tool_calls": "not-a-list"}]

    ctx.mock_agent_tool_call("agent", "tool", {"x": 1})

    assert ctx._agent_mock_turns["agent"][0]["tool_calls"] == [{"tool": "tool", "args": {"x": 1}}]


def test_mock_agent_tool_call_appends_to_existing_list(tmp_path):
    ctx = TactusTestContext(procedure_file=tmp_path / "proc.tac")
    ctx.runtime = SimpleNamespace(external_agent_mocks=None)
    ctx._agent_mock_turns["agent"] = [{"tool_calls": []}]

    ctx.mock_agent_tool_call("agent", "tool", {"x": 2})

    assert ctx._agent_mock_turns["agent"][0]["tool_calls"] == [{"tool": "tool", "args": {"x": 2}}]


def test_mock_agent_tool_call_skips_external_mocks_when_runtime_missing(tmp_path):
    ctx = TactusTestContext(procedure_file=tmp_path / "proc.tac")

    def fake_setup_runtime():
        ctx.runtime = None

    ctx.setup_runtime = fake_setup_runtime  # type: ignore[assignment]

    ctx.mock_agent_tool_call("agent", "tool", {"y": 2})

    assert ctx.runtime is None
    assert ctx._agent_mock_turns["agent"][0]["tool_calls"][0]["tool"] == "tool"


def test_mock_agent_data_reuses_existing_turn(tmp_path):
    ctx = TactusTestContext(procedure_file=tmp_path / "proc.tac")
    ctx.set_scenario_message("ping")
    ctx.runtime = SimpleNamespace(external_agent_mocks=None)
    ctx._agent_mock_turns["agent"] = [{"when_message": "ping"}]

    ctx.mock_agent_data("agent", {"ok": True})

    assert ctx._agent_mock_turns["agent"][0]["data"] == {"ok": True}


def test_mock_agent_data_skips_when_message_when_not_set(tmp_path):
    ctx = TactusTestContext(procedure_file=tmp_path / "proc.tac")
    ctx.runtime = SimpleNamespace(external_agent_mocks=None)

    ctx.mock_agent_data("agent", {"ok": True})

    assert "when_message" not in ctx._agent_mock_turns["agent"][0]


def test_mock_agent_data_skips_external_mocks_when_runtime_missing(tmp_path):
    ctx = TactusTestContext(procedure_file=tmp_path / "proc.tac")

    def fake_setup_runtime():
        ctx.runtime = None

    ctx.setup_runtime = fake_setup_runtime  # type: ignore[assignment]

    ctx.mock_agent_data("agent", {"ok": True})

    assert ctx.runtime is None


def test_mock_tool_returns_initializes_mock_manager(tmp_path):
    ctx = TactusTestContext(procedure_file=tmp_path / "proc.tac")
    ctx.runtime = SimpleNamespace(mock_manager=None)

    ctx.mock_tool_returns("tool", {"result": 1})

    assert ctx.runtime.mock_manager is not None
    assert "tool" in ctx.runtime.mock_manager.mocks


def test_mock_tool_returns_reuses_existing_mock_manager(tmp_path):
    from tactus.core.mocking import MockManager

    ctx = TactusTestContext(procedure_file=tmp_path / "proc.tac")
    ctx.runtime = SimpleNamespace(mock_manager=MockManager())

    ctx.mock_tool_returns("tool", {"result": 2})

    assert "tool" in ctx.runtime.mock_manager.mocks


def test_setup_runtime_mocked_creates_registry(monkeypatch, tmp_path):
    ctx = TactusTestContext(procedure_file=tmp_path / "proc.tac", mocked=True)

    class DummyRuntime:
        def __init__(self, **_kwargs):
            self.mock_manager = None

    monkeypatch.setattr("tactus.core.runtime.TactusRuntime", DummyRuntime)

    ctx.setup_runtime()

    assert ctx.mock_registry is not None
    assert ctx.runtime is not None


def test_run_procedure_async_injects_dependencies_and_metrics(tmp_path):
    proc = tmp_path / "proc.tac"
    proc.write_text('Agent "a" {}')

    ctx = TactusTestContext(procedure_file=proc, mocked=True)

    async def create_mock_dependencies(_deps):
        return {"dep": "mocked"}

    ctx.mock_registry = SimpleNamespace(create_mock_dependencies=create_mock_dependencies)

    class DummyRuntime:
        def __init__(self):
            self.registry = SimpleNamespace(dependencies={"dep": SimpleNamespace(config={"x": 1})})
            self.user_dependencies = None
            self.lua_sandbox = object()
            self.tool_primitive = "tool"
            self.state_primitive = "state"
            self.iterations_primitive = "iterations"
            self.stop_primitive = "stop"

        async def execute(self, source, context, format):
            return {
                "success": True,
                "total_cost": 1.25,
                "total_tokens": 5,
                "cost_breakdown": [{"cost": 1.25}],
                "iterations": 2,
                "tools_used": ["tool"],
            }

    ctx.runtime = DummyRuntime()

    import asyncio

    asyncio.run(ctx.run_procedure_async())

    assert ctx.runtime.user_dependencies == {"dep": "mocked"}
    assert ctx.total_cost == 1.25
    assert ctx.total_tokens == 5
    assert ctx.tools_used == ["tool"]
    assert ctx._primitives["tool"] == "tool"


def test_run_procedure_async_handles_empty_execution_result(tmp_path):
    proc = tmp_path / "proc.tac"
    proc.write_text('Agent "a" {}')

    ctx = TactusTestContext(procedure_file=proc)

    class DummyRuntime:
        def __init__(self):
            self.registry = SimpleNamespace(dependencies={})
            self.user_dependencies = None
            self.lua_sandbox = object()
            self.tool_primitive = "tool"
            self.state_primitive = "state"
            self.iterations_primitive = "iterations"
            self.stop_primitive = "stop"

        async def execute(self, source, context, format):
            return {}

    ctx.runtime = DummyRuntime()

    import asyncio

    asyncio.run(ctx.run_procedure_async())

    assert ctx.execution_result == {}


def test_output_fallbacks_and_status_defaults(tmp_path):
    ctx = TactusTestContext(procedure_file=tmp_path / "proc.tac")

    assert ctx.output_get("missing") is None
    assert ctx.output_exists("missing") is False
    assert ctx.stop_success() is False
    assert ctx.stop_reason() == ""
    assert ctx.iterations() == 0
    assert ctx.agent_context() == ""

    ctx.execution_result = {"result": {"x": 1}}

    assert ctx.output_get("x") == 1
    assert ctx.output_exists("x") is True


def test_output_without_result_key_returns_defaults(tmp_path):
    ctx = TactusTestContext(procedure_file=tmp_path / "proc.tac")
    ctx.execution_result = {"output": "value"}

    assert ctx.output_get("x") is None
    assert ctx.output_exists("x") is False

    ctx.execution_result = {"foo": "bar"}

    assert ctx.output_get("x") is None
    assert ctx.output_exists("x") is False


def test_output_result_non_dict_returns_none(tmp_path):
    ctx = TactusTestContext(procedure_file=tmp_path / "proc.tac")
    ctx.execution_result = {"result": "not-a-dict"}

    assert ctx.output_get("x") is None
    assert ctx.output_exists("x") is False
