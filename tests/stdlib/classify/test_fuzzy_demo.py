"""
Tests for the similarity calculation helper used by the fuzzy matching demo.

The FuzzyMatchClassifier class now lives in .tac code and is tested via
classify.spec.tac. These tests cover the Python calculate_similarity
helper that the .tac code calls via require("tactus.classify.similarity").
"""

import pytest

from tactus.stdlib.classify.similarity import calculate_similarity


class TestSimilarityForSchoolNames:
    """Test similarity calculations with real school name variations."""

    SCHOOLS = [
        "United Education Institute",
        "Abilene Christian University",
        "Arizona School of Integrative Studies",
        "California Institute of Arts and Technology",
        "Florida Technical College",
    ]

    def test_exact_match(self):
        """Exact match should return 1.0."""
        sim = calculate_similarity("United Education Institute", "United Education Institute")
        assert sim >= 0.99

    def test_token_set_ratio_reordered_tokens(self):
        """token_set_ratio should handle reordered tokens."""
        sim = calculate_similarity(
            "United Education Institute",
            "Institute Education United",
            "token_set_ratio",
        )
        assert sim == 1.0

    def test_token_set_ratio_with_extra_words(self):
        """token_set_ratio should handle extra words."""
        sim = calculate_similarity(
            "United Education Institute",
            "United Education Institute - Dallas",
            "token_set_ratio",
        )
        assert sim >= 0.70

    def test_token_sort_ratio_reordered(self):
        """token_sort_ratio should handle reordered words."""
        sim = calculate_similarity(
            "United Education Institute",
            "Institute Education United",
            "token_sort_ratio",
        )
        assert sim >= 0.90

    def test_partial_ratio_shortened_names(self):
        """partial_ratio should match shortened names."""
        sim = calculate_similarity(
            "Florida Technical College", "Florida Tech College", "partial_ratio"
        )
        assert sim >= 0.70

    def test_abbreviation_limitation(self):
        """Pure abbreviations should not match well (documented limitation)."""
        sim = calculate_similarity(
            "United Education Institute", "UEI", "token_set_ratio"
        )
        # UEI shares no tokens with "United Education Institute"
        assert sim < 0.50


class TestConfigurationValidation:
    """Test validation of calculate_similarity parameters."""

    def test_invalid_algorithm_raises_error(self):
        """Invalid algorithm should raise ValueError."""
        with pytest.raises(ValueError, match="Unsupported algorithm"):
            calculate_similarity("test", "test", algorithm="invalid")
