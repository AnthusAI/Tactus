"""
OpenAI provider implementation.
"""

import os
from typing import Optional, Dict
from tactus.providers.base import ProviderConfig


class OpenAIProvider:
    """OpenAI LLM provider."""

    PROVIDER_NAME = "openai"

    # Known OpenAI models
    KNOWN_MODELS = {
        "gpt-4o",
        "gpt-4o-mini",
        "gpt-4-turbo",
        "gpt-4-turbo-preview",
        "gpt-4",
        "gpt-3.5-turbo",
        "o1",
        "o1-mini",
        "o1-preview",
    }

    @staticmethod
    def validate_model(model_id: str) -> bool:
        """
        Validate that a model ID is valid for OpenAI.

        Args:
            model_id: The model identifier to validate

        Returns:
            True if valid (starts with 'gpt' or 'o1'), False otherwise
        """
        # Accept known models or anything starting with gpt/o1
        return model_id in OpenAIProvider.KNOWN_MODELS or model_id.startswith(("gpt", "o1"))

    @staticmethod
    def get_required_credentials() -> list[str]:
        """
        Get list of required credential keys for OpenAI.

        Returns:
            List containing 'OPENAI_API_KEY'
        """
        return ["OPENAI_API_KEY"]

    @staticmethod
    def check_credentials() -> bool:
        """
        Check if OpenAI credentials are available.

        Returns:
            True if OPENAI_API_KEY is set
        """
        return bool(os.environ.get("OPENAI_API_KEY"))

    @staticmethod
    def create_config(
        model_id: str,
        credentials: Optional[Dict[str, str]] = None,
        region: Optional[str] = None,
        **kwargs,
    ) -> ProviderConfig:
        """
        Create an OpenAI provider configuration.

        Args:
            model_id: Model identifier (e.g., 'gpt-4o')
            credentials: Optional credentials dict with 'api_key'
            region: Ignored for OpenAI
            **kwargs: Additional config (ignored)

        Returns:
            ProviderConfig instance
        """
        # Get API key from credentials or environment
        api_key = None
        if credentials and "api_key" in credentials:
            api_key = credentials["api_key"]
        elif not os.environ.get("OPENAI_API_KEY"):
            # Try to get from credentials dict with uppercase key
            if credentials and "OPENAI_API_KEY" in credentials:
                api_key = credentials["OPENAI_API_KEY"]

        creds = {"api_key": api_key} if api_key else None

        return ProviderConfig(
            provider_name=OpenAIProvider.PROVIDER_NAME,
            model_id=model_id,
            credentials=creds,
            region=None,  # OpenAI doesn't use regions
            additional_config=kwargs,
        )
