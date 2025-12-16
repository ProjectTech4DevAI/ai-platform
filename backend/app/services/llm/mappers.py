"""Parameter mappers for converting Kaapi-abstracted parameters to provider-specific formats."""

from app.models.llm import KaapiLLMParams, KaapiCompletionConfig, NativeCompletionConfig


def map_kaapi_to_openai_params(kaapi_params: KaapiLLMParams) -> dict:
    """Map Kaapi-abstracted parameters to OpenAI API parameters.

    This mapper transforms standardized Kaapi parameters into OpenAI-specific
    parameter format, enabling provider-agnostic interface design.

    Args:
        kaapi_params: KaapiLLMParams instance with standardized parameters

    Returns:
        Dictionary of OpenAI API parameters ready to be passed to the API

    Supported Mapping:
        - model → model
        - instructions → instructions
        - knowledge_base_ids → tools[file_search].vector_store_ids
        - max_num_results → tools[file_search].max_num_results (fallback default)
        - reasoning → reasoning.effort
        - temperature → temperature
    """
    openai_params = {}

    if kaapi_params.temperature is not None and kaapi_params.reasoning is not None:
        raise ValueError(
            "Cannot set both 'temperature' and 'reasoning' parameters together for OpenAI."
        )

    if kaapi_params.model:
        openai_params["model"] = kaapi_params.model

    if kaapi_params.instructions:
        openai_params["instructions"] = kaapi_params.instructions

    if kaapi_params.knowledge_base_ids:
        openai_params["tools"] = [
            {
                "type": "file_search",
                "vector_store_ids": kaapi_params.knowledge_base_ids,
                "max_num_results": kaapi_params.max_num_results or 20,
            }
        ]

    if kaapi_params.reasoning:
        openai_params["reasoning"] = {"effort": kaapi_params.reasoning}

    if kaapi_params.temperature is not None:
        openai_params["temperature"] = kaapi_params.temperature

    return openai_params


def transform_kaapi_config_to_native(
    kaapi_config: KaapiCompletionConfig,
) -> NativeCompletionConfig:
    """Transform Kaapi completion config to native provider config with mapped parameters.

    Currently supports OpenAI. Future: Claude, Gemini mappers.

    Args:
        kaapi_config: KaapiCompletionConfig with abstracted parameters

    Returns:
        NativeCompletionConfig with provider-native parameters ready for API
    """
    if kaapi_config.provider == "openai":
        mapped_params = map_kaapi_to_openai_params(kaapi_config.params)
        return NativeCompletionConfig(provider="openai-native", params=mapped_params)

    raise ValueError(f"Unsupported provider: {kaapi_config.provider}")
