"""Main LLM service orchestration.

This module provides the main entry point for executing LLM calls.
It uses the provider factory pattern to route requests to the appropriate
provider implementation (OpenAI, Anthropic, etc.).
"""

import logging
from typing import Any

from app.models.llm import LLMCallRequest, LLMCallResponse
from app.services.llm.provider_factory import ProviderFactory

logger = logging.getLogger(__name__)


def execute_llm_call(
    request: LLMCallRequest,
    client: Any,
) -> tuple[LLMCallResponse | None, str | None]:
    """Execute LLM call using the appropriate provider.

    This is the main orchestration function that routes requests to
    provider-specific implementations. It uses the provider factory
    to instantiate the correct provider based on the request configuration.

    The function is designed to be provider-agnostic, supporting multiple
    LLM providers (OpenAI, Anthropic, Google, etc.) through a unified interface.

    Args:
        request: LLM call request with configuration (includes provider type)
        client: Provider-specific client instance

    Returns:
        Tuple of (response, error_message)
        - If successful: (LLMCallResponse, None)
        - If failed: (None, error_message)

    Example:
        >>> request = LLMCallRequest(
        ...     llm=LLMConfig(
        ...         provider="openai",
        ...         prompt="Hello, world!",
        ...         llm_model_spec=LLMModelSpec(model="gpt-4")
        ...     )
        ... )
        >>> response, error = execute_llm_call(request, openai_client)
    """
    provider_type = request.llm.llm_model_spec.provider

    logger.info(
        f"[execute_llm_call] Processing LLM call for provider: {provider_type}, "
        f"model: {request.llm.llm_model_spec.model}"
    )

    try:
        # Create the appropriate provider using the factory
        provider = ProviderFactory.create_provider(
            provider_type=provider_type,
            client=client,
        )

        # Execute the LLM call through the provider
        response, error = provider.execute(request)

        if response:
            logger.info(
                f"[execute_llm_call] Successfully generated response: {response.response_id}"
            )
        else:
            logger.error(f"[execute_llm_call] Failed to generate response: {error}")

        return response, error

    except ValueError as e:
        error_message = str(e)
        logger.error(f"[execute_llm_call] Provider error: {error_message}")
        return None, error_message

    except Exception as e:
        error_message = f"Unexpected error in LLM service: {str(e)}"
        logger.error(f"[execute_llm_call] {error_message}", exc_info=True)
        return None, error_message
