"""
Output Validation

Utilities for validating LLM outputs against expected schemas and values.
"""

import re
from typing import Any, Dict, List, Optional


def validate_output(
    output: str,
    valid_values: Optional[List[str]] = None,
    schema: Optional[Dict[str, Any]] = None,
    strict: bool = True,
) -> Dict[str, Any]:
    """
    Validate an LLM output against constraints.

    Args:
        output: The output to validate
        valid_values: List of valid output values (for classification)
        schema: Optional JSON schema to validate against
        strict: If True, exact match required; if False, fuzzy matching allowed

    Returns:
        Dict with:
            - valid: True if validation passed
            - value: The validated/normalized value
            - error: Error message if validation failed
            - suggestions: Suggestions for fixing invalid output
    """
    if not output:
        return {
            "valid": False,
            "value": None,
            "error": "Empty output",
            "suggestions": ["Provide a response"],
        }

    # Validate against valid values
    if valid_values:
        return _validate_classification(output, valid_values, strict)

    # Validate against schema
    if schema:
        return _validate_schema(output, schema)

    # No validation rules - pass through
    return {
        "valid": True,
        "value": output,
        "error": None,
        "suggestions": None,
    }


def _validate_classification(
    output: str,
    valid_values: List[str],
    strict: bool = True,
) -> Dict[str, Any]:
    """
    Validate output is one of the valid classification values.

    Args:
        output: The output to validate
        valid_values: List of valid values
        strict: If True, exact match required

    Returns:
        Validation result dict
    """
    # Get first line (classification should be first)
    first_line = output.strip().split("\n")[0].strip()

    # Clean up common formatting
    cleaned = re.sub(r"[\*\"\'\`\:\.]", "", first_line).strip()
    cleaned_lower = cleaned.lower()

    # Create lookup for case-insensitive matching
    value_map = {v.lower(): v for v in valid_values}

    # Exact match (case-insensitive)
    if cleaned_lower in value_map:
        return {
            "valid": True,
            "value": value_map[cleaned_lower],
            "error": None,
            "suggestions": None,
        }

    # Prefix match (e.g., "Yes - because..." matches "Yes")
    for v_lower, v_original in value_map.items():
        if cleaned_lower.startswith(v_lower):
            return {
                "valid": True,
                "value": v_original,
                "error": None,
                "suggestions": None,
            }

    # Fuzzy matching (if not strict)
    if not strict:
        best_match = _find_best_fuzzy_match(cleaned, valid_values)
        if best_match and best_match["similarity"] >= 0.8:
            return {
                "valid": True,
                "value": best_match["value"],
                "error": None,
                "suggestions": None,
            }

    # Validation failed - provide helpful suggestions
    suggestions = _generate_suggestions(cleaned, valid_values)

    return {
        "valid": False,
        "value": first_line,
        "error": f"'{first_line}' is not a valid classification. Valid options: {', '.join(valid_values)}",
        "suggestions": suggestions,
    }


def _find_best_fuzzy_match(
    text: str,
    candidates: List[str],
) -> Optional[Dict[str, Any]]:
    """
    Find the best fuzzy match for text among candidates.

    Uses simple similarity based on common characters.

    Args:
        text: Text to match
        candidates: List of candidate values

    Returns:
        Dict with value and similarity, or None if no good match
    """
    text_lower = text.lower()
    best_match = None
    best_similarity = 0.0

    for candidate in candidates:
        candidate_lower = candidate.lower()
        similarity = _calculate_similarity(text_lower, candidate_lower)

        if similarity > best_similarity:
            best_similarity = similarity
            best_match = candidate

    if best_match:
        return {"value": best_match, "similarity": best_similarity}

    return None


def _calculate_similarity(s1: str, s2: str) -> float:
    """
    Calculate similarity between two strings.

    Uses a simple character-based approach (not full Levenshtein).

    Args:
        s1: First string
        s2: Second string

    Returns:
        Similarity score between 0.0 and 1.0
    """
    if not s1 or not s2:
        return 0.0

    if s1 == s2:
        return 1.0

    # Check if one contains the other
    if s1 in s2 or s2 in s1:
        return 0.85

    # Character overlap
    set1 = set(s1)
    set2 = set(s2)
    intersection = len(set1 & set2)
    union = len(set1 | set2)

    return intersection / union


def _generate_suggestions(
    invalid_value: str,
    valid_values: List[str],
) -> List[str]:
    """
    Generate helpful suggestions for fixing invalid output.

    Args:
        invalid_value: The invalid value that was provided
        valid_values: List of valid values

    Returns:
        List of suggestion strings
    """
    suggestions = []

    # Find closest match
    best_match = _find_best_fuzzy_match(invalid_value, valid_values)
    if best_match and best_match["similarity"] > 0.3:
        suggestions.append(f"Did you mean '{best_match['value']}'?")

    # Format the valid options
    valid_str = ", ".join(f"'{v}'" for v in valid_values)
    suggestions.append(f"Valid options are: {valid_str}")

    # Add formatting advice
    suggestions.append("Start your response with the classification on its own line")

    return suggestions


def _validate_schema(output: str, schema: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate output against a JSON schema.

    Args:
        output: The output to validate (should be JSON)
        schema: JSON schema dict

    Returns:
        Validation result dict
    """
    import json

    # Try to parse as JSON
    try:
        data = json.loads(output)
    except json.JSONDecodeError as e:
        return {
            "valid": False,
            "value": output,
            "error": f"Invalid JSON: {e}",
            "suggestions": ["Ensure output is valid JSON format"],
        }

    # Validate against schema
    try:
        import jsonschema

        jsonschema.validate(instance=data, schema=schema)
        return {
            "valid": True,
            "value": data,
            "error": None,
            "suggestions": None,
        }
    except ImportError:
        # jsonschema not installed - skip validation
        return {
            "valid": True,
            "value": data,
            "error": None,
            "suggestions": None,
        }
    except jsonschema.ValidationError as e:
        return {
            "valid": False,
            "value": data,
            "error": f"Schema validation failed: {e.message}",
            "suggestions": [f"Fix field '{e.path}'" if e.path else "Fix schema errors"],
        }
