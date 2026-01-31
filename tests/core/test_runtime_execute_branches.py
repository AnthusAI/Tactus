import os

import pytest

from tactus.core import runtime as runtime_module
from tactus.core.exceptions import ProcedureWaitingForHuman
from tactus.core.output_validator import OutputValidationError


class DummyLua:
    def __init__(self):
        self.executed = []

    def execute(self, code):
        self.executed.append(code)


class DummyLuaSandbox:
    def __init__(self, execution_context=None, strict_determinism=False, base_path=None):
        self.execution_context = execution_context
        self.strict_determinism = strict_determinism
        self.base_path = base_path
        self.lua = DummyLua()
        self.injected = {}
        self.globals = {}

    def set_execution_context(self, execution_context):
        self.execution_context = execution_context

    def inject_primitive(self, name, value):
        self.injected[name] = value

    def set_global(self, name, value):
        self.globals[name] = value

    def execute(self, code):
        return {"result": code}


class DummyMetadata:
    def __init__(self):
        self.execution_log = [
            type("Checkpoint", (), {"type": "alpha", "duration_ms": 12})(),
            type("Checkpoint", (), {"type": "alpha", "duration_ms": None})(),
            type("Checkpoint", (), {"type": "beta", "duration_ms": 4})(),
        ]


class DummyExecutionContext:
    def __init__(
        self,
        procedure_id,
        storage_backend,
        hitl_handler=None,
        strict_determinism=False,
        log_handler=None,
    ):
        self.procedure_id = procedure_id
        self.storage = storage_backend
        self.hitl = hitl_handler
        self.strict_determinism = strict_determinism
        self.log_handler = log_handler
        self.metadata = DummyMetadata()
        self.current_tac_file = None

    def set_run_id(self, run_id):
        self.current_run_id = run_id

    def set_lua_sandbox(self, lua_sandbox):
        self.lua_sandbox = lua_sandbox

    def set_tac_file(self, file_path, content=None):
        self.current_tac_file = file_path
        self.current_tac_content = content

    def set_procedure_metadata(self, procedure_name=None, input_data=None):
        self.procedure_name = procedure_name
        self._input_data = input_data


class DummyExecutionContextNoMetadata:
    def __init__(
        self,
        procedure_id,
        storage_backend,
        hitl_handler=None,
        strict_determinism=False,
        log_handler=None,
    ):
        self.procedure_id = procedure_id
        self.storage = storage_backend
        self.hitl = hitl_handler
        self.strict_determinism = strict_determinism
        self.log_handler = log_handler
        self.current_tac_file = None

    def set_run_id(self, run_id):
        self.current_run_id = run_id

    def set_lua_sandbox(self, lua_sandbox):
        self.lua_sandbox = lua_sandbox

    def set_tac_file(self, file_path, content=None):
        self.current_tac_file = file_path
        self.current_tac_content = content


class DummyLogHandler:
    def __init__(self):
        self.cost_events = [
            type("Cost", (), {"total_cost": 0.12, "total_tokens": 120})(),
            type("Cost", (), {"total_cost": 0.08, "total_tokens": 80})(),
        ]
        self.logged = []

    def log(self, event):
        self.logged.append(event)


class DummyChatRecorder:
    def __init__(self):
        self.sessions = []

    async def start_session(self, context):
        self.sessions.append(("start", context))
        return "session-1"

    async def end_session(self, session_id, status=None):
        self.sessions.append(("end", session_id, status))


class DummyAgent:
    async def flush_recordings(self):
        return None


class DummyToolPrimitive:
    def get_all_calls(self):
        return [type("Call", (), {"name": "done"})()]


class DummyStatePrimitive:
    def all(self):
        return {"ok": True}


class DummyIterationsPrimitive:
    def current(self):
        return 2


class DummyStopPrimitive:
    def requested(self):
        return True

    def reason(self):
        return "done"


class DummyRegistry:
    def __init__(self):
        self.agents = {"agent": object()}
        self.lua_tools = {}
        self.mocks = {"tool": object()}
        self.agent_mocks = {}
        self.named_procedures = {}


class DummyMockManager:
    def __init__(self):
        self.registered = []
        self.enabled = []

    def register_mock(self, name, config):
        self.registered.append(name)

    def enable_mock(self, name=None):
        self.enabled.append(name or "*")


async def _noop_async(*_args, **_kwargs):
    return None


@pytest.mark.asyncio
async def test_execute_success_with_summary(monkeypatch, tmp_path):
    runtime = runtime_module.TactusRuntime(
        procedure_id="proc",
        storage_backend=None,
        hitl_handler=object(),
        openai_api_key="key",
        external_config={"toolsets": {"extra": {}}, "default_model": "m"},
        run_id="run-1",
        source_file_path=str(tmp_path / "workflow.tac"),
    )

    runtime.mock_manager = DummyMockManager()
    runtime.external_agent_mocks = {"agent": [{"message": "hi"}]}
    runtime.mock_all_agents = True
    runtime.toolset_primitive = None

    monkeypatch.setattr(runtime_module, "LuaSandbox", DummyLuaSandbox)
    monkeypatch.setattr(runtime_module, "BaseExecutionContext", DummyExecutionContext)

    monkeypatch.setattr(runtime, "_parse_declarations", lambda *_args, **_kwargs: DummyRegistry())
    monkeypatch.setattr(
        runtime,
        "_registry_to_config",
        lambda _registry: {
            "output": {"out": {"type": "string"}},
            "hitl": {},
            "return_prompt": "summarize",
        },
    )

    async def fake_initialize_primitives(placeholder_tool=None):
        runtime.state_primitive = DummyStatePrimitive()
        runtime.iterations_primitive = DummyIterationsPrimitive()
        runtime.tool_primitive = DummyToolPrimitive()
        runtime.stop_primitive = DummyStopPrimitive()
        runtime.toolset_primitive = None

    monkeypatch.setattr(runtime, "_initialize_primitives", fake_initialize_primitives)
    monkeypatch.setattr(runtime, "_initialize_toolsets", _noop_async)
    monkeypatch.setattr(runtime, "_initialize_named_procedures", _noop_async)
    monkeypatch.setattr(runtime, "_setup_agents", _noop_async)
    monkeypatch.setattr(runtime, "_setup_models", _noop_async)
    monkeypatch.setattr(runtime, "_execute_workflow", lambda: {"result": "ok"})

    chat_recorder = DummyChatRecorder()
    runtime.chat_recorder = chat_recorder
    runtime.log_handler = DummyLogHandler()
    runtime.agents["agent"] = DummyAgent()

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    result = await runtime.execute("return {}", context={"name": "Ada"}, format="lua")

    assert result["success"] is True
    assert result["state"] == {"ok": True}
    assert result["stop_requested"] is True
    assert os.environ.get("OPENAI_API_KEY") == "key"


@pytest.mark.asyncio
async def test_execute_success_with_summary_no_metadata(monkeypatch, tmp_path):
    runtime = runtime_module.TactusRuntime(
        procedure_id="proc",
        storage_backend=None,
        hitl_handler=object(),
        source_file_path=str(tmp_path / "workflow.tac"),
    )
    runtime.toolset_primitive = None

    monkeypatch.setattr(runtime_module, "LuaSandbox", DummyLuaSandbox)
    monkeypatch.setattr(runtime_module, "BaseExecutionContext", DummyExecutionContextNoMetadata)
    monkeypatch.setattr(runtime, "_parse_declarations", lambda *_args, **_kwargs: DummyRegistry())
    monkeypatch.setattr(
        runtime,
        "_registry_to_config",
        lambda _registry: {"output": {"out": {"type": "string"}}, "hitl": {}},
    )
    monkeypatch.setattr(runtime, "_initialize_primitives", _noop_async)
    monkeypatch.setattr(runtime, "_initialize_toolsets", _noop_async)
    monkeypatch.setattr(runtime, "_initialize_named_procedures", _noop_async)
    monkeypatch.setattr(runtime, "_setup_agents", _noop_async)
    monkeypatch.setattr(runtime, "_setup_models", _noop_async)
    monkeypatch.setattr(runtime, "_execute_workflow", lambda: {"result": "ok"})

    runtime.log_handler = DummyLogHandler()

    result = await runtime.execute("return {}", context=None, format="lua")

    assert result["success"] is True


@pytest.mark.asyncio
async def test_execute_output_validation_error(monkeypatch, tmp_path):
    runtime = runtime_module.TactusRuntime(
        procedure_id="proc",
        storage_backend=None,
        hitl_handler=object(),
        source_file_path=str(tmp_path / "workflow.tac"),
    )
    runtime.toolset_primitive = None
    runtime.toolset_primitive = None
    runtime.toolset_primitive = None

    monkeypatch.setattr(runtime_module, "LuaSandbox", DummyLuaSandbox)
    monkeypatch.setattr(runtime_module, "BaseExecutionContext", DummyExecutionContext)
    monkeypatch.setattr(runtime, "_parse_declarations", lambda *_args, **_kwargs: DummyRegistry())
    monkeypatch.setattr(runtime, "_registry_to_config", lambda _registry: {"output": {}})
    monkeypatch.setattr(runtime, "_initialize_primitives", _noop_async)
    monkeypatch.setattr(runtime, "_initialize_toolsets", _noop_async)
    monkeypatch.setattr(runtime, "_initialize_named_procedures", _noop_async)
    monkeypatch.setattr(runtime, "_setup_agents", _noop_async)
    monkeypatch.setattr(runtime, "_setup_models", _noop_async)
    monkeypatch.setattr(runtime, "_execute_workflow", lambda: {"result": "ok"})

    class DummyValidator:
        def validate(self, _value):
            raise OutputValidationError("bad")

    monkeypatch.setattr(runtime_module, "OutputValidator", lambda _schema: DummyValidator())

    result = await runtime.execute("return {}", context=None, format="lua")

    assert result["success"] is True


@pytest.mark.asyncio
async def test_execute_summary_includes_checkpoints(monkeypatch, tmp_path):
    runtime = runtime_module.TactusRuntime(
        procedure_id="proc",
        storage_backend=None,
        hitl_handler=object(),
        log_handler=DummyLogHandler(),
        source_file_path=str(tmp_path / "workflow.tac"),
    )
    runtime.toolset_primitive = None

    monkeypatch.setattr(runtime_module, "LuaSandbox", DummyLuaSandbox)
    monkeypatch.setattr(runtime_module, "BaseExecutionContext", DummyExecutionContext)
    monkeypatch.setattr(runtime, "_parse_declarations", lambda *_args, **_kwargs: DummyRegistry())
    monkeypatch.setattr(runtime, "_registry_to_config", lambda _registry: {"output": {}})
    monkeypatch.setattr(runtime, "_initialize_primitives", _noop_async)
    monkeypatch.setattr(runtime, "_initialize_toolsets", _noop_async)
    monkeypatch.setattr(runtime, "_initialize_named_procedures", _noop_async)
    monkeypatch.setattr(runtime, "_setup_agents", _noop_async)
    monkeypatch.setattr(runtime, "_setup_models", _noop_async)
    monkeypatch.setattr(runtime, "_inject_primitives", lambda: None)
    monkeypatch.setattr(runtime, "_execute_workflow", lambda: {})

    result = await runtime.execute("return {}", context=None, format="lua")

    assert result["success"] is True


@pytest.mark.asyncio
async def test_execute_waiting_for_human(monkeypatch, tmp_path):
    runtime = runtime_module.TactusRuntime(
        procedure_id="proc",
        storage_backend=None,
        hitl_handler=object(),
        source_file_path=str(tmp_path / "workflow.tac"),
    )
    runtime.toolset_primitive = None

    monkeypatch.setattr(runtime_module, "LuaSandbox", DummyLuaSandbox)
    monkeypatch.setattr(runtime_module, "BaseExecutionContext", DummyExecutionContext)
    monkeypatch.setattr(runtime, "_parse_declarations", lambda *_args, **_kwargs: DummyRegistry())
    monkeypatch.setattr(runtime, "_registry_to_config", lambda _registry: {"output": {}})
    monkeypatch.setattr(runtime, "_initialize_primitives", _noop_async)
    monkeypatch.setattr(runtime, "_initialize_toolsets", _noop_async)
    monkeypatch.setattr(runtime, "_initialize_named_procedures", _noop_async)
    monkeypatch.setattr(runtime, "_setup_agents", _noop_async)
    monkeypatch.setattr(runtime, "_setup_models", _noop_async)
    monkeypatch.setattr(
        runtime,
        "_execute_workflow",
        lambda: (_ for _ in ()).throw(ProcedureWaitingForHuman("wait", pending_message_id="msg-1")),
    )

    result = await runtime.execute("return {}", context=None, format="lua")

    assert result["status"] == "WAITING_FOR_HUMAN"


@pytest.mark.asyncio
async def test_execute_config_error(monkeypatch, tmp_path):
    runtime = runtime_module.TactusRuntime(
        procedure_id="proc",
        storage_backend=None,
        hitl_handler=object(),
        source_file_path=str(tmp_path / "workflow.tac"),
    )
    runtime.toolset_primitive = None
    runtime.toolset_primitive = None

    monkeypatch.setattr(runtime_module, "LuaSandbox", DummyLuaSandbox)
    monkeypatch.setattr(runtime_module, "BaseExecutionContext", DummyExecutionContext)
    monkeypatch.setattr(
        runtime,
        "_parse_declarations",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(runtime_module.ProcedureConfigError("bad")),
    )

    result = await runtime.execute("return {}", context=None, format="lua")

    assert result["success"] is False
    assert "Configuration error" in result["error"]


@pytest.mark.asyncio
async def test_execute_lua_error(monkeypatch, tmp_path):
    runtime = runtime_module.TactusRuntime(
        procedure_id="proc",
        storage_backend=None,
        hitl_handler=object(),
        source_file_path=str(tmp_path / "workflow.tac"),
    )

    monkeypatch.setattr(runtime_module, "LuaSandbox", DummyLuaSandbox)
    monkeypatch.setattr(runtime_module, "BaseExecutionContext", DummyExecutionContext)
    monkeypatch.setattr(runtime, "_parse_declarations", lambda *_args, **_kwargs: DummyRegistry())
    monkeypatch.setattr(
        runtime, "_registry_to_config", lambda _registry: {"output": {}, "error_prompt": "oops"}
    )
    monkeypatch.setattr(runtime, "_initialize_primitives", _noop_async)
    monkeypatch.setattr(runtime, "_initialize_toolsets", _noop_async)
    monkeypatch.setattr(runtime, "_initialize_named_procedures", _noop_async)
    monkeypatch.setattr(runtime, "_setup_agents", _noop_async)
    monkeypatch.setattr(runtime, "_setup_models", _noop_async)
    monkeypatch.setattr(runtime, "_inject_primitives", lambda: None)
    monkeypatch.setattr(
        runtime,
        "_execute_workflow",
        lambda: (_ for _ in ()).throw(runtime_module.LuaSandboxError("fail")),
    )

    result = await runtime.execute("return {}", context=None, format="lua")

    assert result["success"] is False
    assert "Lua execution error" in result["error"]


@pytest.mark.asyncio
async def test_execute_external_agent_mocks_must_be_list(monkeypatch, tmp_path):
    runtime = runtime_module.TactusRuntime(
        procedure_id="proc",
        storage_backend=None,
        hitl_handler=object(),
        source_file_path=str(tmp_path / "workflow.tac"),
    )
    runtime.external_agent_mocks = {"agent": "not-a-list"}

    monkeypatch.setattr(runtime_module, "LuaSandbox", DummyLuaSandbox)
    monkeypatch.setattr(runtime_module, "BaseExecutionContext", DummyExecutionContext)
    monkeypatch.setattr(runtime, "_parse_declarations", lambda *_args, **_kwargs: DummyRegistry())
    monkeypatch.setattr(runtime, "_registry_to_config", lambda _registry: {"output": {}})

    result = await runtime.execute("return {}", context=None, format="lua")

    assert result["success"] is False
    assert "must be a list" in result["error"]


@pytest.mark.asyncio
async def test_execute_merges_external_toolsets(monkeypatch, tmp_path):
    runtime = runtime_module.TactusRuntime(
        procedure_id="proc",
        storage_backend=None,
        hitl_handler=object(),
        external_config={"toolsets": {"external": {"foo": "bar"}}, "default_provider": "openai"},
        source_file_path=str(tmp_path / "workflow.tac"),
    )
    runtime.toolset_primitive = None

    monkeypatch.setattr(runtime_module, "LuaSandbox", DummyLuaSandbox)
    monkeypatch.setattr(runtime_module, "BaseExecutionContext", DummyExecutionContext)
    monkeypatch.setattr(runtime, "_parse_declarations", lambda *_args, **_kwargs: DummyRegistry())
    monkeypatch.setattr(runtime, "_registry_to_config", lambda _registry: {"output": {}})
    monkeypatch.setattr(runtime, "_initialize_primitives", _noop_async)
    monkeypatch.setattr(runtime, "_initialize_toolsets", _noop_async)
    monkeypatch.setattr(runtime, "_initialize_named_procedures", _noop_async)
    monkeypatch.setattr(runtime, "_setup_agents", _noop_async)
    monkeypatch.setattr(runtime, "_setup_models", _noop_async)
    monkeypatch.setattr(runtime, "_inject_primitives", lambda: None)
    monkeypatch.setattr(runtime, "_execute_workflow", lambda: {})

    await runtime.execute("return {}", context=None, format="lua")

    assert runtime.config["toolsets"]["external"]["foo"] == "bar"
    assert runtime.config["default_provider"] == "openai"


@pytest.mark.asyncio
async def test_execute_merges_external_toolsets_into_existing(monkeypatch, tmp_path):
    runtime = runtime_module.TactusRuntime(
        procedure_id="proc",
        storage_backend=None,
        hitl_handler=object(),
        external_config={"toolsets": {"external": {"foo": "bar"}}},
        source_file_path=str(tmp_path / "workflow.tac"),
    )
    runtime.toolset_primitive = None

    monkeypatch.setattr(runtime_module, "LuaSandbox", DummyLuaSandbox)
    monkeypatch.setattr(runtime_module, "BaseExecutionContext", DummyExecutionContext)
    monkeypatch.setattr(runtime, "_parse_declarations", lambda *_args, **_kwargs: DummyRegistry())
    monkeypatch.setattr(
        runtime, "_registry_to_config", lambda _registry: {"output": {}, "toolsets": {"local": {}}}
    )
    monkeypatch.setattr(runtime, "_initialize_primitives", _noop_async)
    monkeypatch.setattr(runtime, "_initialize_toolsets", _noop_async)
    monkeypatch.setattr(runtime, "_initialize_named_procedures", _noop_async)
    monkeypatch.setattr(runtime, "_setup_agents", _noop_async)
    monkeypatch.setattr(runtime, "_setup_models", _noop_async)
    monkeypatch.setattr(runtime, "_inject_primitives", lambda: None)
    monkeypatch.setattr(runtime, "_execute_workflow", lambda: {})

    await runtime.execute("return {}", context=None, format="lua")

    assert "local" in runtime.config["toolsets"]
    assert "external" in runtime.config["toolsets"]


@pytest.mark.asyncio
async def test_execute_chat_recorder_session_missing(monkeypatch, tmp_path):
    class EmptySessionRecorder(DummyChatRecorder):
        async def start_session(self, context):
            return None

    runtime = runtime_module.TactusRuntime(
        procedure_id="proc",
        storage_backend=None,
        hitl_handler=object(),
        chat_recorder=EmptySessionRecorder(),
        source_file_path=str(tmp_path / "workflow.tac"),
    )
    runtime.toolset_primitive = None

    monkeypatch.setattr(runtime_module, "LuaSandbox", DummyLuaSandbox)
    monkeypatch.setattr(runtime_module, "BaseExecutionContext", DummyExecutionContext)
    monkeypatch.setattr(runtime, "_parse_declarations", lambda *_args, **_kwargs: DummyRegistry())
    monkeypatch.setattr(runtime, "_registry_to_config", lambda _registry: {"output": {}})
    monkeypatch.setattr(runtime, "_initialize_primitives", _noop_async)
    monkeypatch.setattr(runtime, "_initialize_toolsets", _noop_async)
    monkeypatch.setattr(runtime, "_initialize_named_procedures", _noop_async)
    monkeypatch.setattr(runtime, "_setup_agents", _noop_async)
    monkeypatch.setattr(runtime, "_setup_models", _noop_async)
    monkeypatch.setattr(runtime, "_inject_primitives", lambda: None)
    monkeypatch.setattr(runtime, "_execute_workflow", lambda: {})

    result = await runtime.execute("return {}", context=None, format="lua")

    assert result["success"] is True


@pytest.mark.asyncio
async def test_execute_waiting_for_human_flushes_recordings(monkeypatch, tmp_path):
    runtime = runtime_module.TactusRuntime(
        procedure_id="proc",
        storage_backend=None,
        hitl_handler=object(),
        chat_recorder=DummyChatRecorder(),
        source_file_path=str(tmp_path / "workflow.tac"),
    )
    runtime.toolset_primitive = None

    dummy_agent = DummyAgent()
    runtime.agents = {"agent": dummy_agent}

    monkeypatch.setattr(runtime_module, "LuaSandbox", DummyLuaSandbox)
    monkeypatch.setattr(runtime_module, "BaseExecutionContext", DummyExecutionContext)
    monkeypatch.setattr(runtime, "_parse_declarations", lambda *_args, **_kwargs: DummyRegistry())
    monkeypatch.setattr(runtime, "_registry_to_config", lambda _registry: {"output": {}})
    monkeypatch.setattr(runtime, "_initialize_primitives", _noop_async)
    monkeypatch.setattr(runtime, "_initialize_toolsets", _noop_async)
    monkeypatch.setattr(runtime, "_initialize_named_procedures", _noop_async)
    monkeypatch.setattr(runtime, "_setup_agents", _noop_async)
    monkeypatch.setattr(runtime, "_setup_models", _noop_async)
    monkeypatch.setattr(
        runtime,
        "_execute_workflow",
        lambda: (_ for _ in ()).throw(ProcedureWaitingForHuman("wait", pending_message_id="msg-2")),
    )

    result = await runtime.execute("return {}", context=None, format="lua")

    assert result["status"] == "WAITING_FOR_HUMAN"


@pytest.mark.asyncio
async def test_execute_waiting_for_human_skips_missing_flush(monkeypatch, tmp_path):
    runtime = runtime_module.TactusRuntime(
        procedure_id="proc",
        storage_backend=None,
        hitl_handler=object(),
        chat_recorder=DummyChatRecorder(),
        source_file_path=str(tmp_path / "workflow.tac"),
    )
    runtime.toolset_primitive = None
    runtime.agents = {"agent": object()}

    monkeypatch.setattr(runtime_module, "LuaSandbox", DummyLuaSandbox)
    monkeypatch.setattr(runtime_module, "BaseExecutionContext", DummyExecutionContext)
    monkeypatch.setattr(runtime, "_parse_declarations", lambda *_args, **_kwargs: DummyRegistry())
    monkeypatch.setattr(runtime, "_registry_to_config", lambda _registry: {"output": {}})
    monkeypatch.setattr(runtime, "_initialize_primitives", _noop_async)
    monkeypatch.setattr(runtime, "_initialize_toolsets", _noop_async)
    monkeypatch.setattr(runtime, "_initialize_named_procedures", _noop_async)
    monkeypatch.setattr(runtime, "_setup_agents", _noop_async)
    monkeypatch.setattr(runtime, "_setup_models", _noop_async)
    monkeypatch.setattr(
        runtime,
        "_execute_workflow",
        lambda: (_ for _ in ()).throw(ProcedureWaitingForHuman("wait", pending_message_id="msg-3")),
    )

    result = await runtime.execute("return {}", context=None, format="lua")

    assert result["status"] == "WAITING_FOR_HUMAN"


@pytest.mark.asyncio
async def test_execute_success_skips_missing_flush_recordings(monkeypatch, tmp_path):
    runtime = runtime_module.TactusRuntime(
        procedure_id="proc",
        storage_backend=None,
        hitl_handler=object(),
        chat_recorder=DummyChatRecorder(),
        source_file_path=str(tmp_path / "workflow.tac"),
    )

    runtime.agents = {"agent": object()}
    runtime.toolset_primitive = None

    monkeypatch.setattr(runtime_module, "LuaSandbox", DummyLuaSandbox)
    monkeypatch.setattr(runtime_module, "BaseExecutionContext", DummyExecutionContext)
    monkeypatch.setattr(runtime, "_parse_declarations", lambda *_args, **_kwargs: DummyRegistry())
    monkeypatch.setattr(runtime, "_registry_to_config", lambda _registry: {"output": {}})
    monkeypatch.setattr(runtime, "_initialize_primitives", _noop_async)
    monkeypatch.setattr(runtime, "_initialize_toolsets", _noop_async)
    monkeypatch.setattr(runtime, "_initialize_named_procedures", _noop_async)
    monkeypatch.setattr(runtime, "_setup_agents", _noop_async)
    monkeypatch.setattr(runtime, "_setup_models", _noop_async)
    monkeypatch.setattr(runtime, "_inject_primitives", lambda: None)
    monkeypatch.setattr(runtime, "_execute_workflow", lambda: {})

    result = await runtime.execute("return {}", context=None, format="lua")

    assert result["success"] is True


@pytest.mark.asyncio
async def test_execute_config_error_flushes_and_logs(monkeypatch, tmp_path):
    class FailingChatRecorder(DummyChatRecorder):
        async def end_session(self, session_id, status=None):
            raise RuntimeError("end failed")

    runtime = runtime_module.TactusRuntime(
        procedure_id="proc",
        storage_backend=None,
        hitl_handler=object(),
        chat_recorder=FailingChatRecorder(),
        log_handler=DummyLogHandler(),
        source_file_path=str(tmp_path / "workflow.tac"),
    )
    runtime.toolset_primitive = None

    monkeypatch.setattr(runtime_module, "LuaSandbox", DummyLuaSandbox)
    monkeypatch.setattr(runtime_module, "BaseExecutionContext", DummyExecutionContext)
    monkeypatch.setattr(
        runtime,
        "_parse_declarations",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(runtime_module.ProcedureConfigError("bad")),
    )

    result = await runtime.execute("return {}", context=None, format="lua")

    assert result["success"] is False


@pytest.mark.asyncio
async def test_execute_config_error_after_session(monkeypatch, tmp_path):
    class FailingChatRecorder(DummyChatRecorder):
        async def end_session(self, session_id, status=None):
            raise RuntimeError("end failed")

    runtime = runtime_module.TactusRuntime(
        procedure_id="proc",
        storage_backend=None,
        hitl_handler=object(),
        chat_recorder=FailingChatRecorder(),
        log_handler=DummyLogHandler(),
        source_file_path=str(tmp_path / "workflow.tac"),
    )
    runtime.toolset_primitive = None

    monkeypatch.setattr(runtime_module, "LuaSandbox", DummyLuaSandbox)
    monkeypatch.setattr(runtime_module, "BaseExecutionContext", DummyExecutionContext)
    monkeypatch.setattr(runtime, "_parse_declarations", lambda *_args, **_kwargs: DummyRegistry())
    monkeypatch.setattr(runtime, "_registry_to_config", lambda _registry: {"output": {}})
    monkeypatch.setattr(runtime, "_initialize_primitives", _noop_async)
    monkeypatch.setattr(runtime, "_initialize_toolsets", _noop_async)
    monkeypatch.setattr(runtime, "_initialize_named_procedures", _noop_async)
    monkeypatch.setattr(runtime, "_setup_agents", _noop_async)
    monkeypatch.setattr(runtime, "_setup_models", _noop_async)
    monkeypatch.setattr(runtime, "_inject_primitives", lambda: None)
    monkeypatch.setattr(
        runtime,
        "_execute_workflow",
        lambda: (_ for _ in ()).throw(runtime_module.ProcedureConfigError("bad")),
    )

    result = await runtime.execute("return {}", context=None, format="lua")

    assert result["success"] is False


@pytest.mark.asyncio
async def test_execute_lua_error_flushes_and_logs(monkeypatch, tmp_path):
    class FailingChatRecorder(DummyChatRecorder):
        async def end_session(self, session_id, status=None):
            raise RuntimeError("end failed")

    runtime = runtime_module.TactusRuntime(
        procedure_id="proc",
        storage_backend=None,
        hitl_handler=object(),
        chat_recorder=FailingChatRecorder(),
        log_handler=DummyLogHandler(),
        source_file_path=str(tmp_path / "workflow.tac"),
    )

    monkeypatch.setattr(runtime_module, "LuaSandbox", DummyLuaSandbox)
    monkeypatch.setattr(runtime_module, "BaseExecutionContext", DummyExecutionContext)
    monkeypatch.setattr(runtime, "_parse_declarations", lambda *_args, **_kwargs: DummyRegistry())
    monkeypatch.setattr(
        runtime, "_registry_to_config", lambda _registry: {"output": {}, "error_prompt": "oops"}
    )
    monkeypatch.setattr(runtime, "_initialize_primitives", _noop_async)
    monkeypatch.setattr(runtime, "_initialize_toolsets", _noop_async)
    monkeypatch.setattr(runtime, "_initialize_named_procedures", _noop_async)
    monkeypatch.setattr(runtime, "_setup_agents", _noop_async)
    monkeypatch.setattr(runtime, "_setup_models", _noop_async)
    monkeypatch.setattr(runtime, "_inject_primitives", lambda: None)
    monkeypatch.setattr(
        runtime,
        "_execute_workflow",
        lambda: (_ for _ in ()).throw(runtime_module.LuaSandboxError("fail")),
    )

    result = await runtime.execute("return {}", context=None, format="lua")

    assert result["success"] is False


@pytest.mark.asyncio
async def test_execute_unexpected_error_with_prompt(monkeypatch, tmp_path):
    class FailingChatRecorder(DummyChatRecorder):
        async def end_session(self, session_id, status=None):
            raise RuntimeError("end failed")

    runtime = runtime_module.TactusRuntime(
        procedure_id="proc",
        storage_backend=None,
        hitl_handler=object(),
        chat_recorder=FailingChatRecorder(),
        log_handler=DummyLogHandler(),
        source_file_path=str(tmp_path / "workflow.tac"),
    )

    monkeypatch.setattr(runtime_module, "LuaSandbox", DummyLuaSandbox)
    monkeypatch.setattr(runtime_module, "BaseExecutionContext", DummyExecutionContext)
    monkeypatch.setattr(runtime, "_parse_declarations", lambda *_args, **_kwargs: DummyRegistry())
    monkeypatch.setattr(
        runtime, "_registry_to_config", lambda _registry: {"output": {}, "error_prompt": "oops"}
    )
    monkeypatch.setattr(runtime, "_initialize_primitives", _noop_async)
    monkeypatch.setattr(runtime, "_initialize_toolsets", _noop_async)
    monkeypatch.setattr(runtime, "_initialize_named_procedures", _noop_async)
    monkeypatch.setattr(runtime, "_setup_agents", _noop_async)
    monkeypatch.setattr(runtime, "_setup_models", _noop_async)
    monkeypatch.setattr(runtime, "_inject_primitives", lambda: None)
    monkeypatch.setattr(
        runtime, "_execute_workflow", lambda: (_ for _ in ()).throw(RuntimeError("boom"))
    )

    result = await runtime.execute("return {}", context=None, format="lua")

    assert result["success"] is False


@pytest.mark.asyncio
async def test_execute_cleanup_handles_errors(monkeypatch, tmp_path):
    runtime = runtime_module.TactusRuntime(
        procedure_id="proc",
        storage_backend=None,
        hitl_handler=object(),
        source_file_path=str(tmp_path / "workflow.tac"),
    )
    runtime.toolset_primitive = None

    class FailingMCP:
        async def __aexit__(self, exc_type, exc, tb):
            raise RuntimeError("mcp")

    class FailingDeps:
        async def cleanup(self):
            raise RuntimeError("deps")

    runtime.mcp_manager = FailingMCP()
    runtime.dependency_manager = FailingDeps()

    monkeypatch.setattr(runtime_module, "LuaSandbox", DummyLuaSandbox)
    monkeypatch.setattr(runtime_module, "BaseExecutionContext", DummyExecutionContext)
    monkeypatch.setattr(runtime, "_parse_declarations", lambda *_args, **_kwargs: DummyRegistry())
    monkeypatch.setattr(runtime, "_registry_to_config", lambda _registry: {"output": {}})
    monkeypatch.setattr(runtime, "_initialize_primitives", _noop_async)
    monkeypatch.setattr(runtime, "_initialize_toolsets", _noop_async)
    monkeypatch.setattr(runtime, "_initialize_named_procedures", _noop_async)
    monkeypatch.setattr(runtime, "_setup_agents", _noop_async)
    monkeypatch.setattr(runtime, "_setup_models", _noop_async)
    monkeypatch.setattr(runtime, "_inject_primitives", lambda: None)
    monkeypatch.setattr(runtime, "_execute_workflow", lambda: {})

    result = await runtime.execute("return {}", context=None, format="lua")

    assert result["success"] is True


@pytest.mark.asyncio
async def test_execute_cleanup_success(monkeypatch, tmp_path):
    runtime = runtime_module.TactusRuntime(
        procedure_id="proc",
        storage_backend=None,
        hitl_handler=object(),
        source_file_path=str(tmp_path / "workflow.tac"),
    )
    runtime.toolset_primitive = None

    class OkDeps:
        async def cleanup(self):
            return None

    runtime.dependency_manager = OkDeps()

    monkeypatch.setattr(runtime_module, "LuaSandbox", DummyLuaSandbox)
    monkeypatch.setattr(runtime_module, "BaseExecutionContext", DummyExecutionContext)
    monkeypatch.setattr(runtime, "_parse_declarations", lambda *_args, **_kwargs: DummyRegistry())
    monkeypatch.setattr(runtime, "_registry_to_config", lambda _registry: {"output": {}})
    monkeypatch.setattr(runtime, "_initialize_primitives", _noop_async)
    monkeypatch.setattr(runtime, "_initialize_toolsets", _noop_async)
    monkeypatch.setattr(runtime, "_initialize_named_procedures", _noop_async)
    monkeypatch.setattr(runtime, "_setup_agents", _noop_async)
    monkeypatch.setattr(runtime, "_setup_models", _noop_async)
    monkeypatch.setattr(runtime, "_inject_primitives", lambda: None)
    monkeypatch.setattr(runtime, "_execute_workflow", lambda: {})

    result = await runtime.execute("return {}", context=None, format="lua")

    assert result["success"] is True


@pytest.mark.asyncio
async def test_execute_yaml_without_parser(monkeypatch, tmp_path):
    class DummyStorage:
        def load_procedure_metadata(self, _procedure_id):
            return {}

    runtime = runtime_module.TactusRuntime(
        procedure_id="proc",
        storage_backend=DummyStorage(),
        hitl_handler=object(),
        source_file_path=str(tmp_path / "workflow.tac"),
    )

    monkeypatch.setattr(runtime_module, "ProcedureYAMLParser", None)
    monkeypatch.setattr(runtime_module, "LuaSandbox", DummyLuaSandbox)
    monkeypatch.setattr(runtime_module, "BaseExecutionContext", DummyExecutionContext)

    result = await runtime.execute("name: test", context=None, format="yaml")

    assert result["success"] is False
    assert "YAML support not available" in result["error"]
