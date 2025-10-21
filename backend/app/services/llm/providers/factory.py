"""Provider factory for creating LLM provider instances.

This module provides a factory pattern for instantiating the appropriate
LLM provider based on the provider type specified in the request.
"""

import logging
from typing import Any

from app.models.llm import ProviderType
from app.services.llm.exceptions import UnsupportedProviderError
from app.services.llm.providers.base import BaseProvider
from app.services.llm.providers.openai import OpenAIProvider

logger = logging.getLogger(__name__)


class ProviderFactory:
    """Factory for creating provider instances.

    This class implements the factory pattern to instantiate the correct
    provider based on the provider type. It maintains a registry of
    available providers and their corresponding classes.
    """

    # Registry of provider types to their implementation classes
    _PROVIDERS: dict[str, type[BaseProvider]] = {
        "openai": OpenAIProvider,
        # Future providers can be added here:
        # "anthropic": AnthropicProvider,
        # "google": GoogleProvider,
        # "azure": AzureOpenAIProvider,
        # "cohere": CohereProvider,
    }

    @classmethod
    def create_provider(
        cls, provider_type: ProviderType, client: Any
    ) -> BaseProvider:
        """Create a provider instance based on the provider type.

        Args:
            provider_type: Type of provider (openai, anthropic, etc.)
            client: Provider-specific client instance

        Returns:
            Instance of the appropriate provider

        Raises:
            UnsupportedProviderError: If the provider type is not supported
        """
        provider_class = cls._PROVIDERS.get(provider_type)

        if provider_class is None:
            raise UnsupportedProviderError(
                provider=provider_type,
                supported_providers=cls.get_supported_providers()
            )

        logger.info(f"[ProviderFactory] Creating {provider_type} provider instance")
        return provider_class(client=client)

    @classmethod
    def get_supported_providers(cls) -> list[str]:
        """Get list of supported provider types.

        Returns:
            List of supported provider type strings
        """
        return list(cls._PROVIDERS.keys())

    @classmethod
    def register_provider(
        cls, provider_type: str, provider_class: type[BaseProvider]
    ) -> None:
        """Register a new provider type.

        This allows for runtime registration of new providers, useful for
        plugins or extensions.

        Args:
            provider_type: Type identifier for the provider
            provider_class: Provider class that implements BaseProvider

        Raises:
            TypeError: If provider_class doesn't inherit from BaseProvider
        """
        if not issubclass(provider_class, BaseProvider):
            raise TypeError(
                f"{provider_class.__name__} must inherit from BaseProvider"
            )

        logger.info(f"[ProviderFactory] Registering provider: {provider_type}")
        cls._PROVIDERS[provider_type] = provider_class
