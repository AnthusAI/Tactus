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


class V1AgentConfig:
    def __init__(self, data):
        self._data = data

    def dict(self):
        return dict(self._data)


@pytest.mark.asyncio
async def test_setup_agents_accepts_v1_agent_config_and_model_settings(monkeypatch):
    runtime = runtime_module.TactusRuntime(procedure_id="proc", hitl_handler=object())
    runtime.lua_sandbox = DummyLuaSandbox()
    runtime.toolset_registry = {}
    runtime.config = {}
    runtime.registry = SimpleNamespace(agents={})
    runtime.agents = {}

    captured = {}

    def _create_agent(name, config, **_kwargs):
        captured["name"] = name
        captured["config"] = config
        return SimpleNamespace()

    agent_config = V1AgentConfig(
        {
            "system_prompt": "system",
            "provider": "openai",
            "model": {"name": "gpt-4o", "temperature": 0.5},
        }
    )
    runtime.registry.agents = {"agent": agent_config}

    async def _noop_dependencies():
        return None

    monkeypatch.setattr(runtime, "_initialize_dependencies", _noop_dependencies)
    monkeypatch.setattr("tactus.dspy.agent.create_dspy_agent", _create_agent)

    await runtime._setup_agents(context={})

    assert captured["name"] == "agent"
    assert captured["config"]["model"] == "openai:gpt-4o"
    assert captured["config"]["temperature"] == 0.5


@pytest.mark.asyncio
async def test_setup_agents_requires_provider(monkeypatch):
    runtime = runtime_module.TactusRuntime(procedure_id="proc", hitl_handler=object())
    runtime.lua_sandbox = DummyLuaSandbox()
    runtime.toolset_registry = {}
    runtime.config = {}
    runtime.registry = SimpleNamespace(agents={"agent": {"system_prompt": "system"}})
    runtime.agents = {}

    async def _noop_dependencies():
        return None

    monkeypatch.setattr(runtime, "_initialize_dependencies", _noop_dependencies)

    with pytest.raises(ValueError, match="must specify a 'provider'"):
        await runtime._setup_agents(context={})


@pytest.mark.asyncio
async def test_setup_agents_provider_prefix_from_model(monkeypatch):
    runtime = runtime_module.TactusRuntime(procedure_id="proc", hitl_handler=object())
    runtime.lua_sandbox = DummyLuaSandbox()
    runtime.toolset_registry = {}

    class FlakyConfig:
        def __init__(self):
            self.calls = 0

        def get(self, key, default=None):
            if key == "default_provider":
                self.calls += 1
                return "openai" if self.calls == 1 else None
            return default

    runtime.config = FlakyConfig()
    runtime.registry = SimpleNamespace(
        agents={
            "agent": {
                "system_prompt": "system",
                "model": "openai:gpt-4o-mini",
            }
        }
    )
    runtime.agents = {}

    captured = {}

    def _create_agent(name, config, **_kwargs):
        captured["model"] = config["model"]
        return SimpleNamespace()

    async def _noop_dependencies():
        return None

    monkeypatch.setattr(runtime, "_initialize_dependencies", _noop_dependencies)
    monkeypatch.setattr("tactus.dspy.agent.create_dspy_agent", _create_agent)

    await runtime._setup_agents(context={})

    assert captured["model"] == "openai:gpt-4o-mini"


@pytest.mark.asyncio
async def test_setup_agents_skips_existing(monkeypatch):
    runtime = runtime_module.TactusRuntime(procedure_id="proc", hitl_handler=object())
    runtime.lua_sandbox = DummyLuaSandbox()
    runtime.toolset_registry = {}
    runtime.config = {}
    runtime.registry = SimpleNamespace(
        agents={
            "agent": {
                "system_prompt": "system",
                "provider": "openai",
                "model": "gpt-4o",
            }
        }
    )
    runtime.agents = {"agent": SimpleNamespace()}

    async def _noop_dependencies():
        return None

    monkeypatch.setattr(runtime, "_initialize_dependencies", _noop_dependencies)
    monkeypatch.setattr(
        "tactus.dspy.agent.create_dspy_agent",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("should not create")),
    )

    await runtime._setup_agents(context={})


@pytest.mark.asyncio
async def test_setup_agents_model_settings_empty(monkeypatch):
    runtime = runtime_module.TactusRuntime(procedure_id="proc", hitl_handler=object())
    runtime.lua_sandbox = DummyLuaSandbox()
    runtime.toolset_registry = {}
    runtime.config = {}
    runtime.registry = SimpleNamespace(
        agents={
            "agent": {
                "system_prompt": "system",
                "provider": "openai",
                "model": {"name": "gpt-4o"},
            }
        }
    )
    runtime.agents = {}

    async def _noop_dependencies():
        return None

    captured = {}

    def _create_agent(name, config, **_kwargs):
        captured["model"] = config["model"]
        return SimpleNamespace()

    monkeypatch.setattr(runtime, "_initialize_dependencies", _noop_dependencies)
    monkeypatch.setattr("tactus.dspy.agent.create_dspy_agent", _create_agent)

    await runtime._setup_agents(context={})

    assert captured["model"] == "openai:gpt-4o"


@pytest.mark.asyncio
async def test_setup_agents_inline_tools_import_error(monkeypatch):
    runtime = runtime_module.TactusRuntime(procedure_id="proc", hitl_handler=object())
    runtime.lua_sandbox = DummyLuaSandbox()
    runtime.toolset_registry = {}
    runtime.config = {}
    runtime.registry = SimpleNamespace(
        agents={
            "agent": {
                "system_prompt": "system",
                "provider": "openai",
                "model": "gpt-4o",
                "inline_tools": [{"handler": "noop"}],
            }
        }
    )
    runtime.agents = {}

    async def _noop_dependencies():
        return None

    monkeypatch.setattr(runtime, "_initialize_dependencies", _noop_dependencies)

    created = {}

    def _create_agent(name, config, **_kwargs):
        created["toolsets"] = config["toolsets"]
        return SimpleNamespace()

    real_import = __import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "tactus.adapters.lua_tools":
            raise ImportError("missing")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr("builtins.__import__", fake_import)
    monkeypatch.setattr("tactus.dspy.agent.create_dspy_agent", _create_agent)

    await runtime._setup_agents(context={})

    assert created["toolsets"] in (None, [])
