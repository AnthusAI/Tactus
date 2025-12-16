"""
Google Gemini provider implementation.
"""

import os
from typing import Optional, Dict
from tactus.providers.base import ProviderConfig


class GoogleProvider:
    """Google Gemini LLM provider."""

    PROVIDER_NAME = "google-gla"  # Google GenAI (not Vertex AI)

    # Known Gemini models
    # Reference: https://ai.google.dev/gemini-api/docs/models/gemini
    KNOWN_MODELS = {
        # Gemini 3 models (preview)
        "gemini-3-pro-preview",
        "gemini-3-flash-preview",
        "gemini-3-pro-image-preview",
        # Gemini 2.0 models
        "gemini-2.0-flash-exp",
        "gemini-2.0-flash-thinking-exp",
        "gemini-2.0-flash",
        "gemini-2.0-flash-lite",
        # Gemini 1.5 models
        "gemini-1.5-pro",
        "gemini-1.5-flash",
        "gemini-1.5-flash-8b",
        # Experimental models
        "gemini-exp-1206",
        "gemini-exp-1121",
    }

    @staticmethod
    def validate_model(model_id: str) -> bool:
        """
        Validate that a model ID is valid for Google Gemini.

        Args:
            model_id: The model identifier to validate

        Returns:
            True if valid (starts with 'gemini' or in known models)
        """
        return model_id in GoogleProvider.KNOWN_MODELS or model_id.startswith("gemini")

    @staticmethod
    def get_required_credentials() -> list[str]:
        """
        Get list of required credential keys for Google Gemini.

        Returns:
            List containing 'GOOGLE_API_KEY'
        """
        return ["GOOGLE_API_KEY"]

    @staticmethod
    def check_credentials() -> bool:
        """
        Check if Google credentials are available.

        Returns:
            True if GOOGLE_API_KEY is set
        """
        return bool(os.environ.get("GOOGLE_API_KEY"))

    @staticmethod
    def create_config(
        model_id: str,
        credentials: Optional[Dict[str, str]] = None,
        region: Optional[str] = None,
        **kwargs,
    ) -> ProviderConfig:
        """
        Create a Google Gemini provider configuration.

        Args:
            model_id: Model identifier (e.g., 'gemini-2.0-flash-exp', 'gemini-1.5-pro')
            credentials: Optional credentials dict with 'api_key'
            region: Ignored for Google (no regional endpoints)
            **kwargs: Additional config (ignored)

        Returns:
            ProviderConfig instance
        """
        # Get API key from credentials or environment
        api_key = None
        if credentials and "api_key" in credentials:
            api_key = credentials["api_key"]
        elif not os.environ.get("GOOGLE_API_KEY"):
            # Try to get from credentials dict with uppercase key
            if credentials and "GOOGLE_API_KEY" in credentials:
                api_key = credentials["GOOGLE_API_KEY"]

        creds = {"api_key": api_key} if api_key else None

        return ProviderConfig(
            provider_name=GoogleProvider.PROVIDER_NAME,
            model_id=model_id,
            credentials=creds,
            region=None,  # Google doesn't use regions
            additional_config=kwargs,
        )
