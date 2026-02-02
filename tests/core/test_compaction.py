import pytest

from tactus.core.compaction import (
    CompactionRequest,
    SummaryCompactor,
    TruncateCompactor,
    build_compactor,
)


def test_truncate_compactor():
    compactor = TruncateCompactor()
    result = compactor.compact(CompactionRequest(text="one two three", max_tokens=2))
    assert result == "one two"


def test_summary_compactor_truncates_sentence():
    compactor = SummaryCompactor()
    result = compactor.compact(
        CompactionRequest(text="First sentence here. Second sentence here.", max_tokens=3)
    )
    assert result.split() == ["First", "sentence", "here"]


def test_summary_compactor_returns_empty_when_no_sentence():
    compactor = SummaryCompactor()
    result = compactor.compact(CompactionRequest(text="", max_tokens=3))
    assert result == ""


def test_build_compactor_defaults_to_truncate():
    compactor = build_compactor({})
    result = compactor.compact(CompactionRequest(text="one two three", max_tokens=2))
    assert result == "one two"


def test_build_compactor_raises_for_unknown_type():
    with pytest.raises(ValueError):
        build_compactor({"type": "unknown"})
