"""
Tests for step registry.
"""

import pytest

from tactus.testing.steps.registry import StepRegistry


def test_register_and_match_simple_step():
    """Test registering and matching a simple step."""
    registry = StepRegistry()

    def my_step(context):
        pass

    registry.register(r"the user is logged in", my_step)

    func, match_dict = registry.match("the user is logged in")
    assert func == my_step
    assert match_dict == {}


def test_register_and_match_with_capture_groups():
    """Test step with regex capture groups."""
    registry = StepRegistry()

    def my_step(context, tool):
        pass

    registry.register(r"the (?P<tool>\w+) tool should be called", my_step)

    func, match_dict = registry.match("the search tool should be called")
    assert func == my_step
    assert match_dict == {"tool": "search"}


def test_match_returns_none_for_no_match():
    """Test that match returns None when no pattern matches."""
    registry = StepRegistry()

    def my_step(context):
        pass

    registry.register(r"the user is logged in", my_step)

    result = registry.match("the user is logged out")
    assert result is None


def test_register_multiple_steps():
    """Test registering multiple steps."""
    registry = StepRegistry()

    def step1(context):
        pass

    def step2(context):
        pass

    registry.register(r"step one", step1)
    registry.register(r"step two", step2)

    func1, _ = registry.match("step one")
    func2, _ = registry.match("step two")

    assert func1 == step1
    assert func2 == step2


def test_case_insensitive_matching():
    """Test that step matching is case insensitive."""
    registry = StepRegistry()

    def my_step(context):
        pass

    registry.register(r"the user is logged in", my_step)

    # Should match regardless of case
    func, _ = registry.match("THE USER IS LOGGED IN")
    assert func == my_step

    func, _ = registry.match("The User Is Logged In")
    assert func == my_step


def test_get_all_patterns():
    """Test getting all registered patterns."""
    registry = StepRegistry()

    def step1(context):
        pass

    def step2(context):
        pass

    registry.register(r"pattern one", step1)
    registry.register(r"pattern two", step2)

    patterns = registry.get_all_patterns()
    assert "pattern one" in patterns
    assert "pattern two" in patterns
    assert len(patterns) == 2


def test_clear_registry():
    """Test clearing all registered steps."""
    registry = StepRegistry()

    def my_step(context):
        pass

    registry.register(r"some step", my_step)
    assert len(registry.get_all_patterns()) == 1

    registry.clear()
    assert len(registry.get_all_patterns()) == 0
    assert registry.match("some step") is None


def test_invalid_regex_pattern():
    """Test that invalid regex pattern raises error."""
    registry = StepRegistry()

    def my_step(context):
        pass

    with pytest.raises(ValueError, match="Invalid step pattern"):
        registry.register(r"invalid [regex", my_step)
