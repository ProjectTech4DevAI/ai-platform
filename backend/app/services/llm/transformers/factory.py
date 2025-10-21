"""Transformer factory for creating configuration transformers.

This module provides a factory for instantiating the appropriate
transformer based on the provider type.
"""

from typing import Optional

from app.models.llm.specs import model_spec_registry
from app.services.llm.exceptions import UnsupportedProviderError
from app.services.llm.transformers.base import ConfigTransformer
from app.services.llm.transformers.openai import OpenAITransformer


class TransformerFactory:
    """Factory for creating transformer instances.

    This factory creates the appropriate transformer based on the provider type
    and optionally uses model specs for validation.
    """

    _TRANSFORMERS: dict[str, type[ConfigTransformer]] = {
        "openai": OpenAITransformer,
        # Future transformers can be added here:
        # "anthropic": AnthropicTransformer,
        # "google": GoogleTransformer,
    }

    @classmethod
    def create_transformer(
        cls,
        provider: str,
        model_name: Optional[str] = None,
        use_spec: bool = True,
    ) -> ConfigTransformer:
        """Create a transformer instance for the given provider.

        Args:
            provider: Provider name (openai, anthropic, google, azure)
            model_name: Optional model name to load spec for validation
            use_spec: Whether to use model spec for validation (default: True)

        Returns:
            ConfigTransformer instance

        Raises:
            UnsupportedProviderError: If provider is not supported
        """
        transformer_class = cls._TRANSFORMERS.get(provider.lower())
        if transformer_class is None:
            raise UnsupportedProviderError(
                provider=provider,
                supported_providers=cls.get_supported_providers()
            )

        # Load model spec if available and requested
        model_spec = None
        if use_spec and model_name:
            model_spec = model_spec_registry.get_spec(provider.lower(), model_name)

        return transformer_class(model_spec=model_spec)

    @classmethod
    def get_supported_providers(cls) -> list[str]:
        """Get list of supported provider types.

        Returns:
            List of supported provider type strings
        """
        return list(cls._TRANSFORMERS.keys())

    @classmethod
    def register_transformer(
        cls, provider: str, transformer_class: type[ConfigTransformer]
    ) -> None:
        """Register a custom transformer for a provider.

        Args:
            provider: Provider name
            transformer_class: Transformer class to register

        Raises:
            TypeError: If transformer_class doesn't inherit from ConfigTransformer
        """
        if not issubclass(transformer_class, ConfigTransformer):
            raise TypeError(
                f"{transformer_class.__name__} must inherit from ConfigTransformer"
            )
        cls._TRANSFORMERS[provider.lower()] = transformer_class
