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


@pytest.mark.parametrize(
    "kwargs,error_match",
    [
        ({"reasoning_effort": "invalid"}, "reasoning_effort"),
        ({"verbosity": "invalid"}, "verbosity"),
        ({"max_tokens": 0}, "max_tokens"),
        ({"temperature": 3}, "temperature"),
    ],
)
def test_runtime_rejects_invalid_gpt5_controls(kwargs, error_match):
    with pytest.raises(ValueError, match=error_match):
        runtime_module.TactusRuntime(procedure_id="proc", hitl_handler=object(), **kwargs)


@pytest.mark.asyncio
async def test_setup_agents_accepts_v1_agent_config_and_model_settings(monkeypatch):
    runtime = runtime_module.TactusRuntime(
        procedure_id="proc",
        hitl_handler=object(),
        reasoning_effort="minimal",
        verbosity="high",
        max_tokens=900,
        temperature=0.2,
    )
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
    assert captured["config"]["model"] == "openai/gpt-4o"
    assert captured["config"]["temperature"] == 0.5
    assert captured["config"]["max_tokens"] == 900
    assert captured["config"]["reasoning_effort"] == "minimal"
    assert captured["config"]["verbosity"] == "high"


@pytest.mark.asyncio
async def test_setup_agents_model_settings_override_runtime_gpt5_controls(monkeypatch):
    runtime = runtime_module.TactusRuntime(
        procedure_id="proc",
        hitl_handler=object(),
        reasoning_effort="low",
        verbosity="medium",
        max_tokens=900,
        temperature=0.2,
    )
    runtime.lua_sandbox = DummyLuaSandbox()
    runtime.toolset_registry = {}
    runtime.config = {}
    runtime.registry = SimpleNamespace(agents={})
    runtime.agents = {}

    captured = {}

    def _create_agent(_name, config, **_kwargs):
        captured["config"] = config
        return SimpleNamespace()

    runtime.registry.agents = {
        "agent": {
            "system_prompt": "system",
            "provider": "openai",
            "model": {
                "name": "gpt-5-mini",
                "reasoning_effort": "xhigh",
                "verbosity": "low",
                "max_tokens": 1200,
                "temperature": 0.0,
            },
        }
    }

    async def _noop_dependencies():
        return None

    monkeypatch.setattr(runtime, "_initialize_dependencies", _noop_dependencies)
    monkeypatch.setattr("tactus.dspy.agent.create_dspy_agent", _create_agent)

    await runtime._setup_agents(context={})

    assert captured["config"]["reasoning_effort"] == "xhigh"
    assert captured["config"]["verbosity"] == "low"
    assert captured["config"]["max_tokens"] == 1200
    assert captured["config"]["temperature"] == 0.0


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
async def test_setup_agents_infers_provider_prefix_from_model_colon(monkeypatch):
    runtime = runtime_module.TactusRuntime(procedure_id="proc", hitl_handler=object())
    runtime.lua_sandbox = DummyLuaSandbox()
    runtime.toolset_registry = {}
    runtime.config = {}
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

    assert captured["model"] == "openai/gpt-4o-mini"


@pytest.mark.asyncio
async def test_setup_agents_infers_provider_prefix_from_model_slash(monkeypatch):
    runtime = runtime_module.TactusRuntime(procedure_id="proc", hitl_handler=object())
    runtime.lua_sandbox = DummyLuaSandbox()
    runtime.toolset_registry = {}
    runtime.config = {}
    runtime.registry = SimpleNamespace(
        agents={
            "agent": {
                "system_prompt": "system",
                "model": "openai/gpt-4o-mini",
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

    assert captured["model"] == "openai/gpt-4o-mini"


@pytest.mark.asyncio
async def test_setup_agents_requires_provider_when_model_has_no_prefix(monkeypatch):
    runtime = runtime_module.TactusRuntime(procedure_id="proc", hitl_handler=object())
    runtime.lua_sandbox = DummyLuaSandbox()
    runtime.toolset_registry = {}
    runtime.config = {}
    runtime.registry = SimpleNamespace(
        agents={
            "agent": {
                "system_prompt": "system",
                "model": "gpt-4o-mini",
            }
        }
    )
    runtime.agents = {}

    async def _noop_dependencies():
        return None

    monkeypatch.setattr(runtime, "_initialize_dependencies", _noop_dependencies)

    with pytest.raises(ValueError, match="must specify a 'provider'"):
        await runtime._setup_agents(context={})


@pytest.mark.asyncio
async def test_setup_agents_infers_provider_prefix_for_bedrock_model(monkeypatch):
    runtime = runtime_module.TactusRuntime(procedure_id="proc", hitl_handler=object())
    runtime.lua_sandbox = DummyLuaSandbox()
    runtime.toolset_registry = {}
    runtime.config = {}
    runtime.registry = SimpleNamespace(
        agents={
            "agent": {
                "system_prompt": "system",
                "model": "bedrock/us.anthropic.claude-haiku-4-5-20251001-v1:0",
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

    assert captured["model"] == "bedrock/us.anthropic.claude-haiku-4-5-20251001-v1:0"


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

    assert captured["model"] == "openai/gpt-4o"


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
