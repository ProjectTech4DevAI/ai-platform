"""Base provider interface for LLM providers.

This module defines the abstract base class that all LLM providers must implement.
It provides a provider-agnostic interface for executing LLM calls.
"""

from abc import ABC, abstractmethod
from typing import Any

from app.models.llm import LLMCallRequest, LLMCallResponse


class BaseProvider(ABC):
    """Abstract base class for LLM providers.

    All provider implementations (OpenAI, Anthropic, etc.) must inherit from
    this class and implement the required methods.

    Attributes:
        client: The provider-specific client instance
    """

    def __init__(self, client: Any):
        """Initialize the provider with client.

        Args:
            client: Provider-specific client (e.g., OpenAI, Anthropic client)
        """
        self.client = client

    @abstractmethod
    def execute(
        self, request: LLMCallRequest
    ) -> tuple[LLMCallResponse | None, str | None]:
        """Execute an LLM call using the provider.

        This is the main method that must be implemented by all providers.
        It should handle the complete lifecycle of an LLM request:
        1. Build provider-specific parameters from the request
        2. Make the API call to the provider
        3. Extract results (including any additional features like RAG)
        4. Return standardized response

        Args:
            request: LLM call request with configuration

        Returns:
            Tuple of (response, error_message)
            - If successful: (LLMCallResponse, None)
            - If failed: (None, error_message)

        Raises:
            NotImplementedError: If the provider hasn't implemented this method
        """
        raise NotImplementedError("Providers must implement execute method")

    @abstractmethod
    def build_params(self, request: LLMCallRequest) -> dict[str, Any]:
        """Build provider-specific API parameters from the request.

        Convert the generic LLMCallRequest into provider-specific parameters.
        This includes handling model names, temperature, tokens, and any
        provider-specific features.

        Args:
            request: LLM call request with configuration

        Returns:
            Dictionary of provider-specific parameters

        Raises:
            NotImplementedError: If the provider hasn't implemented this method
        """
        raise NotImplementedError("Providers must implement build_params method")

    @abstractmethod
    def supports_feature(self, feature: str) -> bool:
        """Check if the provider supports a specific feature.

        Features might include: "reasoning", "text_config", "file_search",
        "streaming", "function_calling", etc.

        Args:
            feature: Feature name to check

        Returns:
            True if the feature is supported, False otherwise

        Raises:
            NotImplementedError: If the provider hasn't implemented this method
        """
        raise NotImplementedError("Providers must implement supports_feature method")

    def get_provider_name(self) -> str:
        """Get the name of the provider.

        Returns:
            Provider name (e.g., "openai", "anthropic", "google")
        """
        return self.__class__.__name__.replace("Provider", "").lower()
