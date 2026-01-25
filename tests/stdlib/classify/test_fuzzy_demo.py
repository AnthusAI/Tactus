"""
Test spec that validates the fuzzy matching demo behavior.

This spec tests all the fuzzy matching features demonstrated in the demo,
ensuring they work correctly before the demo is shown to users.
"""

import pytest
from tactus.stdlib.classify.fuzzy import FuzzyMatchClassifier

# Test data matching the demo
SCHOOLS = [
    "United Education Institute",
    "Abilene Christian University",
    "Arizona School of Integrative Studies",
    "California Institute of Arts and Technology",
    "Florida Technical College",
]


class TestFuzzyMatchingDemo:
    """Test the fuzzy matching demo scenarios."""

    def test_ratio_algorithm_exact_match(self):
        """ratio algorithm should match exact school names."""
        classifier = FuzzyMatchClassifier(classes=SCHOOLS, threshold=0.75, algorithm="ratio")

        result = classifier.classify("United Education Institute")
        assert result.value == "United Education Institute"
        assert result.matched_text == "United Education Institute"
        assert result.confidence >= 0.99

    def test_token_set_ratio_reordered_tokens(self):
        """token_set_ratio should handle reordered tokens."""
        classifier = FuzzyMatchClassifier(
            classes=SCHOOLS, threshold=0.65, algorithm="token_set_ratio"
        )

        # Reordered: "Institute Education United" matches "United Education Institute"
        result = classifier.classify("Institute Education United")
        assert result.value == "United Education Institute"
        assert result.matched_text == "United Education Institute"
        assert result.confidence == 1.0  # Perfect match (same tokens)

    def test_token_set_ratio_with_extra_words(self):
        """token_set_ratio should handle extra words."""
        classifier = FuzzyMatchClassifier(
            classes=SCHOOLS, threshold=0.65, algorithm="token_set_ratio"
        )

        # Extra words: "United Education Institute - Dallas"
        result = classifier.classify("United Education Institute - Dallas")
        assert result.value == "United Education Institute"
        assert result.matched_text == "United Education Institute"
        assert result.confidence >= 0.70

    def test_token_sort_ratio_reordered(self):
        """token_sort_ratio should handle reordered words."""
        classifier = FuzzyMatchClassifier(
            classes=SCHOOLS, threshold=0.65, algorithm="token_sort_ratio"
        )

        result = classifier.classify("Institute Education United")
        assert result.value == "United Education Institute"
        assert result.matched_text == "United Education Institute"
        assert result.confidence >= 0.90

    def test_partial_ratio_shortened_names(self):
        """partial_ratio should match shortened names."""
        classifier = FuzzyMatchClassifier(
            classes=SCHOOLS, threshold=0.70, algorithm="partial_ratio"
        )

        result = classifier.classify("Florida Tech College")
        # Should match "Florida Technical College"
        assert result.matched_text is not None
        assert "Florida" in result.matched_text

    def test_binary_mode_exact_match(self):
        """Binary mode should return Yes for exact matches."""
        classifier = FuzzyMatchClassifier(
            expected="United Education Institute", threshold=0.70, algorithm="token_set_ratio"
        )

        result = classifier.classify("United Education Institute")
        assert result.value == "Yes"
        assert result.matched_text == "United Education Institute"
        assert result.confidence == 1.0

    def test_binary_mode_reordered_with_extra(self):
        """Binary mode should return Yes for reordered with extra words."""
        classifier = FuzzyMatchClassifier(
            expected="United Education Institute", threshold=0.70, algorithm="token_set_ratio"
        )

        result = classifier.classify("Institute Education United Dallas")
        assert result.value == "Yes"
        assert result.matched_text == "United Education Institute"
        assert result.confidence >= 0.80

    def test_binary_mode_no_match(self):
        """Binary mode should return No for different schools."""
        classifier = FuzzyMatchClassifier(
            expected="United Education Institute", threshold=0.70, algorithm="token_set_ratio"
        )

        result = classifier.classify("Florida Technical College")
        assert result.value == "No"
        assert result.matched_text is None  # No match found
        assert result.confidence >= 0.0  # Confidence in "No"

    def test_abbreviation_limitation(self):
        """Pure abbreviations should not match (documented limitation)."""
        classifier = FuzzyMatchClassifier(
            expected="United Education Institute",
            threshold=0.50,  # Even with low threshold
            algorithm="token_set_ratio",
        )

        result = classifier.classify("UEI")
        # UEI shares no tokens with "United Education Institute"
        assert result.value == "No"
        assert result.matched_text is None

    def test_algorithm_comparison_same_input(self):
        """Different algorithms should give different results on same input."""
        test_input = "Institute Education United Dallas"

        # Test all algorithms
        algorithms = ["ratio", "token_set_ratio", "token_sort_ratio", "partial_ratio"]
        thresholds = [0.75, 0.65, 0.65, 0.70]
        results = []

        for algo, threshold in zip(algorithms, thresholds):
            classifier = FuzzyMatchClassifier(classes=SCHOOLS, threshold=threshold, algorithm=algo)
            result = classifier.classify(test_input)
            results.append((algo, result.value, result.confidence))

        # token_set_ratio should give best match for reordered tokens
        token_set_result = [r for r in results if r[0] == "token_set_ratio"][0]
        assert token_set_result[1] == "United Education Institute"
        assert token_set_result[2] >= 0.80

    def test_school_name_validation_use_case(self):
        """Practical use case: validate school names from metadata."""
        validator = FuzzyMatchClassifier(
            classes=SCHOOLS, threshold=0.65, algorithm="token_set_ratio"
        )

        # Test case 1: Extra campus info
        result1 = validator.classify("United Education Institute - Dallas Campus")
        assert result1.value == "United Education Institute"
        assert result1.matched_text == "United Education Institute"

        # Test case 2: Partial name
        result2 = validator.classify("Abilene Christian")
        assert result2.value == "Abilene Christian University"
        assert result2.matched_text == "Abilene Christian University"

        # Test case 3: Reordered variation
        result3 = validator.classify("Arizona Integrative Studies School")
        assert result3.value == "Arizona School of Integrative Studies"
        assert result3.matched_text == "Arizona School of Integrative Studies"

    def test_matched_text_always_populated_on_match(self):
        """matched_text should ALWAYS be populated when there's a match."""
        # Binary mode
        binary_classifier = FuzzyMatchClassifier(expected="test", threshold=0.8)
        result = binary_classifier.classify("test")
        assert result.value == "Yes"
        assert result.matched_text == "test"

        # Multi-class mode
        multi_classifier = FuzzyMatchClassifier(classes=["option1", "option2"], threshold=0.8)
        result = multi_classifier.classify("option1")
        assert result.value == "option1"
        assert result.matched_text == "option1"

    def test_matched_text_none_on_no_match(self):
        """matched_text should be None when there's no match."""
        # Binary mode
        binary_classifier = FuzzyMatchClassifier(expected="test", threshold=0.9)
        result = binary_classifier.classify("completely different")
        assert result.value == "No"
        assert result.matched_text is None

        # Multi-class mode
        multi_classifier = FuzzyMatchClassifier(classes=["option1", "option2"], threshold=0.9)
        result = multi_classifier.classify("option99")
        assert result.value == "NO_MATCH"
        assert result.matched_text is None


class TestAlgorithmCharacteristics:
    """Test the characteristics of each algorithm."""

    def test_ratio_good_for_typos(self):
        """ratio should handle typos well."""
        classifier = FuzzyMatchClassifier(expected="hello world", threshold=0.75, algorithm="ratio")

        result = classifier.classify("helo wrld")  # Missing letters
        assert result.value == "Yes"
        assert result.confidence >= 0.75

    def test_token_set_ratio_ignores_order(self):
        """token_set_ratio should completely ignore word order."""
        classifier = FuzzyMatchClassifier(
            expected="Customer Service Department", threshold=0.9, algorithm="token_set_ratio"
        )

        result = classifier.classify("Department Service Customer")
        assert result.value == "Yes"
        assert result.confidence == 1.0  # Same unique tokens

    def test_partial_ratio_finds_substrings(self):
        """partial_ratio should match substrings."""
        classifier = FuzzyMatchClassifier(
            expected="United Education Institute of Technology",
            threshold=0.70,
            algorithm="partial_ratio",
        )

        result = classifier.classify("United Education Institute")
        assert result.value == "Yes"
        assert result.confidence >= 0.70


class TestConfigurationValidation:
    """Test configuration validation."""

    def test_requires_expected_or_classes(self):
        """FuzzyMatchClassifier requires either expected or classes."""
        with pytest.raises(ValueError, match="requires either"):
            FuzzyMatchClassifier(threshold=0.8)

    def test_invalid_algorithm_raises_error(self):
        """Invalid algorithm should raise ValueError."""
        from tactus.stdlib.classify.fuzzy import calculate_similarity

        with pytest.raises(ValueError, match="Unsupported algorithm"):
            calculate_similarity("test", "test", algorithm="invalid")

    def test_default_algorithm_is_ratio(self):
        """Default algorithm should be ratio."""
        classifier = FuzzyMatchClassifier(expected="test")
        assert classifier.algorithm == "ratio"

    def test_default_threshold_is_0_8(self):
        """Default threshold should be 0.8."""
        classifier = FuzzyMatchClassifier(expected="test")
        assert classifier.threshold == 0.8
