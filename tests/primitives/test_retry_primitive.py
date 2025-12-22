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
