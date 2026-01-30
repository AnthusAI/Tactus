"""Tests for safe library wrappers."""

import warnings

from tactus.utils.safe_libraries import (
    DeterminismWarning,
    NonDeterministicError,
    warn_if_unsafe,
    create_safe_math_library,
    create_safe_os_library,
)


class FakeContext:
    def __init__(self, inside=False, strict=False):
        self._inside_checkpoint = inside
        self.strict_determinism = strict


def test_warn_if_unsafe_allows_no_context():
    def func():
        return "ok"

    wrapped = warn_if_unsafe("op()", lambda: None)(func)

    assert wrapped() == "ok"


def test_warn_if_unsafe_emits_warning():
    def func():
        return "ok"

    wrapped = warn_if_unsafe("op()", lambda: FakeContext(inside=False))(func)

    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        assert wrapped() == "ok"

    assert any(isinstance(w.message, DeterminismWarning) for w in captured)


def test_warn_if_unsafe_raises_in_strict_mode():
    def func():
        return "ok"

    wrapped = warn_if_unsafe("op()", lambda: FakeContext(inside=False, strict=True))(func)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            wrapped()
        except NonDeterministicError as exc:
            assert "op()" in str(exc)
        else:
            assert False, "Expected NonDeterministicError"


def test_safe_math_random_variants():
    safe_math = create_safe_math_library(lambda: FakeContext(inside=True))

    assert 0.0 <= safe_math["random"]() < 1.0
    assert 1 <= safe_math["random"](3) <= 3
    assert 2 <= safe_math["random"](2, 4) <= 4
    assert safe_math["randomseed"](123) is None


def test_safe_os_date_formats():
    safe_os = create_safe_os_library(lambda: FakeContext(inside=True))

    default = safe_os["date"]()
    iso = safe_os["date"]("%Y-%m-%dT%H:%M:%SZ")
    custom = safe_os["date"]("%Y")
    fallback = safe_os["date"](object())

    assert "-" in iso
    assert len(custom) == 4
    assert default
    assert fallback


def test_safe_os_time_clock_getenv_tmpname(monkeypatch):
    safe_os = create_safe_os_library(lambda: FakeContext(inside=True))

    assert isinstance(safe_os["time"](), int)
    assert isinstance(safe_os["time"]({"year": 2024}), int)
    assert isinstance(safe_os["clock"](), float)

    monkeypatch.setenv("TACTUS_TEST_ENV", "ok")
    assert safe_os["getenv"]("TACTUS_TEST_ENV") == "ok"

    tmpname = safe_os["tmpname"]()
    assert isinstance(tmpname, str)
    assert tmpname
