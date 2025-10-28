import logging

from sqlmodel import Session
from openai import OpenAI

from app.crud import get_provider_credential
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

    credentials = get_provider_credential(
        session=session,
        provider=provider_type,
        project_id=project_id,
        org_id=organization_id,
    )

    if not credentials:
        raise ValueError(
            f"Credentials for provider '{provider_type}' not configured for this project."
        )

    if provider_type == "openai":
        if "api_key" not in credentials:
            raise ValueError("OpenAI credentials not configured for this project.")
        client = OpenAI(api_key=credentials["api_key"])
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
