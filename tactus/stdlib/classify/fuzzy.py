"""
FuzzyMatchClassifier - Classification using string similarity.

This classifier uses fuzzy string matching to classify text based on
similarity to expected values. Useful for verification tasks where
you want to check if a response matches an expected value.

Supports multiple algorithms from rapidfuzz library:
- ratio: Basic character-level similarity (default)
- token_set_ratio: Tokenize and compare unique words (handles reordering)
- token_sort_ratio: Sort tokens before comparing
- partial_ratio: Best substring match
"""

import logging
from typing import Any, Dict, List, Optional

try:
    from rapidfuzz import fuzz

    HAS_RAPIDFUZZ = True
except ImportError:
    from difflib import SequenceMatcher

    HAS_RAPIDFUZZ = False

from ..core.base import BaseClassifier
from ..core.models import ClassifierResult

logger = logging.getLogger(__name__)


def calculate_similarity(s1: str, s2: str, algorithm: str = "ratio") -> float:
    """
    Calculate similarity between two strings using specified algorithm.

    Args:
        s1: First string
        s2: Second string
        algorithm: One of "ratio", "token_set_ratio", "token_sort_ratio", "partial_ratio"

    Returns:
        Float between 0.0 (no similarity) and 1.0 (identical)

    Raises:
        ValueError: If algorithm is not supported

    Note:
        Uses rapidfuzz if available (faster), falls back to difflib for basic ratio.
    """
    if not s1 or not s2:
        return 0.0

    # Normalize: lowercase and strip whitespace
    s1_norm = s1.lower().strip()
    s2_norm = s2.lower().strip()

    if HAS_RAPIDFUZZ:
        # Use rapidfuzz (C++ backend, faster)
        if algorithm == "token_set_ratio":
            score = fuzz.token_set_ratio(s1_norm, s2_norm)
        elif algorithm == "token_sort_ratio":
            score = fuzz.token_sort_ratio(s1_norm, s2_norm)
        elif algorithm == "partial_ratio":
            score = fuzz.partial_ratio(s1_norm, s2_norm)
        elif algorithm == "ratio":
            score = fuzz.ratio(s1_norm, s2_norm)
        else:
            raise ValueError(
                f"Unsupported algorithm: {algorithm}. "
                "Choose from: ratio, token_set_ratio, token_sort_ratio, partial_ratio"
            )
        # Normalize from 0-100 to 0.0-1.0
        return score / 100.0
    else:
        # Fallback to difflib (only supports ratio)
        if algorithm != "ratio":
            raise ValueError(
                f"Algorithm '{algorithm}' requires rapidfuzz library. "
                "Install with: pip install rapidfuzz"
            )
        return SequenceMatcher(None, s1_norm, s2_norm).ratio()


class FuzzyMatchClassifier(BaseClassifier):
    """
    String similarity based classifier.

    Compares input text against expected value(s) and returns whether
    they match within a configurable threshold.

    Two modes of operation:

    1. Binary mode (single expected value):
       Returns "Yes" if similarity >= threshold, "No" otherwise.

       classifier = FuzzyMatchClassifier(
           expected="Customer Service",
           threshold=0.8,
       )
       result = classifier.classify("customer service dept")
       # result.value = "Yes", result.confidence = 0.92

    2. Multi-class mode (multiple expected values):
       Returns the closest matching class if similarity >= threshold,
       or "NO_MATCH" if nothing matches.

       classifier = FuzzyMatchClassifier(
           classes=["Technical Support", "Billing", "Sales"],
           threshold=0.7,
       )
       result = classifier.classify("tech support")
       # result.value = "Technical Support", result.confidence = 0.85

    Example usage in Lua:
        -- Binary: Does this match "Customer Service"?
        result = Classify {
            method = "fuzzy",
            expected = "Customer Service",
            threshold = 0.8,
            input = agent_response
        }

        -- Multi-class: Which department?
        result = Classify {
            method = "fuzzy",
            classes = {"Technical Support", "Billing", "Sales"},
            threshold = 0.7,
            input = department_name
        }
    """

    def __init__(
        self,
        classes: Optional[List[str]] = None,
        expected: Optional[str] = None,
        threshold: float = 0.8,
        algorithm: str = "ratio",
        target_classes: Optional[List[str]] = None,
        name: Optional[str] = None,
        # Accept but ignore these (for factory compatibility)
        config: Optional[Dict[str, Any]] = None,
        **kwargs,
    ):
        """
        Initialize FuzzyMatchClassifier.

        Args:
            classes: List of possible values to match against (multi-class mode)
            expected: Single expected value (binary mode, returns Yes/No)
            threshold: Minimum similarity score to consider a match (0.0 to 1.0)
            algorithm: Similarity algorithm - "ratio" (default), "token_set_ratio",
                      "token_sort_ratio", or "partial_ratio"
            target_classes: Classes considered "positive" for precision/recall
            name: Optional name for this classifier

        Algorithm details:
            - ratio: Character-level similarity (best for exact matches)
            - token_set_ratio: Tokenizes and compares unique words (handles reordering)
            - token_sort_ratio: Sorts tokens before comparing (handles reordering)
            - partial_ratio: Best substring match (good for abbreviations)
        """
        # If config dict is provided, extract parameters from it
        if config is not None:
            classes = config.get("classes", classes)
            expected = config.get("expected", expected)
            threshold = config.get("threshold", threshold)
            algorithm = config.get("algorithm", algorithm)
            target_classes = config.get("target_classes", target_classes)
            name = config.get("name", name)

        self.threshold = threshold
        self.algorithm = algorithm
        self.name = name

        # Determine mode: binary or multi-class
        if expected is not None:
            # Binary mode: Yes/No based on match to expected
            self.mode = "binary"
            self.expected = expected
            self.classes = ["Yes", "No"]
            self.target_classes = target_classes or ["Yes"]
        elif classes is not None and len(classes) > 0:
            # Multi-class mode: return closest matching class
            self.mode = "multiclass"
            self.expected = None
            self.classes = list(classes)
            self.target_classes = target_classes or []
        else:
            raise ValueError(
                "FuzzyMatchClassifier requires either 'expected' (binary mode) "
                "or 'classes' (multi-class mode)"
            )

        # Track statistics
        self.total_calls = 0

    def classify(self, input_text: str) -> ClassifierResult:
        """
        Classify the input text using fuzzy string matching.

        Args:
            input_text: The text to classify

        Returns:
            ClassifierResult with value, confidence (similarity score), explanation
        """
        self.total_calls += 1

        if self.mode == "binary":
            return self._classify_binary(input_text)
        else:
            return self._classify_multiclass(input_text)

    def _classify_binary(self, input_text: str) -> ClassifierResult:
        """
        Binary classification: Does input match expected value?

        Returns "Yes" or "No" with similarity as confidence.
        Also returns matched_text (the expected value) for consistency.
        """
        similarity = calculate_similarity(input_text, self.expected, self.algorithm)

        if similarity >= self.threshold:
            return ClassifierResult(
                value="Yes",
                confidence=similarity,
                matched_text=self.expected,  # Return what it matched against
                explanation=f"Input matches expected value with {similarity:.1%} similarity using {self.algorithm} (threshold: {self.threshold:.1%})",
            )
        else:
            return ClassifierResult(
                value="No",
                confidence=1.0 - similarity,  # Confidence in "No"
                matched_text=None,  # No match found
                explanation=f"Input does not match expected value. Similarity: {similarity:.1%} using {self.algorithm} (threshold: {self.threshold:.1%})",
            )

    def _classify_multiclass(self, input_text: str) -> ClassifierResult:
        """
        Multi-class classification: Find best matching class.

        Returns the closest matching class or "NO_MATCH" if none meet threshold.
        matched_text contains the actual matched string from the classes list.
        """
        best_match = None
        best_similarity = 0.0

        for cls in self.classes:
            similarity = calculate_similarity(input_text, cls, self.algorithm)
            if similarity > best_similarity:
                best_similarity = similarity
                best_match = cls

        if best_similarity >= self.threshold:
            return ClassifierResult(
                value=best_match,
                confidence=best_similarity,
                matched_text=best_match,  # The actual matched class name
                explanation=f"Best match: '{best_match}' with {best_similarity:.1%} similarity using {self.algorithm}",
            )
        else:
            return ClassifierResult(
                value="NO_MATCH",
                confidence=1.0 - best_similarity,  # Confidence in no match
                matched_text=None,  # No match found
                explanation=f"No class matched above threshold using {self.algorithm}. Best was '{best_match}' at {best_similarity:.1%} (threshold: {self.threshold:.1%})",
            )

    def reset(self) -> None:
        """Reset classifier state (no-op for fuzzy matcher)."""
        pass

    def __repr__(self) -> str:
        if self.mode == "binary":
            return f"FuzzyMatchClassifier(expected='{self.expected}', threshold={self.threshold}, algorithm='{self.algorithm}')"
        else:
            return f"FuzzyMatchClassifier(classes={self.classes}, threshold={self.threshold}, algorithm='{self.algorithm}')"


# Also provide as FuzzyClassifier for shorter name
FuzzyClassifier = FuzzyMatchClassifier
