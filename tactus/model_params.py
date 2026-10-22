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


REASONING_FAMILY_PREFIXES = ("gpt-5", "gpt-6")
RESPONSES_API_FAMILY_PREFIXES = ("gpt-6",)


def is_openai_gpt5_family_model(model: str) -> bool:
    """Return whether an OpenAI model is a GPT-5-or-later reasoning model (no temperature; effort and verbosity)."""
    return lite_llm_model_id(model).startswith(REASONING_FAMILY_PREFIXES)


def uses_responses_api_by_default(model: str) -> bool:
    """Return whether a model accepts function tools only on the Responses API (the GPT-6 family)."""
    return lite_llm_model_id(model).startswith(RESPONSES_API_FAMILY_PREFIXES)


def default_temperature_for_model(model: str) -> Optional[float]:
    """Return ``None`` for GPT-5-or-later models and deterministic zero otherwise."""
    if is_openai_gpt5_family_model(model):
        return None
    return 0.0
