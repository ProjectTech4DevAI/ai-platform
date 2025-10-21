"""Base provider interface for LLM providers.

This module defines the abstract base class that all LLM providers must implement.
It provides a provider-agnostic interface for executing LLM calls with spec-based
transformation.
"""

from abc import ABC, abstractmethod
from typing import Any, Optional

from app.models.llm import LLMCallRequest, LLMCallResponse
from app.services.llm.transformers.base import ConfigTransformer
from app.services.llm.transformers.factory import TransformerFactory


class BaseProvider(ABC):
    """Abstract base class for LLM providers.

    All provider implementations (OpenAI, Anthropic, etc.) must inherit from
    this class and implement the required methods.

    This provider uses a transformer-based architecture where configuration
    transformation is separated from the provider execution logic.

    Attributes:
        client: The provider-specific client instance
        transformer: ConfigTransformer for converting requests to provider format
    """

    def __init__(self, client: Any, transformer: Optional[ConfigTransformer] = None):
        """Initialize the provider with client and optional transformer.

        Args:
            client: Provider-specific client (e.g., OpenAI, Anthropic client)
            transformer: Optional config transformer. If not provided, one will
                        be created using the TransformerFactory.
        """
        self.client = client
        self.transformer = transformer

    def _get_transformer(self, request: LLMCallRequest) -> ConfigTransformer:
        """Get or create a transformer for this request.

        Args:
            request: LLM call request

        Returns:
            ConfigTransformer instance
        """
        if self.transformer is None:
            # Create transformer using factory
            provider_name = self.get_provider_name()
            model_name = request.llm.llm_model_spec.model
            self.transformer = TransformerFactory.create_transformer(
                provider=provider_name,
                model_name=model_name,
                use_spec=True,
            )
        return self.transformer

    def build_params(self, request: LLMCallRequest) -> dict[str, Any]:
        """Build provider-specific API parameters from the request.

        This method uses the transformer to convert the request.
        Providers can override this if they need custom logic, but the
        default implementation uses the transformer.

        Args:
            request: LLM call request with configuration

        Returns:
            Dictionary of provider-specific parameters
        """
        transformer = self._get_transformer(request)
        return transformer.validate_and_transform(request)

    @abstractmethod
    def execute(
        self, request: LLMCallRequest
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
