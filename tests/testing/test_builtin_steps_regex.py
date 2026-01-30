import pytest

from tactus.testing.steps import builtin


class RegexContext:
    def output_get(self, _key):
        return "hello world"

    def state_get(self, _key):
        return "value-123"

    def stop_reason(self):
        return "completed"

    def tool_calls(self, _tool):
        return [{"args": {"param": "value-123"}}]


def test_regex_steps_match():
    ctx = RegexContext()
    builtin.step_output_matches_pattern(ctx, "key", "hello")
    builtin.step_state_matches_pattern(ctx, "key", r"value-\d+")
    builtin.step_stop_reason_matches_pattern(ctx, "complete")
    builtin.step_tool_arg_matches_pattern(ctx, "tool", "param", r"\d+")


def test_regex_steps_invalid_pattern_raises():
    ctx = RegexContext()
    with pytest.raises(AssertionError):
        builtin.step_output_matches_pattern(ctx, "key", "(")
