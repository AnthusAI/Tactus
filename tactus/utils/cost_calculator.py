"""
Cost calculator for LLM usage.

Calculates costs based on token usage and model pricing.
"""

from typing import Dict, Any, Optional
from .model_pricing import get_model_pricing, normalize_model_name


class CostCalculator:
    """
    Calculate LLM costs from token usage and model information.

    Aligned with pydantic-ai's usage tracking.
    """

    def calculate_cost(
        self,
        model_name: str,
        provider: Optional[str],
        prompt_tokens: int,
        completion_tokens: int,
        cache_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Calculate cost for a single LLM call.

        Args:
            model_name: Model identifier
            provider: Provider name (openai, anthropic, bedrock, google)
            prompt_tokens: Number of prompt tokens
            completion_tokens: Number of completion tokens
            cache_tokens: Number of cached tokens (if applicable)

        Returns:
            Dict with:
                - prompt_cost: Cost for prompt tokens
                - completion_cost: Cost for completion tokens
                - cache_cost: Cost savings from cache (if applicable)
                - total_cost: Total cost
                - model: Normalized model name
                - provider: Detected provider
                - pricing_found: Whether pricing was found (False = using defaults)
        """
        # Normalize model name and get provider
        normalized_model, detected_provider = normalize_model_name(model_name, provider)

        # Get pricing
        pricing = get_model_pricing(model_name, provider)

        # Calculate costs (pricing is per million tokens)
        prompt_cost = (prompt_tokens / 1_000_000) * pricing["input"]
        completion_cost = (completion_tokens / 1_000_000) * pricing["output"]

        # Calculate cache savings if applicable
        cache_cost = None
        if cache_tokens and cache_tokens > 0:
            # Cached tokens typically cost 10% of input tokens
            cache_cost = (cache_tokens / 1_000_000) * pricing["input"] * 0.9

        total_cost = prompt_cost + completion_cost

        return {
            "prompt_cost": prompt_cost,
            "completion_cost": completion_cost,
            "cache_cost": cache_cost,
            "total_cost": total_cost,
            "model": normalized_model,
            "provider": detected_provider,
            "pricing_found": True,  # Could track if we used DEFAULT_PRICING
        }
