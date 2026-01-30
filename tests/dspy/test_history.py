"""Tests for TactusHistory wrapper."""

import pytest

from tactus.dspy.history import TactusHistory, create_history


def test_add_and_get_messages():
    history = TactusHistory()
    history.add({"role": "user", "content": "hi"})
    history.add({"role": "assistant", "content": "hello"})

    assert len(history) == 2
    assert history.get()[-1]["content"] == "hello"


def test_add_invalid_message_raises():
    history = TactusHistory()

    with pytest.raises(ValueError):
        history.add({"content": "hi"})

    with pytest.raises(ValueError):
        history.add({"role": "bad", "content": "hi"})

    with pytest.raises(ValueError):
        history.add({"role": "user"})


def test_add_accepts_message_like_and_legacy():
    history = TactusHistory()

    class DummyMessage:
        def to_dict(self):
            return {"role": "user", "content": "hey"}

    history.add(DummyMessage())
    history.add({"role": "user", "content": "Q?"})
    history.add({"role": "assistant", "content": "A"})
    history.add({"role": "user", "content": "ignored", "question": "What?", "answer": "Because"})
    history.add({"role": "assistant", "content": "ignored", "answer": "Only answer"})

    assert len(history.get()) == 5


def test_add_rejects_non_dict_message():
    history = TactusHistory()
    with pytest.raises(ValueError, match="Message must be a dictionary"):
        history.add("bad")


def test_add_accepts_mapping_with_items():
    history = TactusHistory()

    class Mapping:
        def items(self):
            return [("role", "user"), ("content", "hi")]

    history.add(Mapping())
    assert history.get()[0]["content"] == "hi"


def test_add_mapping_items_failure_raises():
    history = TactusHistory()

    class BadMapping:
        def items(self):
            raise AttributeError("boom")

    with pytest.raises(ValueError, match="Message must be a dictionary"):
        history.add(BadMapping())


def test_context_window_and_token_limit():
    history = TactusHistory()
    history.add({"role": "user", "content": "hello world"})
    history.add({"role": "assistant", "content": "response"})

    assert len(history.get(context_window=1)) == 1
    limited = history.get(token_limit=5)
    assert len(limited) <= 2


def test_token_limit_too_small_returns_empty():
    history = TactusHistory()
    history.add({"role": "user", "content": "short"})
    history.add({"role": "assistant", "content": "this is a much longer message"})

    limited = history.get(token_limit=3)
    assert limited == []


def test_token_limit_includes_messages_when_budget_allows():
    history = TactusHistory()
    history.add({"role": "user", "content": "short"})
    history.add({"role": "assistant", "content": "ok"})

    limited = history.get(token_limit=50)

    assert [msg["role"] for msg in limited] == ["user", "assistant"]


def test_to_from_dspy_history():
    history = TactusHistory([{"role": "user", "content": "hi"}])
    dspy_history = history.to_dspy()

    roundtrip = TactusHistory.from_dspy(dspy_history)

    assert roundtrip.get()[0]["content"] == "hi"


def test_count_tokens_and_iter():
    history = TactusHistory()
    history.add({"role": "user", "content": "hello"})
    history.add({"role": "assistant", "content": "world"})

    assert history.count_tokens() > 0
    assert [msg["role"] for msg in history] == ["user", "assistant"]


def test_create_history_helper():
    history = create_history([{"role": "user", "content": "hi"}])
    assert len(history) == 1
