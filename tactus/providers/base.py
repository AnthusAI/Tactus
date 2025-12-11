"""
Base provider configuration protocol.

Defines the interface that all LLM providers must implement.
"""

from typing import Protocol, Optional, Dict, Any
from dataclasses import dataclass


@dataclass
class ProviderConfig:
    """
    Configuration for an LLM provider.

    Attributes:
        provider_name: Name of the provider (e.g., 'openai', 'bedrock')
        model_id: Model identifier within the provider
        credentials: Optional credentials dict (API keys, etc.)
        region: Optional region for cloud providers
        additional_config: Any additional provider-specific configuration
    """

    provider_name: str
    model_id: str
    credentials: Optional[Dict[str, str]] = None
    region: Optional[str] = None
    additional_config: Optional[Dict[str, Any]] = None

    def get_model_string(self) -> str:
        """
        Get the model string for pydantic-ai.

        Returns:
            Model string in format 'provider:model_id'
        """
        return f"{self.provider_name}:{self.model_id}"


class Provider(Protocol):
    """
    Protocol for LLM provider implementations.

    Each provider must implement methods to:
    - Validate configuration
    - Get model string for pydantic-ai
    - Check if credentials are available
    """

    @staticmethod
    def validate_model(model_id: str) -> bool:
        """
        Validate that a model ID is valid for this provider.

        Args:
            model_id: The model identifier to validate

        Returns:
            True if valid, False otherwise
        """
        ...

    @staticmethod
    def get_required_credentials() -> list[str]:
        """
        Get list of required credential keys for this provider.

        Returns:
            List of environment variable names needed
        """
        ...

    @staticmethod
    def create_config(
        model_id: str,
        credentials: Optional[Dict[str, str]] = None,
        region: Optional[str] = None,
        **kwargs,
    ) -> ProviderConfig:
        """
        Create a provider configuration.

        Args:
            model_id: Model identifier
            credentials: Optional credentials dict
            region: Optional region
            **kwargs: Additional provider-specific config

        Returns:
            ProviderConfig instance
        """
        ...
