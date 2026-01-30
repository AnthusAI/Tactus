import builtins
import sys
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from tactus.primitives.retry import RetryPrimitive


def test_retry_succeeds_after_failures():
    primitive = RetryPrimitive()
    attempts = {"count": 0}

    def flaky():
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise RuntimeError("boom")
        return "ok"

    with patch("tactus.primitives.retry.time.sleep", lambda *_: None):
        result = primitive.with_backoff(flaky, {"max_attempts": 4, "initial_delay": 0.1})

    assert result == "ok"
    assert attempts["count"] == 3


def test_retry_exhausts_attempts():
    primitive = RetryPrimitive()

    def always_fail():
        raise RuntimeError("fail")

    with patch("tactus.primitives.retry.time.sleep", lambda *_: None):
        with pytest.raises(Exception):
            primitive.with_backoff(always_fail, {"max_attempts": 2, "initial_delay": 0})


def test_retry_on_error_callback_and_backoff():
    primitive = RetryPrimitive()
    attempts = {"count": 0}
    errors = []
    delays = []

    def flaky():
        attempts["count"] += 1
        if attempts["count"] < 2:
            raise RuntimeError("boom")
        return "ok"

    def on_error(info):
        errors.append(info)

    with patch("tactus.primitives.retry.time.sleep", lambda delay: delays.append(delay)):
        result = primitive.with_backoff(
            flaky,
            {
                "max_attempts": 3,
                "initial_delay": 0.5,
                "backoff_factor": 2,
                "max_delay": 0.6,
                "on_error": on_error,
            },
        )

    assert result == "ok"
    assert errors[0]["attempt"] == 1
    assert delays == [0.5]


def test_retry_on_error_callback_failure_does_not_stop_retry():
    primitive = RetryPrimitive()
    attempts = {"count": 0}

    def always_fail():
        attempts["count"] += 1
        raise RuntimeError("boom")

    def on_error(_info):
        raise RuntimeError("callback error")

    with patch("tactus.primitives.retry.time.sleep", lambda *_: None):
        with pytest.raises(Exception):
            primitive.with_backoff(always_fail, {"max_attempts": 2, "on_error": on_error})

    assert attempts["count"] == 2


def test_convert_lua_to_python_with_lupa(monkeypatch):
    primitive = RetryPrimitive()
    fake_module = SimpleNamespace(lua_type=lambda value: "table" if isinstance(value, dict) else "")
    monkeypatch.setitem(sys.modules, "lupa", fake_module)

    lua_table = {1: "a", "nested": {2: "b"}}
    converted = primitive._convert_lua_to_python(lua_table)
    assert converted == {1: "a", "nested": {2: "b"}}


def test_convert_lua_to_python_import_error(monkeypatch):
    primitive = RetryPrimitive()
    monkeypatch.delitem(sys.modules, "lupa", raising=False)
    original_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "lupa":
            raise ImportError("missing")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    assert primitive._convert_lua_to_python({"a": 1}) == {"a": 1}


def test_retry_repr():
    assert repr(RetryPrimitive()) == "RetryPrimitive()"


def test_retry_zero_attempts_raises_logic_error():
    primitive = RetryPrimitive()
    with pytest.raises(Exception, match="Retry logic error"):
        primitive.with_backoff(lambda: "ok", {"max_attempts": 0})


def test_convert_lua_to_python_none():
    primitive = RetryPrimitive()
    assert primitive._convert_lua_to_python(None) is None
