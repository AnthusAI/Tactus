import pytest

from tactus.testing.steps import builtin


class DummyContext:
    def __init__(self):
        self.calls = []
        self._output = None
        self.mocked = []
        self._inputs = {}

    def tool_called(self, _tool):
        return True

    def tool_call_count(self, _tool):
        return 2

    def tool_calls(self, _tool):
        return [{"args": {"param": "value"}}]

    def mock_tool_returns(self, tool, value):
        self.mocked.append((tool, value))

    def output_value(self):
        return self._output

    def state_get(self, key):
        return {"key": "value"}.get(key)

    def state_exists(self, key):
        return key == "key"

    def output_get(self, key):
        return {"flag": True, "count": 3, "text": "hello"}.get(key)

    def output_exists(self, key):
        return key in {"flag", "count", "text"}

    def set_input(self, key, value):
        self._inputs[key] = value


def test_parse_step_string_literal_handles_quotes():
    assert builtin._parse_step_string_literal('"hi"') == ("hi", True)
    assert builtin._parse_step_string_literal("'hi'") == ("hi", True)
    assert builtin._parse_step_string_literal("plain") == ("plain", False)


def test_parse_step_string_literal_handles_invalid_literal():
    parsed, was_quoted = builtin._parse_step_string_literal('"\\x"')
    assert parsed == '"\\x"'
    assert was_quoted is True


def test_step_tool_called_helpers():
    ctx = DummyContext()
    builtin.step_tool_called(ctx, "tool")
    builtin.step_tool_called_at_least(ctx, "tool", "1")
    builtin.step_tool_called_exactly(ctx, "tool", "2")


def test_step_tool_called_with_param():
    ctx = DummyContext()
    builtin.step_tool_called_with_param(ctx, "tool", "param", "value")


def test_step_tool_called_with_param_missing_raises():
    ctx = DummyContext()
    with pytest.raises(AssertionError):
        builtin.step_tool_called_with_param(ctx, "tool", "param", "missing")


def test_step_mock_tool_returns_parses_literal():
    ctx = DummyContext()
    builtin.step_mock_tool_returns(ctx, "tool", "123")
    builtin.step_mock_tool_returns(ctx, "tool", '"text"')

    assert ctx.mocked == [("tool", 123), ("tool", "text")]


def test_step_mock_tool_returns_handles_unquoted_string():
    ctx = DummyContext()
    builtin.step_mock_tool_returns(ctx, "tool", "positive")
    assert ctx.mocked == [("tool", "positive")]


def test_step_mock_tool_returns_requires_method():
    class NoMockContext:
        pass

    with pytest.raises(AssertionError):
        builtin.step_mock_tool_returns(NoMockContext(), "tool", "ok")


def test_output_value_fuzzy_match_any_of():
    ctx = DummyContext()
    ctx._output = "Hello there"

    builtin.step_output_value_fuzzy_match(ctx, 'any of ["Hello", "Hi"]', "0.8")


def test_output_value_fuzzy_match_any_of_comma_list():
    ctx = DummyContext()
    ctx._output = "Hey there"

    builtin.step_output_value_fuzzy_match(ctx, "any of hello, hey", "0.4")


def test_output_value_fuzzy_match_any_of_empty():
    ctx = DummyContext()
    ctx._output = "Hello"

    with pytest.raises(AssertionError):
        builtin.step_output_value_fuzzy_match(ctx, "any of ", "0.4")


def test_output_value_fuzzy_match_invalid_threshold():
    ctx = DummyContext()
    ctx._output = "Hello"

    with pytest.raises(AssertionError):
        builtin.step_output_value_fuzzy_match(ctx, "Hello", "not-a-number")


def test_state_steps_and_output_steps():
    ctx = DummyContext()

    builtin.step_state_equals(ctx, "key", "value")
    builtin.step_state_exists(ctx, "key")
    builtin.step_state_contains(ctx, "key")

    builtin.step_output_equals(ctx, "flag", "true")
    builtin.step_output_equals(ctx, "count", "3")
    builtin.step_output_equals(ctx, "text", "hello")
    builtin.step_output_not_equals(ctx, "text", "nope")
    builtin.step_output_exists(ctx, "text")
    builtin.step_output_contains(ctx, "text")


def test_output_equals_handles_quoted_value():
    class OutputContext(DummyContext):
        def output_get(self, key):
            return "hello"

    ctx = OutputContext()
    builtin.step_output_equals(ctx, "text", '"hello"')


def test_output_equals_handles_boolean_string_value():
    class OutputContext(DummyContext):
        def output_get(self, key):
            return "true"

    ctx = OutputContext()
    builtin.step_output_equals(ctx, "flag", "true")


def test_output_equals_handles_numeric_string_value():
    class OutputContext(DummyContext):
        def output_get(self, key):
            return "5"

    ctx = OutputContext()
    builtin.step_output_equals(ctx, "count", "5")


def test_output_equals_falls_back_to_string_comparison():
    class OutputContext(DummyContext):
        def output_get(self, key):
            return "text"

    ctx = OutputContext()
    builtin.step_output_equals(ctx, "text", "text")


def test_output_value_exists_and_equals():
    ctx = DummyContext()
    ctx._output = "Hello"

    builtin.step_output_value_exists(ctx)
    builtin.step_output_value_equals(ctx, '"Hello"')


def test_output_value_equals_handles_boolean_string_value():
    ctx = DummyContext()
    ctx._output = "false"
    builtin.step_output_value_equals(ctx, "false")


def test_output_not_equals_handles_quoted_value():
    class OutputContext(DummyContext):
        def output_get(self, key):
            return "hello"

    ctx = OutputContext()
    builtin.step_output_not_equals(ctx, "text", '"world"')


def test_output_not_equals_handles_boolean_string_value():
    class OutputContext(DummyContext):
        def output_get(self, key):
            return "true"

    ctx = OutputContext()
    builtin.step_output_not_equals(ctx, "flag", "false")


def test_output_not_equals_handles_numeric_string_value():
    class OutputContext(DummyContext):
        def output_get(self, key):
            return "5"

    ctx = OutputContext()
    builtin.step_output_not_equals(ctx, "count", "6")


def test_input_set_number_and_array_helpers():
    ctx = DummyContext()

    builtin.step_input_set_number(ctx, "float", "1.5")
    builtin.step_input_set_number(ctx, "int", "2")
    builtin.step_input_set_array(ctx, "list", '"a", 2')
    builtin.step_input_set_array(ctx, "fallback", "1, 2.5, three")

    assert ctx._inputs["float"] == 1.5
    assert ctx._inputs["int"] == 2
    assert ctx._inputs["list"] == ["a", 2]
    assert ctx._inputs["fallback"] == [1, 2.5, "three"]


def test_mock_agent_steps_validate_context_and_input():
    class AgentContext(DummyContext):
        def __init__(self):
            super().__init__()
            self._agent = {}

        def mock_agent_response(self, agent, message, when_message=None):
            self._agent[agent] = {"message": message, "when": when_message}

        def set_scenario_message(self, message):
            self._message = message

        def mock_agent_tool_call(self, agent, tool, args):
            self._agent.setdefault(agent, {})["tool"] = {"tool": tool, "args": args}

        def mock_agent_data(self, agent, data):
            self._agent.setdefault(agent, {})["data"] = data

    ctx = AgentContext()

    builtin.step_mock_agent_responds_with(ctx, "agent", '"hello"', '"ping"')
    builtin.step_set_scenario_message(ctx, '"hello"')
    builtin.step_mock_agent_calls_tool_with_args(ctx, "agent", "tool", '{"x": 1}')
    builtin.step_mock_agent_returns_data(ctx, "agent", '{"ok": True}')

    assert ctx._agent["agent"]["message"] == "hello"
    assert ctx._agent["agent"]["when"] == "ping"
    assert ctx._message == "hello"
    assert ctx._agent["agent"]["tool"]["args"] == {"x": 1}
    assert ctx._agent["agent"]["data"] == {"ok": True}


def test_mock_agent_steps_reject_invalid_inputs():
    class EmptyContext:
        pass

    with pytest.raises(AssertionError):
        builtin.step_mock_agent_responds_with(EmptyContext(), "agent", "hello")

    with pytest.raises(AssertionError):
        builtin.step_set_scenario_message(EmptyContext(), "hello")

    with pytest.raises(AssertionError):
        builtin.step_mock_agent_calls_tool_with_args(EmptyContext(), "agent", "tool", '{"x": 1}')

    with pytest.raises(AssertionError):
        builtin.step_mock_agent_calls_tool_with_args(DummyContext(), "agent", "tool", "not-json")

    with pytest.raises(AssertionError):
        builtin.step_mock_agent_calls_tool_with_args(DummyContext(), "agent", "tool", "['x']")

    with pytest.raises(AssertionError):
        builtin.step_mock_agent_returns_data(EmptyContext(), "agent", '{"ok": True}')

    with pytest.raises(AssertionError):
        builtin.step_mock_agent_returns_data(DummyContext(), "agent", "not-json")

    with pytest.raises(AssertionError):
        builtin.step_mock_agent_returns_data(DummyContext(), "agent", "['x']")


def test_procedure_runs_raises_on_execution_error():
    class ExecContext(DummyContext):
        def run_procedure(self):
            self.execution_result = {"success": False, "error": "boom"}

    ctx = ExecContext()

    with pytest.raises(AssertionError):
        builtin.step_procedure_runs(ctx)


def test_regex_steps_handle_invalid_patterns():
    class RegexContext(DummyContext):
        def __init__(self):
            super().__init__()
            self._stop_reason = "done"

        def output_get(self, key):
            return "hello"

        def state_get(self, key):
            return "state"

        def stop_reason(self):
            return self._stop_reason

        def tool_calls(self, tool):
            return [{"args": {"query": "hello"}}]

    ctx = RegexContext()

    with pytest.raises(AssertionError):
        builtin.step_output_matches_pattern(ctx, "text", "[")

    with pytest.raises(AssertionError):
        builtin.step_state_matches_pattern(ctx, "status", "[")

    with pytest.raises(AssertionError):
        builtin.step_stop_reason_matches_pattern(ctx, "[")

    with pytest.raises(AssertionError):
        builtin.step_tool_arg_matches_pattern(ctx, "tool", "query", "[")

    with pytest.raises(AssertionError):
        builtin.step_tool_arg_matches_pattern(ctx, "tool", "query", "missing")


def test_model_predicts_runs_procedure():
    class ModelContext(DummyContext):
        def __init__(self):
            super().__init__()
            self.ran = False

        def run_procedure(self):
            self.ran = True

    ctx = ModelContext()
    builtin.step_model_predicts(ctx, "model")
    assert ctx.ran is True
