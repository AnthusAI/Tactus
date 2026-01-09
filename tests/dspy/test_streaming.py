"""
Tests for DSPy streaming support.

Tests the streaming functionality added to DSPyAgentHandle for
real-time response streaming in the IDE.
"""

from typing import List

from tactus.dspy.agent import DSPyAgentHandle, create_dspy_agent
from tactus.dspy.config import reset_lm_configuration
from tactus.protocols.models import AgentStreamChunkEvent, AgentTurnEvent


class MockLogHandler:
    """Mock log handler that records events."""

    def __init__(self):
        self.events: List = []

    def log(self, event) -> None:
        self.events.append(event)

    def get_stream_chunk_events(self) -> List[AgentStreamChunkEvent]:
        """Get only stream chunk events."""
        return [e for e in self.events if isinstance(e, AgentStreamChunkEvent)]

    def get_agent_turn_events(self) -> List[AgentTurnEvent]:
        """Get only agent turn events."""
        return [e for e in self.events if isinstance(e, AgentTurnEvent)]


class TestStreamingConfiguration:
    """Test streaming configuration and detection."""

    def setup_method(self):
        """Reset LM configuration before each test."""
        reset_lm_configuration()

    def test_agent_accepts_log_handler(self):
        """Test that DSPyAgentHandle accepts log_handler parameter."""
        log_handler = MockLogHandler()
        agent = DSPyAgentHandle(
            name="test_agent",
            system_prompt="Test prompt",
            model="openai/gpt-4o-mini",
            log_handler=log_handler,
        )
        assert agent.log_handler is log_handler

    def test_agent_accepts_disable_streaming(self):
        """Test that DSPyAgentHandle accepts disable_streaming parameter."""
        agent = DSPyAgentHandle(
            name="test_agent",
            system_prompt="Test prompt",
            model="openai/gpt-4o-mini",
            disable_streaming=True,
        )
        assert agent.disable_streaming is True

    def test_create_dspy_agent_passes_log_handler(self):
        """Test that create_dspy_agent passes log_handler to agent."""
        log_handler = MockLogHandler()
        agent = create_dspy_agent(
            "test_agent",
            {
                "system_prompt": "Test",
                "model": "openai/gpt-4o-mini",
                "log_handler": log_handler,
            },
        )
        assert agent.log_handler is log_handler

    def test_create_dspy_agent_passes_disable_streaming(self):
        """Test that create_dspy_agent passes disable_streaming to agent."""
        agent = create_dspy_agent(
            "test_agent",
            {
                "system_prompt": "Test",
                "model": "openai/gpt-4o-mini",
                "disable_streaming": True,
            },
        )
        assert agent.disable_streaming is True


class TestShouldStream:
    """Test the _should_stream() method logic."""

    def setup_method(self):
        """Reset LM configuration before each test."""
        reset_lm_configuration()

    def test_should_stream_returns_false_without_log_handler(self):
        """Test that streaming is disabled when no log_handler."""
        agent = DSPyAgentHandle(
            name="test_agent",
            system_prompt="Test prompt",
            model="openai/gpt-4o-mini",
        )
        assert agent._should_stream() is False

    def test_should_stream_returns_true_with_log_handler(self):
        """Test that streaming is enabled with log_handler."""
        log_handler = MockLogHandler()
        agent = DSPyAgentHandle(
            name="test_agent",
            system_prompt="Test prompt",
            model="openai/gpt-4o-mini",
            log_handler=log_handler,
        )
        assert agent._should_stream() is True

    def test_should_stream_returns_false_when_disabled(self):
        """Test that streaming is disabled with disable_streaming=True."""
        log_handler = MockLogHandler()
        agent = DSPyAgentHandle(
            name="test_agent",
            system_prompt="Test prompt",
            model="openai/gpt-4o-mini",
            log_handler=log_handler,
            disable_streaming=True,
        )
        assert agent._should_stream() is False

    def test_should_stream_returns_true_with_output_schema(self):
        """Test that streaming works even with output_schema set.

        Streaming (UI feedback) and validation (post-processing) are orthogonal.
        We stream raw text during generation, then validate after completion.
        """
        log_handler = MockLogHandler()
        agent = DSPyAgentHandle(
            name="test_agent",
            system_prompt="Test",
            model="openai/gpt-4o-mini",
            log_handler=log_handler,
            output_schema={"result": {"type": "string", "required": True}},
        )
        # Streaming should work with structured output
        assert agent._should_stream() is True

    def test_should_stream_with_default_output_schema(self):
        """Test that streaming works with the default output schema."""
        log_handler = MockLogHandler()
        agent = DSPyAgentHandle(
            name="test_agent",
            system_prompt="Test",
            model="openai/gpt-4o-mini",
            log_handler=log_handler,
            # Default output_schema is {"response": {"type": "string", "required": False}}
        )
        # Should stream with default schema (plain text response)
        assert agent._should_stream() is True


class TestStreamingEventsFormat:
    """Test the format of emitted streaming events."""

    def test_agent_stream_chunk_event_has_required_fields(self):
        """Test that AgentStreamChunkEvent has all required fields."""
        event = AgentStreamChunkEvent(
            agent_name="test_agent",
            chunk_text="Hello",
            accumulated_text="Hello",
        )
        assert event.event_type == "agent_stream_chunk"
        assert event.agent_name == "test_agent"
        assert event.chunk_text == "Hello"
        assert event.accumulated_text == "Hello"
        assert event.timestamp is not None

    def test_agent_turn_event_has_required_fields(self):
        """Test that AgentTurnEvent has all required fields."""
        event = AgentTurnEvent(
            agent_name="test_agent",
            stage="started",
        )
        assert event.event_type == "agent_turn"
        assert event.agent_name == "test_agent"
        assert event.stage == "started"


class TestMockLogHandler:
    """Test the MockLogHandler helper class."""

    def test_mock_log_handler_records_events(self):
        """Test that MockLogHandler records events correctly."""
        handler = MockLogHandler()

        event1 = AgentTurnEvent(agent_name="agent1", stage="started")
        event2 = AgentStreamChunkEvent(
            agent_name="agent1",
            chunk_text="Hello",
            accumulated_text="Hello",
        )
        event3 = AgentStreamChunkEvent(
            agent_name="agent1",
            chunk_text=" world",
            accumulated_text="Hello world",
        )

        handler.log(event1)
        handler.log(event2)
        handler.log(event3)

        assert len(handler.events) == 3
        assert len(handler.get_agent_turn_events()) == 1
        assert len(handler.get_stream_chunk_events()) == 2

    def test_mock_log_handler_filters_by_type(self):
        """Test filtering events by type."""
        handler = MockLogHandler()

        handler.log(AgentTurnEvent(agent_name="agent1", stage="started"))
        handler.log(
            AgentStreamChunkEvent(
                agent_name="agent1",
                chunk_text="chunk1",
                accumulated_text="chunk1",
            )
        )
        handler.log(AgentTurnEvent(agent_name="agent1", stage="completed"))

        turn_events = handler.get_agent_turn_events()
        chunk_events = handler.get_stream_chunk_events()

        assert len(turn_events) == 2
        assert len(chunk_events) == 1
        assert turn_events[0].stage == "started"
        assert turn_events[1].stage == "completed"


class TestStreamingWithExistingEventLoop:
    """Test that streaming works when called from within an existing event loop."""

    def setup_method(self):
        """Reset LM configuration before each test."""
        reset_lm_configuration()

    def test_streaming_thread_isolation(self):
        """
        Test that _turn_with_streaming doesn't conflict with existing event loops.

        This test simulates the IDE environment where the Flask/FastAPI server
        is already running an event loop. The streaming implementation must
        run its async code in a separate thread to avoid "Cannot run the event
        loop while another loop is running" errors.
        """

        log_handler = MockLogHandler()
        agent = DSPyAgentHandle(
            name="test_agent",
            system_prompt="Test prompt",
            model="openai/gpt-4o-mini",
            log_handler=log_handler,
        )

        # Verify the agent is configured to stream
        assert agent._should_stream() is True

        # The _turn_with_streaming method should use threading internally.
        # We can verify this by checking the implementation uses threading.Thread.
        # This test ensures the design handles nested event loop scenarios.
        import inspect

        source = inspect.getsource(agent._turn_with_streaming)
        assert (
            "threading.Thread" in source
        ), "Streaming should use threading to avoid event loop conflicts"
        assert "asyncio.run" in source, "Streaming should use asyncio.run in the thread"


# Note: Integration tests with actual LLM calls would require mocking DSPy's
# streaming infrastructure. These tests focus on the configuration and event
# format aspects that can be tested without LLM calls.
