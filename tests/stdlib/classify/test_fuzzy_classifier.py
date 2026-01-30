"""Tests for the FuzzyMatchClassifier."""

import difflib

import pytest

import tactus.stdlib.classify.fuzzy as fuzzy_module
from tactus.stdlib.classify.fuzzy import (
    FuzzyMatchClassifier,
    FuzzyClassifier,
    calculate_similarity,
)
from tactus.stdlib.core.models import ClassifierResult


class TestCalculateSimilarity:
    """Tests for the calculate_similarity function."""

    def test_identical_strings(self):
        """Identical strings should have similarity of 1.0."""
        assert calculate_similarity("hello", "hello") == 1.0

    def test_empty_strings(self):
        """Empty strings should have similarity of 0.0."""
        assert calculate_similarity("", "") == 0.0
        assert calculate_similarity("hello", "") == 0.0
        assert calculate_similarity("", "hello") == 0.0

    def test_case_insensitive(self):
        """Similarity should be case-insensitive."""
        assert calculate_similarity("Hello", "HELLO") == 1.0
        assert calculate_similarity("Customer Service", "customer service") == 1.0

    def test_whitespace_trimmed(self):
        """Leading/trailing whitespace should be trimmed."""
        assert calculate_similarity("  hello  ", "hello") == 1.0

    def test_partial_match(self):
        """Partial matches should return value between 0 and 1."""
        sim = calculate_similarity("hello", "hallo")
        assert 0.5 < sim < 1.0

    def test_no_match(self):
        """Completely different strings should have low similarity."""
        sim = calculate_similarity("abc", "xyz")
        assert sim < 0.5

    def test_difflib_fallback_ratio(self, monkeypatch):
        monkeypatch.setattr(fuzzy_module, "HAS_RAPIDFUZZ", False)
        monkeypatch.setattr(fuzzy_module, "SequenceMatcher", difflib.SequenceMatcher, raising=False)
        assert calculate_similarity("hello", "hello") == 1.0

    def test_difflib_fallback_rejects_other_algorithms(self, monkeypatch):
        monkeypatch.setattr(fuzzy_module, "HAS_RAPIDFUZZ", False)
        monkeypatch.setattr(fuzzy_module, "SequenceMatcher", difflib.SequenceMatcher, raising=False)
        with pytest.raises(ValueError, match="rapidfuzz"):
            calculate_similarity("hello", "hello", algorithm="partial_ratio")


class TestFuzzyMatchClassifierBinaryMode:
    """Tests for FuzzyMatchClassifier in binary mode."""

    def test_exact_match_returns_yes(self):
        """Exact match should return Yes with high confidence."""
        classifier = FuzzyMatchClassifier(expected="Customer Service")
        result = classifier.classify("Customer Service")

        assert result.value == "Yes"
        assert result.confidence == 1.0

    def test_close_match_returns_yes(self):
        """Close match above threshold should return Yes."""
        classifier = FuzzyMatchClassifier(expected="Customer Service", threshold=0.8)
        result = classifier.classify("customer service dept")

        assert result.value == "Yes"
        assert result.confidence >= 0.8

    def test_poor_match_returns_no(self):
        """Poor match below threshold should return No."""
        classifier = FuzzyMatchClassifier(expected="Customer Service", threshold=0.8)
        result = classifier.classify("Technical Support")

        assert result.value == "No"
        assert result.confidence is not None

    def test_threshold_customization(self):
        """Custom threshold should affect matching."""
        # With low threshold, should match
        classifier_low = FuzzyMatchClassifier(expected="hello", threshold=0.5)
        result_low = classifier_low.classify("hallo")
        assert result_low.value == "Yes"

        # With high threshold, should not match
        classifier_high = FuzzyMatchClassifier(expected="hello", threshold=0.99)
        result_high = classifier_high.classify("hallo")
        assert result_high.value == "No"

    def test_classes_set_to_yes_no(self):
        """Binary mode should set classes to ['Yes', 'No']."""
        classifier = FuzzyMatchClassifier(expected="test")
        assert classifier.classes == ["Yes", "No"]

    def test_target_classes_defaults_to_yes(self):
        """Binary mode should default target_classes to ['Yes']."""
        classifier = FuzzyMatchClassifier(expected="test")
        assert classifier.target_classes == ["Yes"]

    def test_explanation_included(self):
        """Result should include explanation."""
        classifier = FuzzyMatchClassifier(expected="hello")
        result = classifier.classify("hello")

        assert result.explanation is not None
        assert "similarity" in result.explanation.lower()


class TestFuzzyMatchClassifierMultiClassMode:
    """Tests for FuzzyMatchClassifier in multi-class mode."""

    def test_exact_match_returns_class(self):
        """Exact match should return the matching class."""
        classifier = FuzzyMatchClassifier(classes=["Technical Support", "Billing", "Sales"])
        result = classifier.classify("Technical Support")

        assert result.value == "Technical Support"
        assert result.confidence == 1.0

    def test_close_match_returns_best_class(self):
        """Close match should return the best matching class."""
        classifier = FuzzyMatchClassifier(
            classes=["Technical Support", "Billing", "Sales"],
            threshold=0.7,
        )
        result = classifier.classify("tech support")

        assert result.value == "Technical Support"
        assert result.confidence >= 0.7

    def test_no_match_returns_no_match(self):
        """When no class matches threshold, should return NO_MATCH."""
        classifier = FuzzyMatchClassifier(
            classes=["Technical Support", "Billing", "Sales"],
            threshold=0.9,
        )
        result = classifier.classify("xyz")

        assert result.value == "NO_MATCH"
        assert result.explanation is not None

    def test_finds_best_among_multiple(self):
        """Should find the best match among multiple options."""
        classifier = FuzzyMatchClassifier(
            classes=["Apple", "Application", "Apricot"],
            threshold=0.5,
        )
        result = classifier.classify("App")

        # "App" is closest to "Apple" (3/5 letters match)
        assert result.value in ["Apple", "Application"]  # Either is reasonable

    def test_custom_target_classes(self):
        """Custom target_classes should be respected."""
        classifier = FuzzyMatchClassifier(
            classes=["Yes", "No", "Maybe"],
            target_classes=["Yes", "Maybe"],
        )
        assert classifier.target_classes == ["Yes", "Maybe"]


class TestFuzzyMatchClassifierInterface:
    """Tests for FuzzyMatchClassifier interface compliance."""

    def test_inherits_from_base_classifier(self):
        """Should inherit from BaseClassifier."""
        from tactus.stdlib.core.base import BaseClassifier

        classifier = FuzzyMatchClassifier(expected="test")
        assert isinstance(classifier, BaseClassifier)

    def test_callable_interface(self):
        """Should be callable via __call__."""
        classifier = FuzzyMatchClassifier(expected="hello")
        result = classifier("hello")

        assert isinstance(result, ClassifierResult)
        assert result.value == "Yes"

    def test_dict_input(self):
        """Should handle dict input with 'text' key."""
        classifier = FuzzyMatchClassifier(expected="hello")
        result = classifier({"text": "hello"})

        assert result.value == "Yes"

    def test_reset_method(self):
        """Should have reset method (no-op for fuzzy)."""
        classifier = FuzzyMatchClassifier(expected="test")
        classifier.reset()  # Should not raise

    def test_result_to_dict(self):
        """Result should be convertible to dict."""
        classifier = FuzzyMatchClassifier(expected="hello")
        result = classifier.classify("hello")
        d = result.to_dict()

        assert d["value"] == "Yes"
        assert d["confidence"] == 1.0
        assert "explanation" in d

    def test_repr(self):
        """Should have meaningful repr."""
        binary = FuzzyMatchClassifier(expected="test", threshold=0.9)
        assert "expected" in repr(binary)
        assert "0.9" in repr(binary)

        multi = FuzzyMatchClassifier(classes=["A", "B"], threshold=0.8)
        assert "classes" in repr(multi)

    def test_total_calls_tracked(self):
        """Should track total number of calls."""
        classifier = FuzzyMatchClassifier(expected="test")
        assert classifier.total_calls == 0

        classifier.classify("test")
        assert classifier.total_calls == 1

        classifier.classify("other")
        assert classifier.total_calls == 2


class TestFuzzyMatchClassifierValidation:
    """Tests for FuzzyMatchClassifier input validation."""

    def test_requires_expected_or_classes(self):
        """Should raise error if neither expected nor classes provided."""
        with pytest.raises(ValueError, match="expected.*classes"):
            FuzzyMatchClassifier()

    def test_accepts_expected_only(self):
        """Should accept expected without classes."""
        classifier = FuzzyMatchClassifier(expected="test")
        assert classifier.mode == "binary"

    def test_accepts_classes_only(self):
        """Should accept classes without expected."""
        classifier = FuzzyMatchClassifier(classes=["A", "B"])
        assert classifier.mode == "multiclass"

    def test_expected_takes_precedence(self):
        """When both provided, expected should take precedence (binary mode)."""
        classifier = FuzzyMatchClassifier(expected="test", classes=["A", "B"])
        assert classifier.mode == "binary"


class TestFuzzyClassifierAlias:
    """Tests for the FuzzyClassifier alias."""

    def test_fuzzy_classifier_is_alias(self):
        """FuzzyClassifier should be an alias for FuzzyMatchClassifier."""
        assert FuzzyClassifier is FuzzyMatchClassifier
