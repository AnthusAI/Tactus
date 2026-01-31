from types import SimpleNamespace

import pytest

from tactus.core import runtime as runtime_module


class DummyLuaGlobals:
    def __init__(self):
        self._globals = {}

    def __call__(self):
        return self._globals


class DummyLuaSandbox:
    def __init__(self):
        self.lua = SimpleNamespace(globals=DummyLuaGlobals())


@pytest.mark.asyncio
async def test_setup_agents_inline_tools_and_default_toolsets(monkeypatch):
    runtime = runtime_module.TactusRuntime(procedure_id="proc", hitl_handler=object())
    runtime.lua_sandbox = DummyLuaSandbox()
    runtime.toolset_registry = {"default": "default_toolset"}
    runtime.config = {"default_toolsets": ["default"]}
    runtime.registry = SimpleNamespace(
        agents={
            "agent": {
                "system_prompt": "sys",
                "provider": "openai",
                "model": "gpt-4o",
                "inline_tools": [{"handler": "noop"}],
            }
        }
    )
    runtime.agents = {}

    async def _noop_dependencies():
        return None

    runtime._parse_toolset_expressions = lambda _expr: ["default_toolset"]
    monkeypatch.setattr(runtime, "_initialize_dependencies", _noop_dependencies)

    class FakeLuaAdapter:
        def __init__(self, tool_primitive=None, mock_manager=None):
            self.tool_primitive = tool_primitive
            self.mock_manager = mock_manager

        def create_inline_tools_toolset(self, _agent_name, _specs):
            return "inline_toolset"

    captured = {}

    def fake_agent(name, config, **_kwargs):
        captured["toolsets"] = config["toolsets"]
        return SimpleNamespace()

    monkeypatch.setattr("tactus.adapters.lua_tools.LuaToolsAdapter", FakeLuaAdapter)
    monkeypatch.setattr("tactus.dspy.agent.create_dspy_agent", fake_agent)

    await runtime._setup_agents(context={})

    assert captured["toolsets"] == ["default_toolset", "inline_toolset"]


@pytest.mark.asyncio
async def test_setup_agents_tools_empty_list_disables_toolsets(monkeypatch):
    runtime = runtime_module.TactusRuntime(procedure_id="proc", hitl_handler=object())
    runtime.lua_sandbox = DummyLuaSandbox()
    runtime.toolset_registry = {"default": "default_toolset"}
    runtime.config = {}
    runtime.registry = SimpleNamespace(
        agents={
            "agent": {
                "system_prompt": "sys",
                "provider": "openai",
                "model": "gpt-4o",
                "tools": [],
            }
        }
    )
    runtime.agents = {}

    async def _noop_dependencies():
        return None

    monkeypatch.setattr(runtime, "_initialize_dependencies", _noop_dependencies)

    captured = {}

    def fake_agent(name, config, **_kwargs):
        captured["toolsets"] = config["toolsets"]
        return SimpleNamespace()

    monkeypatch.setattr("tactus.dspy.agent.create_dspy_agent", fake_agent)

    await runtime._setup_agents(context={})

    assert captured["toolsets"] is None


@pytest.mark.asyncio
async def test_setup_agents_output_schema_paths(monkeypatch):
    runtime = runtime_module.TactusRuntime(procedure_id="proc", hitl_handler=object())
    runtime.lua_sandbox = DummyLuaSandbox()
    runtime.toolset_registry = {}
    runtime.config = {"output": {"field": {"type": "string"}}}
    runtime.registry = SimpleNamespace(
        agents={
            "agent": {
                "system_prompt": "sys",
                "provider": "openai",
                "model": "gpt-4o",
                "output": {"field": {"type": "string"}},
            }
        }
    )
    runtime.agents = {}

    async def _noop_dependencies():
        return None

    monkeypatch.setattr(runtime, "_initialize_dependencies", _noop_dependencies)

    calls = {"pydantic": 0, "schema": 0}

    def fake_pydantic(_schema, _name):
        calls["pydantic"] += 1

    def fake_schema(_schema, _name):
        calls["schema"] += 1

    def fake_agent(name, config, **_kwargs):
        return SimpleNamespace()

    monkeypatch.setattr(runtime, "_create_pydantic_model_from_output", fake_pydantic)
    monkeypatch.setattr(runtime, "_create_output_model_from_schema", fake_schema)
    monkeypatch.setattr("tactus.dspy.agent.create_dspy_agent", fake_agent)

    await runtime._setup_agents(context={})


@pytest.mark.asyncio
async def test_setup_agents_message_history_filter(monkeypatch):
    runtime = runtime_module.TactusRuntime(procedure_id="proc", hitl_handler=object())
    runtime.lua_sandbox = DummyLuaSandbox()
    runtime.toolset_registry = {}
    runtime.config = {}
    runtime.registry = SimpleNamespace(
        agents={
            "agent": {
                "system_prompt": "sys",
                "provider": "openai",
                "model": "gpt-4o",
                "message_history": {"filter": "recent"},
            }
        }
    )
    runtime.agents = {}

    async def _noop_dependencies():
        return None

    captured = {}

    def fake_agent(name, config, **_kwargs):
        captured["model"] = config["model"]
        return SimpleNamespace()

    monkeypatch.setattr(runtime, "_initialize_dependencies", _noop_dependencies)
    monkeypatch.setattr("tactus.dspy.agent.create_dspy_agent", fake_agent)

    await runtime._setup_agents(context={})

    assert captured["model"] == "openai:gpt-4o"


@pytest.mark.asyncio
async def test_setup_agents_message_history_without_filter(monkeypatch):
    runtime = runtime_module.TactusRuntime(procedure_id="proc", hitl_handler=object())
    runtime.lua_sandbox = DummyLuaSandbox()
    runtime.toolset_registry = {}
    runtime.config = {}
    runtime.registry = SimpleNamespace(
        agents={
            "agent": {
                "system_prompt": "sys",
                "provider": "openai",
                "model": "gpt-4o",
                "message_history": {"limit": 5},
            }
        }
    )
    runtime.agents = {}

    async def _noop_dependencies():
        return None

    captured = {}

    def fake_agent(name, config, **_kwargs):
        captured["model"] = config["model"]
        return SimpleNamespace()

    monkeypatch.setattr(runtime, "_initialize_dependencies", _noop_dependencies)
    monkeypatch.setattr("tactus.dspy.agent.create_dspy_agent", fake_agent)

    await runtime._setup_agents(context={})

    assert captured["model"] == "openai:gpt-4o"


@pytest.mark.asyncio
async def test_setup_agents_procedure_output_schema_error(monkeypatch):
    runtime = runtime_module.TactusRuntime(procedure_id="proc", hitl_handler=object())
    runtime.lua_sandbox = DummyLuaSandbox()
    runtime.toolset_registry = {}
    runtime.config = {"output": {"field": {"type": "string"}}}
    runtime.registry = SimpleNamespace(
        agents={
            "agent": {
                "system_prompt": "sys",
                "provider": "openai",
                "model": "gpt-4o",
            }
        }
    )
    runtime.agents = {}

    async def _noop_dependencies():
        return None

    monkeypatch.setattr(runtime, "_initialize_dependencies", _noop_dependencies)
    monkeypatch.setattr(
        runtime,
        "_create_output_model_from_schema",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError("boom")),
    )

    created = {}

    def fake_agent(name, config, **_kwargs):
        created["name"] = name
        return SimpleNamespace()

    monkeypatch.setattr("tactus.dspy.agent.create_dspy_agent", fake_agent)

    await runtime._setup_agents(context={})

    assert created["name"] == "agent"


@pytest.mark.asyncio
async def test_setup_agents_inline_tools_with_no_toolsets(monkeypatch):
    runtime = runtime_module.TactusRuntime(procedure_id="proc", hitl_handler=object())
    runtime.lua_sandbox = DummyLuaSandbox()
    runtime.toolset_registry = {}
    runtime.config = {}
    runtime.registry = SimpleNamespace(
        agents={
            "agent": {
                "system_prompt": "sys",
                "provider": "openai",
                "model": "gpt-4o",
                "tools": [],
                "inline_tools": [{"handler": "noop"}],
            }
        }
    )
    runtime.agents = {}

    async def _noop_dependencies():
        return None

    monkeypatch.setattr(runtime, "_initialize_dependencies", _noop_dependencies)

    class FakeLuaAdapter:
        def __init__(self, tool_primitive=None, mock_manager=None):
            self.tool_primitive = tool_primitive
            self.mock_manager = mock_manager

        def create_inline_tools_toolset(self, _agent_name, _specs):
            return "inline_toolset"

    captured = {}

    def fake_agent(name, config, **_kwargs):
        captured["toolsets"] = config["toolsets"]
        return SimpleNamespace()

    monkeypatch.setattr("tactus.adapters.lua_tools.LuaToolsAdapter", FakeLuaAdapter)
    monkeypatch.setattr("tactus.dspy.agent.create_dspy_agent", fake_agent)

    await runtime._setup_agents(context={})

    assert captured["toolsets"] == ["inline_toolset"]


@pytest.mark.asyncio
async def test_setup_agents_output_model_creation_failure(monkeypatch):
    runtime = runtime_module.TactusRuntime(procedure_id="proc", hitl_handler=object())
    runtime.lua_sandbox = DummyLuaSandbox()
    runtime.toolset_registry = {}
    runtime.config = {}
    runtime.registry = SimpleNamespace(
        agents={
            "agent": {
                "system_prompt": "sys",
                "provider": "openai",
                "model": "gpt-4o",
                "output": {"field": {"type": "string"}},
            }
        }
    )
    runtime.agents = {}

    async def _noop_dependencies():
        return None

    monkeypatch.setattr(runtime, "_initialize_dependencies", _noop_dependencies)

    def fake_pydantic(_schema, _name):
        raise RuntimeError("boom")

    def fake_agent(name, config, **_kwargs):
        return SimpleNamespace()

    monkeypatch.setattr(runtime, "_create_pydantic_model_from_output", fake_pydantic)
    monkeypatch.setattr("tactus.dspy.agent.create_dspy_agent", fake_agent)

    await runtime._setup_agents(context={})


@pytest.mark.asyncio
async def test_setup_agents_output_schema_creation_failure(monkeypatch):
    runtime = runtime_module.TactusRuntime(procedure_id="proc", hitl_handler=object())
    runtime.lua_sandbox = DummyLuaSandbox()
    runtime.toolset_registry = {}
    runtime.config = {}
    runtime.registry = SimpleNamespace(
        agents={
            "agent": {
                "system_prompt": "sys",
                "provider": "openai",
                "model": "gpt-4o",
                "output_schema": {"field": {"type": "string"}},
            }
        }
    )
    runtime.agents = {}

    async def _noop_dependencies():
        return None

    monkeypatch.setattr(runtime, "_initialize_dependencies", _noop_dependencies)

    def fake_schema(_schema, _name):
        raise RuntimeError("boom")

    def fake_agent(name, config, **_kwargs):
        return SimpleNamespace()

    monkeypatch.setattr(runtime, "_create_output_model_from_schema", fake_schema)
    monkeypatch.setattr("tactus.dspy.agent.create_dspy_agent", fake_agent)

    await runtime._setup_agents(context={})


@pytest.mark.asyncio
async def test_setup_agents_ignores_scalar_procedure_output(monkeypatch):
    runtime = runtime_module.TactusRuntime(procedure_id="proc", hitl_handler=object())
    runtime.lua_sandbox = DummyLuaSandbox()
    runtime.toolset_registry = {}
    runtime.config = {"output": {"type": "string"}}
    runtime.registry = SimpleNamespace(
        agents={
            "agent": {
                "system_prompt": "sys",
                "provider": "openai",
                "model": "gpt-4o",
            }
        }
    )
    runtime.agents = {}

    async def _noop_dependencies():
        return None

    monkeypatch.setattr(runtime, "_initialize_dependencies", _noop_dependencies)

    def fake_schema(_schema, _name):
        raise RuntimeError("should not call")

    def fake_agent(name, config, **_kwargs):
        return SimpleNamespace()

    monkeypatch.setattr(runtime, "_create_output_model_from_schema", fake_schema)
    monkeypatch.setattr("tactus.dspy.agent.create_dspy_agent", fake_agent)

    await runtime._setup_agents(context={})


@pytest.mark.asyncio
async def test_setup_agents_output_schema_fallback(monkeypatch):
    runtime = runtime_module.TactusRuntime(procedure_id="proc", hitl_handler=object())
    runtime.lua_sandbox = DummyLuaSandbox()
    runtime.toolset_registry = {}
    runtime.config = {}
    runtime.registry = SimpleNamespace(
        agents={
            "agent": {
                "system_prompt": "sys",
                "provider": "openai",
                "model": "gpt-4o",
                "output_schema": {"field": {"type": "string"}},
            }
        }
    )
    runtime.agents = {}

    async def _noop_dependencies():
        return None

    monkeypatch.setattr(runtime, "_initialize_dependencies", _noop_dependencies)

    calls = {"schema": 0}

    def fake_schema(_schema, _name):
        calls["schema"] += 1

    def fake_agent(name, config, **_kwargs):
        return SimpleNamespace()

    monkeypatch.setattr(runtime, "_create_output_model_from_schema", fake_schema)
    monkeypatch.setattr("tactus.dspy.agent.create_dspy_agent", fake_agent)

    await runtime._setup_agents(context={})

    assert calls["schema"] == 1


@pytest.mark.asyncio
async def test_setup_agents_procedure_output_schema_fallback(monkeypatch):
    runtime = runtime_module.TactusRuntime(procedure_id="proc", hitl_handler=object())
    runtime.lua_sandbox = DummyLuaSandbox()
    runtime.toolset_registry = {}
    runtime.config = {"output": {"field": {"type": "string"}}}
    runtime.registry = SimpleNamespace(
        agents={
            "agent": {
                "system_prompt": "sys",
                "provider": "openai",
                "model": "gpt-4o",
            }
        }
    )
    runtime.agents = {}

    async def _noop_dependencies():
        return None

    monkeypatch.setattr(runtime, "_initialize_dependencies", _noop_dependencies)

    calls = {"schema": 0}

    def fake_schema(_schema, _name):
        calls["schema"] += 1

    def fake_agent(name, config, **_kwargs):
        return SimpleNamespace()

    monkeypatch.setattr(runtime, "_create_output_model_from_schema", fake_schema)
    monkeypatch.setattr("tactus.dspy.agent.create_dspy_agent", fake_agent)

    await runtime._setup_agents(context={})

    assert calls["schema"] == 1


@pytest.mark.asyncio
async def test_setup_agents_tools_conversion_failure(monkeypatch):
    runtime = runtime_module.TactusRuntime(procedure_id="proc", hitl_handler=object())
    runtime.lua_sandbox = DummyLuaSandbox()
    runtime.toolset_registry = {"default": "default_toolset"}
    runtime.config = {}

    class BadTools:
        def __len__(self):
            return 1

        def values(self):
            raise TypeError("bad")

        def __iter__(self):
            raise TypeError("bad")

    runtime.registry = SimpleNamespace(
        agents={
            "agent": {
                "system_prompt": "sys",
                "provider": "openai",
                "model": "gpt-4o",
                "tools": BadTools(),
            }
        }
    )
    runtime.agents = {}

    async def _noop_dependencies():
        return None

    monkeypatch.setattr(runtime, "_initialize_dependencies", _noop_dependencies)
    runtime._parse_toolset_expressions = lambda _expr: ["default_toolset"]

    def fake_agent(name, config, **_kwargs):
        return SimpleNamespace()

    monkeypatch.setattr("tactus.dspy.agent.create_dspy_agent", fake_agent)

    await runtime._setup_agents(context={})


@pytest.mark.asyncio
async def test_setup_agents_message_history_filter(monkeypatch):  # noqa: F811
    runtime = runtime_module.TactusRuntime(procedure_id="proc", hitl_handler=object())
    runtime.lua_sandbox = DummyLuaSandbox()
    runtime.toolset_registry = {}
    runtime.config = {}
    runtime.registry = SimpleNamespace(
        agents={
            "agent": {
                "system_prompt": "sys",
                "provider": "openai",
                "model": "gpt-4o",
                "message_history": {"filter": {"roles": ["user"]}},
            }
        }
    )
    runtime.agents = {}

    async def _noop_dependencies():
        return None

    monkeypatch.setattr(runtime, "_initialize_dependencies", _noop_dependencies)

    captured = {}

    def fake_agent(name, config, **_kwargs):
        captured["config"] = config
        return SimpleNamespace()

    monkeypatch.setattr("tactus.dspy.agent.create_dspy_agent", fake_agent)

    await runtime._setup_agents(context={})

    assert captured["config"]["model"] == "openai:gpt-4o"


@pytest.mark.asyncio
async def test_setup_agents_inline_tools_callable_entry(monkeypatch):
    runtime = runtime_module.TactusRuntime(procedure_id="proc", hitl_handler=object())
    runtime.lua_sandbox = DummyLuaSandbox()
    runtime.toolset_registry = {}
    runtime.config = {}
    runtime.registry = SimpleNamespace(
        agents={
            "agent": {
                "system_prompt": "sys",
                "provider": "openai",
                "model": "gpt-4o",
                "inline_tools": [{1: lambda: "ok"}],
            }
        }
    )
    runtime.agents = {}

    async def _noop_dependencies():
        return None

    monkeypatch.setattr(runtime, "_initialize_dependencies", _noop_dependencies)

    class FakeLuaAdapter:
        def __init__(self, tool_primitive=None, mock_manager=None):
            self.tool_primitive = tool_primitive
            self.mock_manager = mock_manager

        def create_inline_tools_toolset(self, _agent_name, _specs):
            return "inline_toolset"

    captured = {}

    def fake_agent(name, config, **_kwargs):
        captured["toolsets"] = config["toolsets"]
        return SimpleNamespace()

    monkeypatch.setattr("tactus.adapters.lua_tools.LuaToolsAdapter", FakeLuaAdapter)
    monkeypatch.setattr("tactus.dspy.agent.create_dspy_agent", fake_agent)

    await runtime._setup_agents(context={})

    assert captured["toolsets"] == ["inline_toolset"]


@pytest.mark.asyncio
async def test_setup_agents_inline_tools_without_handlers(monkeypatch):
    runtime = runtime_module.TactusRuntime(procedure_id="proc", hitl_handler=object())
    runtime.lua_sandbox = DummyLuaSandbox()
    runtime.toolset_registry = {}
    runtime.config = {}
    runtime.registry = SimpleNamespace(
        agents={
            "agent": {
                "system_prompt": "sys",
                "provider": "openai",
                "model": "gpt-4o",
                "inline_tools": [{"name": "noop"}],
            }
        }
    )
    runtime.agents = {}

    async def _noop_dependencies():
        return None

    monkeypatch.setattr(runtime, "_initialize_dependencies", _noop_dependencies)

    captured = {}

    def fake_agent(name, config, **_kwargs):
        captured["toolsets"] = config["toolsets"]
        return SimpleNamespace()

    monkeypatch.setattr("tactus.dspy.agent.create_dspy_agent", fake_agent)

    await runtime._setup_agents(context={})

    assert captured["toolsets"] == []


@pytest.mark.asyncio
async def test_setup_agents_inline_tools_non_list(monkeypatch):
    runtime = runtime_module.TactusRuntime(procedure_id="proc", hitl_handler=object())
    runtime.lua_sandbox = DummyLuaSandbox()
    runtime.toolset_registry = {}
    runtime.config = {}
    runtime.registry = SimpleNamespace(
        agents={
            "agent": {
                "system_prompt": "sys",
                "provider": "openai",
                "model": "gpt-4o",
                "inline_tools": {"name": "noop"},
            }
        }
    )
    runtime.agents = {}

    async def _noop_dependencies():
        return None

    monkeypatch.setattr(runtime, "_initialize_dependencies", _noop_dependencies)

    captured = {}

    def fake_agent(name, config, **_kwargs):
        captured["toolsets"] = config["toolsets"]
        return SimpleNamespace()

    monkeypatch.setattr("tactus.dspy.agent.create_dspy_agent", fake_agent)

    await runtime._setup_agents(context={})

    assert captured["toolsets"] == []
