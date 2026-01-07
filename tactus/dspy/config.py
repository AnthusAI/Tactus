"""
DSPy configuration for Tactus.

This module handles Language Model configuration using DSPy's LM abstraction,
which uses LiteLLM under the hood for provider-agnostic LLM access.
"""

from typing import Optional, Any

import dspy


# Global reference to the current LM configuration
_current_lm: Optional[dspy.LM] = None


def configure_lm(
    model: str,
    api_key: Optional[str] = None,
    api_base: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: Optional[int] = None,
    **kwargs: Any,
) -> dspy.LM:
    """
    Configure the default Language Model for DSPy operations.

    This uses LiteLLM's model naming convention:
    - OpenAI: "openai/gpt-4o", "openai/gpt-4o-mini"
    - Anthropic: "anthropic/claude-3-5-sonnet-20241022"
    - AWS Bedrock: "bedrock/anthropic.claude-3-5-sonnet-20240620-v1:0"
    - Google: "gemini/gemini-pro"

    Args:
        model: Model identifier in LiteLLM format (e.g., "openai/gpt-4o")
        api_key: API key (optional, can use environment variables)
        api_base: Custom API base URL (optional)
        temperature: Sampling temperature (default: 0.7)
        max_tokens: Maximum tokens in response (optional)
        **kwargs: Additional LiteLLM parameters

    Returns:
        Configured dspy.LM instance

    Example:
        >>> configure_lm("openai/gpt-4o", temperature=0.3)
        >>> configure_lm("anthropic/claude-3-5-sonnet-20241022")
    """
    global _current_lm

    # Build configuration
    lm_kwargs = {
        "temperature": temperature,
        **kwargs,
    }

    if api_key:
        lm_kwargs["api_key"] = api_key
    if api_base:
        lm_kwargs["api_base"] = api_base
    if max_tokens:
        lm_kwargs["max_tokens"] = max_tokens

    # Create and configure the LM
    lm = dspy.LM(model, **lm_kwargs)

    # Set as global default
    dspy.configure(lm=lm)
    _current_lm = lm

    return lm


def get_current_lm() -> Optional[dspy.LM]:
    """
    Get the currently configured Language Model.

    Returns:
        The current dspy.LM instance, or None if not configured.
    """
    return _current_lm


def ensure_lm_configured() -> dspy.LM:
    """
    Ensure a Language Model is configured, raising an error if not.

    Returns:
        The current dspy.LM instance.

    Raises:
        RuntimeError: If no LM has been configured.
    """
    if _current_lm is None:
        raise RuntimeError(
            "No Language Model configured. "
            "Call configure_lm() or use LM() primitive in your Tactus code."
        )
    return _current_lm
