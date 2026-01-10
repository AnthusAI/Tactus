"""Tests for AgentHandle shorthand call behavior."""

from tactus.primitives.handles import AgentHandle


class StubAgentPrimitive:
    """Minimal agent primitive stub for testing."""

    def __init__(self):
        self.received = None

    def __call__(self, inputs=None):
        self.received = inputs
        return inputs


def test_agent_handle_converts_string_to_message_dict():
    """Calling an agent with a string should wrap it in a message dict."""
    primitive = StubAgentPrimitive()
    handle = AgentHandle("worker")
    handle._set_primitive(primitive)

    result = handle("hello world")

    assert primitive.received == {"message": "hello world"}
    assert result == {"message": "hello world"}
