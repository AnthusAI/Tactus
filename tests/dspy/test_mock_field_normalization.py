"""
Test that mock data with 'message' field is properly normalized to 'response' field.

This ensures that Lua code can access result.response even when the mock
configuration uses the 'message' field (which is the standard in Mocks {} blocks).
"""

from tactus.dspy.agent import DSPyAgentHandle


def test_mock_message_field_normalized_to_response():
    """Test that mock 'message' field is accessible as 'response' in prediction."""
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
        "data": {},
        "usage": {},
    }

    # Wrap mock response
    result = agent._wrap_mock_response(mock_data, {})

    # Verify that result.value contains the prediction with 'response' field
    assert isinstance(result.value, dict), "Result value should be a dict"
    assert "response" in result.value, "Prediction should have 'response' field"
    assert result.value["response"] == "Hello from mock", "Response should match mock message"

    # Verify that 'message' field is still accessible
    assert "message" in result.value, "Prediction should have 'message' field"
    assert result.value["message"] == "Hello from mock", "Message should match mock message"


def test_mock_response_field_not_overwritten():
    """Test that explicit 'response' field in mock data is not overwritten."""
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

    # Verify that explicit 'response' field is preserved
    assert result.value["response"] == "Response field", "Explicit response should be preserved"
    # Both fields should exist in the value dict
    assert result.value["message"] == "Message field", "Message field should be preserved"


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
    assert result.value == "Direct response", "Response should be accessible"


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
        "data": {"result": "success"},
        "usage": {"total_tokens": 100},
    }

    # Wrap mock response
    result = agent._wrap_mock_response(mock_data, {})

    # Verify that 'response' field is accessible (normalized from 'message')
    assert "response" in result.value, "Result should have 'response' field"
    assert (
        result.value["response"] == "Task completed successfully"
    ), "Response should match mock message"

    # Verify other fields are preserved
    assert "data" in result.value, "Result should have 'data' field"
    assert result.value["data"] == {"result": "success"}, "Data should be preserved"
