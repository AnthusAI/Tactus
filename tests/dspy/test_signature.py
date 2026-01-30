import pytest
import dspy

from tactus.dspy.signature import (
    parse_signature_string,
    create_structured_signature,
    create_signature,
)


def test_parse_signature_string_valid():
    sig = parse_signature_string("question -> answer")
    assert issubclass(sig, dspy.Signature)


@pytest.mark.parametrize(
    "sig_str",
    ["", None, "question answer", "question ->", "-> answer", "q -> a -> b"],
)
def test_parse_signature_string_invalid(sig_str):
    with pytest.raises(ValueError):
        parse_signature_string(sig_str)  # type: ignore[arg-type]


def test_parse_signature_string_duplicate_fields():
    with pytest.raises(ValueError, match="duplicate"):
        parse_signature_string("q, q -> a")


def test_parse_signature_string_rejects_empty_field():
    with pytest.raises(ValueError, match="empty fields"):
        parse_signature_string("q, -> a")


def test_create_structured_signature_with_descriptions_and_instructions():
    sig = create_structured_signature(
        input_fields={"q": {"description": "question"}},
        output_fields={"a": {"description": "answer"}},
        instructions="Be concise",
    )
    assert issubclass(sig, dspy.Signature)
    assert "q" in sig.signature
    assert "a" in sig.signature


def test_create_signature_from_structured_dict():
    sig = create_signature(
        {
            "input": {"q": {"type": "string"}},
            "output": {"a": {"type": "string"}},
        }
    )
    assert issubclass(sig, dspy.Signature)


def test_create_signature_requires_fields():
    with pytest.raises(ValueError, match="Structured signature"):
        create_signature({})


def test_create_signature_rejects_other_types():
    with pytest.raises(TypeError):
        create_signature(123)  # type: ignore[arg-type]
