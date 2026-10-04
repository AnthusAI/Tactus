"""Model-specific defaults and validation shared by the lightweight runtime."""

from __future__ import annotations

from typing import Optional

REASONING_EFFORT_VALUES = {"none", "minimal", "low", "medium", "high", "xhigh"}
VERBOSITY_VALUES = {"low", "medium", "high"}


def validate_gpt5_controls(
    reasoning_effort: Optional[str] = None,
    verbosity: Optional[str] = None,
) -> None:
    """Validate optional GPT-5-family reasoning and verbosity controls."""
    if reasoning_effort is not None and reasoning_effort not in REASONING_EFFORT_VALUES:
        allowed = ", ".join(sorted(REASONING_EFFORT_VALUES))
        raise ValueError(f"reasoning_effort must be one of: {allowed}. Got: {reasoning_effort}")

    if verbosity is not None and verbosity not in VERBOSITY_VALUES:
        allowed = ", ".join(sorted(VERBOSITY_VALUES))
        raise ValueError(f"verbosity must be one of: {allowed}. Got: {verbosity}")


def lite_llm_model_id(model: str) -> str:
    """Return the provider-local model id from a LiteLLM model string."""
    if not model:
        return ""
    return model.split("/", 1)[-1] if "/" in model else model


def is_openai_gpt5_family_model(model: str) -> bool:
    """Return whether an OpenAI model belongs to the GPT-5 family."""
    return lite_llm_model_id(model).startswith("gpt-5")


def rejects_temperature(model: str) -> bool:
    """Return whether the model's API refuses any ``temperature`` field.

    Bedrock's Moonshot Kimi models answer every request that carries one with
    "This model doesn't support the temperature field. Remove temperature and
    try again." (observed 2026-09-22), so the field has to be left out entirely.
    """
    model_id = lite_llm_model_id(model).lower()
    return "moonshotai" in model_id or model_id.startswith("kimi")


def default_temperature_for_model(model: str) -> Optional[float]:
    """Return ``None`` for models that reject the field, deterministic zero otherwise."""
    if is_openai_gpt5_family_model(model) or rejects_temperature(model):
        return None
    return 0.0
