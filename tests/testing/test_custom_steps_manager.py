"""Tests for custom step manager."""

import pytest

from tactus.testing.steps.custom import CustomStepManager


def test_register_and_execute():
    manager = CustomStepManager()
    called = {}

    def func(ctx, value):
        called["value"] = value

    manager.register_from_lua(r"value (\d+)", func)

    assert manager.execute("value 42", context={}) is True
    assert called["value"] == "42"


def test_register_invalid_pattern_raises():
    manager = CustomStepManager()

    with pytest.raises(ValueError):
        manager.register_from_lua("(", lambda ctx: None)


def test_execute_unknown_returns_false():
    manager = CustomStepManager()

    assert manager.execute("no match", context={}) is False


def test_execute_returns_false_when_pattern_does_not_match():
    manager = CustomStepManager()
    manager.register_from_lua(r"value (\d+)", lambda _ctx, _v: None)

    assert manager.execute("value nope", context={}) is False


def test_execute_by_pattern():
    manager = CustomStepManager()
    called = {}

    def func(ctx, value):
        called["value"] = value

    pattern = r"value (\d+)"
    manager.register_from_lua(pattern, func)

    assert manager.execute_by_pattern(pattern, {}, "7") is True
    assert called["value"] == "7"


def test_execute_raises_when_custom_step_fails():
    manager = CustomStepManager()

    def boom(_ctx):
        raise RuntimeError("nope")

    manager.register_from_lua(r"boom", boom)

    with pytest.raises(AssertionError, match="Custom step failed"):
        manager.execute("boom", context={})


def test_execute_by_pattern_handles_missing_handler():
    manager = CustomStepManager()

    def func(_ctx):
        return None

    pattern = r"hello"
    manager.register_from_lua(pattern, func)
    manager._steps.clear()

    assert manager.execute_by_pattern(pattern, {}, "unused") is False


def test_execute_by_pattern_raises_when_handler_fails():
    manager = CustomStepManager()

    def boom(_ctx, *_args):
        raise RuntimeError("nope")

    pattern = r"hi"
    manager.register_from_lua(pattern, boom)

    with pytest.raises(AssertionError, match="Custom step failed"):
        manager.execute_by_pattern(pattern, {}, "there")


def test_has_step_and_clear():
    manager = CustomStepManager()
    manager.register_from_lua(r"hello", lambda ctx: None)

    assert manager.has_step("hello") is True

    manager.clear()
    assert manager.get_all_patterns() == []
