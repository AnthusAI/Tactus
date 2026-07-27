"""
DSPy configuration for Tactus.

This module handles Language Model configuration using DSPy's LM abstraction,
which uses LiteLLM under the hood for provider-agnostic LLM access.
"""

from dataclasses import dataclass
from threading import RLock
from typing import Optional, Any

import dspy

from tactus.dspy.model_params import default_temperature_for_model

# Global reference to the current LM configuration
_current_lm: Optional[dspy.BaseLM] = None
_prewarmed_lms: dict[tuple[Any, ...], "PrewarmedLM"] = {}
_prewarmed_lms_lock = RLock()

REASONING_EFFORT_VALUES = {"none", "minimal", "low", "medium", "high", "xhigh"}
VERBOSITY_VALUES = {"low", "medium", "high"}


@dataclass(frozen=True)
class PrewarmedLM:
    """Provider client and adapter initialized without making an inference request."""

    lm: Any
    adapter: Any


def _freeze_config(value: Any) -> Any:
    if isinstance(value, dict):
        return tuple(sorted((str(key), _freeze_config(item)) for key, item in value.items()))
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_config(item) for item in value)
    if isinstance(value, set):
        return tuple(sorted(_freeze_config(item) for item in value))
    try:
        hash(value)
    except TypeError:
        return repr(value)
    return value


def _prewarm_key(model: str, config: dict[str, Any]) -> tuple[Any, ...]:
    return model, _freeze_config(config)


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


def _apply_gpt5_controls(
    lm_kwargs: dict[str, Any],
    *,
    reasoning_effort: Optional[str] = None,
    verbosity: Optional[str] = None,
    model_type: Optional[str] = None,
) -> None:
    validate_gpt5_controls(reasoning_effort=reasoning_effort, verbosity=verbosity)

    if reasoning_effort is not None:
        lm_kwargs["reasoning_effort"] = reasoning_effort

    if verbosity is not None:
        if model_type == "responses":
            text_config = dict(lm_kwargs.get("text") or {})
            text_config["verbosity"] = verbosity
            lm_kwargs["text"] = text_config
        else:
            lm_kwargs["verbosity"] = verbosity


def create_adapter() -> Any:
    """Create the DSPy adapter Tactus uses for LM calls."""
    from dspy.adapters.chat_adapter import ChatAdapter

    try:
        return ChatAdapter(use_native_function_calling=True)
    except TypeError:
        return ChatAdapter()


def configure_lm(
    model: str,
    api_key: Optional[str] = None,
    api_base: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    model_type: Optional[str] = None,
    reasoning_effort: Optional[str] = None,
    verbosity: Optional[str] = None,
    request_timeout: Optional[float] = None,
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
        temperature: Sampling temperature. If omitted, GPT-5 family omits the
            parameter; other models default to 0.0 (deterministic when supported).
        max_tokens: Maximum tokens in response (optional)
        model_type: Model type (e.g., "chat", "responses" for reasoning models)
        reasoning_effort: Optional GPT-5-family reasoning effort control
        verbosity: Optional GPT-5-family response verbosity control
        request_timeout: Provider request timeout in seconds
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

    try:
        import litellm

        litellm.disable_aiohttp_transport = True
        litellm.use_aiohttp_transport = False
    except ImportError as exc:
        import logging

        logging.getLogger(__name__).debug("LiteLLM not importable during configure_lm: %r", exc)

    if temperature is None:
        temperature = default_temperature_for_model(model)

    # Build configuration — omit temperature for GPT-5 family (unsupported / not accepted).
    lm_kwargs = {
        # IMPORTANT: Disable caching to enable streaming. With cache=True (default),
        # DSPy returns cached responses which breaks streamify()'s ability to stream.
        "cache": False,
        **kwargs,
    }
    if temperature is not None:
        lm_kwargs["temperature"] = temperature

    if api_key:
        lm_kwargs["api_key"] = api_key
    if api_base:
        lm_kwargs["api_base"] = api_base
    if max_tokens:
        lm_kwargs["max_tokens"] = max_tokens
    if model_type:
        lm_kwargs["model_type"] = model_type
    if request_timeout is not None:
        lm_kwargs["timeout"] = request_timeout
    _apply_gpt5_controls(
        lm_kwargs,
        reasoning_effort=reasoning_effort,
        verbosity=verbosity,
        model_type=model_type,
    )

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

    import logging

    logger = logging.getLogger(__name__)

    adapter = create_adapter()
    use_native = getattr(adapter, "use_native_function_calling", None)
    logger.debug(f"[ADAPTER] Created ChatAdapter with use_native_function_calling={use_native}")

    # Set as global default with adapter
    dspy.configure(lm=lm, adapter=adapter)
    logger.debug(f"[ADAPTER] Configured DSPy with adapter: {adapter}")
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
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    model_type: Optional[str] = None,
    reasoning_effort: Optional[str] = None,
    verbosity: Optional[str] = None,
    request_timeout: Optional[float] = None,
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
        temperature: Sampling temperature; if omitted, same defaults as configure_lm.
        max_tokens: Maximum tokens in response (optional)
        model_type: Model type (e.g., "chat", "responses" for reasoning models)
        reasoning_effort: Optional GPT-5-family reasoning effort control
        verbosity: Optional GPT-5-family response verbosity control
        request_timeout: Provider request timeout in seconds
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

    try:
        import litellm

        litellm.disable_aiohttp_transport = True
        litellm.use_aiohttp_transport = False
    except ImportError as exc:
        import logging

        logging.getLogger(__name__).debug(
            "LiteLLM not importable during create_lm_for_agent: %r", exc
        )

    if temperature is None:
        temperature = default_temperature_for_model(model)

    # Build configuration
    lm_kwargs = {
        # IMPORTANT: Disable caching to enable streaming
        "cache": False,
        **kwargs,
    }
    if temperature is not None:
        lm_kwargs["temperature"] = temperature

    if api_key:
        lm_kwargs["api_key"] = api_key
    if api_base:
        lm_kwargs["api_base"] = api_base
    if max_tokens:
        lm_kwargs["max_tokens"] = max_tokens
    if model_type:
        lm_kwargs["model_type"] = model_type
    if request_timeout is not None:
        lm_kwargs["timeout"] = request_timeout
    _apply_gpt5_controls(
        lm_kwargs,
        reasoning_effort=reasoning_effort,
        verbosity=verbosity,
        model_type=model_type,
    )

    import os

    if os.environ.get("TACTUS_BROKER_SOCKET"):
        from tactus.dspy.broker_lm import BrokeredLM

        lm_kwargs.pop("api_key", None)
        lm_kwargs.pop("api_base", None)
        return BrokeredLM(model, **lm_kwargs)

    # Create LM without setting as global default
    return dspy.LM(model, **lm_kwargs)


def prewarm_lm(
    model: str,
    api_key: Optional[str] = None,
    api_base: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    model_type: Optional[str] = None,
    reasoning_effort: Optional[str] = None,
    verbosity: Optional[str] = None,
    request_timeout: Optional[float] = None,
    **kwargs: Any,
) -> PrewarmedLM:
    """Initialize and cache the configured LM stack without provider inference.

    Construction imports DSPy and LiteLLM, creates the DSPy adapter, and creates
    the configured provider client. It deliberately does not call the LM.
    Agents with the same effective configuration reuse this prewarmed stack.
    """
    config = {
        "api_key": api_key,
        "api_base": api_base,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "model_type": model_type,
        "reasoning_effort": reasoning_effort,
        "verbosity": verbosity,
        "request_timeout": request_timeout,
        **kwargs,
    }
    config = {key: value for key, value in config.items() if value is not None}
    key = _prewarm_key(model, config)
    with _prewarmed_lms_lock:
        warmed = _prewarmed_lms.get(key)
        if warmed is None:
            lm = create_lm(model, **config)
            warmed = PrewarmedLM(lm=lm, adapter=create_adapter())
            _prewarmed_lms[key] = warmed
        return warmed


def get_prewarmed_lm(model: str, **config: Any) -> Optional[Any]:
    """Return a matching prewarmed LM, if one was prepared."""
    with _prewarmed_lms_lock:
        warmed = _prewarmed_lms.get(_prewarm_key(model, config))
    return warmed.lm if warmed is not None else None


def get_prewarmed_adapter(model: str, **config: Any) -> Optional[Any]:
    """Return the adapter paired with a matching prewarmed LM."""
    with _prewarmed_lms_lock:
        warmed = _prewarmed_lms.get(_prewarm_key(model, config))
    return warmed.adapter if warmed is not None else None


def reset_prewarmed_lms() -> None:
    """Clear prewarmed LM state (primarily for tests and process reconfiguration)."""
    with _prewarmed_lms_lock:
        _prewarmed_lms.clear()
