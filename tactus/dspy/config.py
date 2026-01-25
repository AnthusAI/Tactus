"""
DSPy configuration for Tactus.

This module handles Language Model configuration using DSPy's LM abstraction,
which uses LiteLLM under the hood for provider-agnostic LLM access.
"""

from typing import Optional, Any

import dspy

# Global reference to the current LM configuration
_current_lm: Optional[dspy.BaseLM] = None


def configure_lm(
    model: str,
    api_key: Optional[str] = None,
    api_base: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: Optional[int] = None,
    model_type: Optional[str] = None,
    **kwargs: Any,
) -> dspy.BaseLM:
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
        model_type: Model type (e.g., "chat", "responses" for reasoning models)
        **kwargs: Additional LiteLLM parameters

    Returns:
        Configured dspy.LM instance

    Example:
        >>> configure_lm("openai/gpt-4o", temperature=0.3)
        >>> configure_lm("anthropic/claude-3-5-sonnet-20241022")
        >>> configure_lm("openai/gpt-5-mini", model_type="responses")
    """
    global _current_lm

    import os

    # Validate model parameter
    if model is None or not model:
        raise ValueError("model is required for LM configuration")

    if not isinstance(model, str) or not model.startswith(
        ("openai/", "anthropic/", "bedrock/", "gemini/", "ollama/")
    ):
        # Check if it's at least formatted correctly
        if "/" not in model:
            raise ValueError(
                f"Invalid model format: {model}. Expected format like 'provider/model-name'"
            )

    # Build configuration
    lm_kwargs = {
        "temperature": temperature,
        # IMPORTANT: Disable caching to enable streaming. With cache=True (default),
        # DSPy returns cached responses which breaks streamify()'s ability to stream.
        "cache": False,
        **kwargs,
    }

    if api_key:
        lm_kwargs["api_key"] = api_key
    if api_base:
        lm_kwargs["api_base"] = api_base
    if max_tokens:
        lm_kwargs["max_tokens"] = max_tokens
    if model_type:
        lm_kwargs["model_type"] = model_type

    # If running inside the secretless runtime container, use the brokered LM.
    if os.environ.get("TACTUS_BROKER_SOCKET"):
        from tactus.dspy.broker_lm import BrokeredLM

        # Ensure we don't accidentally pass credentials into the runtime container process.
        lm_kwargs.pop("api_key", None)
        lm_kwargs.pop("api_base", None)

        # BrokeredLM reads the socket path from TACTUS_BROKER_SOCKET.
        lm = BrokeredLM(model, **lm_kwargs)
    else:
        # Create and configure the standard DSPy LM (LiteLLM-backed)
        lm = dspy.LM(model, **lm_kwargs)

    # Create adapter with native function calling enabled
    from dspy.adapters.chat_adapter import ChatAdapter
    import logging

    logger = logging.getLogger(__name__)

    adapter = ChatAdapter(use_native_function_calling=True)
    logger.info(
        f"[ADAPTER] Created ChatAdapter with use_native_function_calling={adapter.use_native_function_calling}"
    )

    # Set as global default with adapter
    dspy.configure(lm=lm, adapter=adapter)
    logger.info(f"[ADAPTER] Configured DSPy with adapter: {adapter}")
    _current_lm = lm

    return lm


def get_current_lm() -> Optional[dspy.BaseLM]:
    """
    Get the currently configured Language Model.

    Returns:
        The current dspy.BaseLM instance, or None if not configured.
    """
    return _current_lm


def ensure_lm_configured() -> dspy.BaseLM:
    """
    Ensure a Language Model is configured, raising an error if not.

    Returns:
        The current dspy.BaseLM instance.

    Raises:
        RuntimeError: If no LM has been configured.
    """
    if _current_lm is None:
        raise RuntimeError(
            "No Language Model configured. "
            "Call configure_lm() or use LM() primitive in your Tactus code."
        )
    return _current_lm


def reset_lm_configuration() -> None:
    """
    Reset the LM configuration (primarily for testing).

    This clears the global LM state, allowing tests to verify
    error handling when no LM is configured.
    """
    global _current_lm
    _current_lm = None
    # Also reset DSPy's global configuration
    dspy.configure(lm=None)


def create_lm(
    model: str,
    api_key: Optional[str] = None,
    api_base: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: Optional[int] = None,
    model_type: Optional[str] = None,
    **kwargs: Any,
) -> dspy.LM:
    """
    Create a Language Model instance WITHOUT setting it as global default.

    This is useful for creating LMs in async contexts where dspy.configure()
    cannot be called (e.g., in different event loops or async tasks).

    Use with dspy.context(lm=...) to set the LM for a specific scope:
        lm = create_lm("openai/gpt-4o")
        with dspy.context(lm=lm):
            # Use DSPy operations here

    Args:
        model: Model identifier in LiteLLM format (e.g., "openai/gpt-4o")
        api_key: API key (optional, can use environment variables)
        api_base: Custom API base URL (optional)
        temperature: Sampling temperature (default: 0.7)
        max_tokens: Maximum tokens in response (optional)
        model_type: Model type (e.g., "chat", "responses" for reasoning models)
        **kwargs: Additional LiteLLM parameters

    Returns:
        dspy.LM instance (not configured globally)
    """
    # Validate model parameter
    if model is None or not model:
        raise ValueError("model is required for LM configuration")

    if not isinstance(model, str) or not model.startswith(
        ("openai/", "anthropic/", "bedrock/", "gemini/", "ollama/")
    ):
        # Check if it's at least formatted correctly
        if "/" not in model:
            raise ValueError(
                f"Invalid model format: {model}. Expected format like 'provider/model-name'"
            )

    # Build configuration
    lm_kwargs = {
        "temperature": temperature,
        # IMPORTANT: Disable caching to enable streaming
        "cache": False,
        **kwargs,
    }

    if api_key:
        lm_kwargs["api_key"] = api_key
    if api_base:
        lm_kwargs["api_base"] = api_base
    if max_tokens:
        lm_kwargs["max_tokens"] = max_tokens
    if model_type:
        lm_kwargs["model_type"] = model_type

    # Create LM without setting as global default
    return dspy.LM(model, **lm_kwargs)
