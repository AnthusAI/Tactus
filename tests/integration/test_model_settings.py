"""
Integration tests for model_settings support.

Tests that model-specific parameters can be configured in YAML and are properly
passed to the underlying LLM models.
"""

import pytest
import os

from tactus.core.runtime import TactusRuntime
from tactus.adapters.memory import MemoryStorage


# Mark all tests in this module as requiring real API
pytestmark = pytest.mark.integration


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
async def test_gpt4_with_temperature():
    """Test GPT-4 model with temperature setting."""
    yaml_config = """
name: test_temperature
version: 1.0.0
class: LuaDSL

agents:
  greeter:
    model:
      name: gpt-4o-mini
      temperature: 0.3
      max_tokens: 50
    system_prompt: |
      You are a concise greeter. Greet the user briefly.
      When done, call the done tool with your greeting.
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
        procedure_id="test-temperature",
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
async def test_gpt5_with_reasoning_effort():
    """Test GPT-5 model with reasoning_effort setting."""
    yaml_config = """
name: test_reasoning
version: 1.0.0
class: LuaDSL

agents:
  thinker:
    model: gpt-5-nano
    model_settings:
      openai_reasoning_effort: medium
      max_tokens: 1000
    system_prompt: |
      You are a thoughtful assistant. Think carefully and respond.
      When done, call the done tool with your response.
    initial_message: "What is 2+2?"
    tools:
      - done

procedure: |
  repeat
    Thinker.turn()
  until Tool.called("done")
  
  return { completed = true }
"""

    runtime = TactusRuntime(
        procedure_id="test-reasoning",
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
async def test_mixed_model_settings():
    """Test multiple agents with different model settings."""
    yaml_config = """
name: test_mixed_settings
version: 1.0.0
class: LuaDSL

agents:
  creative:
    model: gpt-4o-mini
    model_settings:
      temperature: 0.9
      top_p: 0.95
      max_tokens: 100
    system_prompt: |
      You are creative. Be imaginative.
      When done, call the done tool.
    initial_message: "Be creative!"
    tools:
      - done
  
  precise:
    model: gpt-4.1-mini
    model_settings:
      temperature: 0.1
      max_tokens: 50
    system_prompt: |
      You are precise. Be exact.
      When done, call the done tool.
    initial_message: "Be precise!"
    tools:
      - done

procedure: |
  repeat
    Creative.turn()
  until Tool.called("done")
  
  repeat
    Precise.turn()
  until Tool.called("done")
  
  return { completed = true }
"""

    runtime = TactusRuntime(
        procedure_id="test-mixed",
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
