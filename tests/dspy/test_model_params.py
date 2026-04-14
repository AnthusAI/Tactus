"""Tests for tactus.dspy.model_params."""

from tactus.dspy.model_params import (
    default_temperature_for_model,
    is_openai_gpt5_family_model,
    lite_llm_model_id,
)


def test_lite_llm_model_id():
    assert lite_llm_model_id("openai/gpt-5.4-mini") == "gpt-5.4-mini"
    assert lite_llm_model_id("gpt-4o-mini") == "gpt-4o-mini"


def test_is_openai_gpt5_family_model():
    assert is_openai_gpt5_family_model("openai/gpt-5.4-mini") is True
    assert is_openai_gpt5_family_model("openai/gpt-5-mini") is True
    assert is_openai_gpt5_family_model("openai/gpt-4o-mini") is False


def test_default_temperature_for_model():
    assert default_temperature_for_model("openai/gpt-5.4-mini") is None
    assert default_temperature_for_model("openai/gpt-4o-mini") == 0.0
    assert default_temperature_for_model("anthropic/claude-3-5-sonnet-20241022") == 0.0
