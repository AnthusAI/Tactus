from tactus.core import runtime as runtime_module
from tactus.primitives.handles import AgentHandle, ModelHandle


class DummyLua:
    def globals(self):
        return {}


class DummyLuaSandbox:
    def __init__(self):
        self.lua = DummyLua()


def test_enhance_handles_no_registry():
    runtime = runtime_module.TactusRuntime(procedure_id="proc", hitl_handler=object())
    runtime._enhance_handles()


def test_enhance_handles_agent_and_model():
    runtime = runtime_module.TactusRuntime(procedure_id="proc", hitl_handler=object())
    runtime.lua_sandbox = DummyLuaSandbox()
    runtime.execution_context = object()

    agent_handle = AgentHandle("agent")
    model_handle = ModelHandle("model")

    runtime._dsl_registries = {"agent": {"agent": agent_handle}, "model": {"model": model_handle}}
    runtime.agents = {"agent": object()}
    runtime.models = {"model": object()}

    runtime._enhance_handles()

    assert agent_handle._primitive is runtime.agents["agent"]
    assert agent_handle._execution_context is runtime.execution_context
    assert model_handle._primitive is runtime.models["model"]


def test_enhance_handles_updates_execution_context():
    runtime = runtime_module.TactusRuntime(procedure_id="proc", hitl_handler=object())
    runtime.lua_sandbox = DummyLuaSandbox()
    runtime.execution_context = object()

    agent_handle = AgentHandle("agent")
    agent_handle._primitive = object()
    agent_handle._execution_context = None

    runtime._dsl_registries = {"agent": {"agent": agent_handle}, "model": {}}
    runtime.agents = {"agent": agent_handle._primitive}

    runtime._enhance_handles()

    assert agent_handle._execution_context is runtime.execution_context


def test_enhance_handles_non_handle_entries():
    runtime = runtime_module.TactusRuntime(procedure_id="proc", hitl_handler=object())
    runtime.lua_sandbox = DummyLuaSandbox()

    runtime._dsl_registries = {"agent": {"agent": "not-handle"}, "model": {"model": "bad"}}
    runtime.agents = {"agent": object()}
    runtime.models = {"model": object()}

    runtime._enhance_handles()


def test_enhance_handles_model_already_connected():
    runtime = runtime_module.TactusRuntime(procedure_id="proc", hitl_handler=object())
    runtime.lua_sandbox = DummyLuaSandbox()

    model_handle = ModelHandle("model")
    model_handle._primitive = object()

    runtime._dsl_registries = {"agent": {}, "model": {"model": model_handle}}
    runtime.models = {"model": model_handle._primitive}

    runtime._enhance_handles()


def test_enhance_handles_missing_registry_entries():
    runtime = runtime_module.TactusRuntime(procedure_id="proc", hitl_handler=object())
    runtime.lua_sandbox = DummyLuaSandbox()

    runtime._dsl_registries = {"agent": {}, "model": {}}
    runtime.agents = {"agent": object()}
    runtime.models = {"model": object()}

    runtime._enhance_handles()
