"""
Confidence Extraction

Utilities for extracting confidence scores from LLM responses.
"""

import re
from typing import Optional


def extract_confidence(
    response: str,
    mode: str = "heuristic",
    classification: Optional[str] = None,
) -> Optional[float]:
    """
    Extract confidence score from an LLM response.

    Args:
        response: The LLM response text
        mode: Extraction mode - "heuristic", "explicit", or "none"
        classification: The classification value (for context)

    Returns:
        Confidence score between 0.0 and 1.0, or None if extraction disabled

    Modes:
        - "heuristic": Look for confidence indicators in text (default)
        - "explicit": Look for explicit confidence values like "Confidence: 85%"
        - "none": Return None (confidence disabled)
    """
    if mode == "none":
        return None

    if mode == "explicit":
        return _extract_explicit_confidence(response)

    return _extract_heuristic_confidence(response)


def _extract_explicit_confidence(response: str) -> Optional[float]:
    """
    Extract explicit confidence values from response.

    Looks for patterns like:
    - "Confidence: 85%"
    - "confidence = 0.85"
    - "(85% confident)"
    """
    patterns = [
        r"confidence[:\s=]+(\d+)%",
        r"confidence[:\s=]+0?\.(\d+)",
        r"\((\d+)%\s*confident\)",
        r"(\d+)%\s*confidence",
    ]

    response_lower = response.lower()

    for pattern in patterns:
        match = re.search(pattern, response_lower)
        if match:
            value = match.group(1)
            # Convert to float between 0 and 1
            if "." not in pattern:
                return float(value) / 100.0
            else:
                return float(f"0.{value}")

    # Fallback to heuristic if no explicit value found
    return _extract_heuristic_confidence(response)


def _extract_heuristic_confidence(response: str) -> Optional[float]:
    """
    Extract confidence using text heuristics.

    Looks for language indicators of certainty level.
    """
    response_lower = response.lower()

    # Very high confidence indicators (0.95)
    very_high = [
        "definitely",
        "certainly",
        "absolutely",
        "100%",
        "without a doubt",
        "unquestionably",
        "undoubtedly",
        "clearly",
        "obviously",
    ]
    for indicator in very_high:
        if indicator in response_lower:
            return 0.95

    # High confidence indicators (0.85)
    high = [
        "very confident",
        "highly likely",
        "strongly believe",
        "sure that",
        "confident that",
        "very likely",
    ]
    for indicator in high:
        if indicator in response_lower:
            return 0.85

    # Medium-high confidence indicators (0.75)
    med_high = [
        "likely",
        "probably",
        "appears to be",
        "seems to be",
        "based on",
        "indicates",
        "suggests",
    ]
    for indicator in med_high:
        if indicator in response_lower:
            return 0.75

    # Medium confidence indicators (0.60)
    medium = [
        "may be",
        "might be",
        "could be",
        "possibly",
        "perhaps",
        "somewhat",
    ]
    for indicator in medium:
        if indicator in response_lower:
            return 0.60

    # Low confidence indicators (0.45)
    low = [
        "not entirely sure",
        "uncertain",
        "difficult to determine",
        "hard to tell",
        "ambiguous",
        "unclear",
    ]
    for indicator in low:
        if indicator in response_lower:
            return 0.45

    # Very low confidence indicators (0.30)
    very_low = [
        "very uncertain",
        "cannot determine",
        "impossible to tell",
        "no way to know",
        "purely guessing",
    ]
    for indicator in very_low:
        if indicator in response_lower:
            return 0.30

    # Default confidence when no indicators found
    return 0.70


# Confidence level mappings for string labels
CONFIDENCE_LABELS = {
    "very_high": 0.95,
    "high": 0.85,
    "medium_high": 0.75,
    "medium": 0.60,
    "low": 0.45,
    "very_low": 0.30,
}


def confidence_to_label(confidence: float) -> str:
    """
    Convert numeric confidence to a label.

    Args:
        confidence: Confidence value between 0.0 and 1.0

    Returns:
        Label string: "very_high", "high", "medium_high", "medium", "low", or "very_low"
    """
    if confidence >= 0.90:
        return "very_high"
    elif confidence >= 0.80:
        return "high"
    elif confidence >= 0.70:
        return "medium_high"
    elif confidence >= 0.55:
        return "medium"
    elif confidence >= 0.40:
        return "low"
    else:
        return "very_low"


def label_to_confidence(label: str) -> float:
    """
    Convert a label to numeric confidence.

    Args:
        label: Confidence label

    Returns:
        Confidence value between 0.0 and 1.0
    """
    return CONFIDENCE_LABELS.get(label.lower(), 0.70)
