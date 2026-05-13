"""Tests for MessageHistoryManager auto-compaction."""

import pytest

from tactus.core.message_history_manager import MessageHistoryManager
from tactus.core.compaction_strategies import RollingSummaryStrategy


class FakeLLM:
    """Mock LLM for testing."""

    def __init__(self, response="Summary"):
        self.response = response

    def invoke(self, prompt):
        return self.response


class ManualCompactionStrategy:
    """Test strategy that always compacts to a fixed result."""

    def __init__(self, compacted_result=None):
        self.compacted_result = compacted_result or [{"role": "system", "content": "Compacted"}]
        self.should_compact_calls = []
        self.compact_calls = []

    def should_compact(self, messages, estimated_tokens, max_tokens):
        self.should_compact_calls.append((len(messages), estimated_tokens, max_tokens))
        return estimated_tokens > max_tokens

    def compact(self, messages, max_tokens):
        self.compact_calls.append((len(messages), max_tokens))
        metadata = {
            "summary": "Test summary",
            "tokens_before": 1000,
            "tokens_after": 200,
            "tokens_saved": 800,
            "messages_summarized": len(messages) - 1,
            "messages_retained": 1,
        }
        return self.compacted_result, metadata


def _make_message(role="user", content="Hello"):
    return {"role": role, "content": content}


# ---------------------------------------------------------------------------
# Constructor and configuration
# ---------------------------------------------------------------------------

def test_manager_accepts_compaction_parameters():
    strategy = ManualCompactionStrategy()
    manager = MessageHistoryManager(
        compaction_strategy=strategy,
        auto_compact=True,
        max_tokens=100,
    )

    assert manager.compaction_strategy is strategy
    assert manager.auto_compact is True
    assert manager.max_tokens == 100


def test_manager_defaults_to_no_compaction():
    manager = MessageHistoryManager()

    assert manager.compaction_strategy is None
    assert manager.auto_compact is False
    assert manager.max_tokens is None


# ---------------------------------------------------------------------------
# Auto-compaction triggers
# ---------------------------------------------------------------------------

def test_auto_compact_triggers_when_over_budget():
    strategy = ManualCompactionStrategy()
    manager = MessageHistoryManager(
        compaction_strategy=strategy,
        auto_compact=True,
        max_tokens=10,  # Very low budget
    )

    # Add messages that exceed budget
    manager.add_message("agent1", _make_message("user", "x" * 200))
    manager.add_message("agent1", _make_message("assistant", "y" * 200))

    history = manager.get_history_for_agent("agent1")

    # Should have been compacted
    assert len(strategy.compact_calls) == 1
    assert history == strategy.compacted_result


def test_auto_compact_does_not_trigger_when_under_budget():
    strategy = ManualCompactionStrategy()
    manager = MessageHistoryManager(
        compaction_strategy=strategy,
        auto_compact=True,
        max_tokens=10000,  # High budget
    )

    manager.add_message("agent1", _make_message("user", "Short"))
    manager.add_message("agent1", _make_message("assistant", "Also short"))

    history = manager.get_history_for_agent("agent1")

    # Should NOT have been compacted
    assert len(strategy.compact_calls) == 0
    assert len(history) == 2


def test_auto_compact_disabled_does_not_compact():
    strategy = ManualCompactionStrategy()
    manager = MessageHistoryManager(
        compaction_strategy=strategy,
        auto_compact=False,  # Disabled
        max_tokens=10,
    )

    manager.add_message("agent1", _make_message("user", "x" * 200))

    history = manager.get_history_for_agent("agent1")

    # Should NOT have been compacted
    assert len(strategy.compact_calls) == 0
    assert len(history) == 1


def test_auto_compact_without_strategy_does_nothing():
    manager = MessageHistoryManager(
        compaction_strategy=None,  # No strategy
        auto_compact=True,
        max_tokens=10,
    )

    manager.add_message("agent1", _make_message("user", "x" * 200))

    # Should not crash
    history = manager.get_history_for_agent("agent1")
    assert len(history) == 1


# ---------------------------------------------------------------------------
# Compaction metadata
# ---------------------------------------------------------------------------

def test_compaction_metadata_stored_after_compaction():
    strategy = ManualCompactionStrategy()
    manager = MessageHistoryManager(
        compaction_strategy=strategy,
        auto_compact=True,
        max_tokens=10,
    )

    manager.add_message("agent1", _make_message("user", "x" * 200))
    manager.get_history_for_agent("agent1")

    metadata = manager.get_compaction_metadata("agent1")
    assert metadata is not None
    assert metadata["summary"] == "Test summary"
    assert metadata["tokens_saved"] == 800


def test_compaction_metadata_none_when_no_compaction():
    manager = MessageHistoryManager(
        compaction_strategy=ManualCompactionStrategy(),
        auto_compact=True,
        max_tokens=10000,
    )

    manager.add_message("agent1", _make_message("user", "Short"))
    manager.get_history_for_agent("agent1")

    metadata = manager.get_compaction_metadata("agent1")
    assert metadata is None


def test_compaction_metadata_per_agent():
    strategy1 = ManualCompactionStrategy()
    strategy2 = ManualCompactionStrategy()
    manager1 = MessageHistoryManager(compaction_strategy=strategy1, auto_compact=True, max_tokens=10)
    manager2 = MessageHistoryManager(compaction_strategy=strategy2, auto_compact=True, max_tokens=10)

    manager1.add_message("agent1", _make_message("user", "x" * 200))
    manager2.add_message("agent2", _make_message("user", "y" * 200))

    manager1.get_history_for_agent("agent1")
    manager2.get_history_for_agent("agent2")

    # Each agent's metadata should be independent
    assert manager1.get_compaction_metadata("agent1") is not None
    assert manager2.get_compaction_metadata("agent2") is not None
    assert manager1.get_compaction_metadata("agent2") is None


# ---------------------------------------------------------------------------
# Integration with RollingSummaryStrategy
# ---------------------------------------------------------------------------

def test_integration_with_rolling_summary_strategy():
    llm = FakeLLM("Summarized: User asked questions, assistant provided answers")
    strategy = RollingSummaryStrategy(llm_backend=llm, recent_window=2)
    manager = MessageHistoryManager(
        compaction_strategy=strategy,
        auto_compact=True,
        max_tokens=50,  # Low budget to trigger compaction
    )

    # Add messages with enough content to exceed 50-token budget
    # 50 tokens * 4 chars/token = 200 chars, so use more than that
    manager.add_message("agent1", _make_message("user", "Old question 1" * 20))  # ~260 chars
    manager.add_message("agent1", _make_message("assistant", "Old answer 1" * 20))
    manager.add_message("agent1", _make_message("user", "Old question 2" * 20))
    manager.add_message("agent1", _make_message("assistant", "Old answer 2" * 20))
    manager.add_message("agent1", _make_message("user", "Recent question" * 5))
    manager.add_message("agent1", _make_message("assistant", "Recent answer" * 5))

    history = manager.get_history_for_agent("agent1")

    # Should have: [summary] + [2 recent messages]
    assert len(history) == 3
    assert history[0]["role"] == "system"
    assert "Summarized" in history[0]["content"]
    assert "Recent question" in history[1]["content"]
    assert "Recent answer" in history[2]["content"]

    # Check metadata
    metadata = manager.get_compaction_metadata("agent1")
    assert metadata is not None
    assert metadata["messages_summarized"] == 4
    assert metadata["messages_retained"] == 3


def test_compaction_with_message_history_config_filter():
    """Test that compaction applies after config filters."""
    from tactus.core.registry import MessageHistoryConfiguration

    strategy = ManualCompactionStrategy(compacted_result=[{"role": "system", "content": "Filtered+Compacted"}])
    manager = MessageHistoryManager(
        compaction_strategy=strategy,
        auto_compact=True,
        max_tokens=10,
    )

    # Add many messages
    for i in range(20):
        manager.add_message("agent1", _make_message("user", f"Message {i}" * 10))

    # Get history with filter that keeps last 5
    config = MessageHistoryConfiguration(source="own", filter=("last_n", 5))
    history = manager.get_history_for_agent("agent1", message_history_config=config)

    # Filter should apply first (reducing to 5), then compaction
    # Strategy's should_compact was called on the 5 filtered messages
    assert len(strategy.should_compact_calls) > 0
    # The filtered result still exceeds budget, so compaction occurred
    assert len(strategy.compact_calls) == 1


def test_empty_history_does_not_trigger_compaction():
    strategy = ManualCompactionStrategy()
    manager = MessageHistoryManager(
        compaction_strategy=strategy,
        auto_compact=True,
        max_tokens=10,
    )

    history = manager.get_history_for_agent("agent1")

    assert history == []
    assert len(strategy.should_compact_calls) == 0
    assert len(strategy.compact_calls) == 0


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

def test_compaction_handles_pydantic_ai_model_messages():
    """Test that compaction works with pydantic_ai ModelMessage objects."""

    class FakeModelMessage:
        def __init__(self, role, content):
            self.role = role
            self.content = content

    strategy = ManualCompactionStrategy()
    manager = MessageHistoryManager(
        compaction_strategy=strategy,
        auto_compact=True,
        max_tokens=10,
    )

    # Add pydantic-style messages
    manager.add_message("agent1", FakeModelMessage("user", "x" * 200))

    history = manager.get_history_for_agent("agent1")

    # Should have been compacted (converted to dict internally)
    assert len(strategy.compact_calls) == 1


def test_multiple_get_history_calls_recompact():
    """Each get_history call should re-evaluate compaction."""
    strategy = ManualCompactionStrategy()
    manager = MessageHistoryManager(
        compaction_strategy=strategy,
        auto_compact=True,
        max_tokens=10,
    )

    manager.add_message("agent1", _make_message("user", "x" * 200))

    # First call
    manager.get_history_for_agent("agent1")
    assert len(strategy.compact_calls) == 1

    # Second call (should re-compact)
    manager.get_history_for_agent("agent1")
    assert len(strategy.compact_calls) == 2
