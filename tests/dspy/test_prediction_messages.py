"""
Tests for TactusPrediction message tracking (new_messages and all_messages).
"""

import dspy
import pytest

from tactus.dspy.prediction import (
    create_prediction,
    wrap_prediction,
    TactusPrediction,
    validate_field_type,
)


def test_create_prediction_with_messages():
    """Test creating a prediction with message tracking."""
    new_msgs = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there!"},
    ]
    all_msgs = [
        {"role": "user", "content": "Previous message"},
        {"role": "assistant", "content": "Previous response"},
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there!"},
    ]

    result = create_prediction(
        response="Hi there!",
        __new_messages__=new_msgs,
        __all_messages__=all_msgs,
    )

    # Verify new_messages returns only the messages from this turn
    assert result.new_messages() == new_msgs
    assert len(result.new_messages()) == 2

    # Verify all_messages returns the complete history
    assert result.all_messages() == all_msgs
    assert len(result.all_messages()) == 4


def test_create_prediction_without_messages():
    """Test creating a prediction without message tracking (defaults to empty lists)."""
    result = create_prediction(response="Hello")

    # Should return empty lists when no messages provided
    assert result.new_messages() == []
    assert result.all_messages() == []


def test_wrap_prediction_with_messages():
    """Test wrapping a DSPy prediction with message tracking."""
    dspy_pred = dspy.Prediction(response="Test response")

    new_msgs = [{"role": "user", "content": "Test"}]
    all_msgs = [
        {"role": "user", "content": "Previous"},
        {"role": "user", "content": "Test"},
    ]

    result = wrap_prediction(dspy_pred, new_messages=new_msgs, all_messages=all_msgs)

    assert result.new_messages() == new_msgs
    assert result.all_messages() == all_msgs


def test_wrap_prediction_without_messages():
    """Test wrapping a DSPy prediction without message tracking."""
    dspy_pred = dspy.Prediction(response="Test response")

    result = wrap_prediction(dspy_pred)

    # Should return empty lists when no messages provided
    assert result.new_messages() == []
    assert result.all_messages() == []


def test_messages_are_copied():
    """Test that message lists are copied, not referenced."""
    new_msgs = [{"role": "user", "content": "Hello"}]
    all_msgs = [{"role": "user", "content": "Hello"}]

    result = create_prediction(response="Hi", __new_messages__=new_msgs, __all_messages__=all_msgs)

    # Get messages
    returned_new = result.new_messages()
    returned_all = result.all_messages()

    # Modify the returned lists
    returned_new.append({"role": "assistant", "content": "Modified"})
    returned_all.append({"role": "assistant", "content": "Modified"})

    # Original messages should be unchanged
    assert len(result.new_messages()) == 1
    assert len(result.all_messages()) == 1


def test_prediction_with_structured_data_and_messages():
    """Test prediction with both structured data and message tracking."""
    new_msgs = [{"role": "user", "content": "Extract city"}]
    all_msgs = [{"role": "user", "content": "Extract city"}]

    result = create_prediction(
        city="Paris",
        country="France",
        population=2161000,
        __new_messages__=new_msgs,
        __all_messages__=all_msgs,
    )

    # Verify structured data access
    assert result.city == "Paris"
    assert result.country == "France"
    assert result.population == 2161000

    # Verify message access
    assert result.new_messages() == new_msgs
    assert result.all_messages() == all_msgs


def test_getattr_rejects_private_attribute():
    pred = TactusPrediction(dspy.Prediction(response="ok"))
    with pytest.raises(AttributeError):
        _ = pred._secret


def test_to_dspy_and_from_dspy():
    base = dspy.Prediction(response="ok")
    wrapped = TactusPrediction.from_dspy(base)
    assert wrapped.to_dspy() is base


def test_message_falls_back_to_custom_field():
    from types import SimpleNamespace

    pred = TactusPrediction(SimpleNamespace(custom="hello"))
    assert pred.message == "hello"


def test_validate_field_type_without_schema_returns_true():
    assert validate_field_type("field", 1, None) is True


def test_create_prediction_missing_required_field_raises():
    with pytest.raises(ValueError, match="Required field missing"):
        create_prediction(__schema__={"required": ["answer"]})


def test_create_prediction_with_required_fields():
    result = create_prediction(
        answer="ok",
        __schema__={"required": ["answer"], "fields": {"answer": {"type": "str"}}},
    )

    assert result.answer == "ok"
