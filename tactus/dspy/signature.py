"""
DSPy Signature integration for Tactus.

This module provides the Signature primitive that maps to DSPy signatures,
supporting both string format ("question -> answer") and structured format.
"""

from typing import Dict, Any, Optional, Union

import dspy


# Map Tactus types to Python types for DSPy fields
TYPE_MAP = {
    "string": str,
    "str": str,
    "number": float,
    "float": float,
    "integer": int,
    "int": int,
    "boolean": bool,
    "bool": bool,
    "array": list,
    "list": list,
    "object": dict,
    "dict": dict,
}


def parse_signature_string(sig_str: str) -> dspy.Signature:
    """
    Parse a DSPy-style signature string into a dspy.Signature.

    DSPy 3.x natively supports parsing signature strings, so we delegate to it.

    Signature string format:
    - Simple: "question -> answer"
    - Multi-field: "context, question -> reasoning, answer"
    - Typed: "question: str -> answer: str"

    Args:
        sig_str: Signature string like "question -> answer"

    Returns:
        A dspy.Signature class

    Raises:
        ValueError: If the signature string is invalid
    """
    # DSPy 3.x can parse signature strings directly
    return dspy.Signature(sig_str)


def create_structured_signature(
    input_fields: Dict[str, Dict[str, Any]],
    output_fields: Dict[str, Dict[str, Any]],
    name: Optional[str] = None,
    instructions: Optional[str] = None,
) -> dspy.Signature:
    """
    Create a DSPy Signature from structured field definitions.

    This allows defining signatures with descriptions and types using
    Tactus's field.string{}, field.number{} etc. syntax.

    Args:
        input_fields: Dict mapping field names to their definitions
                     e.g., {"question": {"type": "string", "description": "The question"}}
        output_fields: Dict mapping field names to their definitions
                      e.g., {"answer": {"type": "string", "description": "The answer"}}
        name: Optional name for the signature class
        instructions: Optional instructions/docstring for the signature

    Returns:
        A dspy.Signature class with the specified fields and descriptions
    """
    # Build field names for the string signature
    input_names = list(input_fields.keys())
    output_names = list(output_fields.keys())

    # Create base signature string
    sig_str = f"{', '.join(input_names)} -> {', '.join(output_names)}"

    # Create the base signature
    sig = dspy.Signature(sig_str)

    # Update each field with its description using with_updated_fields
    # DSPy's with_updated_fields takes one field name at a time
    for field_name, field_def in input_fields.items():
        desc = field_def.get("description", "")
        if desc:
            sig = sig.with_updated_fields(field_name, desc=desc)

    for field_name, field_def in output_fields.items():
        desc = field_def.get("description", "")
        if desc:
            sig = sig.with_updated_fields(field_name, desc=desc)

    # Add instructions if provided
    if instructions:
        sig = sig.with_instructions(instructions)

    return sig


def create_signature(
    sig_input: Union[str, Dict[str, Any]],
    name: Optional[str] = None,
) -> dspy.Signature:
    """
    Create a DSPy Signature from string or structured input.

    Args:
        sig_input: Either a string like "question -> answer" or a dict with
                   input/output field definitions
        name: Optional name for the signature (used in structured form)

    Returns:
        A dspy.Signature class

    Examples:
        # String form
        create_signature("question -> answer")
        create_signature("context, question -> reasoning, answer")

        # Structured form
        create_signature({
            "input": {"question": {"type": "string", "description": "The question"}},
            "output": {"answer": {"type": "string", "description": "The answer"}}
        })
    """
    if isinstance(sig_input, str):
        return parse_signature_string(sig_input)
    elif isinstance(sig_input, dict):
        # Structured form
        input_fields = sig_input.get("input", {})
        output_fields = sig_input.get("output", {})
        instructions = sig_input.get("instructions")

        if not input_fields and not output_fields:
            raise ValueError(
                "Structured signature must have 'input' and/or 'output' field definitions"
            )

        return create_structured_signature(
            input_fields=input_fields,
            output_fields=output_fields,
            name=name,
            instructions=instructions,
        )
    else:
        raise TypeError(f"Signature expects a string or dict, got {type(sig_input).__name__}")
