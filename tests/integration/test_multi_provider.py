"""
Integration tests for multi-provider support.

Tests that multiple providers (OpenAI and Bedrock) can be used in procedures.
These tests require --real-api flag and appropriate credentials.
"""

import pytest
import os

from tactus.core.runtime import TactusRuntime
from tactus.adapters.memory import MemoryStorage


def create_bedrock_procedure_yaml(model: str) -> str:
    """Create a simple procedure using Bedrock."""
    return f"""
name: test_bedrock_{model.replace('.', '_').replace(':', '_').replace('-', '_')}
version: 1.0.0
class: LuaDSL

params:
  task:
    type: string
    default: "test"

agents:
  worker:
    provider: bedrock
    model: {model}
    system_prompt: |
      You are a helpful assistant. Process the task: {{params.task}}
      When done, call the done tool.
    initial_message: "Please process the task."
    tools:
      - done

procedure: |
  repeat
    Worker.turn()
  until Tool.called("done")

  return {{
    completed = true,
    result = Tool.last_call("done").args.reason
  }}
"""


def create_mixed_provider_procedure_yaml() -> str:
    """Create a procedure with both OpenAI and Bedrock agents."""
    return """
name: test_mixed_providers
version: 1.0.0
class: LuaDSL

params:
  task:
    type: string
    default: "analyze data"

agents:
  openai_worker:
    provider: openai
    model: gpt-4o-mini
    system_prompt: |
      You are an OpenAI-powered worker. Process: {params.task}
      When done, call the done tool.
    initial_message: "Please process the task."
    tools:
      - done
  
  bedrock_reviewer:
    provider: bedrock
    model: anthropic.claude-3-5-haiku-20241022-v1:0
    system_prompt: |
      You are a Bedrock-powered reviewer. Review the work.
      When done, call the done tool.
    initial_message: "Please review the work."
    tools:
      - done

procedure: |
  -- OpenAI worker processes
  repeat
    Openai_worker.turn()
  until Tool.called("done")
  
  local worker_result = Tool.last_call("done").args.reason
  
  -- Bedrock reviewer reviews
  repeat
    Bedrock_reviewer.turn()
  until Tool.called("done")
  
  local review_result = Tool.last_call("done").args.reason
  
  return {
    worker_result = worker_result,
    review_result = review_result,
    providers_used = {"openai", "bedrock"}
  }
"""


@pytest.mark.asyncio
async def test_bedrock_claude_sonnet(use_real_api: bool):
    """Test Bedrock with Claude 3.5 Sonnet."""
    if not use_real_api:
        pytest.skip("Bedrock tests require --real-api flag")

    if not os.environ.get("AWS_ACCESS_KEY_ID") or not os.environ.get("AWS_SECRET_ACCESS_KEY"):
        pytest.skip("AWS credentials not available")

    model = "anthropic.claude-3-5-sonnet-20240620-v1:0"

    runtime = TactusRuntime(
        procedure_id="test-bedrock-sonnet",
        storage_backend=MemoryStorage(),
        hitl_handler=None,
        chat_recorder=None,
        mcp_server=None,
        openai_api_key=None,  # Not needed for Bedrock
    )

    yaml_config = create_bedrock_procedure_yaml(model)
    result = await runtime.execute(yaml_config, context={"task": "test task"})

    assert result["success"], f"Procedure failed: {result.get('error', 'Unknown error')}"
    assert result["result"]["completed"] is True


@pytest.mark.asyncio
async def test_bedrock_claude_haiku(use_real_api: bool):
    """Test Bedrock with Claude 3.5 Haiku."""
    if not use_real_api:
        pytest.skip("Bedrock tests require --real-api flag")

    if not os.environ.get("AWS_ACCESS_KEY_ID") or not os.environ.get("AWS_SECRET_ACCESS_KEY"):
        pytest.skip("AWS credentials not available")

    model = "anthropic.claude-3-5-haiku-20241022-v1:0"

    runtime = TactusRuntime(
        procedure_id="test-bedrock-haiku", storage_backend=MemoryStorage(), openai_api_key=None
    )

    yaml_config = create_bedrock_procedure_yaml(model)
    result = await runtime.execute(yaml_config, context={"task": "test task"})

    assert result["success"]
    assert result["result"]["completed"] is True


@pytest.mark.asyncio
async def test_mixed_providers(use_real_api: bool):
    """Test procedure with both OpenAI and Bedrock agents."""
    if not use_real_api:
        pytest.skip("Mixed provider tests require --real-api flag")

    if not os.environ.get("OPENAI_API_KEY"):
        pytest.skip("OpenAI API key not available")

    if not os.environ.get("AWS_ACCESS_KEY_ID") or not os.environ.get("AWS_SECRET_ACCESS_KEY"):
        pytest.skip("AWS credentials not available")

    runtime = TactusRuntime(
        procedure_id="test-mixed-providers",
        storage_backend=MemoryStorage(),
        openai_api_key=os.environ.get("OPENAI_API_KEY"),
    )

    yaml_config = create_mixed_provider_procedure_yaml()
    result = await runtime.execute(yaml_config, context={"task": "analyze data"})

    assert result["success"]
    assert "worker_result" in result["result"]
    assert "review_result" in result["result"]
    assert result["result"]["providers_used"] == ["openai", "bedrock"]


@pytest.mark.asyncio
async def test_default_provider_openai(use_real_api: bool):
    """Test that default_provider works correctly."""
    if not use_real_api:
        pytest.skip("Provider tests require --real-api flag")

    if not os.environ.get("OPENAI_API_KEY"):
        pytest.skip("OpenAI API key not available")

    yaml_config = """
name: test_default_provider
version: 1.0.0
class: LuaDSL

default_provider: openai
default_model: gpt-4o-mini

agents:
  worker:
    system_prompt: |
      You are a helpful assistant. When done, call the done tool.
    initial_message: "Please complete the task."
    tools:
      - done

procedure: |
  repeat
    Worker.turn()
  until Tool.called("done")
  
  return {completed = true}
"""

    runtime = TactusRuntime(
        procedure_id="test-default-provider",
        storage_backend=MemoryStorage(),
        openai_api_key=os.environ.get("OPENAI_API_KEY"),
    )

    result = await runtime.execute(yaml_config)
    assert result["success"]


@pytest.mark.asyncio
async def test_provider_override(use_real_api: bool):
    """Test that agent provider overrides default_provider."""
    if not use_real_api:
        pytest.skip("Provider tests require --real-api flag")

    if not os.environ.get("AWS_ACCESS_KEY_ID") or not os.environ.get("AWS_SECRET_ACCESS_KEY"):
        pytest.skip("AWS credentials not available")

    yaml_config = """
name: test_provider_override
version: 1.0.0
class: LuaDSL

default_provider: openai
default_model: gpt-4o

agents:
  worker:
    provider: bedrock
    model: anthropic.claude-3-5-haiku-20241022-v1:0
    system_prompt: |
      You are a helpful assistant. When done, call the done tool.
    initial_message: "Please complete the task."
    tools:
      - done

procedure: |
  repeat
    Worker.turn()
  until Tool.called("done")
  
  return {completed = true}
"""

    runtime = TactusRuntime(
        procedure_id="test-provider-override",
        storage_backend=MemoryStorage(),
        openai_api_key=None,  # Not needed since we're using Bedrock
    )

    result = await runtime.execute(yaml_config)
    assert result["success"]
