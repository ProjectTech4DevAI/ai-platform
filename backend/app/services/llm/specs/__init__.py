"""Model specifications initialization.

This module initializes all model specifications and registers them
with the global registry.
"""

from app.services.llm.specs.openai import register_openai_specs


def initialize_model_specs() -> None:
    """Initialize and register all model specifications.

    This should be called during application startup to ensure all
    model specs are available for validation and transformation.
    """
    # Register OpenAI specs
    register_openai_specs()

    # Future: Register other provider specs
    # register_anthropic_specs()
    # register_google_specs()
    # register_azure_specs()


# Auto-initialize when module is imported
initialize_model_specs()
