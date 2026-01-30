"""Tests for builtin step helpers."""

import pytest

from tactus.testing.steps.builtin import (
    register_builtin_steps,
    _parse_step_string_literal,
    step_tool_called,
    step_tool_not_called,
    step_tool_called_at_least,
    step_tool_called_exactly,
    step_tool_called_with_param,
    step_mock_tool_returns,
    step_state_equals,
    step_state_exists,
    step_state_contains,
    step_output_equals,
    step_output_value_equals,
    step_output_value_fuzzy_match,
    step_output_not_equals,
    step_output_exists,
    step_output_contains,
    step_procedure_completes,
    step_procedure_fails,
    step_stop_reason_equals,
    step_stop_reason_contains,
    step_iterations_less_than,
    step_iterations_between,
    step_agent_turns_at_least,
    step_parameter_equals,
    step_agent_context_includes,
    step_input_set_string,
    step_input_set_number,
    step_input_set_array,
    step_agent_takes_turn,
    step_mock_agent_responds_with,
    step_set_scenario_message,
    step_mock_agent_calls_tool_with_args,
    step_mock_agent_returns_data,
    step_output_matches_pattern,
    step_state_matches_pattern,
    step_stop_reason_matches_pattern,
    step_tool_arg_matches_pattern,
    step_output_value_exists,
    step_output_similar_default,
    step_state_similar_default,
)
from tactus.testing.steps.registry import StepRegistry


class FakeContext:
    def __init__(self):
        self._calls = {
            "search": [
                {"args": {"query": "hello"}},
                {"args": {"query": "world"}},
            ]
        }
        self.mocked = {}

    def tool_called(self, tool):
        return tool in self._calls

    def tool_call_count(self, tool):
        return len(self._calls.get(tool, []))

    def tool_calls(self, tool):
        return self._calls.get(tool, [])

    def mock_tool_returns(self, tool, value):
        self.mocked[tool] = value


class ExtendedContext:
    def __init__(self):
        self._state = {"status": "ok"}
        self._output = {"count": 2, "flag": True, "text": "hello"}
        self._output_value = "hello"
        self._params = {"param": "value"}
        self._inputs = {}
        self.execution_result = {"success": True}
        self._stop_success = True
        self._stop_reason = "done"
        self.iterations = 3
        self._agent_turns = 2
        self._agent_context = "hello world"
        self._ran = False
        self._mock_agent = {}

    def state_get(self, key):
        return self._state.get(key)

    def state_exists(self, key):
        return key in self._state

    def output_get(self, key):
        return self._output.get(key)

    def output_value(self):
        return self._output_value

    def output_exists(self, key):
        return key in self._output

    def stop_success(self):
        return self._stop_success

    def stop_reason(self):
        return self._stop_reason

    def agent_turns(self):
        return self._agent_turns

    def get_params(self):
        return self._params

    def agent_context(self):
        return self._agent_context

    def set_input(self, key, value):
        self._inputs[key] = value

    def run_procedure(self):
        self._ran = True

    def mock_agent_response(self, agent, message, when_message=None):
        self._mock_agent[agent] = {"message": message, "when": when_message}

    def set_scenario_message(self, message):
        self._scenario_message = message

    def mock_agent_tool_call(self, agent, tool, args):
        self._mock_agent.setdefault(agent, {})["tool"] = {"name": tool, "args": args}

    def mock_agent_data(self, agent, data):
        self._mock_agent.setdefault(agent, {})["data"] = data

    def tool_calls(self, tool):
        return [{"args": {"query": "hello"}}]


def test_parse_step_string_literal():
    assert _parse_step_string_literal("'hi'") == ("hi", True)
    assert _parse_step_string_literal('"hi"') == ("hi", True)
    assert _parse_step_string_literal("hi") == ("hi", False)


def test_parse_step_string_literal_invalid_escape():
    parsed, was_quoted = _parse_step_string_literal('"\\x"')
    assert was_quoted is True
    assert parsed == '"\\x"'


def test_parse_step_string_literal_non_string_result(monkeypatch):
    monkeypatch.setattr(
        "tactus.testing.steps.builtin.ast.literal_eval",
        lambda _value: 123,
    )
    parsed, was_quoted = _parse_step_string_literal('"123"')
    assert was_quoted is False
    assert parsed == '"123"'


def test_tool_steps():
    ctx = FakeContext()

    step_tool_called(ctx, "search")
    step_tool_not_called(ctx, "missing")
    step_tool_called_at_least(ctx, "search", "2")
    step_tool_called_exactly(ctx, "search", "2")
    step_tool_called_with_param(ctx, "search", "query", "hello")


def test_mock_tool_returns():
    ctx = FakeContext()

    step_mock_tool_returns(ctx, "search", '"result"')

    assert ctx.mocked["search"] == "result"


def test_mock_tool_returns_requires_context():
    class EmptyContext:
        pass

    with pytest.raises(AssertionError):
        step_mock_tool_returns(EmptyContext(), "search", "ok")


def test_state_and_output_steps():
    ctx = ExtendedContext()

    step_state_equals(ctx, "status", "ok")
    step_state_equals(ctx, "status", '"ok"')
    step_state_exists(ctx, "status")
    step_state_contains(ctx, "status")
    step_output_equals(ctx, "count", "2")
    step_output_equals(ctx, "flag", "true")
    step_output_value_equals(ctx, "hello")
    step_output_not_equals(ctx, "text", "nope")
    step_output_exists(ctx, "text")
    step_output_contains(ctx, "text")


def test_completion_and_iteration_steps():
    ctx = ExtendedContext()

    step_procedure_completes(ctx)
    step_stop_reason_equals(ctx, "done")
    step_stop_reason_contains(ctx, "do")
    step_iterations_less_than(ctx, "5")
    step_iterations_between(ctx, "1", "5")
    step_agent_turns_at_least(ctx, "2")

    ctx._stop_success = False
    step_procedure_fails(ctx)


def test_procedure_started_and_runs_handles_execution_result():
    class RunContext(ExtendedContext):
        def __init__(self):
            super().__init__()
            self.execution_result = None

    ctx = RunContext()
    from tactus.testing.steps.builtin import step_procedure_started, step_procedure_runs

    step_procedure_started(ctx)
    step_procedure_runs(ctx)

    ctx.execution_result = {"success": True}
    step_procedure_runs(ctx)

    ctx.execution_result = {"success": False, "error": "boom"}
    with pytest.raises(AssertionError, match="Procedure execution failed"):
        step_procedure_runs(ctx)


def test_parameter_and_input_steps():
    ctx = ExtendedContext()

    step_parameter_equals(ctx, "param", "value")
    step_agent_context_includes(ctx, "world")
    step_input_set_string(ctx, "name", "Ada")
    step_input_set_number(ctx, "count", "3")
    step_input_set_array(ctx, "items", "1, 2, three")

    assert ctx._inputs["name"] == "Ada"
    assert ctx._inputs["count"] == 3
    assert ctx._inputs["items"] == [1, 2, "three"]


def test_agent_and_regex_steps():
    ctx = ExtendedContext()

    step_agent_takes_turn(ctx, "agent")
    assert ctx._ran is True

    step_mock_agent_responds_with(ctx, "agent", '"hi"')
    step_set_scenario_message(ctx, '"hello"')
    step_mock_agent_calls_tool_with_args(ctx, "agent", "done", '{"ok": True}')
    step_mock_agent_returns_data(ctx, "agent", '{"value": 1}')

    step_output_matches_pattern(ctx, "text", "he.*")
    step_state_matches_pattern(ctx, "status", "o.*")
    step_stop_reason_matches_pattern(ctx, "do.*")
    step_tool_arg_matches_pattern(ctx, "search", "query", "hel.*")


def test_register_builtin_steps_adds_patterns():
    registry = StepRegistry()
    register_builtin_steps(registry)

    patterns = registry.get_all_patterns()
    assert any("the output" in pattern for pattern in patterns)
    assert any("the state" in pattern for pattern in patterns)


def test_output_value_exists_and_similarity_steps():
    ctx = ExtendedContext()

    step_output_value_exists(ctx)
    step_output_similar_default(ctx, "text", "hello")
    step_state_similar_default(ctx, "status", "ok")


def test_output_value_fuzzy_match_any_of():
    ctx = ExtendedContext()

    step_output_value_fuzzy_match(
        ctx,
        'any of ["Hello", "Hi"]',
        "0.9",
    )


def test_output_value_fuzzy_match_invalid_threshold():
    ctx = ExtendedContext()

    with pytest.raises(AssertionError):
        step_output_value_fuzzy_match(ctx, "hello", "nope")


def test_output_not_equals_boolean():
    ctx = ExtendedContext()

    step_output_not_equals(ctx, "flag", "false")


def test_output_value_equals_boolean_and_numeric_coercion():
    ctx = ExtendedContext()
    ctx._output_value = True

    step_output_value_equals(ctx, "true")

    ctx._output_value = "2"
    step_output_value_equals(ctx, "2")

    ctx._output_value = 2
    step_output_value_equals(ctx, "2")


def test_output_not_equals_numeric_actual():
    ctx = ExtendedContext()
    step_output_not_equals(ctx, "count", "3")


def test_output_value_fuzzy_match_any_of_empty_list():
    ctx = ExtendedContext()

    with pytest.raises(AssertionError, match="No expected values provided"):
        step_output_value_fuzzy_match(ctx, "any of []", "0.8")


def test_tool_arg_matches_pattern_skips_missing_param():
    class MissingParamContext(ExtendedContext):
        def tool_calls(self, tool):
            return [{"args": {"other": "value"}}]

    ctx = MissingParamContext()

    with pytest.raises(AssertionError):
        step_tool_arg_matches_pattern(ctx, "search", "query", "hel.*")


def test_regex_steps_invalid_pattern():
    ctx = ExtendedContext()

    with pytest.raises(AssertionError):
        step_output_matches_pattern(ctx, "text", "[")
