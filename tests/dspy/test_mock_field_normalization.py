"""
Test that agent mocks produce a stable `result.output`.

Policy:
- Without an explicit agent output schema, `result.output` is the plain text response string.
- With an explicit output schema, `result.output` may be structured.
"""

from tactus.dspy.agent import DSPyAgentHandle


def test_mock_message_field_normalized_to_response():
    """Test that mock 'message' becomes the plain string output by default."""
    # Create agent with mock data
    agent = DSPyAgentHandle(
        name="test_agent",
        system_prompt="Test agent",
        model="openai/gpt-4o-mini",
        registry=None,
        mock_manager=None,
    )

    # Simulate mock data with 'message' field (as used in Mocks {} blocks)
    mock_data = {
        "message": "Hello from mock",
        "tool_calls": [],
    }

    # Wrap mock response
    result = agent._wrap_mock_response(mock_data, {})

    assert result.output == "Hello from mock"


def test_mock_response_field_not_overwritten():
    """Test that explicit 'response' wins over 'message' for plain output."""
    agent = DSPyAgentHandle(
        name="test_agent",
        system_prompt="Test agent",
        model="openai/gpt-4o-mini",
        registry=None,
        mock_manager=None,
    )

    # Mock data with both 'message' and 'response' fields
    mock_data = {
        "message": "Message field",
        "response": "Response field",
        "tool_calls": [],
    }

    # Wrap mock response
    result = agent._wrap_mock_response(mock_data, {})

    assert result.output == "Response field"


def test_mock_without_message_field():
    """Test that mock data without 'message' field works correctly."""
    agent = DSPyAgentHandle(
        name="test_agent",
        system_prompt="Test agent",
        model="openai/gpt-4o-mini",
        registry=None,
        mock_manager=None,
    )

    # Mock data with only 'response' field
    mock_data = {
        "response": "Direct response",
        "tool_calls": [],
    }

    # Wrap mock response
    result = agent._wrap_mock_response(mock_data, {})

    # Verify that 'response' value is accessible (simplified to string when single field)
    assert result.output == "Direct response", "Response should be accessible"


def test_mock_data_with_tool_calls():
    """Test that mock data with tool_calls and message field is normalized correctly."""
    agent = DSPyAgentHandle(
        name="test_agent",
        system_prompt="Test agent",
        model="openai/gpt-4o-mini",
        registry=None,
        mock_manager=None,
    )

    # Mock data with tool_calls (simulating a done tool call)
    mock_data = {
        "message": "Task completed successfully",
        "tool_calls": [{"tool": "done", "args": {"reason": "Task completed"}}],
    }

    # Wrap mock response
    result = agent._wrap_mock_response(mock_data, {})

    assert result.output == "Task completed successfully"
