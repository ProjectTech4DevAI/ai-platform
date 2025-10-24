import logging
from typing import Any

from sqlmodel import Session
from app.services.llm.providers.base import BaseProvider
from app.services.llm.providers.openai import OpenAIProvider

logger = logging.getLogger(__name__)


# Registry of provider types to their implementation classes
PROVIDER_REGISTRY: dict[str, type[BaseProvider]] = {
    "openai": OpenAIProvider,
    # Future providers can be added here:
    # "anthropic": AnthropicProvider,
    # "google": GoogleProvider,
}


def get_llm_provider(
    session: Session, provider_type: str, project_id: int, organization_id: int
) -> BaseProvider:
    # Import here to avoid circular imports
    from app.utils import get_openai_client

    provider_class = PROVIDER_REGISTRY.get(provider_type)

    if provider_class is None:
        supported = list(PROVIDER_REGISTRY.keys())
        logger.error(
            f"[get_llm_provider] Unsupported provider type requested: {provider_type}"
        )
        raise ValueError(
            f"Provider '{provider_type}' is not supported. "
            f"Supported providers: {', '.join(supported)}"
        )

    if provider_type == "openai":
        client = get_openai_client(
            session=session, org_id=organization_id, project_id=project_id
        )
    else:
        logger.error(
            f"[get_llm_provider] Unsupported provider type requested: {provider_type}"
        )
        raise ValueError(f"Provider '{provider_type}' is not supported.")

    return provider_class(client=client)


def get_supported_providers() -> list[str]:
    """Get list of supported provider types.

    Returns:
        List of supported provider type strings
    """
    return list(PROVIDER_REGISTRY.keys())
