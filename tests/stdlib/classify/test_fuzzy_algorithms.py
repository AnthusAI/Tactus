"""Tests for string similarity algorithms (rapidfuzz integration).

The FuzzyMatchClassifier class now lives in .tac code. These tests cover
the Python calculate_similarity helper that the .tac code calls.
"""

import pytest

from tactus.stdlib.classify.similarity import calculate_similarity


class TestCalculateSimilarityAlgorithms:
    """Tests for different similarity algorithms."""

    def test_ratio_algorithm_default(self):
        """ratio (default) should be character-level similarity."""
        # Exact match
        assert calculate_similarity("hello", "hello", "ratio") == 1.0

        # Partial match
        sim = calculate_similarity("hello", "hallo", "ratio")
        assert 0.7 < sim < 0.9

    def test_token_set_ratio_handles_reordering(self):
        """token_set_ratio should match regardless of token order."""
        # Same tokens, different order
        sim = calculate_similarity(
            "United Education Institute", "Institute Education United", "token_set_ratio"
        )
        assert sim == 1.0  # Perfect match because same unique tokens

    def test_token_set_ratio_handles_extra_tokens(self):
        """token_set_ratio should handle additional tokens gracefully."""
        # One has extra tokens
        sim = calculate_similarity(
            "United Education Institute",
            "United Education Institute - Dallas Campus",
            "token_set_ratio",
        )
        # Should still have high similarity (shared tokens)
        assert sim > 0.7

    def test_token_sort_ratio_handles_reordering(self):
        """token_sort_ratio should handle reordered tokens."""
        sim = calculate_similarity(
            "Customer Service Department", "Department Service Customer", "token_sort_ratio"
        )
        assert sim == 1.0  # Same tokens sorted

    def test_partial_ratio_finds_substrings(self):
        """partial_ratio should find best substring match."""
        sim = calculate_similarity("United Education Institute", "UEI", "partial_ratio")
        assert sim > 0.0

    def test_invalid_algorithm_raises_error(self):
        """Unknown algorithm should raise ValueError."""
        with pytest.raises(ValueError, match="Unsupported algorithm"):
            calculate_similarity("hello", "world", "invalid_algo")

    def test_empty_strings_return_zero(self):
        """Empty strings should return 0.0 similarity."""
        assert calculate_similarity("", "hello") == 0.0
        assert calculate_similarity("hello", "") == 0.0
        assert calculate_similarity("", "") == 0.0

    def test_case_insensitive(self):
        """Similarity should be case-insensitive."""
        assert calculate_similarity("Hello", "hello") == 1.0
        assert calculate_similarity("HELLO", "hello") == 1.0

    def test_whitespace_stripped(self):
        """Leading/trailing whitespace should be ignored."""
        assert calculate_similarity("  hello  ", "hello") == 1.0


class TestAlgorithmComparison:
    """Compare behavior of different algorithms on same inputs."""

    def test_algorithms_give_different_scores(self):
        """Different algorithms should produce different similarity scores."""
        text1 = "United Education Institute Dallas"
        text2 = "Dallas Institute Education United"

        ratio_sim = calculate_similarity(text1, text2, "ratio")
        token_set_sim = calculate_similarity(text1, text2, "token_set_ratio")
        token_sort_sim = calculate_similarity(text1, text2, "token_sort_ratio")

        # token_set and token_sort should handle reordering better
        assert token_set_sim > ratio_sim
        assert token_sort_sim > ratio_sim

    def test_default_algorithm_is_ratio(self):
        """Default algorithm should be 'ratio'."""
        sim_default = calculate_similarity("hello", "hallo")
        sim_ratio = calculate_similarity("hello", "hallo", "ratio")
        assert sim_default == sim_ratio
