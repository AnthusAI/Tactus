"""
Model-specific defaults for DSPy / LiteLLM (temperature, etc.).

OpenAI GPT-5 family models do not accept arbitrary sampling temperature via the
Chat Completions path Tactus uses; callers must omit ``temperature`` rather than
send 0.7 or 1.0.

For models that *do* support temperature, Tactus defaults to ``0`` for
deterministic, classification-style behavior unless the agent overrides it.
"""

from __future__ import annotations

from typing import Optional


def lite_llm_model_id(model: str) -> str:
    """
    Return the provider-local model id (e.g. ``gpt-5.4-mini``) from a LiteLLM
    model string (``openai/gpt-5.4-mini``).
    """
    if not model:
        return ""
    return model.split("/", 1)[-1] if "/" in model else model


def is_openai_gpt5_family_model(model: str) -> bool:
    """
    True for OpenAI GPT-5 family models (omit ``temperature`` for API calls).

    Matches ``gpt-5``, ``gpt-5.4-mini``, ``gpt-5-mini``, etc.
    """
    mid = lite_llm_model_id(model)
    return mid.startswith("gpt-5")


def default_temperature_for_model(model: str) -> Optional[float]:
    """
    Default sampling temperature before any per-agent override.

    - GPT-5 family: ``None`` (do not send ``temperature`` to the provider).
    - Everything else: ``0.0`` (deterministic when supported; classification default).
    """
    if is_openai_gpt5_family_model(model):
        return None
    return 0.0
