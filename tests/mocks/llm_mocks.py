"""
Mock LLM provider system for testing.

Provides mocks for pydantic-ai Agent calls that can be enabled/disabled
via pytest configuration.
"""

from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch
from dataclasses import dataclass, field
from pydantic_ai import Agent
from pydantic_ai.models import ModelMessage


@dataclass
class MockResponse:
    """Mock response from an LLM provider."""

    content: str
    model: str
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    finish_reason: str = "stop"


class MockLLMProvider:
    """
    Mock provider that intercepts pydantic-ai calls.

    This can be used to mock LLM responses in tests without making
    actual API calls.
    """

    def __init__(self, provider_name: str, model_name: str):
        self.provider_name = provider_name
        self.model_name = model_name
        self.call_count = 0
        self.call_history: List[Dict[str, Any]] = []
        self._response_generator = None

    def set_response(self, content: str, tool_calls: Optional[List[Dict[str, Any]]] = None):
        """Set the response that will be returned for the next call."""
        self._next_response = MockResponse(
            content=content, model=self.model_name, tool_calls=tool_calls or []
        )

    def set_response_generator(self, generator):
        """Set a generator function that returns responses based on input."""
        self._response_generator = generator

    async def mock_agent_run(
        self,
        user_input: str,
        deps: Any = None,
        message_history: List = None,
        output: type = None,
    ):
        """Mock implementation of Agent.run() method."""
        self.call_count += 1

        # Record the call
        call_info = {
            "user_input": user_input,
            "model": self.model_name,
            "provider": self.provider_name,
            "has_deps": deps is not None,
            "message_count": len(message_history) if message_history else 0,
        }
        self.call_history.append(call_info)

        # Generate response
        if self._response_generator:
            response = self._response_generator(user_input, message_history or [])
        elif hasattr(self, "_next_response"):
            response = self._next_response
            delattr(self, "_next_response")
        else:
            # Default mock response
            response = MockResponse(
                content=f"Mock response from {self.provider_name}:{self.model_name}",
                model=self.model_name,
            )

        # Create a mock result object that mimics pydantic-ai's AgentRunResult
        # The result should have:
        # - response: the actual response (string or structured data)
        # - new_messages(): method that returns list of ModelMessage objects
        mock_result = MagicMock()

        # Set response - this is what gets returned as the main result
        mock_result.response = response.content

        # Create mock messages that mimic pydantic-ai's ModelMessage structure
        messages = []
        if response.content:
            # Create a mock message object
            msg = MagicMock(spec=ModelMessage)
            msg.role = "assistant"
            msg.source = "assistant"
            # ModelMessage might have 'parts' or 'content' attribute
            if hasattr(msg, "parts"):
                # Multi-part message
                part = MagicMock()
                part.text = response.content
                msg.parts = [part]
            else:
                msg.content = response.content
                msg.text = response.content
            messages.append(msg)

        # Mock new_messages() method to return the list
        mock_result.new_messages = MagicMock(return_value=messages)

        # Handle tool calls if present
        if response.tool_calls:
            # Mock tool call structure - pydantic-ai might handle this differently
            # For now, we'll just set it as an attribute
            mock_result.tool_calls = response.tool_calls

        return mock_result


# Global registry of mock providers
_mock_providers: Dict[str, MockLLMProvider] = {}


def register_mock_provider(model_string: str, provider: MockLLMProvider):
    """Register a mock provider for a specific model string."""
    _mock_providers[model_string] = provider


def get_mock_provider(model_string: str) -> Optional[MockLLMProvider]:
    """Get a registered mock provider for a model string."""
    return _mock_providers.get(model_string)


def clear_mock_providers():
    """Clear all registered mock providers."""
    _mock_providers.clear()


def create_mock_agent_patch(use_real_api: bool = False):
    """
    Create a patch for pydantic-ai Agent class that uses mocks unless use_real_api is True.

    Args:
        use_real_api: If True, don't patch (use real API). If False, use mocks.

    Returns:
        A context manager that patches Agent.run() method
    """
    if use_real_api:
        # Return a no-op context manager
        from contextlib import nullcontext

        return nullcontext()

    # Create a patch that intercepts Agent.run()
    _ = Agent.run  # noqa: F841

    async def patched_run(
        self,
        user_input: str,
        deps: Any = None,
        message_history: List = None,
        output: type = None,
    ):
        """Patched version of Agent.run() that uses mocks."""
        # Extract model string from Agent instance
        # Try multiple ways to get the model identifier
        model_string = None

        # Try to get from _model attribute
        if hasattr(self, "_model"):
            model_obj = self._model
            if hasattr(model_obj, "model_id"):
                model_string = model_obj.model_id
            elif hasattr(model_obj, "__str__"):
                model_string = str(model_obj)

        # Try to get from model attribute directly
        if not model_string and hasattr(self, "model"):
            model_obj = self.model
            if isinstance(model_obj, str):
                model_string = model_obj
            elif hasattr(model_obj, "model_id"):
                model_string = model_obj.model_id
            elif hasattr(model_obj, "__str__"):
                model_string = str(model_obj)

        # Fallback: try to get from any string attribute
        if not model_string:
            for attr in ["_model_name", "model_name", "model_string"]:
                if hasattr(self, attr):
                    val = getattr(self, attr)
                    if isinstance(val, str):
                        model_string = val
                        break

        # Default if we can't find it
        if not model_string:
            model_string = "unknown"

        # Try to find a mock provider
        mock_provider = get_mock_provider(model_string)
        if not mock_provider and ":" in model_string:
            # Try without provider prefix
            _, model_part = model_string.split(":", 1)
            mock_provider = get_mock_provider(model_part)

        if not mock_provider:
            # Try to find by provider prefix
            if ":" in model_string:
                provider, model = model_string.split(":", 1)
                # Try provider-only match
                for key, provider_obj in _mock_providers.items():
                    if provider_obj.provider_name == provider:
                        mock_provider = provider_obj
                        break

        if mock_provider:
            return await mock_provider.mock_agent_run(user_input, deps, message_history, output)
        else:
            # Fallback: create a default mock
            default_mock = MockLLMProvider("openai", model_string)
            default_mock.set_response(f"Default mock response for {model_string}")
            return await default_mock.mock_agent_run(user_input, deps, message_history, output)

    return patch.object(Agent, "run", patched_run)


# Convenience function to create default mocks for common models
def setup_default_mocks():
    """Set up default mock providers for common OpenAI models."""
    openai_models = [
        "gpt-4o",
        "gpt-4o-mini",
        "gpt-4-turbo",
        "gpt-4-turbo-preview",
        "o1",
        "o1-mini",
        "o1-preview",
    ]

    for model in openai_models:
        # Register with both formats: with and without 'openai:' prefix
        provider = MockLLMProvider("openai", model)
        provider.set_response(f"Mock response from {model}")
        register_mock_provider(f"openai:{model}", provider)
        register_mock_provider(model, provider)
