"""Base provider interface for LLM providers.

This module defines the abstract base class that all LLM providers must implement.
It provides a provider-agnostic interface for executing LLM calls with spec-based
transformation.
"""

from abc import ABC, abstractmethod
from typing import Any

from app.models.llm import CompletionConfig, LLMCallResponse, QueryParams


class BaseProvider(ABC):
    """Abstract base class for LLM providers.

    All provider implementations (OpenAI, Anthropic, etc.) must inherit from
    this class and implement the required methods.

    Each provider uses its own spec class for parameter validation and conversion
    to the provider's API format.

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
        self, completion_config: CompletionConfig, query: QueryParams
    ) -> tuple[LLMCallResponse | None, str | None]:
        """Execute an LLM call using the provider.

        This is the main method that must be implemented by all providers.
        It should handle the complete lifecycle of an LLM request:
        1. Build provider-specific parameters (using transformer)
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

    def get_provider_name(self) -> str:
        """Get the name of the provider.

        Returns:
            Provider name (e.g., "openai", "anthropic", "google")
        """
        return self.__class__.__name__.replace("Provider", "").lower()
