from types import SimpleNamespace


from tactus.testing.mock_agent import MockAgentPrimitive, MockAgentResult


class DummyToolPrimitive:
    def __init__(self, fail: bool = False):
        self.calls = []
        self.fail = fail

    def record_call(self, tool_name, args):
        self.calls.append((tool_name, args))
        if self.fail:
            raise RuntimeError("boom")
        return {"ok": True, "tool": tool_name}


class DummyInputs:
    def __init__(self, message=""):
        self.message = message

    def items(self):
        raise TypeError("not a mapping")

    def get(self, key, default=None):
        if key == "message":
            return self.message
        return default


def test_mock_agent_result_repr_and_new_messages_fallback():
    def broken_table_from(_messages):
        raise RuntimeError("nope")

    result = MockAgentResult(
        message="hi",
        tool_calls=[{"tool": "done"}],
        data={"a": 1},
        usage={"total_tokens": "bad"},
        new_messages=[{"role": "assistant", "content": "hi"}],
        lua_table_from=broken_table_from,
    )

    assert "MockAgentResult" in repr(result)
    assert result.new_messages() == [{"role": "assistant", "content": "hi"}]
    assert result.tokens == 0


def test_mock_agent_init_uses_lua_table_from():
    def table_from(messages):
        return {"items": messages}

    agent = MockAgentPrimitive(
        name="agent",
        tool_primitive=None,
        lua_table_from=table_from,
    )

    assert agent._lua_table_from is table_from


def test_mock_agent_init_uses_lua_runtime_table_from():
    lua_runtime = SimpleNamespace(table_from=lambda messages: {"items": messages})
    agent = MockAgentPrimitive(
        name="agent",
        tool_primitive=None,
        lua_runtime=lua_runtime,
    )

    assert agent._lua_table_from is lua_runtime.table_from


def test_mock_agent_turn_temporal_selects_by_when_message():
    mock_config = SimpleNamespace(
        message="default",
        tool_calls=[],
        data={},
        usage={},
        temporal=[
            {"when_message": "ping", "message": "matched"},
            {"message": "fallback"},
        ],
    )
    registry = SimpleNamespace(agent_mocks={"agent": mock_config})
    agent = MockAgentPrimitive(name="agent", tool_primitive=None, registry=registry)

    result = agent.turn({"message": "ping"})

    assert result.message == "matched"


def test_mock_agent_turn_temporal_index_clamps():
    mock_config = SimpleNamespace(
        message="default",
        tool_calls=[],
        data={},
        usage={},
        temporal=[{"message": "first"}],
    )
    registry = SimpleNamespace(agent_mocks={"agent": mock_config})
    agent = MockAgentPrimitive(name="agent", tool_primitive=None, registry=registry)
    agent.turn_count = -1

    result = agent.turn({})

    assert result.message == "first"


def test_mock_agent_turn_temporal_index_clamps_high():
    mock_config = SimpleNamespace(
        message="default",
        tool_calls=[],
        data={},
        usage={},
        temporal=[{"message": "first"}],
    )
    registry = SimpleNamespace(agent_mocks={"agent": mock_config})
    agent = MockAgentPrimitive(name="agent", tool_primitive=None, registry=registry)
    agent.turn_count = 5

    result = agent.turn({})

    assert result.message == "first"


def test_mock_agent_turn_temporal_non_dict_turn():
    mock_config = SimpleNamespace(
        message="default",
        tool_calls=[],
        data={},
        usage={},
        temporal=["fallback"],
    )
    registry = SimpleNamespace(agent_mocks={"agent": mock_config})
    agent = MockAgentPrimitive(name="agent", tool_primitive=None, registry=registry)

    result = agent.turn({})

    assert result.message == "default"


def test_mock_agent_turn_temporal_no_match_uses_index():
    mock_config = SimpleNamespace(
        message="default",
        tool_calls=[],
        data={},
        usage={},
        temporal=[
            {"when_message": "other", "message": "first"},
            {"message": "second"},
        ],
    )
    registry = SimpleNamespace(agent_mocks={"agent": mock_config})
    agent = MockAgentPrimitive(name="agent", tool_primitive=None, registry=registry)

    result = agent.turn({"message": "missing"})

    assert result.message == "first"


def test_mock_agent_turn_usage_total_tokens_defaulted():
    mock_config = SimpleNamespace(
        message="default",
        tool_calls=[],
        data={},
        usage={"prompt_tokens": 2, "completion_tokens": 3},
    )
    registry = SimpleNamespace(agent_mocks={"agent": mock_config})
    agent = MockAgentPrimitive(name="agent", tool_primitive=None, registry=registry)

    result = agent.turn({})

    assert result.usage["total_tokens"] == 5


def test_mock_agent_turn_fills_default_data_and_messages():
    mock_config = SimpleNamespace(
        message="hello",
        tool_calls=[],
        data={},
        usage={},
    )
    registry = SimpleNamespace(agent_mocks={"agent": mock_config})
    agent = MockAgentPrimitive(name="agent", tool_primitive=None, registry=registry)

    result = agent.turn({})

    assert result.data["response"] == "hello"
    assert result.new_messages() == [{"role": "assistant", "content": "hello"}]


def test_mock_agent_turn_preserves_data_and_usage():
    mock_config = SimpleNamespace(
        message="hello",
        tool_calls=[],
        data={"ok": True},
        usage={"total_tokens": 7},
    )
    registry = SimpleNamespace(agent_mocks={"agent": mock_config})
    agent = MockAgentPrimitive(name="agent", tool_primitive=None, registry=registry)

    result = agent.turn({"message": "hi"})

    assert result.data == {"ok": True}
    assert result.usage["total_tokens"] == 7
    assert result.new_messages() == [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "hello"},
    ]


def test_mock_agent_turn_without_message_skips_assistant_entry():
    mock_config = SimpleNamespace(
        message="",
        tool_calls=[],
        data={},
        usage={},
    )
    registry = SimpleNamespace(agent_mocks={"agent": mock_config})
    agent = MockAgentPrimitive(name="agent", tool_primitive=None, registry=registry)

    result = agent.turn({})

    assert result.new_messages() == []


def test_execute_tool_calls_handles_missing_tool_name_and_exception():
    tool_primitive = DummyToolPrimitive(fail=True)
    mock_config = SimpleNamespace(
        message="default",
        tool_calls=[{"tool": ""}, {"tool": "done", "args": {"x": 1}}],
        data={},
        usage={},
    )
    registry = SimpleNamespace(agent_mocks={"agent": mock_config})
    agent = MockAgentPrimitive(name="agent", tool_primitive=tool_primitive, registry=registry)

    result = agent.turn({})

    assert len(result.tool_calls) == 1
    assert result.tool_calls[0]["tool"] == "done"
    assert result.tool_calls[0]["result"]["tool"] == "done"


def test_execute_tool_calls_skips_record_call_without_tool_primitive():
    mock_config = SimpleNamespace(
        message="default",
        tool_calls=[{"tool": "done", "args": {}}],
        data={},
        usage={},
    )
    registry = SimpleNamespace(agent_mocks={"agent": mock_config})
    agent = MockAgentPrimitive(name="agent", tool_primitive=None, registry=registry)

    result = agent.turn({})

    assert result.tool_calls[0]["result"] is None


def test_mock_agent_call_handles_bad_items_and_message_logging():
    mock_config = SimpleNamespace(
        message="default",
        tool_calls=[],
        data={},
        usage={},
    )
    registry = SimpleNamespace(agent_mocks={"agent": mock_config})
    agent = MockAgentPrimitive(name="agent", tool_primitive=None, registry=registry)

    result = agent(DummyInputs(message="hello"))

    assert result.message == "default"


def test_mock_agent_call_converts_mapping_inputs():
    mock_config = SimpleNamespace(
        message="default",
        tool_calls=[],
        data={},
        usage={},
    )
    registry = SimpleNamespace(agent_mocks={"agent": mock_config})
    agent = MockAgentPrimitive(name="agent", tool_primitive=None, registry=registry)

    result = agent({"message": "hello"})

    assert result.message == "default"


def test_mock_agent_call_skips_mapping_conversion_when_missing_items():
    class InputsNoItems:
        def get(self, key, default=None):
            return default

    mock_config = SimpleNamespace(
        message="default",
        tool_calls=[],
        data={},
        usage={},
    )
    registry = SimpleNamespace(agent_mocks={"agent": mock_config})
    agent = MockAgentPrimitive(name="agent", tool_primitive=None, registry=registry)

    result = agent(InputsNoItems())

    assert result.message == "default"


def test_get_agent_mock_config_missing_registry_entry():
    registry = SimpleNamespace(agent_mocks={})
    agent = MockAgentPrimitive(name="agent", tool_primitive=None, registry=registry)

    assert agent._get_agent_mock_config() is None


def test_get_agent_mock_config_missing_agent_mocks_attr():
    agent = MockAgentPrimitive(name="agent", tool_primitive=None, registry=SimpleNamespace())

    assert agent._get_agent_mock_config() is None


def test_mock_agent_repr():
    agent = MockAgentPrimitive(name="agent", tool_primitive=None)

    assert "MockAgentPrimitive" in repr(agent)
