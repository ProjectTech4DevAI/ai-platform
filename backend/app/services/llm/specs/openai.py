"""OpenAI model specifications.

This module contains specifications for OpenAI models including GPT-4,
GPT-3.5, and o-series models with reasoning capabilities.
"""

from app.models.llm.specs import (
    ModelCapabilities,
    ModelSpec,
    ParameterSpec,
    model_spec_registry,
)


def create_openai_specs() -> list[ModelSpec]:
    """Create specifications for OpenAI models.

    Returns:
        List of ModelSpec objects for OpenAI models
    """
    specs = []

    # Standard parameters for most OpenAI models
    standard_params = [
        ParameterSpec(
            name="temperature",
            type="float",
            required=False,
            min_value=0.0,
            max_value=2.0,
            default=1.0,
            description="Sampling temperature (0-2). Higher values make output more random.",
        ),
        ParameterSpec(
            name="max_tokens",
            type="int",
            required=False,
            min_value=1,
            max_value=128000,
            description="Maximum number of tokens to generate.",
        ),
        ParameterSpec(
            name="top_p",
            type="float",
            required=False,
            min_value=0.0,
            max_value=1.0,
            default=1.0,
            description="Nucleus sampling parameter.",
        ),
    ]

    # GPT-4 models
    gpt4_models = [
        "gpt-4",
        "gpt-4-turbo",
        "gpt-4-turbo-preview",
        "gpt-4o",
        "gpt-4o-mini",
    ]

    for model_name in gpt4_models:
        specs.append(
            ModelSpec(
                model_name=model_name,
                provider="openai",
                capabilities=ModelCapabilities(
                    supports_reasoning=False,
                    supports_text_config=False,
                    supports_file_search=True,
                    supports_function_calling=True,
                    supports_streaming=True,
                    supports_vision=True
                    if "4o" in model_name or "vision" in model_name
                    else False,
                ),
                parameters=standard_params.copy(),
            )
        )

    # GPT-3.5 models
    gpt35_models = ["gpt-3.5-turbo", "gpt-3.5-turbo-16k"]

    for model_name in gpt35_models:
        specs.append(
            ModelSpec(
                model_name=model_name,
                provider="openai",
                capabilities=ModelCapabilities(
                    supports_reasoning=False,
                    supports_text_config=False,
                    supports_file_search=True,
                    supports_function_calling=True,
                    supports_streaming=True,
                    supports_vision=False,
                ),
                parameters=standard_params.copy(),
            )
        )

    # O-series models (reasoning models)
    o_series_params = standard_params.copy() + [
        ParameterSpec(
            name="reasoning",
            type="str",
            required=False,
            allowed_values=["low", "medium", "high"],
            description="Reasoning effort level for o-series models.",
        ),
        ParameterSpec(
            name="text",
            type="str",
            required=False,
            allowed_values=["low", "medium", "high"],
            description="Text verbosity level for o-series models.",
        ),
    ]

    o_series_models = [
        "o1",
        "o1-preview",
        "o1-mini",
        "o3",
        "o3-mini",
    ]

    for model_name in o_series_models:
        specs.append(
            ModelSpec(
                model_name=model_name,
                provider="openai",
                capabilities=ModelCapabilities(
                    supports_reasoning=True,
                    supports_text_config=True,
                    supports_file_search=True,
                    supports_function_calling=False,  # o-series don't support functions yet
                    supports_streaming=True,
                    supports_vision=False,
                ),
                parameters=o_series_params.copy(),
            )
        )

    return specs


def register_openai_specs() -> None:
    """Register all OpenAI model specs with the global registry."""
    specs = create_openai_specs()
    for spec in specs:
        model_spec_registry.register(spec)
