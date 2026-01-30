from tactus.stdlib.core.confidence import (
    confidence_to_label,
    extract_confidence,
    label_to_confidence,
)


def test_extract_confidence_modes():
    assert extract_confidence("anything", mode="none") is None
    assert extract_confidence("Confidence: 85%", mode="explicit") == 0.85
    assert extract_confidence("Definitely yes", mode="heuristic") == 0.95


def test_confidence_to_label():
    assert confidence_to_label(0.95) == "very_high"
    assert confidence_to_label(0.82) == "high"
    assert confidence_to_label(0.72) == "medium_high"
    assert confidence_to_label(0.58) == "medium"
    assert confidence_to_label(0.42) == "low"
    assert confidence_to_label(0.1) == "very_low"


def test_label_to_confidence():
    assert label_to_confidence("HIGH") == 0.85
    assert label_to_confidence("unknown") == 0.70


def test_extract_confidence_explicit_decimal_and_fallback():
    assert extract_confidence("confidence = 0.42", mode="explicit") == 0.42
    assert extract_confidence("No explicit value", mode="explicit") == 0.70


def test_extract_confidence_heuristic_levels():
    assert extract_confidence("purely guessing") == 0.30
    assert extract_confidence("difficult to determine") == 0.45
    assert extract_confidence("perhaps", mode="heuristic") == 0.60
    assert extract_confidence("likely", mode="heuristic") == 0.75
    assert extract_confidence("very confident") == 0.85
