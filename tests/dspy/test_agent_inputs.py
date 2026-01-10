"""Tests for DSPy agent input normalization."""

from types import SimpleNamespace
from typing import List

from tactus.dspy.agent import DSPyAgentHandle, create_dspy_agent


def test_create_dspy_agent_accepts_message_alias():
    """Ensure message alias populates the initial message."""
    agent = create_dspy_agent(
        "test_agent",
        {
            "system_message": "Test prompt",
            "model": "openai/gpt-4o-mini",
            "message": "Hello from alias",
        },
    )

    assert agent.initial_message == "Hello from alias"


class StubMockManager:
    """Mock manager stub that captures agent opts."""

    def __init__(self):
        self.calls: List[dict] = []

    def get_mock_response(self, agent_name, opts):
        self.calls.append({"agent": agent_name, "opts": opts})
        return {"response": f"echo:{opts.get('inject')}"}


def test_agent_accepts_string_input_as_message():
    """Calling agent with a string should inject it as the message."""
    registry = SimpleNamespace(mocks={"string_agent": {}})
    mock_manager = StubMockManager()
    agent = DSPyAgentHandle(
        name="string_agent",
        system_message="Test prompt",
        model="openai/gpt-4o-mini",
        registry=registry,
        mock_manager=mock_manager,
    )

    result = agent("ping")

    assert mock_manager.calls, "Mock manager should capture the call"
    assert mock_manager.calls[0]["opts"]["inject"] == "ping"
    assert result.response == "echo:ping"
