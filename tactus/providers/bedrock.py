"""
AWS Bedrock provider implementation.
"""

import os
from typing import Optional, Dict
from tactus.providers.base import ProviderConfig


class BedrockProvider:
    """AWS Bedrock LLM provider."""

    PROVIDER_NAME = "bedrock"

    # Known Bedrock models (Claude via Bedrock)
    KNOWN_MODELS = {
        "anthropic.claude-haiku-4-5-20251001-v1:0",  # Claude 4.5 Haiku
        "anthropic.claude-3-5-sonnet-20240620-v1:0",
        "anthropic.claude-3-5-haiku-20241022-v1:0",
        "anthropic.claude-3-sonnet-20240229-v1:0",
        "anthropic.claude-3-haiku-20240307-v1:0",
        "anthropic.claude-v2",
        "anthropic.claude-v2:1",
        "anthropic.claude-instant-v1",
    }

    @staticmethod
    def validate_model(model_id: str) -> bool:
        """
        Validate that a model ID is valid for Bedrock.

        Args:
            model_id: The model identifier to validate

        Returns:
            True if valid (starts with 'anthropic.' or in known models)
        """
        return (
            model_id in BedrockProvider.KNOWN_MODELS
            or model_id.startswith("anthropic.")
            or model_id.startswith("amazon.")
            or model_id.startswith("meta.")
            or model_id.startswith("cohere.")
        )

    @staticmethod
    def get_required_credentials() -> list[str]:
        """
        Get list of required credential keys for Bedrock.

        Returns:
            List containing AWS credential keys
        """
        return [
            "AWS_ACCESS_KEY_ID",
            "AWS_SECRET_ACCESS_KEY",
            "AWS_DEFAULT_REGION",  # Optional but recommended
        ]

    @staticmethod
    def check_credentials() -> bool:
        """
        Check if Bedrock credentials are available.

        Returns:
            True if AWS credentials are set
        """
        return bool(os.environ.get("AWS_ACCESS_KEY_ID") and os.environ.get("AWS_SECRET_ACCESS_KEY"))

    @staticmethod
    def create_config(
        model_id: str,
        credentials: Optional[Dict[str, str]] = None,
        region: Optional[str] = None,
        **kwargs,
    ) -> ProviderConfig:
        """
        Create a Bedrock provider configuration.

        Args:
            model_id: Model identifier (e.g., 'anthropic.claude-3-5-sonnet-20240620-v1:0')
            credentials: Optional credentials dict with AWS keys
            region: AWS region (defaults to us-east-1)
            **kwargs: Additional config

        Returns:
            ProviderConfig instance
        """
        # Get credentials from dict or environment
        creds = {}
        if credentials:
            if "access_key_id" in credentials:
                creds["access_key_id"] = credentials["access_key_id"]
            if "secret_access_key" in credentials:
                creds["secret_access_key"] = credentials["secret_access_key"]
            # Also check uppercase keys
            if "AWS_ACCESS_KEY_ID" in credentials:
                creds["access_key_id"] = credentials["AWS_ACCESS_KEY_ID"]
            if "AWS_SECRET_ACCESS_KEY" in credentials:
                creds["secret_access_key"] = credentials["AWS_SECRET_ACCESS_KEY"]

        # Get region from parameter, credentials, or environment
        if not region:
            if credentials and "region" in credentials:
                region = credentials["region"]
            elif credentials and "AWS_DEFAULT_REGION" in credentials:
                region = credentials["AWS_DEFAULT_REGION"]
            else:
                region = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")

        return ProviderConfig(
            provider_name=BedrockProvider.PROVIDER_NAME,
            model_id=model_id,
            credentials=creds if creds else None,
            region=region,
            additional_config=kwargs,
        )
