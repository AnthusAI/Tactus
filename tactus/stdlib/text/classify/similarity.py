"""
String similarity calculation using rapidfuzz (or difflib fallback).

This is a Python helper module for the Tactus classify stdlib.
The FuzzyMatchClassifier class lives in the .tac layer; this module
provides only the similarity computation that benefits from rapidfuzz's
C++ backend.

Loaded from Tactus via: require("tactus.text.classify.similarity")
"""

try:
    from rapidfuzz import fuzz

    HAS_RAPIDFUZZ = True
except ImportError:
    from difflib import SequenceMatcher

    HAS_RAPIDFUZZ = False


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


__tactus_exports__ = ["calculate_similarity"]
