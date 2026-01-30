from types import SimpleNamespace

from tactus.dspy.agent import DSPyAgentHandle


def make_agent(**overrides):
    params = {
        "name": "agent",
        "system_prompt": "Test",
        "model": "openai/gpt-4o-mini",
    }
    params.update(overrides)
    return DSPyAgentHandle(**params)


def test_get_mock_response_returns_none_without_registry():
    agent = make_agent()
    assert agent._get_mock_response({"message": "hi"}) is None


def test_get_mock_response_uses_temporal_match():
    mock = SimpleNamespace(
        message="default",
        tool_calls=[],
        data={},
        temporal=[{"when_message": "hello", "message": "matched"}],
    )
    registry = SimpleNamespace(agent_mocks={"agent": mock})

    agent = make_agent(registry=registry)
    result = agent._get_mock_response({"message": "hello"})

    assert result.output == "matched"


def test_wrap_mock_response_records_done_tool():
    agent = make_agent()
    recorded = {}

    class FakeToolPrimitive:
        def record_call(self, tool_name, tool_args, tool_result, agent_name=None):
            recorded["tool_name"] = tool_name
            recorded["tool_args"] = tool_args
            recorded["tool_result"] = tool_result
            recorded["agent_name"] = agent_name

    agent._tool_primitive = FakeToolPrimitive()

    result = agent._wrap_mock_response(
        {"response": "ok", "tool_calls": [{"tool": "done", "args": {"reason": "r"}}]},
        {"message": "hi"},
    )

    assert result.output == "ok"
    assert recorded["tool_name"] == "done"
    assert recorded["tool_result"]["reason"] == "r"
    assert recorded["agent_name"] == "agent"


def test_wrap_mock_response_prefers_data_with_schema():
    agent = make_agent(output_schema={"result": {"type": "string", "required": True}})
    result = agent._wrap_mock_response(
        {"response": "ignore", "data": {"result": "ok"}, "tool_calls": []},
        {"message": "hi"},
    )

    assert result.output == "ok"
