"""Tests for message history compaction strategies."""

import pytest

from tactus.core.compaction_strategies import (
    CompactionStrategy,
    RollingSummaryStrategy,
    DEFAULT_SUMMARY_PROMPT,
)


class FakeLLM:
    """Mock LLM for testing."""

    def __init__(self, response="Summary of conversation"):
        self.response = response
        self.invocations = []

    def invoke(self, prompt):
        self.invocations.append(prompt)
        return self.response


def _make_message(role="user", content="Hello"):
    return {"role": role, "content": content}


# ---------------------------------------------------------------------------
# CompactionStrategy interface
# ---------------------------------------------------------------------------

def test_compaction_strategy_is_abstract():
    with pytest.raises(TypeError):
        # Cannot instantiate abstract class
        CompactionStrategy()


# ---------------------------------------------------------------------------
# RollingSummaryStrategy
# ---------------------------------------------------------------------------

def test_rolling_summary_does_not_compact_when_under_budget():
    strategy = RollingSummaryStrategy(llm_backend=FakeLLM(), recent_window=10)
    messages = [_make_message("user", "Hi"), _make_message("assistant", "Hello")]
    estimated = 5  # Well under budget
    max_tokens = 1000

    assert strategy.should_compact(messages, estimated, max_tokens) is False


def test_rolling_summary_compacts_when_over_budget():
    strategy = RollingSummaryStrategy(llm_backend=FakeLLM(), recent_window=10)
    messages = [_make_message("user", "x" * 10000)]
    estimated = 3000  # Over budget
    max_tokens = 1000

    assert strategy.should_compact(messages, estimated, max_tokens) is True


def test_rolling_summary_preserves_all_when_under_window():
    llm = FakeLLM("Should not be called")
    strategy = RollingSummaryStrategy(llm_backend=llm, recent_window=10)
    messages = [
        _make_message("user", "Message 1"),
        _make_message("assistant", "Response 1"),
        _make_message("user", "Message 2"),
    ]

    compacted, metadata = strategy.compact(messages, max_tokens=1000)

    # No summarization occurred
    assert compacted == messages
    assert metadata["messages_summarized"] == 0
    assert metadata["messages_retained"] == 3
    assert metadata["summary"] == ""
    assert len(llm.invocations) == 0


def test_rolling_summary_summarizes_middle_preserves_recent():
    llm = FakeLLM("Key points: User asked A, B, C. Assistant provided X, Y, Z.")
    strategy = RollingSummaryStrategy(llm_backend=llm, recent_window=2)
    messages = [
        _make_message("user", "Old message 1"),
        _make_message("assistant", "Old response 1"),
        _make_message("user", "Old message 2"),
        _make_message("assistant", "Old response 2"),
        _make_message("user", "Recent message 1"),
        _make_message("assistant", "Recent response 1"),
    ]

    compacted, metadata = strategy.compact(messages, max_tokens=500)

    # Should have: [summary] + [last 2 messages]
    assert len(compacted) == 3
    assert compacted[0]["role"] == "system"
    assert "**Conversation summary:**" in compacted[0]["content"]
    assert "Key points" in compacted[0]["content"]
    assert compacted[1] == messages[-2]
    assert compacted[2] == messages[-1]

    # Metadata
    assert metadata["messages_summarized"] == 4  # First 4 messages
    assert metadata["messages_retained"] == 3  # summary + 2 recent
    assert "Key points" in metadata["summary"]
    # Note: tokens_saved can be negative if summary is longer than original short messages
    assert isinstance(metadata["tokens_saved"], int)


def test_rolling_summary_preserves_leading_system_messages():
    llm = FakeLLM("Summary text")
    strategy = RollingSummaryStrategy(llm_backend=llm, recent_window=2)
    messages = [
        _make_message("system", "System instruction 1"),
        _make_message("system", "System instruction 2"),
        _make_message("user", "Old message"),
        _make_message("assistant", "Old response"),
        _make_message("user", "Recent 1"),
        _make_message("assistant", "Recent 2"),
    ]

    compacted, metadata = strategy.compact(messages, max_tokens=500)

    # Should have: [2 system] + [summary] + [2 recent]
    assert len(compacted) == 5
    assert compacted[0]["role"] == "system"
    assert compacted[0]["content"] == "System instruction 1"
    assert compacted[1]["role"] == "system"
    assert compacted[1]["content"] == "System instruction 2"
    assert compacted[2]["role"] == "system"
    assert "**Conversation summary:**" in compacted[2]["content"]
    assert compacted[3] == messages[-2]
    assert compacted[4] == messages[-1]


def test_rolling_summary_formats_prompt_with_turns():
    llm = FakeLLM("Summary")
    strategy = RollingSummaryStrategy(
        llm_backend=llm,
        recent_window=1,
        summary_prompt_template="Custom template",
    )
    messages = [
        _make_message("user", "Question A"),
        _make_message("assistant", "Answer A"),
        _make_message("user", "Question B"),
    ]

    strategy.compact(messages, max_tokens=100)

    # Check LLM was invoked with formatted turns
    assert len(llm.invocations) == 1
    prompt = llm.invocations[0]
    assert "Custom template" in prompt
    assert "USER turn 1: Question A" in prompt
    assert "ASSISTANT turn 2: Answer A" in prompt


def test_rolling_summary_handles_empty_messages():
    llm = FakeLLM("Empty summary")
    strategy = RollingSummaryStrategy(llm_backend=llm, recent_window=2)

    compacted, metadata = strategy.compact([], max_tokens=100)

    assert compacted == []
    assert metadata["messages_summarized"] == 0
    assert metadata["messages_retained"] == 0
    assert metadata["tokens_before"] == 0
    assert metadata["tokens_after"] == 0


def test_rolling_summary_handles_llm_failure_gracefully():
    class FailingLLM:
        def invoke(self, prompt):
            raise RuntimeError("LLM unavailable")

    strategy = RollingSummaryStrategy(llm_backend=FailingLLM(), recent_window=1)
    messages = [
        _make_message("user", "A"),
        _make_message("assistant", "B"),
        _make_message("user", "C"),
    ]

    compacted, metadata = strategy.compact(messages, max_tokens=50)

    # Summary message should contain error fallback
    summary_msg = next(m for m in compacted if m["role"] == "system")
    assert "Summary generation failed" in summary_msg["content"]


def test_rolling_summary_token_estimation():
    strategy = RollingSummaryStrategy(llm_backend=FakeLLM(), recent_window=2)
    messages = [
        _make_message("user", "a" * 40),  # 40 chars = 10 tokens
        _make_message("assistant", "b" * 80),  # 80 chars = 20 tokens
    ]

    estimated = strategy._estimate_tokens(messages)
    assert estimated == 30  # (40 + 80) / 4


def test_rolling_summary_handles_multipart_content():
    strategy = RollingSummaryStrategy(llm_backend=FakeLLM(), recent_window=2)
    messages = [
        {"role": "user", "content": [{"text": "Part 1"}, {"text": "Part 2"}]},
        _make_message("assistant", "Response"),
    ]

    estimated = strategy._estimate_tokens(messages)
    assert estimated > 0  # Should handle multipart content


def test_default_summary_prompt_template_is_defined():
    assert DEFAULT_SUMMARY_PROMPT
    assert "bullet points" in DEFAULT_SUMMARY_PROMPT.lower()
    assert "decisions" in DEFAULT_SUMMARY_PROMPT.lower()


# ---------------------------------------------------------------------------
# Metadata structure
# ---------------------------------------------------------------------------

def test_compaction_metadata_includes_all_fields():
    llm = FakeLLM("Summary")
    strategy = RollingSummaryStrategy(llm_backend=llm, recent_window=1)
    messages = [
        _make_message("user", "Old"),
        _make_message("user", "Recent"),
    ]

    _, metadata = strategy.compact(messages, max_tokens=50)

    assert "summary" in metadata
    assert "tokens_before" in metadata
    assert "tokens_after" in metadata
    assert "tokens_saved" in metadata
    assert "messages_summarized" in metadata
    assert "messages_retained" in metadata
    assert isinstance(metadata["tokens_saved"], int)
    # tokens_saved can be negative if summary adds more tokens than it replaces
