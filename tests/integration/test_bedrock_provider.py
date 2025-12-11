"""
Integration tests for AWS Bedrock provider support.

These tests require real AWS Bedrock API access. Run with:
    pytest tests/integration/test_bedrock_provider.py --real-api

Without --real-api flag, these tests will be skipped (integration tests require real APIs).
"""

import pytest
import os
from pathlib import Path
from dotyaml import load_config

from tactus.core.runtime import TactusRuntime
from tactus.adapters.memory import MemoryStorage


# Load configuration from .tactus/config.yml
config_path = Path.home() / "Projects" / "Tactus" / ".tactus" / "config.yml"
if config_path.exists():
    load_config(str(config_path), prefix="")  # Load with no prefix for exact key names


# Mark all tests in this module as requiring real API
pytestmark = pytest.mark.integration


# Bedrock Claude models to test
# Note: Using Claude 3.5 Sonnet which supports on-demand throughput
# Claude 3.5 Haiku requires inference profiles which aren't configured in this account
BEDROCK_MODELS = [
    "anthropic.claude-3-5-sonnet-20240620-v1:0",
]


@pytest.fixture(autouse=True)
def require_real_api(use_real_api):
    """All tests in this module require --real-api flag."""
    if not use_real_api:
        pytest.skip("Integration tests require --real-api flag")


@pytest.fixture(autouse=True)
def require_aws_credentials():
    """All tests in this module require AWS credentials."""
    if not (
        os.environ.get("AWS_ACCESS_KEY_ID")
        and os.environ.get("AWS_SECRET_ACCESS_KEY")
        and os.environ.get("AWS_DEFAULT_REGION")
    ):
        pytest.fail(
            "AWS credentials not set. Need AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, and AWS_DEFAULT_REGION."
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("model", BEDROCK_MODELS)
async def test_bedrock_model(model: str):
    """
    Test that Bedrock Claude models work with provider specification.

    Verifies:
    1. Provider can be specified as 'bedrock'
    2. Bedrock model IDs work
    3. Procedure executes successfully
    """
    yaml_config = f"""
name: test_bedrock_{model.replace('.', '_').replace(':', '_').replace('-', '_')}
version: 1.0.0
class: LuaDSL

agents:
  assistant:
    provider: bedrock
    model: {model}
    system_prompt: |
      You are a helpful assistant. Respond briefly.
      When done, call the done tool with your response.
    initial_message: "Say hello!"
    tools:
      - done

procedure: |
  repeat
    Assistant.turn()
  until Tool.called("done")
  
  return {{{{ completed = true }}}}
"""

    runtime = TactusRuntime(
        procedure_id=f"test-bedrock-{model}",
        storage_backend=MemoryStorage(),
        hitl_handler=None,
        chat_recorder=None,
        mcp_server=None,
        openai_api_key=None,  # Not needed for Bedrock
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
async def test_mixed_providers():
    """
    Test using both OpenAI and Bedrock providers in the same procedure.

    Verifies that different agents can use different providers.
    """
    yaml_config = """
name: test_mixed_providers
version: 1.0.0
class: LuaDSL

agents:
  openai_agent:
    provider: openai
    model: gpt-4o-mini
    system_prompt: |
      You are an OpenAI assistant. Say "Hello from OpenAI!"
      When done, call the done tool.
    initial_message: "Greet from OpenAI."
    tools:
      - done
  
  bedrock_agent:
    provider: bedrock
    model: anthropic.claude-3-5-sonnet-20240620-v1:0
    system_prompt: |
      You are a Bedrock assistant. Say "Hello from Bedrock!"
      When done, call the done tool.
    initial_message: "Greet from Bedrock."
    tools:
      - done

procedure: |
  repeat
    Openai_agent.turn()
  until Tool.called("done")
  
  repeat
    Bedrock_agent.turn()
  until Tool.called("done")
  
  return { completed = true }
"""

    runtime = TactusRuntime(
        procedure_id="test-mixed-providers",
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
async def test_bedrock_with_default_provider():
    """
    Test using default_provider to set Bedrock as default.

    Verifies that default_provider fallback works for Bedrock.
    """
    yaml_config = """
name: test_default_bedrock
version: 1.0.0
class: LuaDSL

default_provider: bedrock
default_model: anthropic.claude-3-5-sonnet-20240620-v1:0

agents:
  assistant:
    # Uses default_provider and default_model
    system_prompt: |
      You are a helpful assistant. Respond briefly.
      When done, call the done tool.
    initial_message: "Say hello!"
    tools:
      - done

procedure: |
  repeat
    Assistant.turn()
  until Tool.called("done")
  
  return { completed = true }
"""

    runtime = TactusRuntime(
        procedure_id="test-default-bedrock",
        storage_backend=MemoryStorage(),
        hitl_handler=None,
        chat_recorder=None,
        mcp_server=None,
        openai_api_key=None,
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
