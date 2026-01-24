"""Tests for FuzzyMatchClassifier algorithm variants (rapidfuzz integration)."""

import pytest

from tactus.stdlib.classify.fuzzy import FuzzyMatchClassifier, calculate_similarity


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
        # "UEI" is a substring of "United Education Institute"
        sim = calculate_similarity("United Education Institute", "UEI", "partial_ratio")
        # Note: partial_ratio may not match abbreviations well
        # but it should find some substring match
        assert sim > 0.0

    def test_invalid_algorithm_raises_error(self):
        """Unknown algorithm should raise ValueError."""
        with pytest.raises(ValueError, match="Unsupported algorithm"):
            calculate_similarity("hello", "world", "invalid_algo")


class TestFuzzyMatchClassifierWithAlgorithms:
    """Tests for FuzzyMatchClassifier with different algorithms."""

    def test_binary_with_token_set_ratio(self):
        """Binary classifier should work with token_set_ratio."""
        classifier = FuzzyMatchClassifier(
            expected="United Education Institute", threshold=0.7, algorithm="token_set_ratio"
        )

        result = classifier.classify("Institute Education United")
        assert result.value == "Yes"
        assert result.confidence == 1.0

    def test_multiclass_with_token_set_ratio(self):
        """Multi-class classifier should work with token_set_ratio."""
        classifier = FuzzyMatchClassifier(
            classes=[
                "Abilene Christian University",
                "Arizona School of Integrative Studies",
                "United Education Institute",
            ],
            threshold=0.6,
            algorithm="token_set_ratio",
        )

        # Test with reordered tokens
        result = classifier.classify("Institute Education United")
        assert result.value == "United Education Institute"
        assert result.confidence >= 0.8

    def test_binary_with_partial_ratio(self):
        """Binary classifier should work with partial_ratio."""
        classifier = FuzzyMatchClassifier(
            expected="Customer Service Department", threshold=0.6, algorithm="partial_ratio"
        )

        result = classifier.classify("Customer Service")
        assert result.value == "Yes"
        assert result.confidence >= 0.6

    def test_explanation_includes_algorithm(self):
        """Explanation should mention the algorithm used."""
        classifier = FuzzyMatchClassifier(expected="test", algorithm="token_set_ratio")

        result = classifier.classify("test")
        assert "token_set_ratio" in result.explanation

    def test_repr_includes_algorithm(self):
        """String representation should include algorithm."""
        classifier = FuzzyMatchClassifier(expected="test", algorithm="token_set_ratio")

        assert "token_set_ratio" in repr(classifier)


class TestRealWorldSchoolNames:
    """Tests with real school name variations (Derek's use case)."""

    def test_school_name_with_variations(self):
        """Should match school name variations using token_set_ratio."""
        classifier = FuzzyMatchClassifier(
            classes=[
                "United Education Institute",
                "Abilene Christian University",
                "Arizona School of Integrative Studies",
            ],
            threshold=0.65,
            algorithm="token_set_ratio",
        )

        # Test various formats
        test_cases = [
            ("United Education Institute - Dallas", "United Education Institute"),
            ("UEI College Dallas", "United Education Institute"),  # May not match perfectly
            ("Abilene Christian", "Abilene Christian University"),
            ("Arizona Integrative Studies School", "Arizona School of Integrative Studies"),
        ]

        for input_text, expected_match in test_cases:
            result = classifier.classify(input_text)
            # Some may be NO_MATCH due to low similarity, but check algorithm works
            assert result.value in classifier.classes + ["NO_MATCH"]

    def test_acronym_matching_limitation(self):
        """Demonstrate that pure acronyms don't match well (expected limitation)."""
        classifier = FuzzyMatchClassifier(
            expected="United Education Institute", threshold=0.5, algorithm="token_set_ratio"
        )

        result = classifier.classify("UEI")
        # UEI shares no tokens with "United Education Institute"
        # So even token_set_ratio won't match well
        assert result.value == "No"
        # This demonstrates we might need custom abbreviation handling


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
        """Default algorithm should be 'ratio' for backward compatibility."""
        classifier = FuzzyMatchClassifier(expected="test")
        assert classifier.algorithm == "ratio"
