"""
Model pricing data for cost calculation.

Prices are per million tokens in USD.
Data sourced from provider documentation and pricing pages.
"""

from typing import Dict, Optional

# Pricing per million tokens (USD)
MODEL_PRICING: Dict[str, Dict[str, Dict[str, float]]] = {
    "openai": {
        "gpt-4o": {"input": 2.50, "output": 10.00},
        "gpt-4o-mini": {"input": 0.15, "output": 0.60},
        "gpt-4o-2024-11-20": {"input": 2.50, "output": 10.00},
        "gpt-4o-2024-08-06": {"input": 2.50, "output": 10.00},
        "gpt-4o-2024-05-13": {"input": 5.00, "output": 15.00},
        "gpt-4-turbo": {"input": 10.00, "output": 30.00},
        "gpt-4-turbo-preview": {"input": 10.00, "output": 30.00},
        "gpt-4": {"input": 30.00, "output": 60.00},
        "gpt-3.5-turbo": {"input": 0.50, "output": 1.50},
        "o1": {"input": 15.00, "output": 60.00},
        "o1-mini": {"input": 1.10, "output": 4.40},
        "o3-mini": {"input": 1.10, "output": 4.40},
    },
    "anthropic": {
        "claude-3-5-sonnet": {"input": 3.00, "output": 15.00},
        "claude-3-5-sonnet-20241022": {"input": 3.00, "output": 15.00},
        "claude-3-5-haiku": {"input": 0.80, "output": 4.00},
        "claude-3-5-haiku-20241022": {"input": 0.80, "output": 4.00},
        "claude-3-opus": {"input": 15.00, "output": 75.00},
        "claude-3-sonnet": {"input": 3.00, "output": 15.00},
        "claude-3-haiku": {"input": 0.25, "output": 1.25},
        "claude-sonnet-4": {"input": 3.00, "output": 15.00},
        "claude-sonnet-4.5": {"input": 3.00, "output": 15.00},
        "claude-opus-4": {"input": 15.00, "output": 75.00},
    },
    "bedrock": {
        # Anthropic models on Bedrock
        "anthropic.claude-3-5-sonnet-20241022-v2:0": {"input": 3.00, "output": 15.00},
        "anthropic.claude-3-5-sonnet-20240620-v1:0": {"input": 3.00, "output": 15.00},
        "anthropic.claude-3-5-haiku-20241022-v1:0": {"input": 0.80, "output": 4.00},
        "anthropic.claude-3-opus-20240229-v1:0": {"input": 15.00, "output": 75.00},
        "anthropic.claude-3-sonnet-20240229-v1:0": {"input": 3.00, "output": 15.00},
        "anthropic.claude-3-haiku-20240307-v1:0": {"input": 0.25, "output": 1.25},
    },
    "google": {
        "gemini-2.5-flash": {"input": 0.30, "output": 2.50},
        "gemini-2.5-pro": {"input": 1.25, "output": 10.00},
        "gemini-2.0-flash": {"input": 0.10, "output": 0.40},
        "gemini-1.5-pro": {"input": 1.25, "output": 5.00},
        "gemini-1.5-flash": {"input": 0.075, "output": 0.30},
    },
}

# Default pricing for unknown models (conservative estimate)
DEFAULT_PRICING = {"input": 10.00, "output": 30.00}


def normalize_model_name(model_name: str, provider: Optional[str] = None) -> tuple[str, str]:
    """
    Normalize model name and extract provider.

    Handles formats like:
    - "gpt-4o" -> ("gpt-4o", "openai")
    - "openai:gpt-4o" -> ("gpt-4o", "openai")
    - "anthropic.claude-3-5-sonnet-20241022-v2:0" -> (full name, "bedrock")

    Args:
        model_name: Model identifier
        provider: Optional provider hint

    Returns:
        Tuple of (normalized_model_name, provider)
    """
    # Extract provider from model name if present
    if ":" in model_name:
        parts = model_name.split(":", 1)
        detected_provider = parts[0].lower()
        model_only = parts[1]
        return (model_only, detected_provider)

    # Check for Bedrock format (anthropic.claude-...)
    if model_name.startswith("anthropic."):
        return (model_name, "bedrock")

    # Use provided provider or try to infer
    if provider:
        return (model_name, provider.lower())

    # Infer provider from model name patterns
    if model_name.startswith("gpt-") or model_name.startswith("o1") or model_name.startswith("o3"):
        return (model_name, "openai")
    elif model_name.startswith("claude-"):
        return (model_name, "anthropic")
    elif model_name.startswith("gemini-"):
        return (model_name, "google")

    # Default to openai if unknown
    return (model_name, provider or "openai")


def get_model_pricing(model_name: str, provider: Optional[str] = None) -> Dict[str, float]:
    """
    Get pricing for a model.

    Args:
        model_name: Model identifier
        provider: Optional provider

    Returns:
        Dict with 'input' and 'output' pricing per million tokens
    """
    normalized_model, detected_provider = normalize_model_name(model_name, provider)

    # Look up pricing
    provider_pricing = MODEL_PRICING.get(detected_provider, {})
    pricing = provider_pricing.get(normalized_model)

    if pricing:
        return pricing

    # Try without version suffix (e.g., "gpt-4o-2024-11-20" -> "gpt-4o")
    base_model = normalized_model.split("-")[0:2]  # Get first two parts
    if len(base_model) >= 2:
        base_name = "-".join(base_model)
        pricing = provider_pricing.get(base_name)
        if pricing:
            return pricing

    # Return default pricing with warning
    return DEFAULT_PRICING
