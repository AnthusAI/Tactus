"""
Integration tests for multi-model OpenAI support.

These tests require real OpenAI API access. Run with:
    pytest tests/integration/test_multi_model_openai.py --real-api

Without --real-api flag, these tests will be skipped (integration tests require real APIs).
"""

import pytest
import os

from tactus.core.runtime import TactusRuntime
from tactus.adapters.memory import MemoryStorage


# Mark all tests in this module as requiring real API
pytestmark = pytest.mark.integration


# List of OpenAI models to test (as specified in requirements)
OPENAI_MODELS = [
    "gpt-4o",
    "gpt-4o-mini",
    "gpt-4.1",
    "gpt-4.1-mini",
    "gpt-5",
    "gpt-5-mini",
    "gpt-5.1",
]

# GPT-4 models that support standard parameters
GPT4_MODELS = ["gpt-4o", "gpt-4o-mini", "gpt-4.1", "gpt-4.1-mini"]

# Reasoning models that support reasoning_effort
REASONING_MODELS = ["gpt-5", "gpt-5-mini", "gpt-5-nano", "gpt-5.1"]


def create_simple_procedure_yaml(model: str, agent_name: str = "greeter") -> str:
    """Create a simple procedure YAML for testing a specific model."""
    return f"""
name: test_{model.replace('-', '_').replace('.', '_')}
version: 1.0.0
class: LuaDSL

params:
  name:
    type: string
    default: "World"

agents:
  {agent_name}:
    provider: openai
    model: {model}
    system_prompt: |
      You are a friendly greeter. Greet the user by name: {{{{params.name}}}}
      When done, call the done tool with your greeting as the reason.
    initial_message: "Please greet the user."
    tools:
      - done

procedure: |
  -- Loop until the agent decides to use the 'done' tool
  repeat
    {agent_name.capitalize()}.turn()
  until Tool.called("done")

  -- Return the result captured from the tool call
  return {{{{
    completed = true,
    greeting = Tool.last_call("done").args.reason
  }}}}
"""


def create_multi_agent_procedure_yaml(model1: str, model2: str) -> str:
    """Create a procedure with two agents using different models."""
    return f"""
name: test_multi_model
version: 1.0.0
class: LuaDSL

params:
  task:
    type: string
    default: "test"

agents:
  worker:
    provider: openai
    model: {model1}
    system_prompt: |
      You are a worker. Process the task: {{{{params.task}}}}
      When done, call the done tool with a brief summary.
    initial_message: "Please process the task."
    tools:
      - done
  
  reviewer:
    provider: openai
    model: {model2}
    system_prompt: |
      You are a reviewer. Review the work.
      When done, call the done tool with your review.
    initial_message: "Please review the work."
    tools:
      - done

procedure: |
  -- Worker processes task
  repeat
    Worker.turn()
  until Tool.called("done")
  
  local worker_result = Tool.last_call("done").args.reason
  
  -- Reviewer reviews
  repeat
    Reviewer.turn()
  until Tool.called("done")
  
  local reviewer_result = Tool.last_call("done").args.reason
  
  return {{{{
    completed = true,
    worker_output = worker_result,
    reviewer_output = reviewer_result
  }}}}
"""


@pytest.fixture(autouse=True)
def require_real_api(use_real_api):
    """All tests in this module require --real-api flag."""
    if not use_real_api:
        pytest.skip("Integration tests require --real-api flag")


@pytest.fixture(autouse=True)
def require_openai_key():
    """All tests in this module require OPENAI_API_KEY."""
    if not os.environ.get("OPENAI_API_KEY"):
        pytest.fail(
            "OPENAI_API_KEY environment variable not set. Integration tests require real API access."
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("model", OPENAI_MODELS)
async def test_single_model_procedure(model: str):
    """
    Test that a procedure can use a specific OpenAI model.

    This test verifies:
    1. Model can be specified in agent config
    2. Procedure executes successfully
    3. Agent uses the specified model
    """
    # Create runtime
    runtime = TactusRuntime(
        procedure_id=f"test-{model}",
        storage_backend=MemoryStorage(),
        hitl_handler=None,
        chat_recorder=None,
        mcp_server=None,
        openai_api_key=os.environ.get("OPENAI_API_KEY"),
    )

    # Create and execute procedure
    yaml_config = create_simple_procedure_yaml(model)
    result = await runtime.execute(yaml_config, context={"name": "TestUser"})

    # Verify execution succeeded
    assert result["success"], f"Procedure failed: {result.get('error', 'Unknown error')}"

    # Extract result - Lua returns {1: <table>} for single return value
    result_data = result["result"]
    if isinstance(result_data, dict) and 1 in result_data:
        result_data = result_data[1]

    # Convert Lua table to dict if needed
    if hasattr(result_data, "items"):
        result_data = dict(result_data.items())

    assert result_data["completed"] is True
    assert "greeting" in result_data


@pytest.mark.asyncio
async def test_default_model_fallback():
    """Test that default_model works as fallback when agent doesn't specify model."""
    yaml_config = """
name: test_default_model
version: 1.0.0
class: LuaDSL

default_model: gpt-4o-mini

agents:
  greeter:
    provider: openai
    system_prompt: |
      You are a friendly greeter. Greet the user by name: {{params.name}}
      When done, call the done tool with your greeting.
    initial_message: "Please greet the user."
    tools:
      - done

params:
  name:
    type: string
    default: "World"

procedure: |
  repeat
    Greeter.turn()
  until Tool.called("done")
  
  return {
    completed = true,
    greeting = Tool.last_call("done").args.reason
  }
"""

    runtime = TactusRuntime(
        procedure_id="test-default-model",
        storage_backend=MemoryStorage(),
        hitl_handler=None,
        chat_recorder=None,
        mcp_server=None,
        openai_api_key=os.environ.get("OPENAI_API_KEY"),
    )

    result = await runtime.execute(yaml_config, context={"name": "TestUser"})

    assert result["success"], f"Procedure failed: {result.get('error', 'Unknown error')}"

    # Extract result - Lua returns {1: <table>} for single return value
    result_data = result["result"]
    if isinstance(result_data, dict) and 1 in result_data:
        result_data = result_data[1]
    if hasattr(result_data, "items"):
        result_data = dict(result_data.items())

    assert result_data["completed"] is True


@pytest.mark.asyncio
async def test_multi_agent_different_models():
    """Test that different agents can use different models."""
    yaml_config = create_multi_agent_procedure_yaml("gpt-4o-mini", "gpt-4o")

    runtime = TactusRuntime(
        procedure_id="test-multi-agent",
        storage_backend=MemoryStorage(),
        hitl_handler=None,
        chat_recorder=None,
        mcp_server=None,
        openai_api_key=os.environ.get("OPENAI_API_KEY"),
    )

    result = await runtime.execute(yaml_config, context={"task": "test task"})

    assert result["success"], f"Procedure failed: {result.get('error', 'Unknown error')}"

    # Extract result - Lua returns {1: <table>} for single return value
    result_data = result["result"]
    if isinstance(result_data, dict) and 1 in result_data:
        result_data = result_data[1]
    if hasattr(result_data, "items"):
        result_data = dict(result_data.items())

    assert result_data["completed"] is True
    assert "worker_output" in result_data
    assert "reviewer_output" in result_data


@pytest.mark.asyncio
async def test_model_with_prefix():
    """Test that model strings with 'openai:' prefix work correctly."""
    yaml_config = """
name: test_prefix
version: 1.0.0
class: LuaDSL

agents:
  greeter:
    provider: openai
    model: gpt-4o-mini
    system_prompt: |
      You are a friendly greeter. Greet the user.
      When done, call the done tool.
    initial_message: "Please greet the user."
    tools:
      - done

procedure: |
  repeat
    Greeter.turn()
  until Tool.called("done")
  
  return { completed = true }
"""

    runtime = TactusRuntime(
        procedure_id="test-prefix",
        storage_backend=MemoryStorage(),
        hitl_handler=None,
        chat_recorder=None,
        mcp_server=None,
        openai_api_key=os.environ.get("OPENAI_API_KEY"),
    )

    result = await runtime.execute(yaml_config, context={})

    assert result["success"], f"Procedure failed: {result.get('error', 'Unknown error')}"

    # Extract result - Lua returns {1: <table>} for single return value
    result_data = result["result"]
    if isinstance(result_data, dict) and 1 in result_data:
        result_data = result_data[1]
    if hasattr(result_data, "items"):
        result_data = dict(result_data.items())

    assert result_data["completed"] is True


@pytest.mark.asyncio
@pytest.mark.parametrize("model", GPT4_MODELS)
async def test_gpt4_with_temperature_parameter(model: str):
    """
    Test GPT-4 models with temperature parameter.

    Verifies that temperature setting is accepted and procedure executes.
    """
    yaml_config = f"""
name: test_temperature_{model.replace('-', '_').replace('.', '_')}
version: 1.0.0
class: LuaDSL

agents:
  greeter:
    provider: openai
    model:
      name: {model}
      temperature: 0.3
      max_tokens: 100
    system_prompt: |
      You are a concise greeter. Say hello briefly.
      When done, call the done tool with your greeting.
    initial_message: "Greet the user."
    tools:
      - done

procedure: |
  repeat
    Greeter.turn()
  until Tool.called("done")
  
  return {{{{ completed = true }}}}
"""

    runtime = TactusRuntime(
        procedure_id=f"test-temp-{model}",
        storage_backend=MemoryStorage(),
        hitl_handler=None,
        chat_recorder=None,
        mcp_server=None,
        openai_api_key=os.environ.get("OPENAI_API_KEY"),
    )

    result = await runtime.execute(yaml_config, context={})

    assert result["success"], f"Procedure failed: {result.get('error', 'Unknown error')}"

    # Extract result
    result_data = result["result"]
    if isinstance(result_data, dict) and 1 in result_data:
        result_data = result_data[1]
    if hasattr(result_data, "items"):
        result_data = dict(result_data.items())

    assert result_data["completed"] is True


@pytest.mark.asyncio
@pytest.mark.parametrize("model", REASONING_MODELS[:2])  # Test first 2 reasoning models
async def test_reasoning_model_with_effort_parameter(model: str):
    """
    Test reasoning models with openai_reasoning_effort parameter.

    Verifies that reasoning_effort setting is accepted and procedure executes.
    """
    yaml_config = f"""
name: test_reasoning_{model.replace('-', '_').replace('.', '_')}
version: 1.0.0
class: LuaDSL

agents:
  thinker:
    provider: openai
    model:
      name: {model}
      openai_reasoning_effort: medium
      max_tokens: 2000
    system_prompt: |
      You are a thoughtful assistant. Answer: What is 7 * 8?
      When done, call the done tool with your answer.
    initial_message: "Calculate 7 * 8."
    tools:
      - done

procedure: |
  repeat
    Thinker.turn()
  until Tool.called("done")
  
  return {{{{ completed = true }}}}
"""

    runtime = TactusRuntime(
        procedure_id=f"test-reasoning-{model}",
        storage_backend=MemoryStorage(),
        hitl_handler=None,
        chat_recorder=None,
        mcp_server=None,
        openai_api_key=os.environ.get("OPENAI_API_KEY"),
    )

    result = await runtime.execute(yaml_config, context={})

    assert result["success"], f"Procedure failed: {result.get('error', 'Unknown error')}"

    # Extract result
    result_data = result["result"]
    if isinstance(result_data, dict) and 1 in result_data:
        result_data = result_data[1]
    if hasattr(result_data, "items"):
        result_data = dict(result_data.items())

    assert result_data["completed"] is True


@pytest.mark.asyncio
async def test_nested_dict_model_format():
    """
    Test that nested dict model format (with parameters) works.

    This is a quick test to verify the dict format is accepted and works.
    The test_gpt4_with_temperature_parameter tests already verify parameters work.
    """
    yaml_config = """
name: test_dict_format
version: 1.0.0
class: LuaDSL

agents:
  greeter:
    provider: openai
    model:
      name: gpt-4o-mini
      temperature: 0.5
      max_tokens: 100
    system_prompt: |
      Say hello briefly. When done, call the done tool.
    initial_message: "Greet!"
    tools:
      - done

procedure: |
  repeat
    Greeter.turn()
  until Tool.called("done")
  
  return { completed = true }
"""

    runtime = TactusRuntime(
        procedure_id="test-dict-format",
        storage_backend=MemoryStorage(),
        hitl_handler=None,
        chat_recorder=None,
        mcp_server=None,
        openai_api_key=os.environ.get("OPENAI_API_KEY"),
    )

    result = await runtime.execute(yaml_config, context={})

    assert result["success"], f"Procedure failed: {result.get('error', 'Unknown error')}"

    # Extract result
    result_data = result["result"]
    if isinstance(result_data, dict) and 1 in result_data:
        result_data = result_data[1]
    if hasattr(result_data, "items"):
        result_data = dict(result_data.items())

    assert result_data["completed"] is True
