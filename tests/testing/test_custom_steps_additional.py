import pytest

from tactus.testing.steps.custom import CustomStepManager


def test_register_from_lua_rejects_invalid_regex():
    manager = CustomStepManager()
    with pytest.raises(ValueError):
        manager.register_from_lua("(", lambda *_a: None)


def test_execute_returns_false_when_no_match():
    manager = CustomStepManager()
    assert manager.execute("no match", object()) is False


def test_execute_raises_on_failure():
    manager = CustomStepManager()

    def bad_step(*_args):
        raise RuntimeError("boom")

    manager.register_from_lua("step (.+)", bad_step)
    with pytest.raises(AssertionError):
        manager.execute("step value", object())


def test_execute_by_pattern_missing_returns_false():
    manager = CustomStepManager()
    assert manager.execute_by_pattern("missing", object()) is False
