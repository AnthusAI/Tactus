"""
Integration tests for agent message tracking via result.new_messages() and result.all_messages().
"""

from tactus.dspy.agent import DSPyAgentHandle
from tactus.core.registry import ProcedureRegistry
from tactus.core.mocking import MockManager


def test_agent_tracks_messages_in_result():
    """Test that agent results include new_messages and all_messages."""
    # Create a mock registry with agent mock
    from tactus.core.registry import AgentMockConfig

    registry = ProcedureRegistry()
    registry.agent_mocks["test_agent"] = AgentMockConfig(
        tool_calls=[],
        message="Hello from agent",
        data={},
        usage={},
    )

    # Create mock manager
    mock_manager = MockManager()

    # Create agent
    agent = DSPyAgentHandle(
        name="test_agent",
        system_prompt="You are a test agent",
        initial_message="Start",
        registry=registry,
        mock_manager=mock_manager,
    )

    # First turn
    result1 = agent({"message": "Hello"})

    # Verify new_messages contains the messages from this turn
    new_msgs1 = result1.new_messages()
    assert len(new_msgs1) == 2  # user message + assistant response
    assert new_msgs1[0]["role"] == "user"
    assert new_msgs1[0]["content"] == "Hello"
    assert new_msgs1[1]["role"] == "assistant"
    assert new_msgs1[1]["content"] == "Hello from agent"

    # Verify all_messages contains the same (first turn)
    all_msgs1 = result1.all_messages()
    assert len(all_msgs1) == 2
    assert all_msgs1 == new_msgs1

    # Second turn
    result2 = agent({"message": "How are you?"})

    # Verify new_messages contains only messages from this turn
    new_msgs2 = result2.new_messages()
    assert len(new_msgs2) == 2
    assert new_msgs2[0]["role"] == "user"
    assert new_msgs2[0]["content"] == "How are you?"
    assert new_msgs2[1]["role"] == "assistant"
    assert new_msgs2[1]["content"] == "Hello from agent"

    # Verify all_messages contains all messages from both turns
    all_msgs2 = result2.all_messages()
    assert len(all_msgs2) == 4  # 2 from turn 1 + 2 from turn 2
    assert all_msgs2[0]["role"] == "user"
    assert all_msgs2[0]["content"] == "Hello"
    assert all_msgs2[1]["role"] == "assistant"
    assert all_msgs2[2]["role"] == "user"
    assert all_msgs2[2]["content"] == "How are you?"
    assert all_msgs2[3]["role"] == "assistant"


def test_agent_with_initial_message():
    """Test that initial_message is included in messages."""
    # Create a mock registry with agent mock
    from tactus.core.registry import AgentMockConfig

    registry = ProcedureRegistry()
    registry.agent_mocks["test_agent"] = AgentMockConfig(
        tool_calls=[],
        message="Response to initial message",
        data={},
        usage={},
    )

    # Create mock manager
    mock_manager = MockManager()

    # Create agent with initial_message
    agent = DSPyAgentHandle(
        name="test_agent",
        system_prompt="You are a test agent",
        initial_message="Initial prompt",
        registry=registry,
        mock_manager=mock_manager,
    )

    # First turn without explicit message (should use initial_message)
    result = agent()

    # Verify new_messages includes initial_message
    new_msgs = result.new_messages()
    assert len(new_msgs) == 2
    assert new_msgs[0]["role"] == "user"
    assert new_msgs[0]["content"] == "Initial prompt"
    assert new_msgs[1]["role"] == "assistant"
    assert new_msgs[1]["content"] == "Response to initial message"


def test_agent_without_user_message():
    """Test agent turn with no user message (only assistant response)."""
    # Create a mock registry with agent mock
    from tactus.core.registry import AgentMockConfig

    registry = ProcedureRegistry()
    registry.agent_mocks["test_agent"] = AgentMockConfig(
        tool_calls=[],
        message="Unprompted response",
        data={},
        usage={},
    )

    # Create mock manager
    mock_manager = MockManager()

    # Create agent without initial_message
    agent = DSPyAgentHandle(
        name="test_agent",
        system_prompt="You are a test agent",
        registry=registry,
        mock_manager=mock_manager,
    )

    # Turn without message
    result = agent()

    # Verify new_messages contains only assistant response
    new_msgs = result.new_messages()
    assert len(new_msgs) == 1
    assert new_msgs[0]["role"] == "assistant"
    assert new_msgs[0]["content"] == "Unprompted response"


def test_messages_persist_across_turns():
    """Test that conversation history accumulates correctly."""
    # Create a mock registry with agent mock
    from tactus.core.registry import AgentMockConfig

    registry = ProcedureRegistry()
    registry.agent_mocks["test_agent"] = AgentMockConfig(
        tool_calls=[],
        message="Response",
        data={},
        usage={},
    )

    # Create mock manager
    mock_manager = MockManager()

    # Create agent
    agent = DSPyAgentHandle(
        name="test_agent",
        system_prompt="You are a test agent",
        registry=registry,
        mock_manager=mock_manager,
    )

    # Multiple turns
    result1 = agent({"message": "Turn 1"})
    result2 = agent({"message": "Turn 2"})
    result3 = agent({"message": "Turn 3"})

    # Verify each result has correct new_messages
    assert len(result1.new_messages()) == 2
    assert len(result2.new_messages()) == 2
    assert len(result3.new_messages()) == 2

    # Verify all_messages accumulates
    assert len(result1.all_messages()) == 2
    assert len(result2.all_messages()) == 4
    assert len(result3.all_messages()) == 6

    # Verify content
    all_msgs = result3.all_messages()
    assert all_msgs[0]["content"] == "Turn 1"
    assert all_msgs[2]["content"] == "Turn 2"
    assert all_msgs[4]["content"] == "Turn 3"
